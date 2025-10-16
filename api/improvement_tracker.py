"""
Improvement impact tracking and reporting system.
Tracks improvements made based on feedback and measures their impact.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

from .config import get_settings
from .dao import get_dao
from .logging_config import get_logger

logger = get_logger(__name__)


class ImprovementType(Enum):
    SOURCE_BOOST = "source_boost"
    PROMPT_UPDATE = "prompt_update"
    DOCUMENT_UPDATE = "document_update"
    SEARCH_STRATEGY = "search_strategy"
    THRESHOLD_ADJUSTMENT = "threshold_adjustment"
    UI_ENHANCEMENT = "ui_enhancement"
    OTHER = "other"


@dataclass
class ImprovementAction:
    """Represents an improvement action taken based on feedback."""
    id: Optional[int] = None
    feedback_id: Optional[int] = None
    action_type: ImprovementType = ImprovementType.OTHER
    description: str = ""
    implemented_at: Optional[datetime] = None
    impact_metrics: Optional[Dict[str, Any]] = None
    created_by: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ImpactMetrics:
    """Metrics to measure improvement impact."""
    before_avg_rating: float = 0.0
    after_avg_rating: float = 0.0
    before_accuracy_rate: float = 0.0
    after_accuracy_rate: float = 0.0
    before_helpfulness_rate: float = 0.0
    after_helpfulness_rate: float = 0.0
    feedback_count_before: int = 0
    feedback_count_after: int = 0
    improvement_period_days: int = 7
    measurement_date: Optional[datetime] = None


class ImprovementTracker:
    """Tracks improvements and measures their impact."""
    
    def __init__(self):
        self.dao = get_dao()
        self.ensure_schema()
    
    def ensure_schema(self):
        """Ensure improvement tracking schema exists."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Schema already exists from enhanced_feedback_schema.sql
                # Just ensure additional indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_improvement_actions_type_implemented 
                    ON improvement_actions (action_type, implemented_at DESC);
                """)
                conn.commit()
    
    def record_improvement(self, improvement: ImprovementAction) -> int:
        """Record a new improvement action."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO improvement_actions (
                        feedback_id, action_type, description, implemented_at,
                        impact_metrics, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    improvement.feedback_id,
                    improvement.action_type.value,
                    improvement.description,
                    improvement.implemented_at,
                    json.dumps(improvement.impact_metrics) if improvement.impact_metrics else None,
                    improvement.created_by
                ))
                improvement_id = cur.fetchone()[0]
                conn.commit()
                return improvement_id
    
    def get_baseline_metrics(self, before_date: datetime, days: int = 7) -> ImpactMetrics:
        """Get baseline metrics before an improvement."""
        end_date = before_date
        start_date = before_date - timedelta(days=days)
        
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as feedback_count,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) as accuracy_rate,
                        COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) as helpfulness_rate
                    FROM user_feedback 
                    WHERE created_at >= %s AND created_at < %s;
                """, (start_date, end_date))
                
                row = cur.fetchone()
                return ImpactMetrics(
                    feedback_count_before=row[0] or 0,
                    before_avg_rating=float(row[1]) if row[1] else 0.0,
                    before_accuracy_rate=float(row[2]) if row[2] else 0.0,
                    before_helpfulness_rate=float(row[3]) if row[3] else 0.0,
                    improvement_period_days=days,
                    measurement_date=before_date
                )
    
    def measure_improvement_impact(self, improvement_id: int, 
                                 measurement_period_days: int = 7) -> Optional[ImpactMetrics]:
        """Measure the impact of an improvement action."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Get improvement details
                cur.execute("""
                    SELECT implemented_at, action_type, description
                    FROM improvement_actions 
                    WHERE id = %s;
                """, (improvement_id,))
                
                improvement_row = cur.fetchone()
                if not improvement_row:
                    return None
                
                implemented_at, action_type, description = improvement_row
                if not implemented_at:
                    return None
                
                # Get baseline metrics (before implementation)
                baseline = self.get_baseline_metrics(implemented_at, measurement_period_days)
                
                # Get post-implementation metrics
                after_start = implemented_at
                after_end = implemented_at + timedelta(days=measurement_period_days)
                
                cur.execute("""
                    SELECT 
                        COUNT(*) as feedback_count,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) as accuracy_rate,
                        COUNT(CASE WHEN is_helpful = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_helpful IS NOT NULL THEN 1 END), 0) as helpfulness_rate
                    FROM user_feedback 
                    WHERE created_at >= %s AND created_at < %s;
                """, (after_start, after_end))
                
                after_row = cur.fetchone()
                
                impact_metrics = ImpactMetrics(
                    before_avg_rating=baseline.before_avg_rating,
                    after_avg_rating=float(after_row[1]) if after_row[1] else 0.0,
                    before_accuracy_rate=baseline.before_accuracy_rate,
                    after_accuracy_rate=float(after_row[2]) if after_row[2] else 0.0,
                    before_helpfulness_rate=baseline.before_helpfulness_rate,
                    after_helpfulness_rate=float(after_row[3]) if after_row[3] else 0.0,
                    feedback_count_before=baseline.feedback_count_before,
                    feedback_count_after=after_row[0] or 0,
                    improvement_period_days=measurement_period_days,
                    measurement_date=datetime.now()
                )
                
                # Update the improvement record with impact metrics
                cur.execute("""
                    UPDATE improvement_actions 
                    SET impact_metrics = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (json.dumps(asdict(impact_metrics)), improvement_id))
                
                conn.commit()
                return impact_metrics
    
    def get_improvement_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get summary of improvements and their impact."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Get improvement counts by type
                cur.execute("""
                    SELECT 
                        action_type,
                        COUNT(*) as count,
                        COUNT(CASE WHEN implemented_at IS NOT NULL THEN 1 END) as implemented_count
                    FROM improvement_actions 
                    WHERE created_at >= %s
                    GROUP BY action_type
                    ORDER BY count DESC;
                """, (datetime.now() - timedelta(days=days),))
                
                improvement_types = {}
                for row in cur.fetchall():
                    action_type, count, implemented = row
                    improvement_types[action_type] = {
                        'total': count,
                        'implemented': implemented,
                        'pending': count - implemented
                    }
                
                # Get recent improvements with impact
                cur.execute("""
                    SELECT 
                        id, action_type, description, implemented_at,
                        impact_metrics, created_by, created_at
                    FROM improvement_actions 
                    WHERE created_at >= %s
                    AND implemented_at IS NOT NULL
                    ORDER BY implemented_at DESC
                    LIMIT 10;
                """, (datetime.now() - timedelta(days=days),))
                
                recent_improvements = []
                total_rating_improvement = 0.0
                total_accuracy_improvement = 0.0
                improvements_with_metrics = 0
                
                for row in cur.fetchall():
                    improvement_id, action_type, description, implemented_at, impact_metrics_json, created_by, created_at = row
                    
                    improvement_data = {
                        'id': improvement_id,
                        'action_type': action_type,
                        'description': description,
                        'implemented_at': implemented_at.isoformat() if implemented_at else None,
                        'created_by': created_by,
                        'created_at': created_at.isoformat() if created_at else None,
                        'impact_metrics': None
                    }
                    
                    if impact_metrics_json:
                        impact_metrics = json.loads(impact_metrics_json)
                        improvement_data['impact_metrics'] = impact_metrics
                        
                        # Calculate improvements
                        rating_improvement = impact_metrics.get('after_avg_rating', 0) - impact_metrics.get('before_avg_rating', 0)
                        accuracy_improvement = impact_metrics.get('after_accuracy_rate', 0) - impact_metrics.get('before_accuracy_rate', 0)
                        
                        total_rating_improvement += rating_improvement
                        total_accuracy_improvement += accuracy_improvement
                        improvements_with_metrics += 1
                    
                    recent_improvements.append(improvement_data)
                
                # Calculate average improvements
                avg_rating_improvement = total_rating_improvement / improvements_with_metrics if improvements_with_metrics > 0 else 0
                avg_accuracy_improvement = total_accuracy_improvement / improvements_with_metrics if improvements_with_metrics > 0 else 0
                
                return {
                    'time_period_days': days,
                    'improvement_types': improvement_types,
                    'recent_improvements': recent_improvements,
                    'impact_summary': {
                        'improvements_with_metrics': improvements_with_metrics,
                        'avg_rating_improvement': avg_rating_improvement,
                        'avg_accuracy_improvement': avg_accuracy_improvement,
                        'total_rating_improvement': total_rating_improvement,
                        'total_accuracy_improvement': total_accuracy_improvement
                    }
                }
    
    def get_improvement_recommendations(self) -> List[Dict[str, Any]]:
        """Generate improvement recommendations based on feedback patterns."""
        recommendations = []
        
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Analyze low-rated queries for patterns
                cur.execute("""
                    SELECT 
                        missing_info,
                        COUNT(*) as occurrence_count,
                        AVG(rating) as avg_rating
                    FROM user_feedback 
                    WHERE rating <= 3 
                    AND missing_info IS NOT NULL
                    AND created_at >= %s
                    GROUP BY missing_info
                    HAVING COUNT(*) >= 2
                    ORDER BY COUNT(*) DESC, AVG(rating) ASC
                    LIMIT 5;
                """, (datetime.now() - timedelta(days=14),))
                
                for row in cur.fetchall():
                    missing_info, count, avg_rating = row
                    recommendations.append({
                        'type': 'document_update',
                        'priority': 'high' if count >= 5 else 'medium',
                        'title': 'Address Missing Information',
                        'description': f"Users frequently report missing: '{missing_info[:100]}...'",
                        'details': {
                            'missing_info': missing_info,
                            'occurrence_count': count,
                            'avg_rating': avg_rating
                        },
                        'suggested_action': 'Update documentation to include this information'
                    })
                
                # Analyze source preferences
                cur.execute("""
                    WITH source_analysis AS (
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
                    FROM source_analysis
                    GROUP BY source_name
                    HAVING COUNT(*) >= 3
                    ORDER BY AVG(rating) DESC, COUNT(*) DESC
                    LIMIT 3;
                """, (datetime.now() - timedelta(days=14),))
                
                for row in cur.fetchall():
                    source_name, count, avg_rating, accuracy_rate = row
                    if avg_rating > 4.0:
                        recommendations.append({
                            'type': 'source_boost',
                            'priority': 'medium',
                            'title': 'Boost High-Quality Source',
                            'description': f"Source '{source_name}' consistently receives high ratings",
                            'details': {
                                'source_name': source_name,
                                'mention_count': count,
                                'avg_rating': avg_rating,
                                'accuracy_rate': accuracy_rate
                            },
                            'suggested_action': 'Increase search weight for this source'
                        })
                
                # Analyze search strategy effectiveness
                cur.execute("""
                    SELECT 
                        search_strategy,
                        COUNT(*) as usage_count,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END)::FLOAT / 
                            NULLIF(COUNT(CASE WHEN is_accurate IS NOT NULL THEN 1 END), 0) as accuracy_rate
                    FROM user_feedback 
                    WHERE search_strategy IS NOT NULL
                    AND created_at >= %s
                    GROUP BY search_strategy
                    HAVING COUNT(*) >= 5
                    ORDER BY AVG(rating) DESC;
                """, (datetime.now() - timedelta(days=14),))
                
                strategies = cur.fetchall()
                if len(strategies) > 1:
                    best_strategy = strategies[0]
                    worst_strategy = strategies[-1]
                    
                    rating_diff = best_strategy[2] - worst_strategy[2]
                    if rating_diff > 0.5:
                        recommendations.append({
                            'type': 'search_strategy',
                            'priority': 'high',
                            'title': 'Optimize Search Strategy Usage',
                            'description': f"'{best_strategy[0]}' strategy performs better than '{worst_strategy[0]}'",
                            'details': {
                                'best_strategy': best_strategy[0],
                                'best_rating': best_strategy[2],
                                'worst_strategy': worst_strategy[0],
                                'worst_rating': worst_strategy[2],
                                'rating_difference': rating_diff
                            },
                            'suggested_action': f"Increase usage of '{best_strategy[0]}' strategy"
                        })
        
        return recommendations
    
    def auto_measure_recent_improvements(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Automatically measure impact for recent improvements."""
        results = []
        
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Find improvements that were implemented recently and don't have impact metrics yet
                cur.execute("""
                    SELECT id, action_type, description, implemented_at
                    FROM improvement_actions 
                    WHERE implemented_at IS NOT NULL
                    AND implemented_at >= %s
                    AND (impact_metrics IS NULL OR impact_metrics = '{}')
                    ORDER BY implemented_at DESC;
                """, (datetime.now() - timedelta(days=days_back),))
                
                for row in cur.fetchall():
                    improvement_id, action_type, description, implemented_at = row
                    
                    # Check if enough time has passed for measurement (at least 3 days)
                    if datetime.now() - implemented_at >= timedelta(days=3):
                        try:
                            impact_metrics = self.measure_improvement_impact(improvement_id)
                            if impact_metrics:
                                results.append({
                                    'improvement_id': improvement_id,
                                    'action_type': action_type,
                                    'description': description,
                                    'implemented_at': implemented_at.isoformat(),
                                    'impact_metrics': asdict(impact_metrics),
                                    'status': 'measured'
                                })
                                logger.info(f"Measured impact for improvement {improvement_id}: "
                                          f"rating {impact_metrics.before_avg_rating:.2f} -> {impact_metrics.after_avg_rating:.2f}")
                        except Exception as e:
                            logger.error(f"Failed to measure impact for improvement {improvement_id}: {e}")
                            results.append({
                                'improvement_id': improvement_id,
                                'action_type': action_type,
                                'description': description,
                                'status': 'error',
                                'error': str(e)
                            })
        
        return results


# Global instance
_improvement_tracker: Optional[ImprovementTracker] = None


def get_improvement_tracker() -> ImprovementTracker:
    """Get or create the improvement tracker instance."""
    global _improvement_tracker
    if _improvement_tracker is None:
        _improvement_tracker = ImprovementTracker()
    return _improvement_tracker