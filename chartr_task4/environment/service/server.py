import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from store import Store

STORE = Store(os.environ.get('CLINIC_STATE', '/state/state.sqlite'), os.environ.get('CLINIC_SOURCES', '/data/sources.sqlite'),
              os.environ.get('CLINIC_ECG', '/data/ecg'))


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *args):
        pass  # No request bodies or patient text in container stdout.

    def handle_request(self):
        if self.command == 'GET' and self.path == '/health':
            status, body = 200, {'ready': True}
        else:
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 <= length <= 16384:
                    raise ValueError('Request body exceeds 16384 bytes')
                body = json.loads(self.rfile.read(length)) if length else None
            except (ValueError, TimeoutError):
                body = None
            status, body = STORE.request(self.command, self.path, body)
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass  # A committed write must never be repeated implicitly.

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request


if __name__ == '__main__':
    STORE.initialize()
    ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
