# Bigger Picture Change Plan

This plan prioritizes changes that materially improve product reliability, data quality, and business readiness.

## Already implemented in this pass
- Google login endpoint: `POST /api/v1/auth/google`
- JWT issuance with provider metadata.
- User model fields for identity provider and login tracking.
- Migration for Google auth user fields.

## P0 (next 1-2 weeks)
- Replace all `temp-user-id` usage with authenticated user from token.
- Enforce authorization checks for all user-owned records (`resumes`, `applications`, `matches`, `history`).
- Add password hashing or disable local password login entirely if Google-only.
- Add DB-backed session/audit events for auth and critical actions.

## P1 (next 2-4 weeks)
- Persist scraped job URL content with dedupe and refresh policy.
- Add robust parser adapters for common ATS hosts (Greenhouse, Lever, Ashby).
- Add application-level idempotency key for scoring requests.
- Add rate limiting for auth and compute endpoints.

## P2 (next 1-2 months)
- Add model registry and scoring version traceability (`score_version` + artifact hash).
- Add data retention policies for resume text snapshots.
- Add explicit user consent tracking for model training usage.
- Add async ingestion pipeline and retries (Celery) for URL/file extraction.

## Architecture corrections that should happen soon
- Fix ORM/schema mismatches (types, foreign keys, enum handling) to avoid silent data drift.
- Move raw SQL inserts/selects to typed repository layer for maintainability.
- Introduce Alembic-based migration workflow as the default migration path.
- Add contract tests for auth, score compute, and history APIs.

## Product-level guardrails
- Keep output name as "Fit Index" until calibrated outcome labels are available.
- Do not claim hiring probability unless model is trained on real outcomes and monitored.
- Store recommendation rationale and evidence references for user trust.
