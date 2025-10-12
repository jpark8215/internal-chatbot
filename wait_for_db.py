#!/usr/bin/env python3
"""
Database connection waiter for Docker startup.
Waits for the database to be ready before starting the application.
"""

import os
import sys
import time
import psycopg2
from urllib.parse import urlparse


def wait_for_database(max_attempts=30, delay=2):
    """Wait for database to be ready."""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Build from individual components
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        dbname = os.getenv('DB_NAME', 'internal_chatbot')
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'postgres')
        
        database_url = f"postgres://{user}:{password}@{host}:{port}/{dbname}"
    
    print(f"Waiting for database at {database_url.split('@')[1] if '@' in database_url else 'localhost'}...")
    
    for attempt in range(max_attempts):
        try:
            conn = psycopg2.connect(database_url)
            conn.close()
            print("Database is ready!")
            return True
        except psycopg2.OperationalError as e:
            if attempt < max_attempts - 1:
                print(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")
                time.sleep(delay)
            else:
                print(f"Database connection failed after {max_attempts} attempts: {e}")
                return False
    
    return False


if __name__ == "__main__":
    if not wait_for_database():
        sys.exit(1)
    print("Database connection successful!")
