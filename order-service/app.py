import json
import socket
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from common import Handler, Problem, database, initialize, os, quantity, serve, text

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
 id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, customer TEXT NOT NULL,
 sku TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
 status TEXT NOT NULL CHECK(status IN ('PENDING','CONFIRMED','REJECTED')),
 reason TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""

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
