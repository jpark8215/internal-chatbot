CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  embedding vector(768),
  source_file TEXT,
  file_type TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_source_file ON documents (source_file);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);

-- Additional composite indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_documents_source_embedding ON documents (source_file, embedding);
CREATE INDEX IF NOT EXISTS idx_documents_content_gin ON documents USING gin(to_tsvector('english', content));

-- Index for file type filtering
CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents (file_type);

-- Composite index for time-based queries with source
CREATE INDEX IF NOT EXISTS idx_documents_source_created ON documents (source_file, created_at DESC);
