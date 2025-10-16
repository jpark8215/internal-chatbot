-- Enhanced Feedback System Database Schema Migration
-- This script enhances the existing user_feedback table and adds new tables for comprehensive feedback management

-- First, let's enhance the existing user_feedback table with new fields
-- We'll use ALTER TABLE statements to add new columns to the existing table

-- Add new columns to existing user_feedback table
ALTER TABLE user_feedback 
ADD COLUMN IF NOT EXISTS session_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS search_strategy VARCHAR(50),
ADD COLUMN IF NOT EXISTS quick_rating VARCHAR(20), -- 'thumbs_up', 'thumbs_down', etc.
ADD COLUMN IF NOT EXISTS accuracy_confidence INTEGER CHECK (accuracy_confidence >= 1 AND accuracy_confidence <= 5),
ADD COLUMN IF NOT EXISTS helpfulness_confidence INTEGER CHECK (helpfulness_confidence >= 1 AND helpfulness_confidence <= 5),
ADD COLUMN IF NOT EXISTS suggested_improvements TEXT,
ADD COLUMN IF NOT EXISTS user_expertise_level VARCHAR(20), -- 'beginner', 'intermediate', 'expert'
ADD COLUMN IF NOT EXISTS feedback_quality_score FLOAT,
ADD COLUMN IF NOT EXISTS admin_notes TEXT,
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'new', -- 'new', 'reviewed', 'addressed'
ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255),
ADD COLUMN IF NOT EXISTS resolution_notes TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS ip_address INET,
ADD COLUMN IF NOT EXISTS user_agent TEXT;

-- Rename user_session to session_id for consistency (if it exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_feedback' AND column_name = 'user_session') THEN
        ALTER TABLE user_feedback RENAME COLUMN user_session TO session_id_old;
    END IF;
END $$;

-- Update session_id from old column if it exists
UPDATE user_feedback 
SET session_id = session_id_old 
WHERE session_id_old IS NOT NULL AND session_id IS NULL;

-- Drop the old column if it exists
ALTER TABLE user_feedback DROP COLUMN IF EXISTS session_id_old;

-- Create feedback categories table for classification
CREATE TABLE IF NOT EXISTS feedback_categories (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER REFERENCES user_feedback(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL, -- 'accuracy', 'completeness', 'relevance', 'source_quality', etc.
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique category per feedback
    UNIQUE(feedback_id, category)
);

-- Create improvement actions table for tracking improvements
CREATE TABLE IF NOT EXISTS improvement_actions (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER REFERENCES user_feedback(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL, -- 'source_boost', 'prompt_update', 'document_update', 'search_strategy'
    description TEXT NOT NULL,
    implemented_at TIMESTAMP,
    impact_metrics JSONB, -- Store before/after metrics
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create feedback alerts table for automated monitoring
CREATE TABLE IF NOT EXISTS feedback_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL, -- 'low_rating', 'accuracy_drop', 'volume_spike', 'pattern_detected'
    severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    title VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_conditions JSONB, -- Store the conditions that triggered the alert
    related_feedback_ids INTEGER[], -- Array of related feedback IDs
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'acknowledged', 'resolved'
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create feedback insights table for storing automated analysis results
CREATE TABLE IF NOT EXISTS feedback_insights (
    id SERIAL PRIMARY KEY,
    insight_type VARCHAR(50) NOT NULL, -- 'pattern', 'recommendation', 'trend', 'anomaly'
    title VARCHAR(255) NOT NULL,
    description TEXT,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    data_source JSONB, -- Store the data that generated this insight
    recommendations JSONB, -- Store actionable recommendations
    impact_score FLOAT, -- Estimated impact of addressing this insight
    status VARCHAR(20) DEFAULT 'new', -- 'new', 'reviewed', 'implemented', 'dismissed'
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP -- When this insight becomes stale
);

-- Create indexes for optimal query performance

-- Enhanced indexes for user_feedback table
CREATE INDEX IF NOT EXISTS idx_user_feedback_status ON user_feedback (status);
CREATE INDEX IF NOT EXISTS idx_user_feedback_assigned_to ON user_feedback (assigned_to);
CREATE INDEX IF NOT EXISTS idx_user_feedback_updated_at ON user_feedback (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_feedback_session_id ON user_feedback (session_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_search_strategy ON user_feedback (search_strategy);
CREATE INDEX IF NOT EXISTS idx_user_feedback_quick_rating ON user_feedback (quick_rating);
CREATE INDEX IF NOT EXISTS idx_user_feedback_accuracy_confidence ON user_feedback (accuracy_confidence);
CREATE INDEX IF NOT EXISTS idx_user_feedback_helpfulness_confidence ON user_feedback (helpfulness_confidence);
CREATE INDEX IF NOT EXISTS idx_user_feedback_expertise_level ON user_feedback (user_expertise_level);
CREATE INDEX IF NOT EXISTS idx_user_feedback_quality_score ON user_feedback (feedback_quality_score);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_user_feedback_status_created_at ON user_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_feedback_rating_accuracy ON user_feedback (rating, is_accurate);
CREATE INDEX IF NOT EXISTS idx_user_feedback_assigned_status ON user_feedback (assigned_to, status) WHERE assigned_to IS NOT NULL;

-- Indexes for feedback_categories table
CREATE INDEX IF NOT EXISTS idx_feedback_categories_feedback_id ON feedback_categories (feedback_id);
CREATE INDEX IF NOT EXISTS idx_feedback_categories_category ON feedback_categories (category);
CREATE INDEX IF NOT EXISTS idx_feedback_categories_confidence ON feedback_categories (confidence DESC);

-- Indexes for improvement_actions table
CREATE INDEX IF NOT EXISTS idx_improvement_actions_feedback_id ON improvement_actions (feedback_id);
CREATE INDEX IF NOT EXISTS idx_improvement_actions_type ON improvement_actions (action_type);
CREATE INDEX IF NOT EXISTS idx_improvement_actions_implemented_at ON improvement_actions (implemented_at DESC);
CREATE INDEX IF NOT EXISTS idx_improvement_actions_created_by ON improvement_actions (created_by);

-- Indexes for feedback_alerts table
CREATE INDEX IF NOT EXISTS idx_feedback_alerts_type ON feedback_alerts (alert_type);
CREATE INDEX IF NOT EXISTS idx_feedback_alerts_severity ON feedback_alerts (severity);
CREATE INDEX IF NOT EXISTS idx_feedback_alerts_status ON feedback_alerts (status);
CREATE INDEX IF NOT EXISTS idx_feedback_alerts_created_at ON feedback_alerts (created_at DESC);

-- Indexes for feedback_insights table
CREATE INDEX IF NOT EXISTS idx_feedback_insights_type ON feedback_insights (insight_type);
CREATE INDEX IF NOT EXISTS idx_feedback_insights_status ON feedback_insights (status);
CREATE INDEX IF NOT EXISTS idx_feedback_insights_confidence ON feedback_insights (confidence DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_insights_impact_score ON feedback_insights (impact_score DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_insights_created_at ON feedback_insights (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_insights_expires_at ON feedback_insights (expires_at);

-- Create updated analytics views

-- Enhanced feedback summary view
CREATE OR REPLACE VIEW feedback_summary AS
SELECT 
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as total_feedback,
    AVG(rating) as avg_rating,
    COUNT(CASE WHEN is_accurate = true THEN 1 END) as accurate_count,
    COUNT(CASE WHEN is_accurate = false THEN 1 END) as inaccurate_count,
    COUNT(CASE WHEN is_helpful = true THEN 1 END) as helpful_count,
    COUNT(CASE WHEN is_helpful = false THEN 1 END) as not_helpful_count,
    COUNT(CASE WHEN status = 'addressed' THEN 1 END) as resolved_count,
    COUNT(CASE WHEN status = 'new' THEN 1 END) as new_count,
    AVG(feedback_quality_score) as avg_quality_score,
    COUNT(DISTINCT session_id) as unique_sessions
FROM user_feedback
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;

-- Source preference analysis view
CREATE OR REPLACE VIEW source_preferences AS
WITH source_mentions AS (
    SELECT 
        jsonb_array_elements_text(preferred_sources) as source_name,
        rating,
        is_accurate,
        is_helpful,
        created_at
    FROM user_feedback 
    WHERE preferred_sources IS NOT NULL
)
SELECT 
    source_name,
    COUNT(*) as mention_count,
    AVG(rating) as avg_rating_when_mentioned,
    COUNT(CASE WHEN is_accurate = true THEN 1 END) as accurate_mentions,
    COUNT(CASE WHEN is_helpful = true THEN 1 END) as helpful_mentions,
    COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / COUNT(*) as accuracy_rate,
    COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / COUNT(*) as helpfulness_rate,
    MAX(created_at) as last_mentioned
FROM source_mentions
GROUP BY source_name
ORDER BY mention_count DESC, avg_rating_when_mentioned DESC;

-- Admin dashboard metrics view
CREATE OR REPLACE VIEW admin_dashboard_metrics AS
SELECT 
    -- Overall metrics
    COUNT(*) as total_feedback,
    AVG(rating) as avg_rating,
    COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) * 100 as accuracy_rate,
    COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) * 100 as helpfulness_rate,
    
    -- Status breakdown
    COUNT(CASE WHEN status = 'new' THEN 1 END) as new_feedback_count,
    COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed_feedback_count,
    COUNT(CASE WHEN status = 'addressed' THEN 1 END) as addressed_feedback_count,
    
    -- Recent activity (last 7 days)
    COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as recent_feedback_count,
    AVG(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN rating END) as recent_avg_rating,
    
    -- Quality metrics
    AVG(feedback_quality_score) as avg_quality_score,
    COUNT(CASE WHEN feedback_quality_score >= 0.8 THEN 1 END) as high_quality_feedback_count
FROM user_feedback;

-- Feedback trends view for analytics
CREATE OR REPLACE VIEW feedback_trends AS
SELECT 
    DATE_TRUNC('week', created_at) as week,
    COUNT(*) as feedback_count,
    AVG(rating) as avg_rating,
    COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) as accuracy_rate,
    COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) as helpfulness_rate,
    COUNT(DISTINCT session_id) as unique_users,
    AVG(feedback_quality_score) as avg_quality_score
FROM user_feedback
WHERE created_at >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', created_at)
ORDER BY week DESC;

-- Problem queries view for admin attention
CREATE OR REPLACE VIEW problem_queries AS
SELECT 
    f.id,
    f.query_text,
    f.response_text,
    f.rating,
    f.is_accurate,
    f.is_helpful,
    f.missing_info,
    f.incorrect_info,
    f.suggested_improvements,
    f.status,
    f.assigned_to,
    f.created_at,
    f.updated_at,
    -- Calculate problem score (lower is worse)
    COALESCE(f.rating, 0) + 
    CASE WHEN f.is_accurate = false THEN -2 ELSE 0 END +
    CASE WHEN f.is_helpful = false THEN -1 ELSE 0 END as problem_score
FROM user_feedback f
WHERE 
    f.rating <= 3 OR 
    f.is_accurate = false OR 
    f.is_helpful = false OR
    f.missing_info IS NOT NULL OR
    f.incorrect_info IS NOT NULL
ORDER BY problem_score ASC, f.created_at DESC;

-- Create functions for automated feedback analysis

-- Function to calculate feedback quality score
CREATE OR REPLACE FUNCTION calculate_feedback_quality_score(
    p_rating INTEGER,
    p_is_accurate BOOLEAN,
    p_is_helpful BOOLEAN,
    p_missing_info TEXT,
    p_incorrect_info TEXT,
    p_suggested_improvements TEXT,
    p_comments TEXT
) RETURNS FLOAT AS $$
DECLARE
    quality_score FLOAT := 0;
BEGIN
    -- Base score from rating
    IF p_rating IS NOT NULL THEN
        quality_score := quality_score + (p_rating::FLOAT / 5.0) * 0.3;
    END IF;
    
    -- Accuracy feedback adds value
    IF p_is_accurate IS NOT NULL THEN
        quality_score := quality_score + 0.2;
    END IF;
    
    -- Helpfulness feedback adds value
    IF p_is_helpful IS NOT NULL THEN
        quality_score := quality_score + 0.2;
    END IF;
    
    -- Detailed feedback adds significant value
    IF p_missing_info IS NOT NULL AND LENGTH(p_missing_info) > 10 THEN
        quality_score := quality_score + 0.15;
    END IF;
    
    IF p_incorrect_info IS NOT NULL AND LENGTH(p_incorrect_info) > 10 THEN
        quality_score := quality_score + 0.15;
    END IF;
    
    IF p_suggested_improvements IS NOT NULL AND LENGTH(p_suggested_improvements) > 10 THEN
        quality_score := quality_score + 0.1;
    END IF;
    
    IF p_comments IS NOT NULL AND LENGTH(p_comments) > 20 THEN
        quality_score := quality_score + 0.1;
    END IF;
    
    -- Cap at 1.0
    RETURN LEAST(quality_score, 1.0);
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically calculate feedback quality score
CREATE OR REPLACE FUNCTION update_feedback_quality_score()
RETURNS TRIGGER AS $$
BEGIN
    NEW.feedback_quality_score := calculate_feedback_quality_score(
        NEW.rating,
        NEW.is_accurate,
        NEW.is_helpful,
        NEW.missing_info,
        NEW.incorrect_info,
        NEW.suggested_improvements,
        NEW.comments
    );
    
    NEW.updated_at := CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for feedback quality score calculation
DROP TRIGGER IF EXISTS trigger_update_feedback_quality_score ON user_feedback;
CREATE TRIGGER trigger_update_feedback_quality_score
    BEFORE INSERT OR UPDATE ON user_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_feedback_quality_score();

-- Function to detect feedback patterns and create alerts
CREATE OR REPLACE FUNCTION check_feedback_alerts()
RETURNS VOID AS $$
DECLARE
    recent_avg_rating FLOAT;
    recent_accuracy_rate FLOAT;
    recent_feedback_count INTEGER;
    baseline_avg_rating FLOAT;
    baseline_accuracy_rate FLOAT;
BEGIN
    -- Get recent metrics (last 24 hours)
    SELECT 
        AVG(rating),
        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0),
        COUNT(*)
    INTO recent_avg_rating, recent_accuracy_rate, recent_feedback_count
    FROM user_feedback
    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
    
    -- Get baseline metrics (previous 7 days, excluding last 24 hours)
    SELECT 
        AVG(rating),
        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0)
    INTO baseline_avg_rating, baseline_accuracy_rate
    FROM user_feedback
    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '8 days'
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '24 hours';
    
    -- Check for low rating alert
    IF recent_avg_rating IS NOT NULL AND recent_avg_rating < 3.0 AND recent_feedback_count >= 5 THEN
        INSERT INTO feedback_alerts (alert_type, severity, title, description, trigger_conditions)
        VALUES (
            'low_rating',
            'high',
            'Average Rating Below Threshold',
            FORMAT('Average rating in last 24 hours: %.2f (threshold: 3.0)', recent_avg_rating),
            jsonb_build_object('avg_rating', recent_avg_rating, 'threshold', 3.0, 'period', '24 hours')
        )
        ON CONFLICT DO NOTHING;
    END IF;
    
    -- Check for accuracy drop alert
    IF recent_accuracy_rate IS NOT NULL AND baseline_accuracy_rate IS NOT NULL 
       AND recent_accuracy_rate < baseline_accuracy_rate - 0.2 AND recent_feedback_count >= 5 THEN
        INSERT INTO feedback_alerts (alert_type, severity, title, description, trigger_conditions)
        VALUES (
            'accuracy_drop',
            'high',
            'Accuracy Rate Significant Drop',
            FORMAT('Accuracy dropped from %.1f%% to %.1f%% in last 24 hours', 
                   baseline_accuracy_rate * 100, recent_accuracy_rate * 100),
            jsonb_build_object('recent_rate', recent_accuracy_rate, 'baseline_rate', baseline_accuracy_rate, 'drop_threshold', 0.2)
        )
        ON CONFLICT DO NOTHING;
    END IF;
    
    -- Check for feedback volume spike
    IF recent_feedback_count > 50 THEN -- Configurable threshold
        INSERT INTO feedback_alerts (alert_type, severity, title, description, trigger_conditions)
        VALUES (
            'volume_spike',
            'medium',
            'High Feedback Volume',
            FORMAT('Received %s feedback items in last 24 hours', recent_feedback_count),
            jsonb_build_object('feedback_count', recent_feedback_count, 'threshold', 50)
        )
        ON CONFLICT DO NOTHING;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Add comments to tables for documentation
COMMENT ON TABLE user_feedback IS 'Enhanced user feedback table with detailed feedback collection and admin management fields';
COMMENT ON TABLE feedback_categories IS 'Automated categorization of feedback for pattern analysis';
COMMENT ON TABLE improvement_actions IS 'Tracking of improvements made based on user feedback';
COMMENT ON TABLE feedback_alerts IS 'Automated alerts for feedback monitoring and quality assurance';
COMMENT ON TABLE feedback_insights IS 'Automated insights and recommendations generated from feedback analysis';

COMMENT ON COLUMN user_feedback.feedback_quality_score IS 'Automatically calculated score (0-1) indicating the quality and completeness of the feedback';
COMMENT ON COLUMN user_feedback.status IS 'Admin workflow status: new, reviewed, addressed';
COMMENT ON COLUMN user_feedback.quick_rating IS 'Quick feedback options: thumbs_up, thumbs_down, accurate, inaccurate, helpful, not_helpful';
COMMENT ON COLUMN user_feedback.user_expertise_level IS 'Self-reported user expertise: beginner, intermediate, expert';

-- Grant appropriate permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE ON user_feedback TO feedback_user;
-- GRANT SELECT, INSERT, UPDATE ON feedback_categories TO feedback_user;
-- GRANT SELECT, INSERT, UPDATE ON improvement_actions TO feedback_admin;
-- GRANT SELECT, INSERT, UPDATE ON feedback_alerts TO feedback_admin;
-- GRANT SELECT, INSERT, UPDATE ON feedback_insights TO feedback_admin;