-- 003_jobs_progress: explicit counters for the admin progress bar.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS total INT NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS done INT NOT NULL DEFAULT 0;
