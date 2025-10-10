import os
import time
import psycopg2


DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@db:5432/internal_chatbot")


def wait_for_db(max_retries=30, delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.close()
            print("Database reachable")
            return True
        except Exception as e:
            print(f"Waiting for DB (attempt {attempt}/{max_retries}): {e}")
            time.sleep(delay)
    return False


if __name__ == "__main__":
    ok = wait_for_db()
    if not ok:
        print("Failed to connect to database after retries. Exiting.")
        raise SystemExit(1)
