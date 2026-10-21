"""Authenticated, streaming, allow-listed proxy to a local Ollama server.

Python 3.10+, standard library only. Ollama owns protocol compatibility.
"""
import hmac
import http.client
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

GET_PATHS = {'/api/version', '/api/tags', '/v1/models'}
POST_PATHS = {'/api/chat', '/api/generate', '/api/embed', '/api/show',
              '/v1/chat/completions', '/v1/responses', '/v1/messages', '/v1/embeddings'}
MAX_BODY = 2 * 1024 * 1024


class Gateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, upstream, api_key, max_concurrent=2, timeout=180):
        if len(api_key) < 32 or api_key.startswith('replace-with'):
            raise ValueError('SERVICE_API_KEY must be a random secret of at least 32 characters')
        parsed = urlsplit(upstream)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.path not in ('', '/') or parsed.query or parsed.username:
            raise ValueError('Upstream must be a loopback HTTP Ollama URL')
        self.upstream = (parsed.hostname, parsed.port or 11434)
        self.api_key = api_key
        self.slots = threading.BoundedSemaphore(max_concurrent)
        self.upstream_timeout = timeout
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 closes the downstream connection at EOF, including streams.
    # Upstream transfer framing is decoded by http.client, never forwarded.
    protocol_version = 'HTTP/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, fmt, *args):
        # Never log headers, body, or URL query strings containing secrets.
        pass

    def send_json(self, status, value):
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self):
        auth = self.headers.get('Authorization', '')
        token = auth[7:] if auth.startswith('Bearer ') else ''
        other = self.headers.get('x-api-key', '')
        secret = self.server.api_key.encode()
        return any(hmac.compare_digest(v.encode(), secret) for v in (token, other))

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def dispatch(self):
        path = urlsplit(self.path).path
        if self.path == '/healthz' and self.command == 'GET':
            return self.send_json(200, {'status': 'gateway-alive', 'readiness': '/api/tags (authenticated)'})
        if not self.authorized():
            return self.send_json(401, {'error': 'Valid Bearer token or x-api-key required'})
        allowed = GET_PATHS if self.command == 'GET' else POST_PATHS
        if path not in allowed or self.path != path:
            return self.send_json(404, {'error': 'Route not exposed'})
        raw = None
        if self.command == 'POST':
            if self.headers.get('Transfer-Encoding'):
                return self.send_json(400, {'error': 'Send a Content-Length, not chunked request bodies'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return self.send_json(400, {'error': 'Invalid Content-Length'})
            if not 0 < length <= MAX_BODY:
                return self.send_json(413, {'error': 'JSON body must be 1 byte to 2 MiB'})
            try:
                raw = self.rfile.read(length)
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError('JSON object required')
                # Prevent model downloads and cloud model names via public inference.
                # Expose only the model selected by the operator (embedding model optional).
                models = {os.environ.get('OLLAMA_MODEL', 'qwen3.5:0.8b')}
                models.add(os.environ.get('OLLAMA_EMBED_MODEL', 'embeddinggemma'))
                if not isinstance(payload.get('model'), str) or payload['model'] not in models:
                    return self.send_json(400, {'error': 'Model is not on the service allow-list'})
            except (ValueError, UnicodeError):
                return self.send_json(400, {'error': 'Valid JSON object required'})
            except (TimeoutError, socket.timeout):
                return self.send_json(408, {'error': 'Request body timeout'})
        if not self.server.slots.acquire(blocking=False):
            return self.send_json(429, {'error': 'Service busy; retry later'})
        conn = http.client.HTTPConnection(*self.server.upstream, timeout=self.server.upstream_timeout)
        started = False
        try:
            headers = {'Content-Type': 'application/json'}
            for key in ('anthropic-version', 'anthropic-beta', 'Accept'):
                if self.headers.get(key):
                    headers[key] = self.headers[key]
            conn.request(self.command, path, body=raw, headers=headers)
            upstream = conn.getresponse()
            self.send_response(upstream.status)
            self.send_header('Content-Type', upstream.getheader('Content-Type', 'application/json'))
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Connection', 'close')
            self.end_headers()
            started = True
            while chunk := upstream.read1(8192):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (TimeoutError, socket.timeout):
            if not started:
                self.send_json(504, {'error': 'Ollama request timed out'})
        except (OSError, http.client.HTTPException):
            if not started:
                self.send_json(502, {'error': 'Ollama unavailable'})
        finally:
            conn.close()
            self.server.slots.release()
            self.close_connection = True


def main():
    address = (os.environ.get('SERVICE_HOST', '127.0.0.1'), int(os.environ.get('SERVICE_PORT', '8088')))
    server = Gateway(address, os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'),
                     os.environ.get('SERVICE_API_KEY', ''),
                     int(os.environ.get('SERVICE_MAX_CONCURRENT', '2')),
                     int(os.environ.get('SERVICE_TIMEOUT', '180')))
    print(f'Ollama gateway listening on {address[0]}:{address[1]} (authentication enabled)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
