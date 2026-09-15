-- 002_fts: full-text + vector indexes for hybrid retrieval.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS text_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(text,''))) STORED;
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING GIN (text_tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_trgm ON chunks USING GIN (text gin_trgm_ops);
-- HNSW needs data to be useful; safe to create upfront on pgvector>=0.5
-- CREATE INDEX IF NOT EXISTS idx_chunks_vec ON chunks USING hnsw (embedding vector_cosine_ops);
