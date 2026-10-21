import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway import Gateway


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"models":[]}')

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if payload.get('stream'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            raw = 'data: {"delta":"中文"}\n\ndata: [DONE]\n\n'.encode()
            for chunk in (raw[:19], raw[19:]):
                self.wfile.write(f'{len(chunk):x}\r\n'.encode()+chunk+b'\r\n')
                self.wfile.flush()
            self.wfile.write(b'0\r\n\r\n')
        else:
            self.send_response(422)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"upstream validation"}')


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = 'test-secret-'+'x'*40
        cls.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        cls.gateway = Gateway(('127.0.0.1', 0), f'http://127.0.0.1:{cls.upstream.server_port}', cls.key, 1)
        for server in (cls.upstream, cls.gateway):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.gateway, cls.upstream):
            server.shutdown()
            server.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.gateway.server_port, timeout=5)
        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_health_is_public_but_api_requires_key(self):
        self.assertEqual(self.request('GET', '/healthz')[0], 200)
        self.assertEqual(self.request('GET', '/api/tags')[0], 401)
        self.assertEqual(self.request('GET', '/api/tags', headers={'Authorization': 'Bearer invalid'})[0], 401)

    def test_anthropic_key_header(self):
        self.assertEqual(self.request('GET', '/api/tags', headers={'x-api-key': self.key})[0], 200)

    def test_no_model_management_or_query_token(self):
        headers = {'Authorization': 'Bearer '+self.key}
        self.assertEqual(self.request('POST', '/api/pull', '{}', headers)[0], 404)
        self.assertEqual(self.request('GET', '/api/tags?token='+self.key)[0], 401)
        self.assertEqual(self.request('GET', '/api/tags?foo=bar', headers=headers)[0], 404)

    def test_reject_oversized_and_chunked_bodies(self):
        headers = {'Authorization': 'Bearer '+self.key, 'Content-Length': str(3*1024*1024)}
        self.assertEqual(self.request('POST', '/api/chat', b'', headers)[0], 413)
        headers = {'Authorization': 'Bearer '+self.key, 'Transfer-Encoding': 'chunked'}
        self.assertEqual(self.request('POST', '/api/chat', b'', headers)[0], 400)

    def test_upstream_error_status_is_preserved(self):
        status, _, body = self.request('POST', '/api/chat', '{"model":"qwen3.5:0.8b"}', {'x-api-key': self.key})
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(body)['error'], 'upstream validation')

    def test_stream_is_preserved_and_hop_headers_are_removed(self):
        status, headers, body = self.request('POST', '/v1/responses', '{"model":"qwen3.5:0.8b","stream":true}', {'x-api-key': self.key})
        self.assertEqual(status, 200)
        self.assertNotIn('Transfer-Encoding', headers)
        self.assertEqual(body.decode(), 'data: {"delta":"中文"}\n\ndata: [DONE]\n\n')

    def test_concurrent_capacity_is_enforced(self):
        self.gateway.slots.acquire()
        try:
            self.assertEqual(self.request('GET', '/api/tags', headers={'x-api-key': self.key})[0], 429)
        finally:
            self.gateway.slots.release()

    def test_refuses_untrusted_upstream_and_weak_key(self):
        for upstream, key in [('http://example.com', self.key), ('http://127.0.0.1:11434', 'ollama')]:
            with self.assertRaises(ValueError):
                Gateway(('127.0.0.1', 0), upstream, key)


if __name__ == '__main__':
    unittest.main()
