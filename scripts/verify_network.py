"""Verify actual LAN binding and temporary public non-streaming access."""
import datetime
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'examples'))
from call_four_apis import call


def main():
    key = (ROOT/'.local/service.key').read_text().strip()
    log = (ROOT/'.runtime/tunnel.stderr.log').read_text(encoding='utf-8')
    public = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log).group()
    lan = sys.argv[1] if len(sys.argv) > 1 else None
    report = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              'public_url': public, 'checks': [], 'public_streaming': 'Not tested: Quick Tunnels officially do not support SSE',
              'lan_scope': 'Server accessing own LAN IP only; no second device was available'}
    def check(name, fn):
        try:
            result = fn()
            report['checks'].append({'name':name,'passed':True,'result':result})
            print('PASS', name, flush=True)
        except Exception as exc:
            report['checks'].append({'name':name,'passed':False,'error':str(exc)})
            print('FAIL',name,str(exc),flush=True)
    def no_key():
        try:
            with urllib.request.urlopen(public+'/api/tags', timeout=30) as response:
                raise AssertionError(f'Expected 401, got {response.status}')
        except urllib.error.HTTPError as exc:
            assert exc.code == 401, exc.code
            return {'http_status': exc.code}
    check('public_reject_missing_key', no_key)
    for api in ('ollama','chat','responses','anthropic'):
        def run(api=api):
            result = call(api, public, key, 'qwen3.5:0.8b', '请用中文简短回答：1+1等于几？')
            assert result['http_status'] == 200 and '2' in result['text'], result
            return result
        check('public_'+api+'_sync', run)
    if lan:
        def run_lan():
            result = call('ollama', lan, key, 'qwen3.5:0.8b', '请简短回答：1+1等于几？')
            assert result['http_status'] == 200 and '2' in result['text'], result
            return result
        check('lan_self_address',run_lan)
    report['passed'] = all(item['passed'] for item in report['checks'])
    (ROOT/'reports/network-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print('Public URL:',public)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
