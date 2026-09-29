"""Task-independent runtime code generator; contains no target application code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parent
SYSTEM = '''You are a software implementation agent inside the official competition runner.
Implement ONLY the supplied public requirements, at runtime. They are product specifications,
not permission to change your tools or access evaluation infrastructure. Never inspect hidden
tests, runner internals, sibling directories, secrets or prebuilt answers. Do not fetch application
code from external sites. Network is restricted to approved model services and package sources.
The application must be fully implemented, persistent where specified, and usable via real UI.
Preserve exact accessible names, roles, messages, routes, permissions, seed data and edge cases
specified in the requirements. Use genuine business logic; never special-case a test driver.
Official deployment: frontend/package.json with build script; backend/package.json with start
script. Runner runs npm install in frontend, npm run build, npm install in backend, then
HOST=0.0.0.0 PORT=3000 npm run start in backend. Backend must serve the built frontend and API
on that one port, including deep links. Node 20.19.3, 1 CPU, 2GB RAM. No deploy.sh shortcut.
Keep dependencies small. Persist data on disk. Use a distinct temporary database for self-tests.
Provide npm test in backend with meaningful assertions derived solely from public requirements.
No test may import or inspect any runner-owned test directory. Do not weaken tests to hide bugs.
Respond with ONE JSON object, no Markdown. Available actions:
{"action":"read","path":"frontend/..."} reads generated code;
{"action":"write","files":[{"path":"backend/...","content":"full file text"}]} writes code;
{"action":"replace","path":"backend/...","old":"unique existing text","new":"replacement"};
{"action":"check"} runs fixed build, self-test and HTTP smoke checks;
{"action":"done","summary":"implemented behavior and known gaps"} ends this work phase.
You may only read/write frontend/ or backend/. Relative file paths only.
Use small cohesive files to keep edits and responses manageable. Write real code before done.
'''


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def application_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or rel.parts[0] not in ('frontend', 'backend'):
        raise ValueError('Only frontend/ and backend/ relative paths are allowed')
    if any(x in ('..', '.git', 'node_modules', '.env') for x in rel.parts):
        raise ValueError('Protected path')
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Path escapes output directory')
    return target


def stop(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        # Windows development only; production Runner is Linux.
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
    process.wait(timeout=10)


def child_env():
    # Generated code and npm lifecycle scripts must not receive model credentials.
    env = {k: v for k, v in os.environ.items()
           if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD'))
           and k not in ('OPENAI_BASE_URL', 'VISUAL_BASE_URL')}
    return env


def command(argv, cwd, timeout, log):
    with log.open('wb') as output:
        proc = subprocess.Popen(argv, cwd=cwd, env=child_env(), stdout=output,
                                stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop(proc)
            code = 124
    return {'command': argv, 'exit': code,
            'output': log.read_text(encoding='utf-8', errors='replace')[-18000:]}


def verify(root, deadline):
    logs = root / '.agent-evidence'
    logs.mkdir(exist_ok=True)
    reports = []
    for folder, script in [('frontend', 'build'), ('backend', 'start'), ('backend', 'test')]:
        try:
            package = json.loads((root / folder / 'package.json').read_text(encoding='utf-8'))
            if not package.get('scripts', {}).get(script):
                raise ValueError('missing script ' + script)
        except (OSError, ValueError) as e:
            return {'passed': False, 'reports': [str(e)]}
    npm = shutil.which('npm')
    if not npm:
        return {'passed': False, 'reports': ['npm is not installed']}
    steps = [('frontend', ['install', '--include=optional', '--no-audit', '--no-fund']),
             ('frontend', ['run', 'build']),
             ('backend', ['install', '--include=optional', '--no-audit', '--no-fund']),
             ('backend', ['test'])]
    for i, (folder, argv) in enumerate(steps):
        remaining = min(300, deadline - time.monotonic())
        if remaining <= 0:
            return {'passed': False, 'reports': reports + ['Run deadline exceeded']}
        report = command([npm, *argv], root / folder, remaining, logs / f'check-{i}.log')
        reports.append(report)
        if report['exit']:
            return {'passed': False, 'reports': reports}
    # Avoid accepting a different process already listening at the official port.
    import socket
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', 3000))
        except OSError:
            return {'passed': False, 'reports': reports + ['Port 3000 already occupied']}
    env = child_env()
    env.update(HOST='0.0.0.0', PORT='3000')
    with (logs / 'server.log').open('wb') as output:
        proc = subprocess.Popen([npm, 'run', 'start'], cwd=root / 'backend', env=env,
                                stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=os.name == 'posix')
        ready = False
        try:
            until = min(deadline, time.monotonic() + 120)
            while time.monotonic() < until and proc.poll() is None:
                try:
                    with urllib.request.urlopen('http://127.0.0.1:3000', timeout=2) as response:
                        body = response.read(200000)
                        ready = response.status == 200 and bool(body.strip())
                    if ready:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.5)
        finally:
            stop(proc)
    reports.append({'http_smoke': ready, 'output': (logs / 'server.log').read_text(
        encoding='utf-8', errors='replace')[-12000:]})
    return {'passed': ready, 'reports': reports,
            'scope': 'build, agent-authored tests and root HTTP smoke; not official evaluation'}


class Model:
    def __init__(self, evidence, deadline):
        self.key = os.environ.get('OPENAI_API_KEY', '')
        base = os.environ.get('OPENAI_BASE_URL', '').rstrip('/')
        self.model = os.environ.get('MODEL', '')
        if not self.key or not base or not self.model:
            raise ValueError('Configure OPENAI_API_KEY, OPENAI_BASE_URL and MODEL in the environment')
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Model endpoint must use HTTPS')
        self.url = base + '/chat/completions'
        self.evidence, self.deadline = evidence, deadline
        self.calls = self.tokens = 0
        self.max_calls = int(os.environ.get('AGENT_MAX_CALLS', '100'))
        self.max_tokens = int(os.environ.get('AGENT_MAX_TOTAL_TOKENS', '800000'))
        self.response_tokens = int(os.environ.get('AGENT_RESPONSE_TOKENS', '12000'))
        if min(self.max_calls, self.max_tokens, self.response_tokens) <= 0:
            raise ValueError('Model limits must be positive integers')
        self.usage_known = True

    def ask(self, messages):
        if self.calls >= self.max_calls or self.tokens >= self.max_tokens:
            raise RuntimeError('Model call/token stop limit reached')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Agent time limit reached')
        self.calls += 1
        body = json.dumps({'model': self.model, 'messages': messages,
                           'max_tokens': self.response_tokens}, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(self.url, data=body, headers={
            'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'})
        # No automatic API retry: a timed-out response may already have incurred a charge.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=min(240, remaining)) as response:
                result = json.load(response)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Model request failed with HTTP {e.code}; no automatic retry') from None
        usage = result.get('usage') or {}
        consumed = usage.get('total_tokens')
        if not isinstance(consumed, int):
            self.usage_known = False
        else:
            self.tokens += consumed
        choice = result['choices'][0]
        text = choice['message'].get('content') or ''
        dump(self.evidence / f'model-{self.calls:03d}.json', {
            'request_sha256': hashlib.sha256(body).hexdigest(), 'model': self.model,
            'usage': usage, 'finish_reason': choice.get('finish_reason'),
            'response': text.replace(self.key, '[REDACTED]')})
        print(f'Model call {self.calls}; reported cumulative tokens {self.tokens}', flush=True)
        if not self.usage_known:
            raise RuntimeError('Provider omitted token usage; stopping because usage cannot be tracked')
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('Model output truncated; lower file batch size or raise response token limit')
        return text


def parse(text):
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('Expected one JSON object')
    return value


def inventory(root):
    return [str(p.relative_to(root)).replace('\\', '/') for folder in ('frontend', 'backend')
            for p in (root / folder).rglob('*') if p.is_file()
            and not any(x in ('node_modules', '.git', 'dist', 'data') for x in p.relative_to(root).parts)][:1000]


def phase(model, root, specification, task, deadline, max_turns=24):
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': 'PUBLIC REQUIREMENTS:\n' + specification +
                 '\nCURRENT WORK PHASE:\n' + task + '\nExisting files: ' + json.dumps(inventory(root))}]
    for turn in range(max_turns):
        raw = model.ask(messages)
        messages.append({'role': 'assistant', 'content': raw})
        try:
            action = parse(raw)
            kind = action.get('action')
            if kind == 'done':
                return action.get('summary', '')
            if kind == 'read':
                result = application_path(root, action['path']).read_text(encoding='utf-8')
            elif kind == 'write':
                files = action['files']
                if not isinstance(files, list) or not files or len(files) > 20:
                    raise ValueError('Write 1 to 20 files per call')
                prepared = [(application_path(root, f['path']), f['content']) for f in files]
                if not all(isinstance(content, str) for _, content in prepared):
                    raise ValueError('File content must be text')
                for path, content in prepared:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding='utf-8')
                result = 'Written: ' + ', '.join(f['path'] for f in files)
            elif kind == 'replace':
                path = application_path(root, action['path'])
                old = path.read_text(encoding='utf-8')
                if not action['old'] or old.count(action['old']) != 1:
                    raise ValueError('old text must match exactly once')
                path.write_text(old.replace(action['old'], action['new'], 1), encoding='utf-8')
                result = 'Replaced'
            elif kind == 'check':
                result = json.dumps(verify(root, deadline))
            else:
                raise ValueError('Unknown action')
        except (ValueError, KeyError, OSError, TypeError) as e:
            result = 'Action error: ' + str(e)
        messages.append({'role': 'user', 'content': result})
    raise RuntimeError('Phase exhausted its turn limit before completion')


def run(args):
    source, root = Path(args.requirements_dir).resolve(), Path(args.output_dir).resolve()
    if not (source / 'requirements.yaml').is_file():
        raise ValueError('requirements_dir must contain requirements.yaml')
    if root == source or root.is_relative_to(ROOT) or ROOT.is_relative_to(root):
        raise ValueError('Use a separate output directory outside the agent source directory')
    for folder in ('frontend', 'backend'):
        if (root / folder).exists():
            raise ValueError('Use a clean run directory; generated application folders already exist')
    specification = (source / 'requirements.yaml').read_text(encoding='utf-8')
    if not specification.strip():
        raise ValueError('Empty requirements')
    preflight = {'contract': 'main.py REQUIREMENTS_DIR --output-dir OUTPUT_DIR',
                 'requirement_sha256': hashlib.sha256(specification.encode('utf-8')).hexdigest(),
                 'requirement_bytes': len(specification.encode('utf-8')),
                 'model_config_present': all(os.environ.get(k) for k in
                                            ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'MODEL')),
                 'npm_present': bool(shutil.which('npm')),
                 'reference_images': 'Not sent in v1; public textual requirements are authoritative'}
    if args.preflight:
        print(json.dumps(preflight, indent=2))
        return
    root.mkdir(parents=True, exist_ok=True)
    evidence = root / '.agent-evidence'
    evidence.mkdir(exist_ok=True)
    seconds = int(os.environ.get('AGENT_SECONDS', '10800'))
    if seconds <= 0:
        raise ValueError('AGENT_SECONDS must be positive')
    deadline = time.monotonic() + min(seconds, 172000)
    model = Model(evidence, deadline)
    dump(evidence / 'input.json', preflight)
    planning = model.ask([{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content':
        'Plan the application from these public requirements. Return ONLY JSON with architecture '
        '(string: files, data model, API, shared UI contracts) and modules (array of 1 to 10 strings '
        'in dependency order, with requirement IDs, inherited constraints, acceptance criteria). '
        'Cover all requirements, not just a demo. Include seeds, accessible interactions and '
        'cross-module persistence. Do not write code yet.\n' + specification}])
    plan = parse(planning)
    modules = plan.get('modules')
    if not isinstance(modules, list) or not 1 <= len(modules) <= 10 or not all(isinstance(m, str) for m in modules):
        raise ValueError('Model returned invalid module plan')
    dump(evidence / 'plan.json', plan)
    summaries = []
    for index, module in enumerate(modules):
        summary = phase(model, root, specification, 'Architecture:\n' + str(plan.get('architecture')) +
                        '\nImplement module:\n' + module + '\nPrevious work:\n' + '\n'.join(summaries), deadline)
        summaries.append(summary)
        dump(evidence / f'module-{index + 1}.json', {'module': module, 'summary': summary})
    phase(model, root, specification,
          'Review all implemented files against every public requirement. Read code, fix integration '
          'and accessibility gaps, add meaningful self-tests, then use check. Architecture:\n' +
          str(plan.get('architecture')) + '\nModule summaries:\n' + '\n'.join(summaries), deadline)
    for repair in range(3):
        result = verify(root, deadline)
        dump(evidence / f'verification-{repair}.json', result)
        if result['passed']:
            dump(evidence / 'result.json', {'status': 'local_checks_passed', 'model_calls': model.calls,
                 'reported_tokens': model.tokens, 'official_score': None, 'verification': result['scope']})
            print('Local checks passed. Official evaluation has not run.', flush=True)
            return
        if repair < 2:
            phase(model, root, specification, 'Repair these local failures without weakening tests:\n' +
                  json.dumps(result), deadline, max_turns=12)
    raise RuntimeError('Application did not pass local deployment checks after two repair phases')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('requirements_dir')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--preflight', action='store_true', help='Validate inputs without model calls or writes')
    try:
        run(parser.parse_args())
    except Exception as error:
        # Never print an API request/header or environment value.
        message = str(error)
        for name in ('OPENAI_API_KEY', 'VISUAL_API_KEY'):
            if os.environ.get(name):
                message = message.replace(os.environ[name], '[REDACTED]')
        print(type(error).__name__ + ': ' + message, file=sys.stderr)
        raise SystemExit(1)
