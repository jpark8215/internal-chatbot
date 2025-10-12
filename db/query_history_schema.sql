
-- Query history table for tracking user interactions
CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255),
    user_ip VARCHAR(45),
    user_agent TEXT,
    query_text TEXT NOT NULL,
    response_text TEXT,
    sources_used JSONB,
    search_type VARCHAR(50), -- 'semantic', 'keyword', 'hybrid', 'combined'
    response_time_ms INTEGER,
    tokens_used INTEGER,
    model_used VARCHAR(100),
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_history_session_id ON query_history (session_id);
CREATE INDEX IF NOT EXISTS idx_query_history_success ON query_history (success);
CREATE INDEX IF NOT EXISTS idx_query_history_search_type ON query_history (search_type);

-- Query analytics view for common queries
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

-- Daily usage statistics view
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
