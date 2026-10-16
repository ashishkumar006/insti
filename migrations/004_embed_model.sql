-- 004_embed_model: tag every chunk with the model that produced its vector.
-- Vectors from different models live in incompatible spaces, so dense search
-- only considers chunks whose embed_model matches the current embedder.
-- Rows written before this migration are NULL (legacy) and remain searchable;
-- re-embed them (admin "Re-embed all") to tag them with the current model.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embed_model TEXT;
CREATE INDEX IF NOT EXISTS idx_chunks_embed_model ON chunks(embed_model);
