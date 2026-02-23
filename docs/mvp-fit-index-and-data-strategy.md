# CareerOps MVP: Fit Index and Data Strategy

## Objective
Build a defensible MVP that is different from generic AI resume tools without requiring expensive CV -> outcome paired data.

This plan avoids claiming "probability of getting hired" until real outcome labels exist.

## Product Positioning (MVP)
- Output `fit_index` (0-100), not hiring probability.
- Output concrete, evidence-backed change suggestions:
  - matched requirements
  - missing requirements
  - resume lines to improve
  - expected score delta after edits
- Output ATS-risk diagnostics as a separate score and breakdown.

## Scoring Model (V1, no supervised labels)
Use a transparent weighted score:

`fit_index = 100 * (0.55 * semantic_score + 0.35 * keyword_coverage + 0.10 * (1 - ats_risk_score))`

Constraints:
- `semantic_score` in [0,1]
- `keyword_coverage` in [0,1]
- `ats_risk_score` in [0,1] where higher means more risk

### Component definitions
- `semantic_score`: cosine similarity between resume chunks and job requirement chunks, aggregated with top-k mean.
- `keyword_coverage`: fraction of required skills/keywords present in resume (exact + normalized match).
- `ats_risk_score`: heuristic risk from formatting and structure checks (missing sections, low keyword density, unreadable layout patterns).

## Differentiation Features (MVP)
1. Requirement-level grounding
- Every recommendation links to a specific job requirement and resume evidence.

2. Change impact simulation
- Recompute score after proposed edits and show predicted delta for each change.

3. Evidence trace
- Store why a suggestion was produced (`explanation_json` with source chunks and rule IDs).

## Data Strategy Without Paired Outcomes
### Phase A: Weak labels (now)
Build training examples from public resume/job corpora and synthetic pairs:
- Positive pairs: resume with similar role/title/skills to job.
- Hard negatives: same seniority but different skill family.
- Weak label: `fit_label_weak` from deterministic scoring thresholds.

Use this for ranking/consistency tuning only, not hiring probability.

### Phase B: Real labels (later, low-friction)
Collect self-reported outcomes in-app:
- `saved` -> `applied` -> `interview` -> `offer`/`reject`
- Store timestamps and confidence flags.

Once enough labels exist, train an outcome model and calibrate probabilities.

## Schema Changes (minimal, high impact)
Apply these in SQL migration form.

```sql
ALTER TABLE matches
  ADD COLUMN IF NOT EXISTS fit_index DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS score_version TEXT DEFAULT 'v1',
  ADD COLUMN IF NOT EXISTS match_features_json JSONB DEFAULT '{}'::jsonb;

ALTER TABLE applications
  ADD COLUMN IF NOT EXISTS outcome_label TEXT,               -- interview/offer/reject (normalized view)
  ADD COLUMN IF NOT EXISTS outcome_recorded_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS outcome_source TEXT DEFAULT 'user_reported';

CREATE TABLE IF NOT EXISTS training_examples (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
  job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  source TEXT NOT NULL,                                      -- weak_label, user_reported, partner
  task TEXT NOT NULL,                                        -- fit_ranking, interview_probability
  label_value DOUBLE PRECISION NOT NULL,                     -- 0..1
  label_meta_json JSONB DEFAULT '{}'::jsonb,
  features_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_examples_task_source
  ON training_examples(task, source);
```

## API/Service Implementation Targets
1. `POST /api/v1/matches/compute`
- Implement deterministic scoring.
- Persist `fit_index`, component scores, `match_features_json`, `score_version`.

2. `GET /api/v1/matches`
- Return component scores + recommendation/explanation payload.

3. `PUT /api/v1/applications/{id}`
- Normalize transitions and set `outcome_label` + `outcome_recorded_at` on terminal states.

## Data Contracts for Training Pipeline
Training row fields (feature store or exported parquet):
- IDs: `resume_id`, `job_id`, `user_id` (nullable for anonymous/public)
- Versioning: `score_version`, `feature_version`
- Numeric features:
  - `semantic_score`
  - `keyword_coverage`
  - `ats_risk_score`
  - `required_skill_count`
  - `matched_skill_count`
  - `experience_gap_years`
- Labels:
  - `fit_label_weak` (phase A)
  - `interview_label`, `offer_label` (phase B)

## Guardrails
- Do not show "hiring probability" until at least one calibrated model exists with monitored drift and error.
- UI wording for MVP:
  - "Fit Index"
  - "ATS Risk"
  - "Top changes to improve fit"

## Success Metrics (first 30 days after release)
- Median user session includes at least 1 resume-job score.
- At least 40% of scored sessions apply at least one recommended change.
- Mean fit index uplift after edits >= 8 points.
- Outcome capture rate (users reporting interview/offer/reject) >= 15% of applications.

## Execution Order (2-4 weeks)
1. Add schema columns and `training_examples` table.
2. Implement deterministic scoring in match compute endpoint.
3. Add recommendation payload and change-impact simulation.
4. Add outcome capture and export job for training rows.
5. Train weak-label ranking model and compare against deterministic baseline.
