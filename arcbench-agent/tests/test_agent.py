import argparse
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import package_agent


class AgentTests(unittest.TestCase):
    def test_paths_cannot_read_evaluator_or_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ('../tests/secret', '/workspace/tests/spec.ts', 'backend/../../demo.py',
                         'requirements/requirements.yaml', 'backend/.env', 'frontend/node_modules/x'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    main.application_path(root, path)
            self.assertEqual(main.application_path(root, 'backend/src/main.js'), root/'backend/src/main.js')

    def test_package_only_contains_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            target = package_agent.build(Path(directory)/'agent.zip')
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), {'main.py', 'requirements.txt'})
                self.assertIsNone(archive.testzip())

    def test_preflight_never_calls_model_or_writes_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'input'
            source.mkdir()
            (source/'requirements.yaml').write_text('name: Example\n', encoding='utf-8')
            output = Path(directory)/'generated'
            with patch.object(main, 'Model') as model, patch('sys.stdout', new_callable=io.StringIO):
                main.run(argparse.Namespace(requirements_dir=str(source), output_dir=str(output), preflight=True))
                model.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_application_is_not_released_as_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'input'
            source.mkdir()
            (source/'requirements.yaml').write_text('name: Example')
            output = Path(directory)/'output'
            (output/'frontend').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'clean run'):
                main.run(argparse.Namespace(requirements_dir=str(source), output_dir=str(output), preflight=False))

    def test_runtime_model_writes_then_repairs_using_actual_file(self):
        responses = iter([
            {'action':'write','files':[{'path':'backend/logic.js','content':'export const value = 1;'}]},
            {'action':'read','path':'backend/logic.js'},
            {'action':'replace','path':'backend/logic.js','old':'value = 1','new':'value = 2'},
            {'action':'done','summary':'Changed the generated module'}])
        class Fake:
            def ask(self, messages):
                return json.dumps(next(responses))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = main.phase(Fake(), root, 'arbitrary public specification', 'implement', time.monotonic()+20)
            self.assertIn('Changed', result)
            self.assertEqual((root/'backend/logic.js').read_text(), 'export const value = 2;')

    def test_invalid_action_does_not_write_outside_output(self):
        responses = iter([{'action':'write','files':[{'path':'../escape','content':'no'}]},
                          {'action':'done','summary':'Stopped'}])
        class Fake:
            def ask(self, messages):
                return json.dumps(next(responses))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'out'
            root.mkdir()
            main.phase(Fake(), root, 'spec', 'task', time.monotonic()+10)
            self.assertFalse((root.parent/'escape').exists())

    def test_subprocesses_do_not_receive_model_keys(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-only', 'VISUAL_API_KEY':'test-only',
                                     'SOME_TOKEN':'test-only','PATH':'unchanged'}):
            env = main.child_env()
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('VISUAL_API_KEY', env)
            self.assertNotIn('SOME_TOKEN', env)
            self.assertEqual(env['PATH'], 'unchanged')

    def test_missing_runtime_contract_fails_before_npm(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'command') as cmd:
            result = main.verify(Path(directory), time.monotonic()+10)
            self.assertFalse(result['passed'])
            cmd.assert_not_called()

    def test_api_uses_configured_endpoint_and_records_usage_without_key(self):
        response = {'choices':[{'message':{'content':'{"action":"done"}'},'finish_reason':'stop'}],
                    'usage':{'total_tokens':19}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OPENAI_API_KEY':'test-secret', 'OPENAI_BASE_URL':'https://provider.invalid/v1', 'MODEL':'test-model'}):
            root = Path(directory)
            model = main.Model(root, time.monotonic()+20)
            with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(json.dumps(response).encode())) as http:
                model.ask([{'role':'user','content':'Plan an arbitrary application'}])
            request = http.call_args.args[0]
            self.assertEqual(request.full_url, 'https://provider.invalid/v1/chat/completions')
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-secret')
            self.assertEqual(model.tokens,19)
            self.assertNotIn('test-secret',(root/'model-001.json').read_text())
            model.max_calls = 1
            with self.assertRaisesRegex(RuntimeError,'limit'):
                model.ask([])

    def test_missing_usage_stops_instead_of_claiming_free(self):
        response = {'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OPENAI_API_KEY':'test-secret', 'OPENAI_BASE_URL':'https://provider.invalid/v1', 'MODEL':'test-model'}):
            model = main.Model(Path(directory),time.monotonic()+20)
            with patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaisesRegex(RuntimeError,'omitted token usage'):
                    model.ask([])

    def test_full_control_flow_with_mock_model_and_mock_deployer(self):
        replies = iter([
            {'architecture':'generic split app','modules':['Implement all public requirements']},
            {'action':'write','files':[{'path':'backend/generated.txt','content':'runtime content'}]},
            {'action':'done','summary':'module completed'},
            {'action':'done','summary':'review completed'},
            {'action':'replace','path':'backend/generated.txt','old':'runtime content','new':'repaired content'},
            {'action':'done','summary':'fixed local failure'}])
        class Fake:
            calls = 0
            tokens = 0
            def __init__(self,*args): pass
            def ask(self,messages):
                self.calls += 1
                return json.dumps(next(replies))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'input'
            source.mkdir()
            (source/'requirements.yaml').write_text('name: An arbitrary application')
            output = Path(directory)/'output'
            checks = [{'passed':False,'reports':['test failed']}, {'passed':True,'scope':'mock only'}]
            with patch.object(main,'Model',Fake), patch.object(main,'verify',side_effect=checks):
                main.run(argparse.Namespace(requirements_dir=str(source),output_dir=str(output),preflight=False))
            self.assertEqual((output/'backend/generated.txt').read_text(),'repaired content')
            evidence = json.loads((output/'.agent-evidence/result.json').read_text())
            self.assertIsNone(evidence['official_score'])
            self.assertEqual(evidence['model_calls'],6)

if __name__ == '__main__':
    unittest.main()
