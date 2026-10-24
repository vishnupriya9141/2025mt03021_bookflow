# BookFlow order-service

Student: 2025m203021 — Vattikunta Vishnu Priya (individual), SEZG583.

Owns orders and client idempotency keys. POST /orders requires Idempotency-Key. Calls Inventory with a two-second timeout; retry the same key after HTTP 503.

## Run independently

Python 3.13; standard library only. No pip installation is needed.

```powershell
$env:SERVICE_TOKEN = 'replace-with-the-same-random-token-on-both-services'
$env:PORT = '8002'
$env:HOST = '127.0.0.1'
$env:DB_PATH = 'data/service.db'
$env:INVENTORY_URL = 'http://127.0.0.1:8001'
python app.py
```

Routes: POST /orders; GET /orders/{id}; GET /orders (up to 100 rows). Both services expose GET /health/live and /health/ready.

```powershell
python -m unittest discover -s tests -v
docker build -t bookflow-orders:1.0 .
```

The Order unit suite mocks the HTTP dependency; it runs without a live Inventory
service. The Inventory suite uses isolated temporary SQLite databases.
Containers listen on port 8000, run as UID 10001, and store data at /data/service.db.
Pass SERVICE_TOKEN with -e and mount a dedicated /data volume when running the image.
Order additionally needs an INVENTORY_URL reachable on the container network.
No files or modules from a sibling repository are needed to build or test this service.

CI runs unit tests and a Docker build independently. No remote CI success or CD is
claimed. A single-process SQLite deployment is a teaching configuration; production
scaling requires an external database, hardened HTTP runtime, authorization and TLS.
Do not expose these assessment APIs to the public internet.
