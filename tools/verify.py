"""Run isolated unit suites and real two-process HTTP integration tests.

Temporary databases and ephemeral ports prevent changes to a running demo.
Raw evidence is written only after all assertions pass.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    logs = []
    for service in ['inventory-service', 'order-service']:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                cwd=ROOT / service, capture_output=True, text=True)
        logs.append(f'{service}\n{result.stdout}{result.stderr}')
        print(logs[-1], flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    records = []
    processes = []
    with tempfile.TemporaryDirectory() as temp:
        inventory_port, order_port = free_port(), free_port()
        while inventory_port == order_port:
            order_port = free_port()
        inv = f'http://127.0.0.1:{inventory_port}'
        orders = f'http://127.0.0.1:{order_port}'
        token = 'isolated-integration-test-token'

        def start(service, port):
            env = dict(os.environ, HOST='127.0.0.1', PORT=str(port),
                       DB_PATH=str(Path(temp) / f'{service}.db'),
                       SERVICE_TOKEN=token, INVENTORY_URL=inv)
            proc = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT / service, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processes.append(proc)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f'{service} exited early')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health/ready', timeout=.3):
                        return proc
                except (URLError, TimeoutError):
                    time.sleep(.1)
            raise RuntimeError(f'{service} failed to become ready')

        def call(label, base, path, data=None, headers=None, record=True):
            request = Request(base + path, data=None if data is None else json.dumps(data).encode(),
                              headers={'Content-Type': 'application/json', **(headers or {})})
            try:
                with urlopen(request, timeout=12) as response:
                    status, body = response.status, json.load(response)
            except HTTPError as error:
                status, body = error.code, json.load(error)
            if record:
                records.append(dict(label=label, method=request.get_method(), url=request.full_url,
                                    request=data, status=status, response=body))
            return status, body

        try:
            inventory_proc = start('inventory-service', inventory_port)
            start('order-service', order_port)
            assert call('Initial inventory', inv, '/books')[1][0]['available'] == 10
            payload = dict(customer='Vattikunta Vishnu Priya', sku='BOOK-001', quantity=2)
            headers = {'Idempotency-Key': 'demo-order-001'}
            status, first = call('Create order', orders, '/orders', payload, headers)
            assert status == 201 and first['status'] == 'CONFIRMED'
            assert call('Read order', orders, '/orders/' + first['id'])[1]['id'] == first['id']
            status, replay = call('Safe retry', orders, '/orders', payload, headers)
            assert status == 200 and replay == first
            assert call('Stock deducted once', inv, '/books/BOOK-001')[1]['available'] == 8
            assert call('Key conflict', orders, '/orders', {**payload, 'quantity': 3}, headers)[0] == 409
            status, rejected = call('Insufficient stock', orders, '/orders', {**payload, 'quantity': 100},
                                    {'Idempotency-Key': 'demo-reject'})
            assert status == 201 and rejected['status'] == 'REJECTED'
            assert call('Invalid quantity', orders, '/orders', {**payload, 'quantity': True},
                        {'Idempotency-Key': 'bad'})[0] == 400
            assert call('Missing idempotency key', orders, '/orders', payload)[0] == 400
            assert call('Unauthorized reservation', inv, '/reservations',
                        dict(order_id='intruder', sku='BOOK-001', quantity=1))[0] == 401
            req = Request(orders + '/orders', data=b'{broken',
                          headers={'Content-Type': 'application/json', 'Idempotency-Key': 'malformed'})
            try:
                urlopen(req, timeout=5)
                raise AssertionError('Malformed JSON unexpectedly accepted')
            except HTTPError as error:
                assert error.code == 400
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(lambda i: call('concurrent', orders, '/orders',
                    {**payload, 'quantity': 1}, {'Idempotency-Key': f'concurrent-{i}'}, False), range(20)))
            confirmed = sum(body.get('status') == 'CONFIRMED' for _, body in results)
            assert confirmed == 8, results
            assert call('Concurrency: zero stock, no overselling', inv, '/books/BOOK-001')[1]['available'] == 0
            records.append(dict(label='Concurrency summary', requests=20, confirmed=confirmed, rejected=12))
            inventory_proc.terminate()
            inventory_proc.wait(timeout=10)
            retry_payload = dict(customer='Vattikunta Vishnu Priya', sku='BOOK-002', quantity=1)
            retry_headers = {'Idempotency-Key': 'outage-recovery'}
            assert call('Dependency outage', orders, '/orders', retry_payload, retry_headers)[0] == 503
            pending = call('Pending order remains durable', orders, '/orders')[1]
            pending = next(order for order in pending if order['idempotency_key'] == 'outage-recovery')
            assert pending['status'] == 'PENDING'
            start('inventory-service', inventory_port)
            status, recovered = call('Recovery with same key', orders, '/orders', retry_payload, retry_headers)
            assert status == 201 and recovered['status'] == 'CONFIRMED' and recovered['id'] == pending['id']
            assert call('Stock persists after restart', inv, '/books/BOOK-001')[1]['available'] == 0
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=10)
    (evidence / 'api-results.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    (evidence / 'test-results.txt').write_text('\n'.join(logs) + '\nHTTP integration: PASS\n'
        'Verified: confirmation, queries, replay, conflict, rejection, validation, malformed JSON, '
        'authorization, 20 competing orders, outage, recovery, database persistence.\n', encoding='utf-8')
    print('All unit suites and HTTP integration checks passed. Evidence saved.')


if __name__ == '__main__':
    main()
