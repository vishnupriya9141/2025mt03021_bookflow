"""Materialize two independently runnable service repositories and deployment assets."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def write(path, content):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + '\n', encoding='utf-8')

COMMON = r'''
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
'''

INVENTORY = r'''
import hmac
from common import Handler, Problem, database, initialize, os, quantity, serve, text

SCHEMA = ''' + '"""' + r'''
CREATE TABLE IF NOT EXISTS books (
 sku TEXT PRIMARY KEY, title TEXT NOT NULL, available INTEGER NOT NULL CHECK(available >= 0));
CREATE TABLE IF NOT EXISTS reservations (
 order_id TEXT PRIMARY KEY, sku TEXT NOT NULL REFERENCES books(sku),
 quantity INTEGER NOT NULL CHECK(quantity > 0), status TEXT NOT NULL CHECK(status IN ('RESERVED','REJECTED')));
INSERT OR IGNORE INTO books VALUES ('BOOK-001','Designing Distributed Systems',10);
INSERT OR IGNORE INTO books VALUES ('BOOK-002','Microservices in Practice',5);
''' + '"""' + r'''

def reserve(order_id, sku, count):
    with database() as conn:
        # Serialize the read/check/write so competing requests cannot oversell.
        conn.execute('BEGIN IMMEDIATE')
        existing = conn.execute('SELECT * FROM reservations WHERE order_id=?', (order_id,)).fetchone()
        if existing:
            if (existing['sku'], existing['quantity']) != (sku, count):
                raise Problem(409, 'order_id already has a different reservation')
            return (200 if existing['status'] == 'RESERVED' else 409), dict(existing)
        book = conn.execute('SELECT * FROM books WHERE sku=?', (sku,)).fetchone()
        if book is None:
            raise Problem(404, 'Unknown book SKU')
        status = 'RESERVED' if book['available'] >= count else 'REJECTED'
        conn.execute('INSERT INTO reservations VALUES (?,?,?,?)', (order_id, sku, count, status))
        if status == 'RESERVED':
            conn.execute('UPDATE books SET available=available-? WHERE sku=?', (count, sku))
        return (201 if status == 'RESERVED' else 409), dict(order_id=order_id, sku=sku, quantity=count, status=status)

class InventoryHandler(Handler):
    def route(self, method, path):
        if method == 'GET' and path == '/books':
            with database() as conn:
                return 200, [dict(row) for row in conn.execute('SELECT * FROM books ORDER BY sku')]
        if method == 'GET' and path.startswith('/books/'):
            with database() as conn:
                row = conn.execute('SELECT * FROM books WHERE sku=?', (path[7:],)).fetchone()
            if row is None:
                raise Problem(404, 'Unknown book SKU')
            return 200, dict(row)
        if method == 'POST' and path == '/reservations':
            token = os.environ.get('SERVICE_TOKEN', '')
            if not token or not hmac.compare_digest(self.headers.get('X-Service-Token', ''), token):
                raise Problem(401, 'Invalid service token')
            data = self.body()
            return reserve(text(data.get('order_id'), 'order_id'),
                           text(data.get('sku'), 'sku'), quantity(data.get('quantity')))
        raise Problem(404, 'Route not found')

if __name__ == '__main__':
    if not os.environ.get('SERVICE_TOKEN'):
        raise SystemExit('Set SERVICE_TOKEN before starting Inventory')
    initialize(SCHEMA)
    serve(InventoryHandler, 8001)
'''

ORDERS = r'''
import json
import socket
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from common import Handler, Problem, database, initialize, os, quantity, serve, text

SCHEMA = ''' + '"""' + r'''
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, customer TEXT NOT NULL,
 sku TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
 status TEXT NOT NULL CHECK(status IN ('PENDING','CONFIRMED','REJECTED')),
 reason TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
''' + '"""' + r'''

def place_order(key, customer, sku, count):
    with database() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM orders WHERE idempotency_key=?', (key,)).fetchone()
        if row:
            if (row['customer'], row['sku'], row['quantity']) != (customer, sku, count):
                raise Problem(409, 'Idempotency-Key already used for a different order')
            if row['status'] != 'PENDING':
                return 200, dict(row)
            order_id = row['id']
        else:
            order_id = str(uuid.uuid4())
            conn.execute('INSERT INTO orders (id,idempotency_key,customer,sku,quantity,status) VALUES (?,?,?,?,?,?)',
                         (order_id, key, customer, sku, count, 'PENDING'))
    # Commit PENDING before the network call. Never hold a DB transaction across HTTP.
    payload = json.dumps(dict(order_id=order_id, sku=sku, quantity=count)).encode()
    request = Request(os.environ.get('INVENTORY_URL', 'http://127.0.0.1:8001') + '/reservations',
                      data=payload, headers={'Content-Type':'application/json',
                      'X-Service-Token':os.environ['SERVICE_TOKEN']}, method='POST')
    try:
        with urlopen(request, timeout=2) as response:
            reservation = json.load(response)
        if reservation.get('status') != 'RESERVED' or reservation.get('order_id') != order_id:
            raise ValueError('Unexpected inventory response')
        status, reason = 'CONFIRMED', None
    except HTTPError as exc:
        if exc.code in (404, 409):
            status, reason = 'REJECTED', 'Unknown SKU' if exc.code == 404 else 'Insufficient stock'
        else:
            raise Problem(503, 'Inventory unavailable; retry the same Idempotency-Key')
    except (URLError, TimeoutError, socket.timeout, OSError, ValueError):
        raise Problem(503, 'Inventory outcome unknown; retry the same Idempotency-Key')
    with database() as conn:
        conn.execute('UPDATE orders SET status=?,reason=? WHERE id=? AND status=\'PENDING\'',
                     (status, reason, order_id))
        result = dict(conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone())
    return 201, result

class OrderHandler(Handler):
    def route(self, method, path):
        if method == 'POST' and path == '/orders':
            key = text(self.headers.get('Idempotency-Key'), 'Idempotency-Key')
            data = self.body()
            return place_order(key, text(data.get('customer'), 'customer'),
                               text(data.get('sku'), 'sku'), quantity(data.get('quantity')))
        if method == 'GET' and path == '/orders':
            with database() as conn:
                return 200, [dict(row) for row in conn.execute('SELECT * FROM orders ORDER BY created_at,id LIMIT 100')]
        if method == 'GET' and path.startswith('/orders/'):
            with database() as conn:
                row = conn.execute('SELECT * FROM orders WHERE id=?', (path[8:],)).fetchone()
            if row is None:
                raise Problem(404, 'Unknown order')
            return 200, dict(row)
        raise Problem(404, 'Route not found')

if __name__ == '__main__':
    if not os.environ.get('SERVICE_TOKEN'):
        raise SystemExit('Set SERVICE_TOKEN before starting Orders')
    initialize(SCHEMA)
    serve(OrderHandler, 8002)
'''

DOCKERFILE = '''
FROM python:3.13-slim
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app && mkdir /data && chown app:app /data
COPY --chown=app:app app.py common.py ./
USER 10001:10001
ENV HOST=0.0.0.0 PORT=8000 DB_PATH=/data/service.db PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=2)"]
CMD ["python", "app.py"]
'''

def main():
    for name, source in [('inventory-service', INVENTORY), ('order-service', ORDERS)]:
        write(f'{name}/app.py', source)
        write(f'{name}/common.py', COMMON)
        write(f'{name}/Dockerfile', DOCKERFILE)
        write(f'{name}/.dockerignore', '.git\n__pycache__\ndata\ntests\n*.db*')
        write(f'{name}/.gitignore', '__pycache__/\ndata/\n*.db*\n.venv/\n.env')
        write(f'{name}/requirements.txt', '# Python 3.13 standard library only; no pip dependencies.')
        write(f'{name}/.github/workflows/ci.yml', '''
name: Service CI
on: [push, pull_request, workflow_dispatch]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: python -m unittest discover -s tests -v
      - run: docker build -t bookflow-service:ci .
''')
    write('compose.yaml', '''
services:
  inventory:
    build: ./inventory-service
    image: bookflow-inventory:1.0
    ports: ["127.0.0.1:8001:8000"]
    environment:
      SERVICE_TOKEN: ${SERVICE_TOKEN:?Set SERVICE_TOKEN first}
    volumes: ["inventory-data:/data"]
    restart: unless-stopped
  orders:
    build: ./order-service
    image: bookflow-orders:1.0
    ports: ["127.0.0.1:8002:8000"]
    environment:
      SERVICE_TOKEN: ${SERVICE_TOKEN:?Set SERVICE_TOKEN first}
      INVENTORY_URL: http://inventory:8000
    volumes: ["order-data:/data"]
    depends_on:
      inventory:
        condition: service_healthy
    restart: unless-stopped
volumes:
  inventory-data:
  order-data:
''')

if __name__ == '__main__':
    main()
