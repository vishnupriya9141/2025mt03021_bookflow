# 2025m203021 — Final submission checklist

Student: Vattikunta Vishnu Priya. Group: individual. Deadline: 12 November 2026.

Prepared:

- [x] Application description, business capability mapping, commands and queries.
- [x] Implemented topology diagram and proposed scalable production diagram.
- [x] Two self-contained service code roots, Dockerfiles and independent CI definitions.
- [x] Tests and actual local HTTP response evidence.
- [x] Docker Compose, Kubernetes manifests and Minikube deployment script.
- [x] Postman collection, execution instructions and recording script.
- [x] Student-named report and ZIP generation.

Required before claiming a complete submission:

- [ ] Review and understand the code; adapt/disclose assistance according to course policy.
- [ ] Build and run both Docker containers on a configured machine; capture screenshots.
- [ ] Execute the Minikube script and verify Ready Pods and bound PVCs.
- [ ] Access Dashboard, capture real screenshots and write actual observations in the report.
- [ ] Capture real Postman screenshots, not only the rendered local response panels.
- [ ] Publish two separate GitHub repositories and insert both actual URLs in the report.
- [ ] Record and add `2025m203021_BookFlow_Demo.mp4`, or document the approved upload link.
- [ ] Add image references for new screenshots to the Markdown report; regenerate DOCX/ZIP.
- [ ] Inspect `2025m203021_BookFlow.zip` and submit that single ZIP through the LMS.

Run `python tools/build_submission.py` after completing the pending items. The script
preserves edits to the existing Markdown report. Include the resulting DOCX, source,
evidence, and video/link within the ZIP. Local execution cannot substitute for the
required Kubernetes deployment and its evidence.
