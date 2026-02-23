BEGIN;

ALTER TABLE matches
  ADD COLUMN IF NOT EXISTS fit_index DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS score_version TEXT DEFAULT 'v1',
  ADD COLUMN IF NOT EXISTS match_features_json JSONB DEFAULT '{}'::jsonb;

ALTER TABLE applications
  ADD COLUMN IF NOT EXISTS outcome_label TEXT,
  ADD COLUMN IF NOT EXISTS outcome_recorded_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS outcome_source TEXT DEFAULT 'user_reported';

CREATE TABLE IF NOT EXISTS training_examples (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
  job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  source TEXT NOT NULL,
  task TEXT NOT NULL,
  label_value DOUBLE PRECISION NOT NULL,
  label_meta_json JSONB DEFAULT '{}'::jsonb,
  features_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_examples_task_source
  ON training_examples(task, source);

COMMIT;
