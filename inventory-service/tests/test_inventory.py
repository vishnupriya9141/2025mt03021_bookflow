import concurrent.futures
import os
import tempfile
import unittest
import app
import common


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        common.DB_PATH = os.path.join(self.temp.name, 'inventory.db')
        common.initialize(app.SCHEMA)

    def tearDown(self):
        self.temp.cleanup()

    def available(self):
        with common.database() as conn:
            return conn.execute("SELECT available FROM books WHERE sku='BOOK-001'").fetchone()[0]

    def test_replay_deducts_once(self):
        self.assertEqual(app.reserve('a', 'BOOK-001', 2)[0], 201)
        self.assertEqual(app.reserve('a', 'BOOK-001', 2)[0], 200)
        self.assertEqual(self.available(), 8)

    def test_conflicting_replay(self):
        app.reserve('a', 'BOOK-001', 2)
        with self.assertRaises(common.Problem) as ctx:
            app.reserve('a', 'BOOK-001', 3)
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(self.available(), 8)

    def test_rejection_is_durable(self):
        for _ in range(2):
            status, result = app.reserve('a', 'BOOK-001', 11)
            self.assertEqual((status, result['status']), (409, 'REJECTED'))
        self.assertEqual(self.available(), 10)

    def test_concurrency_cannot_oversell(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda i: app.reserve(str(i), 'BOOK-001', 1), range(30)))
        self.assertEqual(sum(status == 201 for status, _ in results), 10)
        self.assertEqual(self.available(), 0)

    def test_unknown_sku(self):
        with self.assertRaises(common.Problem) as ctx:
            app.reserve('a', 'MISSING', 1)
        self.assertEqual(ctx.exception.status, 404)

    def test_restart_does_not_reseed_stock(self):
        app.reserve('a', 'BOOK-001', 4)
        common.initialize(app.SCHEMA)
        self.assertEqual(self.available(), 6)

    def test_quantity_validation(self):
        for invalid in [True, 0, -1, 1.5, '1', None, 1001]:
            with self.subTest(value=invalid), self.assertRaises(common.Problem):
                common.quantity(invalid)


if __name__ == '__main__':
    unittest.main()
