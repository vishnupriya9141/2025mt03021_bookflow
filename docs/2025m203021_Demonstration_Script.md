# 2025m203021 — BookFlow demonstration recording

Presenter: Vattikunta Vishnu Priya; individual submission.

This is a recording script. It is not a completed demonstration video.
Record your actual screen using an installed recorder (for example Windows Snipping
Tool recording or your institution's approved tool). Do not show tokens or credentials.
Save the real result as `2025m203021_BookFlow_Demo.mp4` in this folder and rebuild the ZIP.

1. **0:00–0:40 — Identity and architecture.** State name, student ID, course and BookFlow's
   use case. Show the implemented diagram. Explain that Order owns orders and Inventory
   owns stock; there is no shared database. Distinguish the proposed scalable design.
2. **0:40–1:20 — Independent repositories.** Show both real GitHub repository URLs and each
   service's source, tests, Dockerfile and CI definition. Explain independent releases.
3. **1:20–2:00 — Containers.** Show `docker compose up --build -d`, `docker compose ps`
   and healthy containers. Run the demo once, then stop Compose to free host ports.
4. **2:00–3:10 — Minikube deployment.** Show the Minikube deployment script executing,
   image build results, rollout readiness, Pods, Services and PVCs. If necessary, shorten
   idle build time in the recording and clearly label the edit. Do not substitute API
   process output for actual cluster deployment.
5. **3:10–4:10 — Dashboard.** Open `minikube -p bookflow dashboard`, select namespace
   bookflow, show two 1/1 Deployments, Ready Pods and bound PVCs. Explain probes,
   ClusterIP routing, resource requests and the one-replica SQLite constraint.
6. **4:10–5:30 — API calls.** With both port-forwards running, use the supplied Postman
   collection. Show book stock, confirmed order, GET order, same-key retry and stock
   deducted once. Show rejected order and invalid quantity responses. Explain HTTP
   201 with a REJECTED order represents a stored business rejection.
7. **5:30–6:30 — Restart and persistence.** Restart Inventory deployment, wait for rollout,
   restart its port-forward, then query stock and replay the existing order. Show no
   duplicate deduction and persisted order. Explain PENDING retry after an uncertain
   outcome and the need for a future reconciliation worker.
8. **6:30–7:00 — Validation.** Show the actual test-results.txt and explain the 20-request
   concurrency result. Describe external PostgreSQL and multiple API replicas as future
   production work. End with both repository links visible.

Capture these still images while recording and add them to `evidence/`:

- `2025m203021_postman_confirmed.png`
- `2025m203021_postman_replay_and_stock.png`
- `2025m203021_postman_rejected.png`
- `2025m203021_docker_containers.png`
- `2025m203021_kubernetes_deployments.png`
- `2025m203021_kubernetes_pods_pvc.png`
- `2025m203021_restart_persistence.png`

Add Markdown image references and your actual dashboard analysis to the report before
regenerating its DOCX. For a large video, follow the assignment's approved upload/link
process; do not assume that a public sharing link is required.
