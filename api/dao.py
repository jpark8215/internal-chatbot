from __future__ import annotations

from typing import List, Optional, Tuple
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import pool

from .config import get_settings


class VectorDAO:
    def __init__(self):
        self.settings = get_settings()
        self._connection_pool: Optional[pool.ThreadedConnectionPool] = None
        self._lock = threading.Lock()

    def _get_connection_pool(self) -> pool.ThreadedConnectionPool:
        """Get or create connection pool."""
        if self._connection_pool is None:
            with self._lock:
                if self._connection_pool is None:
                    dsn = self.settings.database_url
                    if not dsn and self.settings.db_host:
                        # Build DSN from parts if provided
                        user = self.settings.db_user or "postgres"
                        password = self.settings.db_password or "postgres"
                        host = self.settings.db_host
                        port = self.settings.db_port or 5432
                        dbname = self.settings.db_name or "internal_chatbot"
                        dsn = f"postgres://{user}:{password}@{host}:{port}/{dbname}"

                    if not dsn:
                        raise RuntimeError("DATABASE_URL or db_* settings are not configured")

                    self._connection_pool = pool.ThreadedConnectionPool(
                        minconn=1,
                        maxconn=self.settings.database_pool_size,
                        dsn=dsn
                    )
        return self._connection_pool

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool with automatic cleanup."""
        pool = self._get_connection_pool()
        conn = None
        try:
            conn = pool.getconn()
            yield conn
        finally:
            if conn:
                pool.putconn(conn)

    def ensure_schema(self) -> None:
        """Ensure database schema exists."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS documents (
                      id SERIAL PRIMARY KEY,
                      content TEXT NOT NULL,
                      embedding vector({self.settings.embedding_dim}),
                      source_file TEXT,
                      file_type TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                # Create index for better performance
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);"
                )
                # Create index for source file lookups
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_documents_source_file ON documents (source_file);"
                )

    def insert_document(self, content: str, embedding: List[float],
                       source_file: Optional[str] = None, file_type: Optional[str] = None) -> int:
        """Insert a document with metadata."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO documents (content, embedding, source_file, file_type) 
                       VALUES (%s, %s, %s, %s) RETURNING id;""",
                    (content, embedding, source_file, file_type),
                )
                new_id = cur.fetchone()[0]
                conn.commit()  # Explicit commit
                return new_id

    def insert_documents_batch(self, documents: List[Tuple[str, List[float], Optional[str], Optional[str]]]) -> List[int]:
        """Insert multiple documents in a single transaction."""
        ids = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for content, embedding, source_file, file_type in documents:
                    cur.execute(
                        """INSERT INTO documents (content, embedding, source_file, file_type) 
                           VALUES (%s, %s, %s, %s) RETURNING id;""",
                        (content, embedding, source_file, file_type),
                    )
                    ids.append(cur.fetchone()[0])
                conn.commit()  # Explicit commit
        return ids

    def search(self, query_embedding: List[float], top_k: int = 5,
               source_file_filter: Optional[str] = None) -> List[Tuple[int, str, float, Optional[str]]]:
        """Return list of (id, content, distance, source_file) ordered by similarity (ASC)."""
        with self.get_connection() as conn:
            # Set query timeout for faster failure
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SET statement_timeout = '5s';")  # 5 second timeout
                
                if source_file_filter:
                    # Optimized query with index hints
                    cur.execute(
                        """
                        SELECT id, content, (embedding <-> %s::vector) AS distance, source_file
                        FROM documents
                        WHERE source_file = %s
                        ORDER BY embedding <-> %s::vector ASC
                        LIMIT %s;
                        """,
                        (query_embedding, source_file_filter, query_embedding, top_k),
                    )
                else:
                    # Use LIMIT with index scan for better performance
                    cur.execute(
                        """
                        SELECT id, content, (embedding <-> %s::vector) AS distance, source_file
                        FROM documents
                        ORDER BY embedding <-> %s::vector ASC
                        LIMIT %s;
                        """,
                        (query_embedding, query_embedding, top_k),
                    )
                rows = cur.fetchall()
                return [(int(r[0]), str(r[1]), float(r[2]), r[3]) for r in rows]

    def search_keyword(self, query_text: str, top_k: int = 5) -> List[Tuple[int, str, float, Optional[str]]]:
        """Keyword-based search for simple terms."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Split query into individual terms
                terms = query_text.lower().split()
                if not terms:
                    return []

                # Build ILIKE query for each term
                conditions = []
                params = []
                for term in terms:
                    conditions.append("LOWER(content) ILIKE %s")
                    params.append(f"%{term}%")

                where_clause = " AND ".join(conditions)

                cur.execute(
                    f"""
                    SELECT id, content, 
                           (CASE 
                               WHEN LOWER(content) ILIKE %s THEN 0.1
                               ELSE 0.5
                           END) AS score,
                           source_file
                    FROM documents
                    WHERE {where_clause}
                    ORDER BY score ASC, LENGTH(content) ASC
                    LIMIT %s;
                    """,
                    params + [f"%{query_text.lower()}%", top_k]
                )
                rows = cur.fetchall()
                return [(int(r[0]), str(r[1]), float(r[2]), r[3]) for r in rows]


    def search_enhanced(self, query_embedding: List[float], query_text: str,
                       top_k: int = 5) -> List[Tuple[int, str, float, Optional[str]]]:
        """Enhanced search that prioritizes exact matches and improves ranking."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Special handling for drug/substance queries
                drug_keywords = ['drug', 'substance', 'test', 'testing', 'list']
                is_drug_query = any(keyword in query_text.lower() for keyword in drug_keywords)

                if is_drug_query:
                    # Prioritize numbered lists and content with multiple drug names
                    cur.execute(
                        """
                        SELECT id, content, 
                               (CASE 
                                   WHEN content LIKE %s AND content LIKE %s AND content LIKE %s THEN 0.1
                                   WHEN content LIKE %s OR content LIKE %s THEN 0.2
                                   WHEN (content ILIKE %s OR content ILIKE %s) AND content LIKE %s THEN 0.3
                                   ELSE 10.0
                               END) AS score,
                               source_file
                        FROM documents
                        WHERE content ILIKE %s OR content ILIKE %s OR content ILIKE %s
                        ORDER BY score ASC
                        LIMIT %s;
                        """,
                        ('%1. %', '%2. %', '%3. %', '%list of tests%', '%tests performed%',
                         '%drug%', '%substance%', '%1. %', '%drug%', '%substance%', '%test%', top_k)
                    )
                    rows = cur.fetchall()
                    drug_results = []
                    for r in rows:
                        try:
                            drug_results.append((int(r[0]), str(r[1]), float(r[2]), r[3]))
                        except (ValueError, TypeError):
                            # Handle Decimal or other numeric types
                            drug_results.append((int(r[0]), str(r[1]), float(str(r[2])), r[3]))

                    if drug_results:
                        return drug_results

                # First, try exact phrase matching
                exact_results = []
                if len(query_text.split()) > 1:
                    cur.execute(
                        """
                        SELECT id, content, 0.1 AS score, source_file
                        FROM documents
                        WHERE LOWER(content) LIKE LOWER(%s)
                        ORDER BY LENGTH(content) ASC
                        LIMIT %s;
                        """,
                        (f"%{query_text}%", top_k)
                    )
                    exact_results = [(int(r[0]), str(r[1]), float(r[2]), r[3]) for r in cur.fetchall()]

                if exact_results:
                    return exact_results

                # Then try individual keyword matching with better scoring
                terms = query_text.lower().split()
                if terms:
                    # Build a query that scores based on number of matching terms
                    conditions = []
                    params = []

                    for i, term in enumerate(terms):
                        conditions.append("(CASE WHEN LOWER(content) LIKE %s THEN 1 ELSE 0 END)")
                        params.append(f"%{term}%")

                    score_formula = " + ".join(conditions)
                    where_conditions = " OR ".join(["LOWER(content) LIKE %s" for _ in terms])

                    cur.execute(
                        f"""
                        SELECT id, content, 
                               (10.0 - ({score_formula})) AS score,
                               source_file
                        FROM documents
                        WHERE {where_conditions}
                        ORDER BY score ASC, LENGTH(content) ASC
                        LIMIT %s;
                        """,
                        params + params + [top_k]  # params twice: once for scoring, once for WHERE
                    )
                    keyword_results = [(int(r[0]), str(r[1]), float(r[2]), r[3]) for r in cur.fetchall()]

                    if keyword_results:
                        return keyword_results

                # Fallback to semantic search
                return self.search(query_embedding, top_k)

    def search_combined(self, query_embedding: List[float], query_text: str,
                       top_k: int = 5) -> List[Tuple[int, str, float, Optional[str]]]:
        """Combined semantic and keyword search with fallback."""
        # Try semantic search first
        semantic_results = self.search(query_embedding, top_k=top_k)

        # If semantic search returns poor results (high distances), try keyword search
        if semantic_results and semantic_results[0][2] > 0.8:  # High distance = poor match
            keyword_results = self.search_keyword(query_text, top_k=top_k)

            # Combine results, preferring keyword matches for simple terms
            combined = {}

            # Add keyword results with higher priority
            for doc_id, content, score, source_file in keyword_results:
                combined[doc_id] = (doc_id, content, score * 0.3, source_file)  # Lower score = better

            # Add semantic results
            for doc_id, content, score, source_file in semantic_results:
                if doc_id not in combined:
                    combined[doc_id] = (doc_id, content, score, source_file)

            # Sort by score and return top_k
            sorted_results = sorted(combined.values(), key=lambda x: x[2])
            return sorted_results[:top_k]

        return semantic_results

    def search_hybrid(self, query_embedding: List[float], query_text: str,
                     top_k: int = 5, alpha: float = 0.7) -> List[Tuple[int, str, float, Optional[str]]]:
        """Hybrid search combining semantic and text similarity."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Combine semantic similarity with text search
                cur.execute(
                    """
                    SELECT id, content, 
                           (%s * (1 - (embedding <-> %s::vector)) + 
                            %s * ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s))) AS score,
                           source_file
                    FROM documents
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (alpha, query_embedding, 1-alpha, query_text, query_text, top_k),
                )
                rows = cur.fetchall()
                return [(int(r[0]), str(r[1]), float(r[2]), r[3]) for r in rows]

    def count_documents(self) -> int:
        """Count total documents."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents;")
                return int(cur.fetchone()[0])

    def count_documents_by_source(self) -> List[Tuple[str, int]]:
        """Count documents grouped by source file."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source_file, COUNT(*) FROM documents GROUP BY source_file ORDER BY COUNT(*) DESC;"
                )
                return [(str(r[0]), int(r[1])) for r in cur.fetchall()]

    def delete_documents_by_source(self, source_file: str) -> int:
        """Delete all documents from a specific source file."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE source_file = %s;", (source_file,))
                return cur.rowcount

    def get_document_by_id(self, doc_id: int) -> Optional[Tuple[str, Optional[str]]]:
        """Get document content and source file by ID."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content, source_file FROM documents WHERE id = %s;",
                    (doc_id,)
                )
                row = cur.fetchone()
                return (row[0], row[1]) if row else None

    def close_pool(self):
        """Close the connection pool."""
        if self._connection_pool:
            self._connection_pool.closeall()
            self._connection_pool = None


_default_dao: Optional[VectorDAO] = None


def get_dao() -> VectorDAO:
    global _default_dao
    if _default_dao is None:
        _default_dao = VectorDAO()
        _default_dao.ensure_schema()
    return _default_dao
