import hmac
from common import Handler, Problem, database, initialize, os, quantity, serve, text

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
 sku TEXT PRIMARY KEY, title TEXT NOT NULL, available INTEGER NOT NULL CHECK(available >= 0));
CREATE TABLE IF NOT EXISTS reservations (
 order_id TEXT PRIMARY KEY, sku TEXT NOT NULL REFERENCES books(sku),
 quantity INTEGER NOT NULL CHECK(quantity > 0), status TEXT NOT NULL CHECK(status IN ('RESERVED','REJECTED')));
INSERT OR IGNORE INTO books VALUES ('BOOK-001','Designing Distributed Systems',10);
INSERT OR IGNORE INTO books VALUES ('BOOK-002','Microservices in Practice',5);
"""

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
