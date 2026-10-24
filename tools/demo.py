"""Use live services on local, Docker or port-forwarded Kubernetes URLs."""
import json
import os
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

inventory = os.environ.get('DEMO_INVENTORY_URL', 'http://127.0.0.1:8001')
orders = os.environ.get('DEMO_ORDER_URL', 'http://127.0.0.1:8002')


def call(base, path, payload=None, key=None):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Idempotency-Key'] = key
    request = Request(base + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    print(f'\n{request.get_method()} {request.full_url}')
    if payload:
        print('Request:', json.dumps(payload))
    try:
        with urlopen(request, timeout=10) as response:
            status, body = response.status, json.load(response)
    except HTTPError as error:
        status, body = error.code, json.load(error)
    print('HTTP', status)
    print(json.dumps(body, indent=2))
    return body


if __name__ == '__main__':
    key = 'demo-' + str(uuid.uuid4())
    data = dict(customer='Vattikunta Vishnu Priya', sku='BOOK-001', quantity=1)
    call(inventory, '/books')
    order = call(orders, '/orders', data, key)
    if 'id' in order:
        call(orders, '/orders/' + order['id'])
    call(orders, '/orders', data, key)
    call(inventory, '/books/BOOK-001')
    call(orders, '/orders', {**data, 'quantity': 1000}, key + '-reject')
    call(orders, '/orders', {**data, 'quantity': 0}, key + '-invalid')
