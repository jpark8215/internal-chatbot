"""
Automated alerting and monitoring system for feedback quality metrics.
Implements threshold-based alerting, pattern detection, and anomaly detection.
"""

import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

from .config import get_settings
from .dao import get_dao
from .logging_config import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    LOW_RATING = "low_rating"
    ACCURACY_DROP = "accuracy_drop"
    VOLUME_SPIKE = "volume_spike"
    VOLUME_DROP = "volume_drop"
    PATTERN_DETECTED = "pattern_detected"
    ANOMALY_DETECTED = "anomaly_detected"
    IMPROVEMENT_IMPACT = "improvement_impact"


@dataclass
class FeedbackAlert:
    """Represents a feedback system alert."""
    id: Optional[int] = None
    alert_type: AlertType = AlertType.LOW_RATING
    severity: AlertSeverity = AlertSeverity.MEDIUM
    title: str = ""
    description: str = ""
    trigger_conditions: Optional[Dict[str, Any]] = None
    related_feedback_ids: Optional[List[int]] = None
    status: str = "active"  # active, acknowledged, resolved
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class AlertThresholds:
    """Configuration for alert thresholds."""
    min_rating_threshold: float = 3.0
    accuracy_rate_threshold: float = 0.7
    accuracy_drop_threshold: float = 0.2
    volume_spike_multiplier: float = 2.0
    volume_drop_threshold: float = 0.3
    min_feedback_count: int = 5
    pattern_confidence_threshold: float = 0.8


@dataclass
class FeedbackMetrics:
    """Feedback metrics for a time period."""
    total_feedback: int = 0
    avg_rating: float = 0.0
    accuracy_rate: float = 0.0
    helpfulness_rate: float = 0.0
    new_count: int = 0
    reviewed_count: int = 0
    addressed_count: int = 0
    unique_sessions: int = 0
    avg_quality_score: float = 0.0


class FeedbackAlertDAO:
    """Data access object for feedback alerts."""
    
    def __init__(self):
        self.dao = get_dao()
        self.ensure_schema()
    
    def ensure_schema(self):
        """Ensure alert schema exists."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # The schema is already created in enhanced_feedback_schema.sql
                # Just ensure indexes exist
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_feedback_alerts_type_status 
                    ON feedback_alerts (alert_type, status);
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_feedback_alerts_severity_created 
                    ON feedback_alerts (severity, created_at DESC);
                """)
                conn.commit()
    
    def create_alert(self, alert: FeedbackAlert) -> int:
        """Create a new alert."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO feedback_alerts (
                        alert_type, severity, title, description, 
                        trigger_conditions, related_feedback_ids, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    alert.alert_type.value,
                    alert.severity.value,
                    alert.title,
                    alert.description,
                    json.dumps(alert.trigger_conditions) if alert.trigger_conditions else None,
                    alert.related_feedback_ids,
                    alert.status
                ))
                alert_id = cur.fetchone()[0]
                conn.commit()
                return alert_id
    
    def get_active_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get active alerts."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id, alert_type, severity, title, description,
                        trigger_conditions, related_feedback_ids, status,
                        acknowledged_by, acknowledged_at, created_at
                    FROM feedback_alerts 
                    WHERE status IN ('active', 'acknowledged')
                    ORDER BY severity DESC, created_at DESC
                    LIMIT %s;
                """, (limit,))
                
                columns = ['id', 'alert_type', 'severity', 'title', 'description',
                          'trigger_conditions', 'related_feedback_ids', 'status',
                          'acknowledged_by', 'acknowledged_at', 'created_at']
                
                alerts = []
                for row in cur.fetchall():
                    alert_dict = dict(zip(columns, row))
                    if alert_dict['trigger_conditions']:
                        alert_dict['trigger_conditions'] = json.loads(alert_dict['trigger_conditions'])
                    alerts.append(alert_dict)
                
                return alerts
    
    def update_alert_status(self, alert_id: int, status: str, 
                           user: Optional[str] = None) -> bool:
        """Update alert status."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                if status == 'acknowledged':
                    cur.execute("""
                        UPDATE feedback_alerts 
                        SET status = %s, acknowledged_by = %s, acknowledged_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (status, user, alert_id))
                elif status == 'resolved':
                    cur.execute("""
                        UPDATE feedback_alerts 
                        SET status = %s, resolved_by = %s, resolved_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (status, user, alert_id))
                else:
                    cur.execute("""
                        UPDATE feedback_alerts 
                        SET status = %s
                        WHERE id = %s;
                    """, (status, alert_id))
                
                conn.commit()
                return cur.rowcount > 0
    
    def get_alert_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get alert summary statistics."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_alerts,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_alerts,
                        COUNT(CASE WHEN status = 'acknowledged' THEN 1 END) as acknowledged_alerts,
                        COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_alerts,
                        COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_alerts,
                        COUNT(CASE WHEN severity = 'high' THEN 1 END) as high_alerts,
                        COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium_alerts,
                        COUNT(CASE WHEN severity = 'low' THEN 1 END) as low_alerts
                    FROM feedback_alerts 
                    WHERE created_at >= %s;
                """, (datetime.now() - timedelta(days=days),))
                
                row = cur.fetchone()
                return {
                    'total_alerts': row[0] or 0,
                    'active_alerts': row[1] or 0,
                    'acknowledged_alerts': row[2] or 0,
                    'resolved_alerts': row[3] or 0,
                    'critical_alerts': row[4] or 0,
                    'high_alerts': row[5] or 0,
                    'medium_alerts': row[6] or 0,
                    'low_alerts': row[7] or 0
                }


class FeedbackMonitor:
    """Monitors feedback metrics and generates alerts."""
    
    def __init__(self, thresholds: Optional[AlertThresholds] = None):
        self.dao = get_dao()
        self.alert_dao = FeedbackAlertDAO()
        self.thresholds = thresholds or AlertThresholds()
    
    def get_feedback_metrics(self, hours: int = 24) -> FeedbackMetrics:
        """Get feedback metrics for the specified time period."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) as accuracy_rate,
                        COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) as helpfulness_rate,
                        COUNT(CASE WHEN status = 'new' THEN 1 END) as new_count,
                        COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed_count,
                        COUNT(CASE WHEN status = 'addressed' THEN 1 END) as addressed_count,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        AVG(feedback_quality_score) as avg_quality_score
                    FROM user_feedback 
                    WHERE created_at >= %s;
                """, (datetime.now() - timedelta(hours=hours),))
                
                row = cur.fetchone()
                return FeedbackMetrics(
                    total_feedback=row[0] or 0,
                    avg_rating=float(row[1]) if row[1] else 0.0,
                    accuracy_rate=float(row[2]) if row[2] else 0.0,
                    helpfulness_rate=float(row[3]) if row[3] else 0.0,
                    new_count=row[4] or 0,
                    reviewed_count=row[5] or 0,
                    addressed_count=row[6] or 0,
                    unique_sessions=row[7] or 0,
                    avg_quality_score=float(row[8]) if row[8] else 0.0
                )
    
    def check_rating_threshold(self, current_metrics: FeedbackMetrics) -> Optional[FeedbackAlert]:
        """Check if average rating is below threshold."""
        if (current_metrics.total_feedback >= self.thresholds.min_feedback_count and
            current_metrics.avg_rating < self.thresholds.min_rating_threshold):
            
            severity = AlertSeverity.CRITICAL if current_metrics.avg_rating < 2.0 else AlertSeverity.HIGH
            
            return FeedbackAlert(
                alert_type=AlertType.LOW_RATING,
                severity=severity,
                title="Average Rating Below Threshold",
                description=f"Average rating in last 24 hours: {current_metrics.avg_rating:.2f} "
                           f"(threshold: {self.thresholds.min_rating_threshold})",
                trigger_conditions={
                    'avg_rating': current_metrics.avg_rating,
                    'threshold': self.thresholds.min_rating_threshold,
                    'feedback_count': current_metrics.total_feedback,
                    'period_hours': 24
                }
            )
        return None
    
    def check_accuracy_threshold(self, current_metrics: FeedbackMetrics, 
                               baseline_metrics: FeedbackMetrics) -> Optional[FeedbackAlert]:
        """Check for accuracy rate drops."""
        if (current_metrics.total_feedback >= self.thresholds.min_feedback_count and
            current_metrics.accuracy_rate < self.thresholds.accuracy_rate_threshold):
            
            # Check for significant drop from baseline
            drop_amount = baseline_metrics.accuracy_rate - current_metrics.accuracy_rate
            is_significant_drop = drop_amount > self.thresholds.accuracy_drop_threshold
            
            severity = AlertSeverity.CRITICAL if current_metrics.accuracy_rate < 0.5 else AlertSeverity.HIGH
            
            title = "Accuracy Rate Below Threshold"
            if is_significant_drop:
                title = "Significant Accuracy Rate Drop"
            
            return FeedbackAlert(
                alert_type=AlertType.ACCURACY_DROP,
                severity=severity,
                title=title,
                description=f"Accuracy rate: {current_metrics.accuracy_rate:.1%} "
                           f"(threshold: {self.thresholds.accuracy_rate_threshold:.1%})"
                           + (f", dropped {drop_amount:.1%} from baseline" if is_significant_drop else ""),
                trigger_conditions={
                    'accuracy_rate': current_metrics.accuracy_rate,
                    'threshold': self.thresholds.accuracy_rate_threshold,
                    'baseline_rate': baseline_metrics.accuracy_rate,
                    'drop_amount': drop_amount,
                    'feedback_count': current_metrics.total_feedback
                }
            )
        return None
    
    def check_volume_anomalies(self, current_metrics: FeedbackMetrics, 
                              baseline_metrics: FeedbackMetrics) -> List[FeedbackAlert]:
        """Check for volume spikes or drops."""
        alerts = []
        
        if baseline_metrics.total_feedback > 0:
            volume_ratio = current_metrics.total_feedback / baseline_metrics.total_feedback
            
            # Volume spike detection
            if volume_ratio > self.thresholds.volume_spike_multiplier:
                alerts.append(FeedbackAlert(
                    alert_type=AlertType.VOLUME_SPIKE,
                    severity=AlertSeverity.MEDIUM,
                    title="High Feedback Volume Detected",
                    description=f"Received {current_metrics.total_feedback} feedback items "
                               f"({volume_ratio:.1f}x baseline of {baseline_metrics.total_feedback})",
                    trigger_conditions={
                        'current_volume': current_metrics.total_feedback,
                        'baseline_volume': baseline_metrics.total_feedback,
                        'volume_ratio': volume_ratio,
                        'spike_threshold': self.thresholds.volume_spike_multiplier
                    }
                ))
            
            # Volume drop detection
            elif volume_ratio < self.thresholds.volume_drop_threshold:
                alerts.append(FeedbackAlert(
                    alert_type=AlertType.VOLUME_DROP,
                    severity=AlertSeverity.MEDIUM,
                    title="Low Feedback Volume Detected",
                    description=f"Received only {current_metrics.total_feedback} feedback items "
                               f"({volume_ratio:.1%} of baseline {baseline_metrics.total_feedback})",
                    trigger_conditions={
                        'current_volume': current_metrics.total_feedback,
                        'baseline_volume': baseline_metrics.total_feedback,
                        'volume_ratio': volume_ratio,
                        'drop_threshold': self.thresholds.volume_drop_threshold
                    }
                ))
        
        return alerts
    
    def detect_feedback_patterns(self) -> List[FeedbackAlert]:
        """Detect emerging patterns in feedback."""
        alerts = []
        
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Detect common missing information patterns
                cur.execute("""
                    SELECT 
                        LOWER(missing_info) as missing_pattern,
                        COUNT(*) as occurrence_count,
                        AVG(rating) as avg_rating
                    FROM user_feedback 
                    WHERE missing_info IS NOT NULL 
                    AND created_at >= %s
                    AND LENGTH(missing_info) > 10
                    GROUP BY LOWER(missing_info)
                    HAVING COUNT(*) >= 3
                    ORDER BY COUNT(*) DESC
                    LIMIT 5;
                """, (datetime.now() - timedelta(days=7),))
                
                for row in cur.fetchall():
                    pattern, count, avg_rating = row
                    if count >= 3:  # Pattern threshold
                        alerts.append(FeedbackAlert(
                            alert_type=AlertType.PATTERN_DETECTED,
                            severity=AlertSeverity.MEDIUM,
                            title="Recurring Missing Information Pattern",
                            description=f"'{pattern[:100]}...' reported missing {count} times "
                                       f"(avg rating: {avg_rating:.1f})",
                            trigger_conditions={
                                'pattern': pattern,
                                'occurrence_count': count,
                                'avg_rating': avg_rating,
                                'pattern_type': 'missing_information'
                            }
                        ))
                
                # Detect source preference patterns
                cur.execute("""
                    WITH source_feedback AS (
                        SELECT 
                            jsonb_array_elements_text(preferred_sources) as source_name,
                            rating,
                            is_accurate
                        FROM user_feedback 
                        WHERE preferred_sources IS NOT NULL
                        AND created_at >= %s
                    )
                    SELECT 
                        source_name,
                        COUNT(*) as mention_count,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / COUNT(*) as accuracy_rate
                    FROM source_feedback
                    GROUP BY source_name
                    HAVING COUNT(*) >= 5
                    ORDER BY AVG(rating) DESC
                    LIMIT 3;
                """, (datetime.now() - timedelta(days=7),))
                
                for row in cur.fetchall():
                    source, count, avg_rating, accuracy_rate = row
                    if avg_rating > 4.0 and accuracy_rate > 0.8:
                        alerts.append(FeedbackAlert(
                            alert_type=AlertType.PATTERN_DETECTED,
                            severity=AlertSeverity.LOW,
                            title="High-Quality Source Identified",
                            description=f"Source '{source}' consistently rated highly "
                                       f"({count} mentions, {avg_rating:.1f} avg rating, "
                                       f"{accuracy_rate:.1%} accuracy)",
                            trigger_conditions={
                                'source_name': source,
                                'mention_count': count,
                                'avg_rating': avg_rating,
                                'accuracy_rate': accuracy_rate,
                                'pattern_type': 'preferred_source'
                            }
                        ))
        
        return alerts
    
    def run_monitoring_cycle(self) -> List[FeedbackAlert]:
        """Run a complete monitoring cycle and return generated alerts."""
        alerts = []
        
        try:
            # Get current metrics (last 24 hours)
            current_metrics = self.get_feedback_metrics(hours=24)
            
            # Get baseline metrics (previous 7 days, excluding last 24 hours)
            baseline_metrics = self.get_feedback_metrics_baseline()
            
            logger.info(f"Monitoring cycle - Current: {current_metrics.total_feedback} feedback, "
                       f"avg rating: {current_metrics.avg_rating:.2f}, "
                       f"accuracy: {current_metrics.accuracy_rate:.1%}")
            
            # Check thresholds
            rating_alert = self.check_rating_threshold(current_metrics)
            if rating_alert:
                alerts.append(rating_alert)
            
            accuracy_alert = self.check_accuracy_threshold(current_metrics, baseline_metrics)
            if accuracy_alert:
                alerts.append(accuracy_alert)
            
            # Check volume anomalies
            volume_alerts = self.check_volume_anomalies(current_metrics, baseline_metrics)
            alerts.extend(volume_alerts)
            
            # Detect patterns
            pattern_alerts = self.detect_feedback_patterns()
            alerts.extend(pattern_alerts)
            
            # Save alerts to database
            for alert in alerts:
                try:
                    alert_id = self.alert_dao.create_alert(alert)
                    logger.info(f"Created alert {alert_id}: {alert.title}")
                except Exception as e:
                    logger.error(f"Failed to save alert: {e}")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")
            return []
    
    def get_feedback_metrics_baseline(self) -> FeedbackMetrics:
        """Get baseline metrics (7 days ago, excluding last 24 hours)."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) as accuracy_rate,
                        COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) as helpfulness_rate,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        AVG(feedback_quality_score) as avg_quality_score
                    FROM user_feedback 
                    WHERE created_at >= %s AND created_at < %s;
                """, (
                    datetime.now() - timedelta(days=8),
                    datetime.now() - timedelta(hours=24)
                ))
                
                row = cur.fetchone()
                return FeedbackMetrics(
                    total_feedback=row[0] or 0,
                    avg_rating=float(row[1]) if row[1] else 0.0,
                    accuracy_rate=float(row[2]) if row[2] else 0.0,
                    helpfulness_rate=float(row[3]) if row[3] else 0.0,
                    unique_sessions=row[4] or 0,
                    avg_quality_score=float(row[5]) if row[5] else 0.0
                )


# Global instances
_alert_dao: Optional[FeedbackAlertDAO] = None
_feedback_monitor: Optional[FeedbackMonitor] = None


def get_alert_dao() -> FeedbackAlertDAO:
    """Get or create the alert DAO instance."""
    global _alert_dao
    if _alert_dao is None:
        _alert_dao = FeedbackAlertDAO()
    return _alert_dao


def get_feedback_monitor() -> FeedbackMonitor:
    """Get or create the feedback monitor instance."""
    global _feedback_monitor
    if _feedback_monitor is None:
        _feedback_monitor = FeedbackMonitor()
    return _feedback_monitor