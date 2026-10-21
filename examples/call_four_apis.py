"""Call the SAME local model via four protocols, no SDK dependencies.

python examples/call_four_apis.py --api all
python examples/call_four_apis.py --api anthropic --stream
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request


def request_spec(api, model, prompt, stream=False):
    messages = [{'role': 'user', 'content': prompt}]
    common = {'model': model, 'stream': stream, 'temperature': 0}
    if api == 'ollama':
        return '/api/chat', dict(model=model, messages=messages, stream=stream, think=False,
                                 options={'temperature': 0, 'num_predict': 128})
    if api == 'chat':
        return '/v1/chat/completions', dict(common, messages=messages, max_tokens=128, reasoning_effort='none')
    if api == 'responses':
        return '/v1/responses', dict(common, input=prompt, max_output_tokens=128, think=False)
    return '/v1/messages', dict(common, messages=messages, max_tokens=128, thinking={'type': 'disabled'})


def text_of(api, value):
    if api == 'ollama':
        return value.get('message', {}).get('content', '')
    if api == 'chat':
        return value['choices'][0]['message'].get('content', '')
    if api == 'responses':
        return ''.join(c.get('text', '') for item in value.get('output', [])
                       for c in item.get('content', []) if c.get('type') == 'output_text')
    return ''.join(c.get('text', '') for c in value.get('content', []) if c.get('type') == 'text')


def stream_text(api, value):
    if api == 'ollama':
        return value.get('message', {}).get('content', '')
    if api == 'chat':
        return ''.join(c.get('delta', {}).get('content') or '' for c in value.get('choices', []))
    if api == 'responses':
        return value.get('delta', '') if value.get('type') == 'response.output_text.delta' else ''
    return value.get('delta', {}).get('text', '') if value.get('type') == 'content_block_delta' else ''


def call(api, base, key, model, prompt, stream=False):
    path, payload = request_spec(api, model, prompt, stream)
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer '+key,
               'x-api-key': key, 'anthropic-version': '2023-06-01'}
    req = urllib.request.Request(base.rstrip('/')+path, json.dumps(payload).encode(), headers)
    # Explicitly bypass any system proxy for the local service only.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if urllib.parse.urlsplit(base).hostname in ('localhost', '127.0.0.1', '::1') else urllib.request.build_opener()
    start = time.perf_counter()
    with opener.open(req, timeout=180) as response:
        if not stream:
            result = json.load(response)
            return {'api': api, 'http_status': response.status, 'seconds': round(time.perf_counter()-start, 3),
                    'text': text_of(api, result), 'raw': result}
        chunks, events = [], 0
        for raw_line in response:
            line = raw_line.decode('utf-8').strip()
            if not line or line.startswith(('event:', ':')):
                continue
            if line.startswith('data:'):
                line = line[5:].strip()
            if line == '[DONE]':
                continue
            value = json.loads(line)
            if value.get('error') or value.get('type') == 'error':
                raise RuntimeError(str(value))
            delta = stream_text(api, value)
            chunks.append(delta)
            events += 1
        return {'api': api, 'http_status': response.status, 'seconds': round(time.perf_counter()-start, 3),
                'stream': True, 'events': events, 'text': ''.join(chunks)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', choices=['all', 'ollama', 'chat', 'responses', 'anthropic'], default='all')
    parser.add_argument('--base-url', default=os.environ.get('SERVICE_BASE_URL', 'http://127.0.0.1:8088'))
    parser.add_argument('--model', default=os.environ.get('OLLAMA_MODEL', 'qwen3.5:0.8b'))
    parser.add_argument('--prompt', default='请用中文简短回答：1+1等于几？')
    parser.add_argument('--stream', action='store_true')
    args = parser.parse_args()
    failed = False
    for api in (['ollama', 'chat', 'responses', 'anthropic'] if args.api == 'all' else [args.api]):
        try:
            result = call(api, args.base_url, os.environ.get('SERVICE_API_KEY', 'ollama'), args.model, args.prompt, args.stream)
            if not result['text'].strip():
                raise RuntimeError('Empty model text')
            print(json.dumps(result, ensure_ascii=False))
        except (urllib.error.URLError, ValueError, RuntimeError, KeyError) as exc:
            print(json.dumps({'api': api, 'error': str(exc)}, ensure_ascii=False))
            failed = True
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
