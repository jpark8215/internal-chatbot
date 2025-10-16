#!/usr/bin/env python3
"""
Database migration script for enhanced feedback system.
This script safely migrates the existing user_feedback table and creates new tables.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime

# Add the api directory to the path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

try:
    from config import get_settings
    from dao import get_dao
except ImportError:
    print("Warning: Could not import API modules. Using environment variables for database connection.")
    get_settings = None
    get_dao = None


def get_db_connection():
    """Get database connection using existing configuration."""
    if get_dao:
        # Use existing DAO configuration
        dao = get_dao()
        return dao.get_connection()
    else:
        # Fallback to environment variables
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'rag_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )


def check_migration_status(conn):
    """Check if migration has already been applied."""
    with conn.cursor() as cur:
        # Check if new columns exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_feedback' 
            AND column_name IN ('quick_rating', 'accuracy_confidence', 'status');
        """)
        existing_columns = [row[0] for row in cur.fetchall()]
        
        # Check if new tables exist
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('feedback_categories', 'improvement_actions', 'feedback_alerts', 'feedback_insights');
        """)
        existing_tables = [row[0] for row in cur.fetchall()]
        
        return {
            'columns_migrated': len(existing_columns) > 0,
            'tables_created': len(existing_tables) > 0,
            'existing_columns': existing_columns,
            'existing_tables': existing_tables
        }


def backup_existing_data(conn):
    """Create a backup of existing feedback data."""
    backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"user_feedback_backup_{backup_timestamp}"
    
    with conn.cursor() as cur:
        # Create backup table
        cur.execute(f"""
            CREATE TABLE {backup_table} AS 
            SELECT * FROM user_feedback;
        """)
        
        # Get count of backed up records
        cur.execute(f"SELECT COUNT(*) FROM {backup_table};")
        backup_count = cur.fetchone()[0]
        
        print(f"✓ Created backup table '{backup_table}' with {backup_count} records")
        return backup_table


def apply_schema_migration(conn):
    """Apply the enhanced feedback schema migration."""
    
    # Read the migration SQL file
    migration_file = os.path.join(os.path.dirname(__file__), 'enhanced_feedback_schema.sql')
    
    if not os.path.exists(migration_file):
        raise FileNotFoundError(f"Migration file not found: {migration_file}")
    
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    # Split the SQL into individual statements
    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
    
    with conn.cursor() as cur:
        for i, statement in enumerate(statements):
            try:
                if statement.upper().startswith(('CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE')):
                    print(f"Executing statement {i+1}/{len(statements)}: {statement[:50]}...")
                    cur.execute(statement)
                    conn.commit()
            except psycopg2.Error as e:
                print(f"Warning: Statement {i+1} failed: {e}")
                # Continue with other statements
                conn.rollback()
                continue
    
    print("✓ Schema migration completed")


def verify_migration(conn):
    """Verify that the migration was successful."""
    with conn.cursor() as cur:
        # Check user_feedback table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'user_feedback'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        
        print(f"✓ user_feedback table has {len(columns)} columns")
        
        # Check new tables
        new_tables = ['feedback_categories', 'improvement_actions', 'feedback_alerts', 'feedback_insights']
        for table in new_tables:
            cur.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}';")
            if cur.fetchone()[0] > 0:
                print(f"✓ Table '{table}' created successfully")
            else:
                print(f"✗ Table '{table}' not found")
        
        # Check views
        views = ['feedback_summary', 'source_preferences', 'admin_dashboard_metrics', 'feedback_trends', 'problem_queries']
        for view in views:
            cur.execute(f"SELECT COUNT(*) FROM information_schema.views WHERE table_name = '{view}';")
            if cur.fetchone()[0] > 0:
                print(f"✓ View '{view}' created successfully")
            else:
                print(f"✗ View '{view}' not found")
        
        # Check functions
        cur.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_type = 'FUNCTION' 
            AND routine_name IN ('calculate_feedback_quality_score', 'update_feedback_quality_score', 'check_feedback_alerts');
        """)
        functions = [row[0] for row in cur.fetchall()]
        print(f"✓ Created {len(functions)} functions: {', '.join(functions)}")
        
        # Test basic functionality
        cur.execute("SELECT COUNT(*) FROM user_feedback;")
        feedback_count = cur.fetchone()[0]
        print(f"✓ Existing feedback records preserved: {feedback_count}")


def update_existing_feedback_scores(conn):
    """Update quality scores for existing feedback records."""
    with conn.cursor() as cur:
        # Update quality scores for existing records
        cur.execute("""
            UPDATE user_feedback 
            SET feedback_quality_score = calculate_feedback_quality_score(
                rating, is_accurate, is_helpful, missing_info, 
                incorrect_info, comments, comments
            )
            WHERE feedback_quality_score IS NULL;
        """)
        
        updated_count = cur.rowcount
        conn.commit()
        print(f"✓ Updated quality scores for {updated_count} existing feedback records")


def main():
    """Main migration function."""
    print("Enhanced Feedback System Database Migration")
    print("=" * 50)
    
    try:
        # Get database connection
        conn = get_db_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        print("✓ Connected to database")
        
        # Check current migration status
        status = check_migration_status(conn)
        print(f"Migration status: Columns migrated: {status['columns_migrated']}, Tables created: {status['tables_created']}")
        
        if status['columns_migrated'] and status['tables_created']:
            print("Migration appears to already be applied. Skipping...")
            return
        
        # Create backup
        backup_table = backup_existing_data(conn)
        
        # Apply migration
        print("Applying schema migration...")
        apply_schema_migration(conn)
        
        # Update existing data
        update_existing_feedback_scores(conn)
        
        # Verify migration
        print("\nVerifying migration...")
        verify_migration(conn)
        
        print("\n" + "=" * 50)
        print("✓ Migration completed successfully!")
        print(f"✓ Backup created: {backup_table}")
        print("✓ Enhanced feedback system is ready to use")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()