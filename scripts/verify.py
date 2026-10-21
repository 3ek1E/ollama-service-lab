"""Real end-to-end checks; writes a shareable report without secrets."""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'examples'))
from call_four_apis import call
from tool_agent import solve
from rag import answer


def main():
    base = os.environ.get('SERVICE_BASE_URL', 'http://127.0.0.1:8088')
    key = (ROOT/'.local/service.key').read_text().strip()
    os.environ['SERVICE_API_KEY'] = key
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if urllib.parse.urlsplit(base).hostname in ('localhost', '127.0.0.1', '::1') else urllib.request.build_opener()
    report = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              'model': 'qwen3.5:0.8b', 'target': base, 'checks': []}
    def check(name, fn):
        try:
            result = fn()
            report['checks'].append({'name': name, 'passed': True, 'result': result})
            print('PASS', name, flush=True)
        except Exception as exc:
            report['checks'].append({'name': name, 'passed': False, 'error': str(exc)})
            print('FAIL', name, str(exc), flush=True)
    def request(path, auth=True, body=None):
        headers = {'Authorization': 'Bearer '+key} if auth else {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(base+path, body, headers)
        with opener.open(req, timeout=15) as response:
            return json.load(response)
    def expect_status(path, code, auth=True, body=None):
        try:
            request(path, auth, body)
        except urllib.error.HTTPError as exc:
            assert exc.code == code, (exc.code, code)
            return {'http_status': exc.code}
        raise AssertionError(f'Expected HTTP {code}')
    check('health', lambda: request('/healthz', False))
    check('reject_missing_key', lambda: expect_status('/api/tags', 401, False))
    check('deny_model_management', lambda: expect_status('/api/pull', 404, body=b'{}'))
    check('reject_invalid_json', lambda: expect_status('/api/chat', 400, body=b'{'))
    check('reject_unapproved_model', lambda: expect_status('/api/chat', 400, body=b'{"model":"not-permitted"}'))
    check('ollama_version', lambda: request('/api/version'))
    check('downloaded_models', lambda: request('/api/tags'))
    for stream in (False, True):
        for api in ('ollama', 'chat', 'responses', 'anthropic'):
            def run(api=api, stream=stream):
                result = call(api, base, key, 'qwen3.5:0.8b', '请用中文简短回答：1+1等于几？', stream)
                assert result['http_status'] == 200 and '2' in result['text'], result
                return result
            check(api+('_stream' if stream else '_sync'), run)
    def tools():
        result = solve('请使用calculate计算(123+456)*7，然后告诉我结果。')
        assert any(x['result'].get('value') == 4053 for x in result['trace']), result
        assert '4053' in result['answer'], result
        return result
    check('tool_call_round_trip', tools)
    def rag():
        result = answer('模型服务网关的端口和认证方式是什么？')
        assert 'service.md' in result['sources'] and '8088' in result['answer'], result
        return result
    check('rag_retrieval_and_generation', rag)
    report['passed'] = all(c['passed'] for c in report['checks'])
    destination = ROOT/'reports/verification.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Report:', destination)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
