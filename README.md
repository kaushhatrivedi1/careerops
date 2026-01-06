# CareerOps-AI

CareerOps is an open-source, outcome-driven AI career intelligence platform that provides:
- Explainable resume ↔ job matching (semantic + keyword)
- ATS risk simulation with failure reasons
- Outcome learning (interview/offer prediction) as labels accumulate
- A/B testing for resume variants
- Market intelligence analytics (skills trends, coverage, ROI)

## Repository Structure
- `frontend/` – Next.js (React) web app
- `backend/` – FastAPI gateway + REST APIs
- `workers/` – Celery workers for async pipelines (parsing, embedding, scoring)
- `models/` – ML training/inference code, notebooks/scripts
- `infra/` – Docker Compose, env templates, deployment manifests
- `docs/` – Architecture, proposal, ADRs, notes

## Tech Stack (Open Source)
- Frontend: Next.js + TypeScript + Tailwind
- Backend: FastAPI (Python)
- Async: Celery + Redis
- DB: PostgreSQL + pgvector
- Storage: MinIO
- Analytics: Metabase
- Observability: Prometheus + Grafana (later)
- MLOps: MLflow (later)

## Getting Started (placeholder)
1. `cd infra`
2. `docker compose up -d`
