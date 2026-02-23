# ML Training Quickstart (Fit Probability)

## What this adds
- A supervised classifier trained from `training_examples`.
- Runtime inference in `POST /api/v1/matches/compute` via `ml_fit_probability`.
- Deterministic fallback remains active when no model artifact exists.

## Prerequisites
- Run migration:
  - `/Users/kaushha/Documents/careerops-1/infra/migrations/001_fit_index_training_schema.sql`
- Populate `training_examples` with:
  - `task='fit_ranking'`
  - `source='weak_label'` (or another source)
  - `features_json` containing:
    - `semantic_score`
    - `keyword_coverage`
    - `ats_risk_score`
  - `label_value` in [0,1]

## Train model
From `/Users/kaushha/Documents/careerops-1/backend`:

```bash
python ../models/train_fit_model.py \
  --db-url "postgresql://careerops:careerops_password@localhost:5433/careerops" \
  --task fit_ranking \
  --source weak_label \
  --output ../models/artifacts/fit_model.pkl
```

## Inference path
- API checks `FIT_MODEL_PATH` from `/Users/kaushha/Documents/careerops-1/backend/app/core/config.py`.
- Default value: `models/artifacts/fit_model.pkl`.
- In response:
  - `ml_fit_probability` is set when model loads successfully.
  - `ml_model_info` explains load or failure reason.

## Important constraints
- Do not call this probability "chance of getting hired" yet.
- Current labels are weak/synthetic unless you ingest real outcomes.
- Upgrade path:
  1. add real `applications` outcomes
  2. train calibrated model on outcome labels
  3. track drift and performance before production claims
