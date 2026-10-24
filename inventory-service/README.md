# BookFlow inventory-service

Student: 2025m203021 — Vattikunta Vishnu Priya (individual), SEZG583.

Owns books and reservations. POST /reservations requires X-Service-Token. Concurrent stock checks and deductions are atomic; replay by order_id does not deduct twice.

## Run independently

Python 3.13; standard library only. No pip installation is needed.

```powershell
$env:SERVICE_TOKEN = 'replace-with-the-same-random-token-on-both-services'
$env:PORT = '8001'
$env:HOST = '127.0.0.1'
$env:DB_PATH = 'data/service.db'
python app.py
```

Routes: GET /books; GET /books/{sku}; POST /reservations. Both services expose GET /health/live and /health/ready.

```powershell
python -m unittest discover -s tests -v
docker build -t bookflow-inventory:1.0 .
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
