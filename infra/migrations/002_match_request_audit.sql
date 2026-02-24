BEGIN;

CREATE TABLE IF NOT EXISTS match_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
  job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  job_url TEXT NOT NULL,
  resume_filename TEXT,
  resume_text_used TEXT NOT NULL,
  suggested_changes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  suggested_resume_text TEXT,
  fit_index DOUBLE PRECISION,
  semantic_score DOUBLE PRECISION,
  keyword_coverage DOUBLE PRECISION,
  ats_risk_score DOUBLE PRECISION,
  ml_fit_probability DOUBLE PRECISION,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_match_requests_requested_at ON match_requests(requested_at);
CREATE INDEX IF NOT EXISTS idx_match_requests_job_url ON match_requests(job_url);

COMMIT;
