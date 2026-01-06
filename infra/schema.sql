cat << 'EOF' > infra/schema.sql
-- CareerOps initial schema (PostgreSQL + pgvector)
-- Target DB: careerops
-- User: careerops

BEGIN;

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- -----------------------------
-- Core: Users
-- -----------------------------
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Resumes
-- -----------------------------
CREATE TABLE IF NOT EXISTS resumes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  version_tag TEXT NOT NULL DEFAULT 'v1',
  file_url TEXT,                 -- MinIO/S3 path
  raw_text TEXT,                 -- extracted text
  parsed_json JSONB,             -- structured sections/fields
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);

-- -----------------------------
-- Jobs
-- -----------------------------
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT,                   -- e.g., "manual", "kaggle", "indeed"
  company TEXT,
  title TEXT,
  location TEXT,
  jd_text TEXT NOT NULL,
  jd_parsed_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);

-- -----------------------------
-- Applications (labels for outcome learning)
-- -----------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'application_status') THEN
    CREATE TYPE application_status AS ENUM ('saved', 'applied', 'interview', 'offer', 'reject');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS applications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
  status application_status NOT NULL DEFAULT 'saved',
  applied_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);

-- -----------------------------
-- Documents & Chunks (for retrieval / explainability)
-- -----------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_owner_type') THEN
    CREATE TYPE document_owner_type AS ENUM ('resume', 'job', 'evidence');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type document_owner_type NOT NULL,
  owner_id UUID NOT NULL,         -- references resumes/jobs/evidence_sources (soft)
  title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_type, owner_id);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'section_type') THEN
    CREATE TYPE section_type AS ENUM ('summary', 'experience', 'education', 'skills', 'projects', 'certifications', 'other');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  section section_type NOT NULL DEFAULT 'other',
  chunk_text TEXT NOT NULL,
  token_count INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

-- -----------------------------
-- Embeddings (pgvector)
-- Store one embedding per chunk per model
-- -----------------------------
CREATE TABLE IF NOT EXISTS embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,                 -- e.g., "all-MiniLM-L6-v2"
  embedding vector(384) NOT NULL,           -- change dim if you use a different model
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(chunk_id, model_name)
);

-- Vector index (IVFFLAT) - requires enough rows for good performance; fine for MVP.
-- You can switch to HNSW later depending on pgvector version/support.
CREATE INDEX IF NOT EXISTS idx_embeddings_model_name ON embeddings(model_name);
CREATE INDEX IF NOT EXISTS idx_embeddings_vector_ivfflat
  ON embeddings USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- -----------------------------
-- Matching results (core outputs)
-- -----------------------------
CREATE TABLE IF NOT EXISTS matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

  -- Scores
  semantic_score DOUBLE PRECISION,          -- embedding similarity
  keyword_coverage DOUBLE PRECISION,        -- 0..1
  ats_risk_score DOUBLE PRECISION,          -- 0..1 risk
  overall_score DOUBLE PRECISION,           -- blended score

  -- Explanations (missing skills, reasons, top chunks)
  explanation_json JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, resume_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches(user_id);
CREATE INDEX IF NOT EXISTS idx_matches_resume_job ON matches(resume_id, job_id);

-- -----------------------------
-- Evidence sources (for grounding claims)
-- -----------------------------
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'evidence_type') THEN
    CREATE TYPE evidence_type AS ENUM ('github', 'document', 'link', 'manual');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS evidence_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type evidence_type NOT NULL,
  url TEXT,
  file_url TEXT,                 -- if uploaded
  raw_text TEXT,
  metadata_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_user_id ON evidence_sources(user_id);

-- Claims extracted/used in resumes (optional early, useful later)
CREATE TABLE IF NOT EXISTS claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
  claim_text TEXT NOT NULL,
  evidence_source_id UUID REFERENCES evidence_sources(id) ON DELETE SET NULL,
  evidence_span_json JSONB,       -- offsets, quote, etc.
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Events (audit log + analytics)
-- -----------------------------
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,               -- e.g., RESUME_UPLOADED, MATCH_COMPUTED
  payload_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, created_at);

COMMIT;
