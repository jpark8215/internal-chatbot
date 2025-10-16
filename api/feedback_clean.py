"""
Clean, simplified feedback system to avoid syntax issues
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from .config import get_settings
from .dao import get_dao
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SimpleFeedback:
    """Simplified feedback data structure."""
    query_text: str
    response_text: str
    rating: Optional[int] = None
    is_accurate: Optional[bool] = None
    is_helpful: Optional[bool] = None
    missing_info: Optional[str] = None
    incorrect_info: Optional[str] = None
    comments: Optional[str] = None
    user_session: Optional[str] = None
    sources_used: Optional[List[Dict]] = None
    search_strategy: Optional[str] = None


class CleanFeedbackDAO:
    """Clean, simplified feedback DAO."""
    
    def __init__(self):
        self.dao = get_dao()
        self.ensure_table()
    
    def ensure_table(self):
        """Ensure feedback table exists."""
        try:
            with self.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # First create the basic table
                    cur.execute("""
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
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # Add search_strategy column if it doesn't exist
                    try:
                        cur.execute("""
                            ALTER TABLE user_feedback 
                            ADD COLUMN IF NOT EXISTS search_strategy VARCHAR(50);
                        """)
                    except Exception:
                        # Column might already exist or not supported
                        pass
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to ensure feedback table: {e}")
    
    def save_feedback(self, feedback: SimpleFeedback) -> int:
        """Save feedback to database."""
        try:
            with self.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # Try with search_strategy column first
                    try:
                        cur.execute("""
                            INSERT INTO user_feedback (
                                query_text, response_text, sources_used, search_strategy,
                                rating, is_accurate, is_helpful, missing_info, 
                                incorrect_info, comments, user_session
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id;
                        """, (
                            feedback.query_text,
                            feedback.response_text,
                            json.dumps(feedback.sources_used) if feedback.sources_used else None,
                            feedback.search_strategy,
                            feedback.rating,
                            feedback.is_accurate,
                            feedback.is_helpful,
                            feedback.missing_info,
                            feedback.incorrect_info,
                            feedback.comments,
                            feedback.user_session
                        ))
                    except Exception as e:
                        if "search_strategy" in str(e):
                            # Fallback without search_strategy column
                            logger.info("search_strategy column not found, using fallback")
                            cur.execute("""
                                INSERT INTO user_feedback (
                                    query_text, response_text, sources_used,
                                    rating, is_accurate, is_helpful, missing_info, 
                                    incorrect_info, comments, user_session
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id;
                            """, (
                                feedback.query_text,
                                feedback.response_text,
                                json.dumps(feedback.sources_used) if feedback.sources_used else None,
                                feedback.rating,
                                feedback.is_accurate,
                                feedback.is_helpful,
                                feedback.missing_info,
                                feedback.incorrect_info,
                                feedback.comments,
                                feedback.user_session
                            ))
                        else:
                            raise e
                    
                    feedback_id = cur.fetchone()[0]
                    conn.commit()
                    return feedback_id
                    
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            raise
    
    def get_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get basic feedback statistics."""
        try:
            with self.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_feedback,
                            AVG(rating) as avg_rating,
                            COUNT(CASE WHEN is_accurate = true THEN 1 END) as accurate_count,
                            COUNT(CASE WHEN is_helpful = true THEN 1 END) as helpful_count,
                            COUNT(CASE WHEN rating >= 4 THEN 1 END) as positive_feedback,
                            COUNT(CASE WHEN rating <= 2 THEN 1 END) as negative_feedback,
                            COUNT(CASE WHEN rating = 1 THEN 1 END) as rating_1,
                            COUNT(CASE WHEN rating = 2 THEN 1 END) as rating_2,
                            COUNT(CASE WHEN rating = 3 THEN 1 END) as rating_3,
                            COUNT(CASE WHEN rating = 4 THEN 1 END) as rating_4,
                            COUNT(CASE WHEN rating = 5 THEN 1 END) as rating_5
                        FROM user_feedback 
                        WHERE created_at >= %s;
                    """, (datetime.now() - timedelta(days=days),))
                    
                    row = cur.fetchone()
                    if row:
                        total = row[0] or 0
                        return {
                            'total_feedback': total,
                            'avg_rating': float(row[1]) if row[1] else 0,
                            'accurate_count': row[2] or 0,
                            'helpful_count': row[3] or 0,
                            'positive_feedback': row[4] or 0,
                            'negative_feedback': row[5] or 0,
                            'accuracy_rate': (row[2] / total * 100) if total > 0 else 0,
                            'helpfulness_rate': (row[3] / total * 100) if total > 0 else 0,
                            'rating_distribution': {
                                '1': row[6] or 0,
                                '2': row[7] or 0,
                                '3': row[8] or 0,
                                '4': row[9] or 0,
                                '5': row[10] or 0
                            }
                        }
                    else:
                        return {
                            'total_feedback': 0,
                            'avg_rating': 0,
                            'accurate_count': 0,
                            'helpful_count': 0,
                            'positive_feedback': 0,
                            'negative_feedback': 0,
                            'accuracy_rate': 0,
                            'helpfulness_rate': 0,
                            'rating_distribution': {
                                '1': 0, '2': 0, '3': 0, '4': 0, '5': 0
                            }
                        }
        except Exception as e:
            logger.error(f"Failed to get feedback stats: {e}")
            return {'error': str(e)}
    
    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent feedback entries."""
        try:
            with self.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            id, query_text, response_text, rating, 
                            is_accurate, is_helpful, comments, 
                            user_session, created_at
                        FROM user_feedback 
                        ORDER BY created_at DESC 
                        LIMIT %s;
                    """, (limit,))
                    
                    rows = cur.fetchall()
                    return [
                        {
                            'id': row[0],
                            'query_text': row[1],
                            'response_text': row[2],
                            'rating': row[3],
                            'is_accurate': row[4],
                            'is_helpful': row[5],
                            'comments': row[6],
                            'user_session': row[7],
                            'created_at': row[8].isoformat() if row[8] else None
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Failed to get recent feedback: {e}")
            return []
    
    def get_trend_data(self, days: int = 30) -> Dict[str, Any]:
        """Get real trend data for charts."""
        try:
            with self.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get daily feedback counts for the last N days
                    cur.execute("""
                        SELECT 
                            DATE(created_at) as feedback_date,
                            COUNT(*) as count
                        FROM user_feedback 
                        WHERE created_at >= %s
                        GROUP BY DATE(created_at)
                        ORDER BY feedback_date;
                    """, (datetime.now() - timedelta(days=days),))
                    
                    rows = cur.fetchall()
                    
                    # Create labels and data arrays
                    if not rows:
                        return {
                            'labels': ['No data'],
                            'data': [0]
                        }
                    
                    labels = []
                    data = []
                    
                    for row in rows:
                        labels.append(row[0].strftime('%m/%d'))
                        data.append(row[1])
                    
                    return {
                        'labels': labels,
                        'data': data
                    }
        except Exception as e:
            logger.error(f"Failed to get trend data: {e}")
            return {
                'labels': ['Error'],
                'data': [0]
            }
    
    def get_feedback_list(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get paginated feedback list for admin."""
        try:
            with self.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get total count
                    cur.execute("SELECT COUNT(*) FROM user_feedback;")
                    total = cur.fetchone()[0] or 0
                    
                    # Get paginated feedback
                    cur.execute("""
                        SELECT 
                            id, query_text, response_text, rating, 
                            is_accurate, is_helpful, comments, 
                            user_session, created_at
                        FROM user_feedback 
                        ORDER BY created_at DESC 
                        LIMIT %s OFFSET %s;
                    """, (limit, offset))
                    
                    rows = cur.fetchall()
                    feedback_list = [
                        {
                            'id': row[0],
                            'query_text': row[1],
                            'response_text': row[2],
                            'rating': row[3],
                            'is_accurate': row[4],
                            'is_helpful': row[5],
                            'comments': row[6],
                            'user_session': row[7],
                            'created_at': row[8].isoformat() if row[8] else None
                        }
                        for row in rows
                    ]
                    
                    return {
                        'feedback': feedback_list,
                        'total': total,
                        'has_more': (offset + len(feedback_list)) < total
                    }
        except Exception as e:
            logger.error(f"Failed to get feedback list: {e}")
            return {
                'feedback': [],
                'total': 0,
                'has_more': False
            }


# Global instance
_clean_feedback_dao: Optional[CleanFeedbackDAO] = None


def get_clean_feedback_dao() -> CleanFeedbackDAO:
    """Get the clean feedback DAO instance."""
    global _clean_feedback_dao
    if _clean_feedback_dao is None:
        _clean_feedback_dao = CleanFeedbackDAO()
    return _clean_feedback_dao