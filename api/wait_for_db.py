"""Simple helper to wait for the Postgres database to accept connections."""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict

import psycopg2
from psycopg2 import OperationalError


def _build_connection_args() -> Dict[str, Any]:
    """Prepare connection parameters from environment variables."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return {"dsn": database_url}

    return {
        "host": os.getenv("DB_HOST", "db"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "internal_chatbot"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
    }


def wait_for_db(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    """Attempt to connect to the database until it is ready or we give up."""
    conn_args = _build_connection_args()

    for attempt in range(1, max_attempts + 1):
        try:
            if "dsn" in conn_args:
                connection = psycopg2.connect(conn_args["dsn"], connect_timeout=5)
            else:
                connection = psycopg2.connect(connect_timeout=5, **conn_args)

            connection.close()
            print("Database connection established.", flush=True)
            return
        except OperationalError as exc:  # pragma: no cover - executed at runtime only
            print(
                f"Attempt {attempt}/{max_attempts}: database not ready ({exc}).",
                flush=True,
            )
            if attempt == max_attempts:
                print("Giving up waiting for the database.", flush=True)
                raise SystemExit(1)
            time.sleep(delay_seconds)


if __name__ == "__main__":
    max_attempts = int(os.getenv("DB_WAIT_MAX_ATTEMPTS", "30"))
    delay_seconds = float(os.getenv("DB_WAIT_DELAY", "2"))
    wait_for_db(max_attempts=max_attempts, delay_seconds=delay_seconds)
