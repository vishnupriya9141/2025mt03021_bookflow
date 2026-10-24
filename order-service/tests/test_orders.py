import io
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import app
import common


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        common.DB_PATH = os.path.join(self.temp.name, 'orders.db')
        common.initialize(app.SCHEMA)
        self.env = patch.dict(os.environ, SERVICE_TOKEN='test-token')
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    @staticmethod
    def reserved(request, timeout):
        data = app.json.loads(request.data)
        return io.BytesIO(app.json.dumps(dict(status='RESERVED', order_id=data['order_id'])).encode())

    def test_confirm_and_replay_without_second_call(self):
        with patch('app.urlopen', side_effect=self.reserved) as remote:
            status, first = app.place_order('k', 'Student', 'BOOK-001', 2)
            again, second = app.place_order('k', 'Student', 'BOOK-001', 2)
        self.assertEqual((status, again), (201, 200))
        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'CONFIRMED')
        self.assertEqual(remote.call_count, 1)

    def test_key_cannot_change_payload(self):
        with patch('app.urlopen', side_effect=self.reserved):
            app.place_order('k', 'Student', 'BOOK-001', 2)
            with self.assertRaises(common.Problem) as ctx:
                app.place_order('k', 'Student', 'BOOK-002', 2)
        self.assertEqual(ctx.exception.status, 409)

    def test_insufficient_stock_rejects(self):
        error = HTTPError('http://inventory', 409, 'Conflict', {}, None)
        with patch('app.urlopen', side_effect=error):
            status, order = app.place_order('k', 'Student', 'BOOK-001', 20)
        self.assertEqual((status, order['status']), (201, 'REJECTED'))

    def test_unknown_book_rejects(self):
        error = HTTPError('http://inventory', 404, 'Not Found', {}, None)
        with patch('app.urlopen', side_effect=error):
            _, order = app.place_order('k', 'Student', 'MISSING', 1)
        self.assertEqual(order['reason'], 'Unknown SKU')

    def test_timeout_stays_pending_and_retry_uses_same_order_id(self):
        with patch('app.urlopen', side_effect=URLError('timeout')):
            with self.assertRaises(common.Problem) as ctx:
                app.place_order('k', 'Student', 'BOOK-001', 2)
        self.assertEqual(ctx.exception.status, 503)
        with common.database() as conn:
            pending = dict(conn.execute('SELECT * FROM orders').fetchone())
        self.assertEqual(pending['status'], 'PENDING')
        common.initialize(app.SCHEMA)  # simulated process restart
        with patch('app.urlopen', side_effect=self.reserved):
            _, result = app.place_order('k', 'Student', 'BOOK-001', 2)
        self.assertEqual(result['id'], pending['id'])
        self.assertEqual(result['status'], 'CONFIRMED')

    def test_auth_failure_does_not_reject_order(self):
        error = HTTPError('http://inventory', 401, 'Unauthorized', {}, None)
        with patch('app.urlopen', side_effect=error), self.assertRaises(common.Problem) as ctx:
            app.place_order('k', 'Student', 'BOOK-001', 2)
        self.assertEqual(ctx.exception.status, 503)
        with common.database() as conn:
            self.assertEqual(conn.execute('SELECT status FROM orders').fetchone()[0], 'PENDING')

    def test_empty_or_oversize_key(self):
        for key in ['', ' ', None, 'a' * 121]:
            with self.subTest(key=key), self.assertRaises(common.Problem):
                common.text(key, 'Idempotency-Key')


if __name__ == '__main__':
    unittest.main()
