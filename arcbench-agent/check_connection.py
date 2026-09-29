"""One small real model request; never print or persist credentials."""
import argparse
import json
import os
from pathlib import Path
import time
from main import Model, parse

def check(env_file, output):
    values = {}
    for raw in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        values[name.strip()] = value.strip().strip('\"\'')
    for name in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'MODEL'):
        if not values.get(name):
            raise ValueError('Missing configuration: ' + name)
        os.environ[name] = values[name]
    os.environ['AGENT_RESPONSE_TOKENS'] = '512'
    os.environ['AGENT_MAX_CALLS'] = '1'
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    model = Model(output, time.monotonic() + 120)
    text = model.ask([{'role':'user','content':'Reply only with this JSON object: {"connection":"ok"}. No explanation.'}])
    valid = parse(text).get('connection') == 'ok'
    result = {'connected': valid, 'model': values['MODEL'], 'base_url': values['OPENAI_BASE_URL'],
              'model_calls': model.calls, 'reported_tokens': model.tokens,
              'cost': None, 'note':'Small real request, not application generation or official evaluation'}
    (output/'connection.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    if not valid:
        raise ValueError('Unexpected model response')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        check(args.env_file, args.output)
    except Exception as error:
        # Only exception type: network errors can contain sensitive URLs.
        print('Connection check failed: ' + type(error).__name__)
        raise SystemExit(1)
