import json
import os
import sqlite3
import traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DB_PATH = os.environ.get('DB_PATH', 'data/service.db')

class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

@contextmanager
def database():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize(schema):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with database() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(schema)

def text(value, name, maximum=120):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Problem(400, f'{name} must be a nonempty string of at most {maximum} characters')
    return value.strip()

def quantity(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise Problem(400, 'quantity must be an integer between 1 and 1000')
    return value

class Handler(BaseHTTPRequestHandler):
    server_version = 'BookFlow/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def body(self):
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise Problem(415, 'Content-Type must be application/json')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise Problem(400, 'JSON body must be between 1 and 16384 bytes')
            value = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            raise Problem(400, 'Malformed JSON body')
        if not isinstance(value, dict):
            raise Problem(400, 'JSON body must be an object')
        return value

    def respond(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def dispatch(self):
        try:
            path = urlsplit(self.path).path.rstrip('/') or '/'
            if self.command == 'GET' and path == '/health/live':
                result = (200, {'status': 'live'})
            elif self.command == 'GET' and path == '/health/ready':
                with database() as conn:
                    conn.execute('SELECT 1').fetchone()
                result = (200, {'status': 'ready'})
            else:
                result = self.route(self.command, path)
            self.respond(*result)
        except Problem as exc:
            self.respond(exc.status, {'error': exc.message})
        except sqlite3.Error:
            traceback.print_exc()
            self.respond(503, {'error': 'Database temporarily unavailable'})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            self.respond(500, {'error': 'Unexpected server error'})

    do_GET = dispatch
    do_POST = dispatch

def serve(handler, default_port):
    server = ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'),
                                  int(os.environ.get('PORT', default_port))), handler)
    print(f'BookFlow listening on {server.server_address}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
