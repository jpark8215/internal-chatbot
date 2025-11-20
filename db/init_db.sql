-- Simple Database Initialization
-- Contains only the essential tables actually used by the application

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Document sources metadata
CREATE TABLE IF NOT EXISTS document_sources (
    id SERIAL PRIMARY KEY,
    source_path TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Essential indexes for document_sources table
CREATE INDEX IF NOT EXISTS idx_document_sources_path ON document_sources (source_path);

-- Core documents table for vector storage
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(768),
    source_file TEXT,
    file_type TEXT,
    chunk_index INTEGER,
    start_position INTEGER,
    end_position INTEGER,
    page_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    document_source_id INTEGER REFERENCES document_sources(id)
);

-- Essential indexes for documents table
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_source_file ON documents (source_file);
CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents (document_source_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);
CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents (file_type);

-- Query history table for tracking user interactions
CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255),
    user_ip VARCHAR(45),
    user_agent TEXT,
    query_text TEXT NOT NULL,
    response_text TEXT,
    sources_used JSONB,
    search_type VARCHAR(50),
    response_time_ms INTEGER,
    tokens_used INTEGER,
    model_used VARCHAR(100),
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Essential indexes for query_history
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_history_session_id ON query_history (session_id);
CREATE INDEX IF NOT EXISTS idx_query_history_success ON query_history (success);

-- User feedback table for collecting feedback
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    response_text TEXT,
    sources_used JSONB,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    is_accurate BOOLEAN,
    is_helpful BOOLEAN,
    missing_info TEXT,
    incorrect_info TEXT,
    comments TEXT,
    user_session VARCHAR(255),
    search_strategy VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Essential indexes for user_feedback
CREATE INDEX IF NOT EXISTS idx_user_feedback_created_at ON user_feedback (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_feedback_rating ON user_feedback (rating);
CREATE INDEX IF NOT EXISTS idx_user_feedback_user_session ON user_feedback (user_session);

-- Improvement actions table (used by app.py)
CREATE TABLE IF NOT EXISTS improvement_actions (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER REFERENCES user_feedback(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    implemented_at TIMESTAMP,
    impact_metrics JSONB,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Essential indexes for improvement_actions
CREATE INDEX IF NOT EXISTS idx_improvement_actions_feedback_id ON improvement_actions (feedback_id);
CREATE INDEX IF NOT EXISTS idx_improvement_actions_type ON improvement_actions (action_type);
CREATE INDEX IF NOT EXISTS idx_improvement_actions_created_at ON improvement_actions (created_at DESC);

-- Simple analytics views for basic reporting
CREATE OR REPLACE VIEW feedback_summary AS
SELECT 
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as total_feedback,
    AVG(rating) as avg_rating,
    COUNT(CASE WHEN is_accurate = true THEN 1 END) as accurate_count,
    COUNT(CASE WHEN is_helpful = true THEN 1 END) as helpful_count
FROM user_feedback
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;

CREATE OR REPLACE VIEW query_analytics AS
SELECT 
    query_text,
    COUNT(*) as query_count,
    AVG(response_time_ms) as avg_response_time,
    COUNT(CASE WHEN success THEN 1 END) as success_count,
    COUNT(CASE WHEN NOT success THEN 1 END) as error_count,
    MAX(created_at) as last_asked,
    MIN(created_at) as first_asked
FROM query_history 
GROUP BY query_text
ORDER BY query_count DESC;

CREATE OR REPLACE VIEW daily_usage_stats AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_queries,
    COUNT(DISTINCT session_id) as unique_sessions,
    AVG(response_time_ms) as avg_response_time,
    COUNT(CASE WHEN success THEN 1 END) as successful_queries,
    COUNT(CASE WHEN NOT success THEN 1 END) as failed_queries
FROM query_history 
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Comments for documentation
COMMENT ON TABLE documents IS 'Core document storage with vector embeddings for semantic search';
COMMENT ON TABLE query_history IS 'Log of all user queries and system responses for analytics';
COMMENT ON TABLE user_feedback IS 'User feedback and ratings on system responses';
COMMENT ON TABLE improvement_actions IS 'Actions taken to improve the system based on feedback';
