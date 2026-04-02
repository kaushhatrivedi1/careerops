# CareerOps

CareerOps is a resume–job fit scoring platform. Upload your resume and a job URL — get an explainable fit score, ATS risk analysis, missing skill recommendations, and an in-browser editor to update your resume before downloading.

## Features

- **Fit scoring** — ESCO taxonomy skill extraction (13k+ skills via spaCy PhraseMatcher) + semantic similarity (sentence-transformers `all-MiniLM-L6-v2`) + ATS risk
- **Explainable results** — matched vs missing skills, score breakdown, improvement recommendations
- **Resume editor** — split view: original PDF on the left, editable extracted text on the right; click missing skill chips to insert at cursor
- **Download options** — original file unchanged, or edited content as a new PDF
- **Scoring history** — all past requests stored per user with scores, suggestions, and timestamps
- **Auth** — email/password + Google Sign-In, JWT bearer tokens

## Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML/JS, pdf-lib (client-side PDF generation) |
| Backend | FastAPI (Python), SQLAlchemy async |
| Database | PostgreSQL 16 + pgvector (port 5433) |
| NLP | spaCy `en_core_web_sm`, ESCO skills taxonomy |
| ML | sentence-transformers `all-MiniLM-L6-v2` |
| Infra | Docker Compose (Postgres, Redis, MinIO, Metabase, Adminer) |

## Project Structure

```
backend/
  app/
    routers/        # auth, matches, resumes, jobs, applications, users
    services/       # scoring.py, skills.py (ESCO), ingestion.py, ml_fit.py
    models/         # SQLAlchemy ORM models
    core/           # config, security (JWT)
    db/             # session, init_db

frontend/
  index.html        # scoring UI + resume editor
  history.html      # scoring history

infra/
  docker-compose.yml
  migrations/       # 001–004 SQL migrations
  schema.sql
```

## Getting Started

### 1. Start infrastructure

```bash
cd infra
docker compose up -d
```

Services:
- PostgreSQL → `localhost:5433`
- Redis → `localhost:6379`
- MinIO → `localhost:9000` (console: `localhost:9001`)
- Metabase → `localhost:3000`
- Adminer → `localhost:8080`

### 2. Set up the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env` and set your values (DB credentials, JWT secret, optional Google client ID).

### 3. Run migrations

```bash
# from repo root
psql -h localhost -p 5433 -U careerops -d careerops -f infra/schema.sql
psql -h localhost -p 5433 -U careerops -d careerops -f infra/migrations/001_fit_index_training_schema.sql
psql -h localhost -p 5433 -U careerops -d careerops -f infra/migrations/002_match_request_audit.sql
psql -h localhost -p 5433 -U careerops -d careerops -f infra/migrations/003_google_auth_users.sql
psql -h localhost -p 5433 -U careerops -d careerops -f infra/migrations/004_applications_tracking.sql
```

### 4. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 5. Open the frontend

Open `frontend/index.html` directly in your browser (no build step needed).

## Scoring Formula

```
fit_index = 100 × (0.60 × skill_coverage + 0.30 × semantic_score + 0.10 × (1 − ats_risk))
```

- **skill_coverage** — fraction of JD skills found in the resume (ESCO taxonomy)
- **semantic_score** — cosine similarity of resume and JD embeddings (0–1)
- **ats_risk** — penalty for short resume, low skill match, or missing contact signals (0–1)

## Roadmap

- **Auto-apply** — one-click job application using saved resume + cover letter, with per-platform adapters (LinkedIn, Greenhouse, Lever, Workday)
- **Application tracker** — status board (applied → interview → offer/reject) with timeline and notes
- **Resume variants** — A/B test multiple resume versions against the same job, compare fit scores
- **Market intelligence** — skill demand trends, salary ranges, coverage gaps across saved jobs
- **Outcome learning** — feed interview/offer outcomes back as labels to improve fit prediction over time

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_HOST` | `localhost` | Postgres host |
| `DATABASE_PORT` | `5433` | Postgres port |
| `DATABASE_NAME` | `careerops` | DB name |
| `DATABASE_USER` | `careerops` | DB user |
| `DATABASE_PASSWORD` | `careerops_password` | DB password |
| `JWT_SECRET_KEY` | — | **Change in production** |
| `GOOGLE_CLIENT_ID` | — | Optional, enables Google Sign-In |
| `SECRET_KEY` | — | App secret, **change in production** |
