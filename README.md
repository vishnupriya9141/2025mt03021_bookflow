# 2025m203021 — BookFlow

**Vattikunta Vishnu Priya · individual submission · SEZG583 Scalable Services**

Book ordering and stock reservation with two independently runnable Python microservices.
Prepared for the assignment due **12 November 2026**. The document filename supplied by the
course uses CCZG583; the report follows SEZG583, the course code inside that document.

## Start here

1. Read `2025m203021_BookFlow_Report.docx` or `2025m203021_BookFlow_Report.md`.
2. Install Python 3.13. Run `python tools/verify.py` to reproduce the tests and evidence.
3. In PowerShell, run `./tools/run-local.ps1`. Keep this terminal running.
4. In a second terminal in this folder, run `python tools/demo.py`.
5. Import `postman/2025m203021_BookFlow.postman_collection.json`; run requests in numbered order.
6. Complete `2025m203021_FINAL_CHECKLIST.md` before submitting the ZIP.

All commands in this package assume this folder is the working directory. If PowerShell
blocks a script, inspect it and run the commands manually or use an execution policy
permitted by your institution. Do not change a machine-wide policy for this assignment.

## Docker

Prerequisite: Docker Desktop running with Linux containers and Compose v2.

```powershell
$env:SERVICE_TOKEN = [guid]::NewGuid().ToString('N')
docker compose up --build -d
docker compose ps
python tools/demo.py
docker compose logs --tail 50
docker compose down
```

Named volumes preserve data after `down`. Stock is finite: repeated demonstrations can
exhaust it. Use an isolated test run for a fresh database. Remove named volumes only
when deliberately discarding demo data. Do not run local Python services at the same
time as containers using the same host ports.

## Minikube

Install Docker Desktop, kubectl and Minikube; enable your virtualization support.
Stop local Python services and Docker Compose before using ports 8001/8002 below.

```powershell
./tools/deploy-minikube.ps1
```

The script creates a separate `bookflow` Minikube profile and namespace, builds both
images inside Minikube, creates a random service Secret if none exists, applies PVCs,
ClusterIP Services and Deployments, and waits for both Deployments to become available.
It does not deploy to an unrelated current kubectl context.

Keep each forwarding command running in its own terminal:

```powershell
kubectl --context bookflow -n bookflow port-forward service/inventory 8001:8000
```

```powershell
kubectl --context bookflow -n bookflow port-forward service/orders 8002:8000
```

Run the demo or Postman against the same localhost URLs, then open the dashboard:

```powershell
minikube -p bookflow dashboard
kubectl --context bookflow -n bookflow get deployments,pods,services,pvc
kubectl --context bookflow -n bookflow describe deployment orders
kubectl --context bookflow -n bookflow logs deployment/orders --tail=50
kubectl --context bookflow -n bookflow get events --sort-by=.metadata.creationTimestamp
```

Select namespace **bookflow** in Dashboard. Capture both Deployments with 1/1 available,
both Pods Ready, both Services, bound PVCs, and deployment details. If a PVC is Pending,
check the default StorageClass and Minikube storage-provisioner/default-storageclass
addons. If images cannot be found, check the active profile and image tags. If startup
fails, inspect logs/events; both services must reference the same Secret token.

To demonstrate recovery, record an order and its stock level, then:

```powershell
kubectl --context bookflow -n bookflow rollout restart deployment/inventory
kubectl --context bookflow -n bookflow rollout status deployment/inventory --timeout=180s
```

Restart the Inventory port-forward after Pod replacement, query the same stock,
and replay the same Order POST with the same Idempotency-Key. Stock must not decrease
twice. `tools/demo.py` creates a NEW key each run, so use Postman request 04 to replay
an existing order. Stop the cluster after recording with `minikube -p bookflow stop`.
Changing images with the same tag requires rebuilding and restarting the Deployments.

## Independent service repositories

`inventory-service/` and `order-service/` are separate code roots. Each contains its own
runtime files, tests, Dockerfile, CI workflow and README, with no sibling imports.
When repository bundles are supplied, restore them with:

```powershell
git clone repository-bundles/2025m203021_inventory-service.bundle inventory-repo
git clone repository-bundles/2025m203021_order-service.bundle orders-repo
```

Create two empty GitHub repositories in your account. From each restored repository:

```powershell
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

Replace those values with the real destinations. Add both real URLs to the report.
GitHub publication has not been performed from this environment. Local CI definitions
run tests and build images on push; there is no automated deployment pipeline.

## Evidence and limitations

`evidence/api-results.json` contains actual calls to fresh local service processes.
`evidence/test-results.txt` contains actual test output. PNG response panels are
renderings of those captured responses, not Postman or Kubernetes screenshots.
Docker builds, Minikube, dashboard screenshots, GitHub uploads and a deployment
screen recording still require execution on a configured machine.

The teaching runtime uses ThreadingHTTPServer and a separate SQLite file per service.
The Minikube demo intentionally runs one replica per service with a Recreate strategy.
Do not increase replicas on a shared SQLite file or claim this configuration is
horizontally scalable. The report describes the production design with external
PostgreSQL databases, multiple API replicas and autoscaling. Local databases alone
do not establish high availability. There is no payment processing, customer login,
automatic pending-order reconciliation, cancellation, delivery or public ingress.

## Regenerate the document and ZIP

```powershell
python -m pip install -r tools/requirements-docs.txt
python tools/build_submission.py
```

Edit the Markdown report to add actual URLs, dashboard observations and video details
before regenerating. Rebuilding refreshes generated diagrams and API panels; it does
not manufacture missing deployment evidence. Your edits to an existing Markdown
report are retained. Source/tests run without the document-generation packages.
