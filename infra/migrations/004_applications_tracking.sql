BEGIN;

-- Extend applications table with fields needed for URL-only submissions,
-- outcome feedback, and stats.

ALTER TABLE applications
  ADD COLUMN IF NOT EXISTS job_url            TEXT,
  ADD COLUMN IF NOT EXISTS company            TEXT,
  ADD COLUMN IF NOT EXISTS role               TEXT,
  ADD COLUMN IF NOT EXISTS cv_snapshot_text   TEXT,
  ADD COLUMN IF NOT EXISTS fit_index          DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS outcome_reported_at TIMESTAMPTZ;

-- job_id is now optional (user may apply via URL without a stored job row)
ALTER TABLE applications
  ALTER COLUMN job_id DROP NOT NULL;

-- Index for stats queries
CREATE INDEX IF NOT EXISTS idx_applications_user_status ON applications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_applications_company     ON applications(user_id, company);

COMMIT;
