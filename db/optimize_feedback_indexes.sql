-- Feedback System Database Index Optimization
-- This script creates additional indexes for optimal query performance based on expected usage patterns

-- Performance analysis and optimization indexes

-- Indexes for admin dashboard queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_admin_dashboard 
ON user_feedback (status, created_at DESC) 
WHERE status IN ('new', 'reviewed');

-- Index for feedback analytics by time periods
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_analytics_time 
ON user_feedback (created_at DESC, rating, is_accurate, is_helpful) 
WHERE rating IS NOT NULL;

-- Index for source preference analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_source_analysis 
ON user_feedback USING GIN (preferred_sources) 
WHERE preferred_sources IS NOT NULL;

-- Index for search strategy performance analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_search_strategy 
ON user_feedback (search_strategy, rating, is_accurate) 
WHERE search_strategy IS NOT NULL;

-- Index for user expertise correlation analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_expertise_rating 
ON user_feedback (user_expertise_level, rating, feedback_quality_score) 
WHERE user_expertise_level IS NOT NULL;

-- Partial indexes for problem identification
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_low_rating 
ON user_feedback (created_at DESC, rating, query_text) 
WHERE rating <= 3;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_inaccurate 
ON user_feedback (created_at DESC, query_text, response_text) 
WHERE is_accurate = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_not_helpful 
ON user_feedback (created_at DESC, query_text, response_text) 
WHERE is_helpful = false;

-- Index for detailed feedback analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_detailed_feedback 
ON user_feedback (created_at DESC) 
WHERE missing_info IS NOT NULL OR incorrect_info IS NOT NULL OR suggested_improvements IS NOT NULL;

-- Composite index for admin workflow
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_admin_workflow 
ON user_feedback (assigned_to, status, updated_at DESC) 
WHERE assigned_to IS NOT NULL;

-- Index for feedback quality analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_feedback_quality_analysis 
ON user_feedback (feedback_quality_score DESC, created_at DESC) 
WHERE feedback_quality_score IS NOT NULL;

-- Indexes for feedback_categories table optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedback_categories_analysis 
ON feedback_categories (category, confidence DESC, created_at DESC);

-- Index for category distribution analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedback_categories_distribution 
ON feedback_categories (created_at DESC, category, confidence) 
WHERE confidence >= 0.7;

-- Indexes for improvement_actions table optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_improvement_actions_impact 
ON improvement_actions (action_type, implemented_at DESC) 
WHERE implemented_at IS NOT NULL;

-- Index for improvement tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_improvement_actions_tracking 
ON improvement_actions USING GIN (impact_metrics) 
WHERE impact_metrics IS NOT NULL;

-- Indexes for feedback_alerts table optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedback_alerts_active 
ON feedback_alerts (created_at DESC, severity, alert_type) 
WHERE status = 'active';

-- Index for alert management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedback_alerts_management 
ON feedback_alerts (status, acknowledged_at DESC, resolved_at DESC);

-- Indexes for feedback_insights table optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedback_insights_active 
ON feedback_insights (impact_score DESC, confidence DESC, created_at DESC) 
WHERE status IN ('new', 'reviewed') AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP);

-- Index for insight type analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedback_insights_type_analysis 
ON feedback_insights (insight_type, status, created_at DESC);

-- Materialized view for real-time dashboard metrics (for better performance)
CREATE MATERIALIZED VIEW IF NOT EXISTS feedback_dashboard_cache AS
SELECT 
    -- Current metrics
    COUNT(*) as total_feedback,
    AVG(rating) as avg_rating,
    COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) * 100 as accuracy_rate,
    COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) * 100 as helpfulness_rate,
    
    -- Status breakdown
    COUNT(CASE WHEN status = 'new' THEN 1 END) as new_count,
    COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed_count,
    COUNT(CASE WHEN status = 'addressed' THEN 1 END) as addressed_count,
    
    -- Recent activity (last 24 hours)
    COUNT(CASE WHEN created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 1 END) as recent_feedback_count,
    AVG(CASE WHEN created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN rating END) as recent_avg_rating,
    
    -- Quality metrics
    AVG(feedback_quality_score) as avg_quality_score,
    COUNT(CASE WHEN feedback_quality_score >= 0.8 THEN 1 END) as high_quality_count,
    
    -- Cache timestamp
    CURRENT_TIMESTAMP as cached_at
FROM user_feedback;

-- Index for the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_dashboard_cache_timestamp 
ON feedback_dashboard_cache (cached_at);

-- Function to refresh dashboard cache
CREATE OR REPLACE FUNCTION refresh_feedback_dashboard_cache()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY feedback_dashboard_cache;
END;
$$ LANGUAGE plpgsql;

-- Materialized view for source performance analysis
CREATE MATERIALIZED VIEW IF NOT EXISTS source_performance_cache AS
WITH source_feedback AS (
    SELECT 
        jsonb_array_elements_text(sources_used->'sources') as source_name,
        rating,
        is_accurate,
        is_helpful,
        created_at,
        search_strategy
    FROM user_feedback 
    WHERE sources_used IS NOT NULL 
    AND jsonb_typeof(sources_used->'sources') = 'array'
),
source_preferences AS (
    SELECT 
        jsonb_array_elements_text(preferred_sources) as source_name,
        'preferred' as preference_type,
        rating,
        created_at
    FROM user_feedback 
    WHERE preferred_sources IS NOT NULL
)
SELECT 
    sf.source_name,
    COUNT(*) as usage_count,
    AVG(sf.rating) as avg_rating,
    COUNT(CASE WHEN sf.is_accurate = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN sf.is_accurate IS NOT NULL THEN 1 END), 0) * 100 as accuracy_rate,
    COUNT(CASE WHEN sf.is_helpful = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN sf.is_helpful IS NOT NULL THEN 1 END), 0) * 100 as helpfulness_rate,
    COUNT(sp.source_name) as preference_mentions,
    MAX(sf.created_at) as last_used,
    -- Performance by search strategy
    jsonb_object_agg(
        COALESCE(sf.search_strategy, 'unknown'), 
        jsonb_build_object(
            'count', COUNT(*) FILTER (WHERE sf.search_strategy IS NOT NULL),
            'avg_rating', AVG(sf.rating) FILTER (WHERE sf.search_strategy IS NOT NULL)
        )
    ) as strategy_performance,
    CURRENT_TIMESTAMP as cached_at
FROM source_feedback sf
LEFT JOIN source_preferences sp ON sf.source_name = sp.source_name
GROUP BY sf.source_name
HAVING COUNT(*) >= 3  -- Only include sources with sufficient data
ORDER BY usage_count DESC, avg_rating DESC;

-- Index for source performance cache
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_performance_cache_source 
ON source_performance_cache (source_name);

-- Function to refresh source performance cache
CREATE OR REPLACE FUNCTION refresh_source_performance_cache()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY source_performance_cache;
END;
$$ LANGUAGE plpgsql;

-- Create a function to analyze index usage and suggest optimizations
CREATE OR REPLACE FUNCTION analyze_feedback_index_usage()
RETURNS TABLE(
    table_name TEXT,
    index_name TEXT,
    index_size TEXT,
    index_scans BIGINT,
    tuples_read BIGINT,
    tuples_fetched BIGINT,
    usage_ratio NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        schemaname||'.'||tablename as table_name,
        indexrelname as index_name,
        pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
        idx_scan as index_scans,
        idx_tup_read as tuples_read,
        idx_tup_fetch as tuples_fetched,
        CASE 
            WHEN idx_scan = 0 THEN 0
            ELSE ROUND((idx_tup_fetch::NUMERIC / idx_tup_read::NUMERIC) * 100, 2)
        END as usage_ratio
    FROM pg_stat_user_indexes 
    WHERE schemaname = 'public' 
    AND (tablename LIKE '%feedback%' OR tablename LIKE '%improvement%' OR tablename LIKE '%alert%' OR tablename LIKE '%insight%')
    ORDER BY idx_scan DESC, pg_relation_size(indexrelid) DESC;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get feedback system performance statistics
CREATE OR REPLACE FUNCTION get_feedback_performance_stats()
RETURNS TABLE(
    metric_name TEXT,
    metric_value TEXT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'Total Feedback Records'::TEXT,
        COUNT(*)::TEXT,
        'Total number of feedback records in the system'::TEXT
    FROM user_feedback
    
    UNION ALL
    
    SELECT 
        'Average Query Time (Recent)'::TEXT,
        COALESCE(ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000), 2)::TEXT || ' ms', 'N/A'),
        'Average time between feedback creation and last update (last 1000 records)'::TEXT
    FROM (
        SELECT created_at, updated_at 
        FROM user_feedback 
        WHERE updated_at IS NOT NULL 
        ORDER BY created_at DESC 
        LIMIT 1000
    ) recent_feedback
    
    UNION ALL
    
    SELECT 
        'Cache Hit Ratio'::TEXT,
        COALESCE(ROUND((blks_hit::NUMERIC / (blks_hit + blks_read)::NUMERIC) * 100, 2)::TEXT || '%', 'N/A'),
        'Database cache hit ratio for feedback tables'::TEXT
    FROM pg_stat_database 
    WHERE datname = current_database()
    
    UNION ALL
    
    SELECT 
        'Index Usage Efficiency'::TEXT,
        COALESCE(ROUND(AVG(
            CASE 
                WHEN idx_scan = 0 THEN 0
                ELSE (idx_tup_fetch::NUMERIC / GREATEST(idx_tup_read::NUMERIC, 1)) * 100
            END
        ), 2)::TEXT || '%', 'N/A'),
        'Average efficiency of index usage across feedback tables'::TEXT
    FROM pg_stat_user_indexes 
    WHERE schemaname = 'public' 
    AND (tablename LIKE '%feedback%' OR tablename LIKE '%improvement%' OR tablename LIKE '%alert%' OR tablename LIKE '%insight%');
END;
$$ LANGUAGE plpgsql;

-- Add table and index comments for documentation
COMMENT ON MATERIALIZED VIEW feedback_dashboard_cache IS 'Cached dashboard metrics for improved performance - refresh every 5 minutes';
COMMENT ON MATERIALIZED VIEW source_performance_cache IS 'Cached source performance analysis - refresh every hour';

COMMENT ON FUNCTION refresh_feedback_dashboard_cache() IS 'Refreshes the dashboard metrics cache - should be called every 5 minutes';
COMMENT ON FUNCTION refresh_source_performance_cache() IS 'Refreshes the source performance cache - should be called every hour';
COMMENT ON FUNCTION analyze_feedback_index_usage() IS 'Analyzes index usage patterns for feedback system optimization';
COMMENT ON FUNCTION get_feedback_performance_stats() IS 'Returns performance statistics for the feedback system';

-- Create a maintenance function to clean up old data
CREATE OR REPLACE FUNCTION cleanup_old_feedback_data(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete old feedback alerts that are resolved
    DELETE FROM feedback_alerts 
    WHERE status = 'resolved' 
    AND resolved_at < CURRENT_DATE - INTERVAL '1 day' * retention_days;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Delete expired insights
    DELETE FROM feedback_insights 
    WHERE expires_at IS NOT NULL 
    AND expires_at < CURRENT_TIMESTAMP;
    
    -- Archive very old feedback (optional - comment out if you want to keep all feedback)
    -- DELETE FROM user_feedback 
    -- WHERE created_at < CURRENT_DATE - INTERVAL '1 day' * (retention_days * 2);
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_feedback_data(INTEGER) IS 'Cleans up old feedback system data - run weekly';

-- Performance monitoring view
CREATE OR REPLACE VIEW feedback_performance_monitor AS
SELECT 
    'user_feedback' as table_name,
    pg_size_pretty(pg_total_relation_size('user_feedback')) as total_size,
    pg_size_pretty(pg_relation_size('user_feedback')) as table_size,
    (SELECT COUNT(*) FROM user_feedback) as row_count,
    (SELECT COUNT(*) FROM user_feedback WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours') as recent_rows
UNION ALL
SELECT 
    'feedback_categories' as table_name,
    pg_size_pretty(pg_total_relation_size('feedback_categories')) as total_size,
    pg_size_pretty(pg_relation_size('feedback_categories')) as table_size,
    (SELECT COUNT(*) FROM feedback_categories) as row_count,
    (SELECT COUNT(*) FROM feedback_categories WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours') as recent_rows
UNION ALL
SELECT 
    'improvement_actions' as table_name,
    pg_size_pretty(pg_total_relation_size('improvement_actions')) as total_size,
    pg_size_pretty(pg_relation_size('improvement_actions')) as table_size,
    (SELECT COUNT(*) FROM improvement_actions) as row_count,
    (SELECT COUNT(*) FROM improvement_actions WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours') as recent_rows
UNION ALL
SELECT 
    'feedback_alerts' as table_name,
    pg_size_pretty(pg_total_relation_size('feedback_alerts')) as total_size,
    pg_size_pretty(pg_relation_size('feedback_alerts')) as table_size,
    (SELECT COUNT(*) FROM feedback_alerts) as row_count,
    (SELECT COUNT(*) FROM feedback_alerts WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours') as recent_rows
UNION ALL
SELECT 
    'feedback_insights' as table_name,
    pg_size_pretty(pg_total_relation_size('feedback_insights')) as total_size,
    pg_size_pretty(pg_relation_size('feedback_insights')) as table_size,
    (SELECT COUNT(*) FROM feedback_insights) as row_count,
    (SELECT COUNT(*) FROM feedback_insights WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours') as recent_rows;