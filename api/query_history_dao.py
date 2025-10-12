"""
Query history data access object for tracking user interactions.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .dao import get_dao


@dataclass
class QueryRecord:
    """Data class for query history records."""
    id: Optional[int] = None
    session_id: Optional[str] = None
    user_ip: Optional[str] = None
    user_agent: Optional[str] = None
    query_text: str = ""
    response_text: Optional[str] = None
    sources_used: Optional[List[Dict]] = None
    search_type: Optional[str] = None
    response_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QueryHistoryDAO:
    """Data access object for query history operations."""
    
    def __init__(self):
        self.dao = get_dao()
    
    def ensure_schema(self):
        """Ensure query history schema exists."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Read and execute schema file
                schema_path = "db/query_history_schema.sql"
                try:
                    with open(schema_path, 'r') as f:
                        schema_sql = f.read()
                    cur.execute(schema_sql)
                    conn.commit()
                except FileNotFoundError:
                    # Fallback: create basic table
                    cur.execute("""
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
                    """)
                    conn.commit()
    
    def log_query(self, record: QueryRecord) -> int:
        """Log a query interaction."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO query_history (
                        session_id, user_ip, user_agent, query_text, response_text,
                        sources_used, search_type, response_time_ms, tokens_used,
                        model_used, success, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    record.session_id, record.user_ip, record.user_agent,
                    record.query_text, record.response_text,
                    json.dumps(record.sources_used) if record.sources_used else None,
                    record.search_type, record.response_time_ms, record.tokens_used,
                    record.model_used, record.success, record.error_message
                ))
                query_id = cur.fetchone()[0]
                conn.commit()
                return query_id
    
    def get_recent_queries(self, limit: int = 50, session_id: Optional[str] = None) -> List[QueryRecord]:
        """Get recent queries, optionally filtered by session."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                if session_id:
                    cur.execute("""
                        SELECT * FROM query_history 
                        WHERE session_id = %s 
                        ORDER BY created_at DESC 
                        LIMIT %s;
                    """, (session_id, limit))
                else:
                    cur.execute("""
                        SELECT * FROM query_history 
                        ORDER BY created_at DESC 
                        LIMIT %s;
                    """, (limit,))
                
                rows = cur.fetchall()
                return [self._row_to_record(row) for row in rows]
    
    def get_query_analytics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get query analytics for the specified number of days."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        query_text,
                        COUNT(*) as query_count,
                        AVG(response_time_ms) as avg_response_time,
                        COUNT(CASE WHEN success THEN 1 END) as success_count,
                        COUNT(CASE WHEN NOT success THEN 1 END) as error_count,
                        MAX(created_at) as last_asked
                    FROM query_history 
                    WHERE created_at >= %s
                    GROUP BY query_text
                    ORDER BY query_count DESC
                    LIMIT 20;
                """, (datetime.now() - timedelta(days=days),))
                
                columns = ['query_text', 'query_count', 'avg_response_time', 
                          'success_count', 'error_count', 'last_asked']
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    
    def get_usage_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get usage statistics for the specified number of days."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_queries,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        AVG(response_time_ms) as avg_response_time,
                        COUNT(CASE WHEN success THEN 1 END) as successful_queries,
                        COUNT(CASE WHEN NOT success THEN 1 END) as failed_queries
                    FROM query_history 
                    WHERE created_at >= %s;
                """, (datetime.now() - timedelta(days=days),))
                
                row = cur.fetchone()
                return {
                    'total_queries': row[0] or 0,
                    'unique_sessions': row[1] or 0,
                    'avg_response_time': float(row[2]) if row[2] else 0,
                    'successful_queries': row[3] or 0,
                    'failed_queries': row[4] or 0,
                    'success_rate': (row[3] / row[0] * 100) if row[0] > 0 else 0
                }
    
    def search_queries(self, search_term: str, limit: int = 20) -> List[QueryRecord]:
        """Search queries by text content."""
        with self.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM query_history 
                    WHERE query_text ILIKE %s OR response_text ILIKE %s
                    ORDER BY created_at DESC 
                    LIMIT %s;
                """, (f"%{search_term}%", f"%{search_term}%", limit))
                
                rows = cur.fetchall()
                return [self._row_to_record(row) for row in rows]
    
    def _row_to_record(self, row) -> QueryRecord:
        """Convert database row to QueryRecord."""
        # Handle JSONB data - it might already be parsed by psycopg2
        sources_data = row[6]
        if sources_data is not None:
            if isinstance(sources_data, str):
                sources_used = json.loads(sources_data)
            else:
                sources_used = sources_data  # Already parsed
        else:
            sources_used = None
            
        return QueryRecord(
            id=row[0],
            session_id=row[1],
            user_ip=row[2],
            user_agent=row[3],
            query_text=row[4],
            response_text=row[5],
            sources_used=sources_used,
            search_type=row[7],
            response_time_ms=row[8],
            tokens_used=row[9],
            model_used=row[10],
            success=row[11],
            error_message=row[12],
            created_at=row[13],
            updated_at=row[14]
        )


# Global instance
_query_history_dao: Optional[QueryHistoryDAO] = None


def get_query_history_dao() -> QueryHistoryDAO:
    """Get or create the query history DAO instance."""
    global _query_history_dao
    if _query_history_dao is None:
        _query_history_dao = QueryHistoryDAO()
        _query_history_dao.ensure_schema()
    return _query_history_dao
