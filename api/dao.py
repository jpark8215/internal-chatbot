from __future__ import annotations

import os
from typing import List, Optional, Tuple

import psycopg2
import psycopg2.extras

from .config import get_settings


class VectorDAO:
    def __init__(self):
        self.settings = get_settings()
        self._conn = None

    def _connect(self):
        if self._conn is not None:
            return
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
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True

    def ensure_schema(self) -> None:
        self._connect()
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS documents (
                  id SERIAL PRIMARY KEY,
                  content TEXT NOT NULL,
                  embedding vector({self.settings.embedding_dim})
                );
                """
            )

    def insert_document(self, content: str, embedding: List[float]) -> int:
        self._connect()
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (content, embedding) VALUES (%s, %s) RETURNING id;",
                (content, embedding),
            )
            new_id = cur.fetchone()[0]
            return new_id

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[int, str, float]]:
        """Return list of (id, content, distance) ordered by similarity (ASC)."""
        self._connect()
        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT id, content, (embedding <-> %s::vector) AS distance
                FROM documents
                ORDER BY embedding <-> %s::vector ASC
                LIMIT %s;
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()
            return [(int(r[0]), str(r[1]), float(r[2])) for r in rows]

    def count_documents(self) -> int:
        self._connect()
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents;")
            return int(cur.fetchone()[0])


_default_dao: Optional[VectorDAO] = None


def get_dao() -> VectorDAO:
    global _default_dao
    if _default_dao is None:
        _default_dao = VectorDAO()
        _default_dao.ensure_schema()
    return _default_dao
