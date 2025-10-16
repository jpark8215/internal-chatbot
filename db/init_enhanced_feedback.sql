-- Enhanced Feedback System Database Initialization
-- This script initializes the complete enhanced feedback system database schema
-- Run this script on a fresh database or after running the migration script

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Source the base schema files
\i init_db.sql
\i query_history_schema.sql

-- Apply the enhanced feedback schema
\i enhanced_feedback_schema.sql

-- Apply performance optimizations
\i optimize_feedback_indexes.sql

-- Insert initial configuration data

-- Insert default feedback categories for classification
INSERT INTO feedback_categories (feedback_id, category, confidence, created_at) VALUES
-- These are example categories that will be populated by the system
-- The actual categories will be created automatically by the feedback analysis system
(NULL, 'accuracy', 1.0, CURRENT_TIMESTAMP),
(NULL, 'completeness', 1.0, CURRENT_TIMESTAMP),
(NULL, 'relevance', 1.0, CURRENT_TIMESTAMP),
(NULL, 'source_quality', 1.0, CURRENT_TIMESTAMP),
(NULL, 'response_clarity', 1.0, CURRENT_TIMESTAMP),
(NULL, 'timeliness', 1.0, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Create initial feedback insights for system monitoring
INSERT INTO feedback_insights (
    insight_type, 
    title, 
    description, 
    confidence, 
    recommendations, 
    impact_score, 
    status,
    created_at
) VALUES 
(
    'system_initialization',
    'Enhanced Feedback System Initialized',
    'The enhanced feedback system has been successfully initialized with comprehensive analytics and monitoring capabilities.',
    1.0,
    '["Monitor feedback collection rates", "Set up automated alert thresholds", "Configure dashboard refresh intervals"]'::jsonb,
    0.9,
    'new',
    CURRENT_TIMESTAMP
),
(
    'recommendation',
    'Establish Baseline Metrics',
    'Collect baseline feedback metrics over the first 30 days to establish normal operating parameters for alerts and insights.',
    0.8,
    '["Collect at least 100 feedback samples", "Monitor accuracy and helpfulness rates", "Identify common feedback patterns"]'::jsonb,
    0.7,
    'new',
    CURRENT_TIMESTAMP
);

-- Create sample improvement actions for reference
INSERT INTO improvement_actions (
    feedback_id,
    action_type,
    description,
    created_by,
    created_at
) VALUES 
(
    NULL,
    'system_setup',
    'Enhanced feedback system database schema initialized with comprehensive tracking and analytics capabilities.',
    'system',
    CURRENT_TIMESTAMP
);

-- Refresh materialized views to initialize cache
SELECT refresh_feedback_dashboard_cache();
SELECT refresh_source_performance_cache();

-- Create a function to initialize feedback system settings
CREATE OR REPLACE FUNCTION initialize_feedback_system_settings()
RETURNS VOID AS $$
BEGIN
    -- Create system configuration table if it doesn't exist
    CREATE TABLE IF NOT EXISTS feedback_system_config (
        key VARCHAR(100) PRIMARY KEY,
        value JSONB NOT NULL,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Insert default configuration values
    INSERT INTO feedback_system_config (key, value, description) VALUES
    ('alert_thresholds', '{
        "low_rating_threshold": 3.0,
        "accuracy_drop_threshold": 0.2,
        "volume_spike_threshold": 50,
        "min_feedback_for_alert": 5
    }'::jsonb, 'Threshold values for automated feedback alerts'),
    
    ('cache_refresh_intervals', '{
        "dashboard_cache_minutes": 5,
        "source_performance_cache_minutes": 60,
        "insights_generation_hours": 24
    }'::jsonb, 'Cache refresh intervals for performance optimization'),
    
    ('feedback_quality_weights', '{
        "rating_weight": 0.3,
        "accuracy_weight": 0.2,
        "helpfulness_weight": 0.2,
        "detailed_feedback_weight": 0.3
    }'::jsonb, 'Weights for calculating feedback quality scores'),
    
    ('retention_policies', '{
        "feedback_retention_days": 1095,
        "alert_retention_days": 365,
        "insight_retention_days": 180
    }'::jsonb, 'Data retention policies for feedback system'),
    
    ('notification_settings', '{
        "email_alerts_enabled": true,
        "slack_alerts_enabled": false,
        "alert_recipients": ["admin@example.com"]
    }'::jsonb, 'Notification settings for feedback alerts')
    
    ON CONFLICT (key) DO NOTHING;
    
    -- Update timestamp
    UPDATE feedback_system_config 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE key IN ('alert_thresholds', 'cache_refresh_intervals', 'feedback_quality_weights', 'retention_policies', 'notification_settings');
    
END;
$$ LANGUAGE plpgsql;

-- Initialize system settings
SELECT initialize_feedback_system_settings();

-- Create a function to get system configuration
CREATE OR REPLACE FUNCTION get_feedback_system_config(config_key VARCHAR DEFAULT NULL)
RETURNS TABLE(key VARCHAR, value JSONB, description TEXT, updated_at TIMESTAMP) AS $$
BEGIN
    IF config_key IS NULL THEN
        RETURN QUERY
        SELECT fsc.key, fsc.value, fsc.description, fsc.updated_at
        FROM feedback_system_config fsc
        ORDER BY fsc.key;
    ELSE
        RETURN QUERY
        SELECT fsc.key, fsc.value, fsc.description, fsc.updated_at
        FROM feedback_system_config fsc
        WHERE fsc.key = config_key;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create a function to update system configuration
CREATE OR REPLACE FUNCTION update_feedback_system_config(
    config_key VARCHAR,
    config_value JSONB,
    config_description TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO feedback_system_config (key, value, description, updated_at)
    VALUES (config_key, config_value, config_description, CURRENT_TIMESTAMP)
    ON CONFLICT (key) DO UPDATE SET
        value = EXCLUDED.value,
        description = COALESCE(EXCLUDED.description, feedback_system_config.description),
        updated_at = EXCLUDED.updated_at;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Create automated maintenance job function
CREATE OR REPLACE FUNCTION run_feedback_system_maintenance()
RETURNS TEXT AS $$
DECLARE
    result_text TEXT := '';
    cleanup_count INTEGER;
BEGIN
    -- Refresh materialized views
    PERFORM refresh_feedback_dashboard_cache();
    result_text := result_text || 'Dashboard cache refreshed. ';
    
    PERFORM refresh_source_performance_cache();
    result_text := result_text || 'Source performance cache refreshed. ';
    
    -- Run feedback alerts check
    PERFORM check_feedback_alerts();
    result_text := result_text || 'Feedback alerts checked. ';
    
    -- Clean up old data
    SELECT cleanup_old_feedback_data() INTO cleanup_count;
    result_text := result_text || 'Cleaned up ' || cleanup_count || ' old records. ';
    
    -- Update statistics
    ANALYZE user_feedback;
    ANALYZE feedback_categories;
    ANALYZE improvement_actions;
    ANALYZE feedback_alerts;
    ANALYZE feedback_insights;
    result_text := result_text || 'Table statistics updated.';
    
    RETURN result_text;
END;
$$ LANGUAGE plpgsql;

-- Create a view for system health monitoring
CREATE OR REPLACE VIEW feedback_system_health AS
SELECT 
    'Database Size' as metric,
    pg_size_pretty(pg_database_size(current_database())) as value,
    'Total database size including all feedback tables' as description
UNION ALL
SELECT 
    'Active Alerts' as metric,
    COUNT(*)::TEXT as value,
    'Number of active feedback alerts requiring attention' as description
FROM feedback_alerts 
WHERE status = 'active'
UNION ALL
SELECT 
    'Pending Insights' as metric,
    COUNT(*)::TEXT as value,
    'Number of new insights awaiting review' as description
FROM feedback_insights 
WHERE status = 'new'
UNION ALL
SELECT 
    'Recent Feedback (24h)' as metric,
    COUNT(*)::TEXT as value,
    'Feedback received in the last 24 hours' as description
FROM user_feedback 
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
UNION ALL
SELECT 
    'Cache Freshness' as metric,
    CASE 
        WHEN MAX(cached_at) >= CURRENT_TIMESTAMP - INTERVAL '10 minutes' THEN 'Fresh'
        WHEN MAX(cached_at) >= CURRENT_TIMESTAMP - INTERVAL '1 hour' THEN 'Stale'
        ELSE 'Very Stale'
    END as value,
    'Freshness of materialized view caches' as description
FROM (
    SELECT cached_at FROM feedback_dashboard_cache
    UNION ALL
    SELECT cached_at FROM source_performance_cache
) cache_times;

-- Grant permissions for feedback system (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO feedback_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO feedback_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO feedback_user;

-- Create final verification function
CREATE OR REPLACE FUNCTION verify_feedback_system_installation()
RETURNS TABLE(
    component VARCHAR,
    status VARCHAR,
    details TEXT
) AS $$
BEGIN
    -- Check tables
    RETURN QUERY
    SELECT 
        'Tables'::VARCHAR as component,
        CASE WHEN COUNT(*) = 5 THEN 'OK' ELSE 'ERROR' END as status,
        'Found ' || COUNT(*) || ' of 5 expected tables' as details
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('user_feedback', 'feedback_categories', 'improvement_actions', 'feedback_alerts', 'feedback_insights');
    
    -- Check views
    RETURN QUERY
    SELECT 
        'Views'::VARCHAR as component,
        CASE WHEN COUNT(*) >= 6 THEN 'OK' ELSE 'WARNING' END as status,
        'Found ' || COUNT(*) || ' views' as details
    FROM information_schema.views 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%feedback%';
    
    -- Check functions
    RETURN QUERY
    SELECT 
        'Functions'::VARCHAR as component,
        CASE WHEN COUNT(*) >= 10 THEN 'OK' ELSE 'WARNING' END as status,
        'Found ' || COUNT(*) || ' functions' as details
    FROM information_schema.routines 
    WHERE routine_schema = 'public' 
    AND routine_type = 'FUNCTION'
    AND routine_name LIKE '%feedback%';
    
    -- Check materialized views
    RETURN QUERY
    SELECT 
        'Materialized Views'::VARCHAR as component,
        CASE WHEN COUNT(*) >= 2 THEN 'OK' ELSE 'ERROR' END as status,
        'Found ' || COUNT(*) || ' materialized views' as details
    FROM pg_matviews 
    WHERE schemaname = 'public';
    
    -- Check configuration
    RETURN QUERY
    SELECT 
        'Configuration'::VARCHAR as component,
        CASE WHEN COUNT(*) >= 5 THEN 'OK' ELSE 'WARNING' END as status,
        'Found ' || COUNT(*) || ' configuration entries' as details
    FROM feedback_system_config;
    
END;
$$ LANGUAGE plpgsql;

-- Run verification
SELECT * FROM verify_feedback_system_installation();

-- Display system information
SELECT 
    'Enhanced Feedback System Initialization Complete' as message,
    CURRENT_TIMESTAMP as completed_at,
    version() as database_version;

-- Show system health
SELECT * FROM feedback_system_health;

COMMENT ON FUNCTION initialize_feedback_system_settings() IS 'Initializes default configuration settings for the feedback system';
COMMENT ON FUNCTION get_feedback_system_config(VARCHAR) IS 'Retrieves feedback system configuration settings';
COMMENT ON FUNCTION update_feedback_system_config(VARCHAR, JSONB, TEXT) IS 'Updates feedback system configuration settings';
COMMENT ON FUNCTION run_feedback_system_maintenance() IS 'Runs automated maintenance tasks for the feedback system';
COMMENT ON FUNCTION verify_feedback_system_installation() IS 'Verifies that all feedback system components are properly installed';
COMMENT ON VIEW feedback_system_health IS 'Provides real-time health monitoring for the feedback system';