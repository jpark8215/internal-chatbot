#!/usr/bin/env python3
"""Quick database access utility for search history."""

import sys
from pathlib import Path
import json
import csv
from datetime import datetime

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def show_connection_info():
    """Show database connection information."""
    print("🔗 Database Connection Information")
    print("=" * 40)
    
    try:
        from api.config import get_settings
        settings = get_settings()
        
        print(f"Database URL: {settings.database_url}")
        print(f"Host: localhost")
        print(f"Port: 5432")
        print(f"Database: internal_chatbot")
        print(f"User: postgres")
        
        print(f"\n💡 Connect via psql:")
        print(f"   psql -h localhost -p 5432 -U postgres -d internal_chatbot")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get connection info: {e}")
        return False

def export_to_json(filename="search_history.json", limit=100):
    """Export search history to JSON file."""
    print(f"\n📄 Exporting to JSON: {filename}")
    
    try:
        from api.query_history_dao import get_query_history_dao
        dao = get_query_history_dao()
        
        queries = dao.get_recent_queries(limit=limit)
        
        # Convert to JSON-serializable format
        data = []
        for q in queries:
            data.append({
                'id': q.id,
                'session_id': q.session_id,
                'created_at': q.created_at.isoformat() if q.created_at else None,
                'query_text': q.query_text,
                'response_text': q.response_text,
                'sources_used': q.sources_used,
                'search_type': q.search_type,
                'response_time_ms': q.response_time_ms,
                'model_used': q.model_used,
                'success': q.success,
                'error_message': q.error_message
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(data)} queries to {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def export_to_csv(filename="search_history.csv", limit=100):
    """Export search history to CSV file."""
    print(f"\n📊 Exporting to CSV: {filename}")
    
    try:
        from api.query_history_dao import get_query_history_dao
        dao = get_query_history_dao()
        
        queries = dao.get_recent_queries(limit=limit)
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'ID', 'Created At', 'Query Text', 'Response Text', 
                'Success', 'Response Time (ms)', 'Model Used', 
                'Search Type', 'Sources Count'
            ])
            
            # Write data
            for q in queries:
                sources_count = len(q.sources_used) if q.sources_used else 0
                writer.writerow([
                    q.id,
                    q.created_at.isoformat() if q.created_at else '',
                    q.query_text,
                    q.response_text or '',
                    q.success,
                    q.response_time_ms or 0,
                    q.model_used or '',
                    q.search_type or '',
                    sources_count
                ])
        
        print(f"✅ Exported {len(queries)} queries to {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def show_recent_queries(limit=5):
    """Show recent queries in a readable format."""
    print(f"\n📝 Recent Queries (Last {limit})")
    print("=" * 50)
    
    try:
        from api.query_history_dao import get_query_history_dao
        dao = get_query_history_dao()
        
        queries = dao.get_recent_queries(limit=limit)
        
        for i, q in enumerate(queries, 1):
            print(f"\n{i}. Query ID: {q.id}")
            print(f"   Time: {q.created_at}")
            print(f"   Query: \"{q.query_text}\"")
            print(f"   Success: {'✅' if q.success else '❌'}")
            print(f"   Response Time: {q.response_time_ms}ms")
            if q.sources_used:
                print(f"   Sources: {len(q.sources_used)} documents")
            if q.response_text:
                preview = q.response_text[:100] + "..." if len(q.response_text) > 100 else q.response_text
                print(f"   Response: {preview}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to show queries: {e}")
        return False

def interactive_menu():
    """Interactive menu for database access."""
    while True:
        print(f"\n🗄️  Database Access Utility")
        print("=" * 40)
        print("SEARCH HISTORY:")
        print("1. Show connection info")
        print("2. View recent queries")
        print("3. Export queries to JSON")
        print("4. Export queries to CSV")
        print("\nFEEDBACK DATA:")
        print("5. Show feedback statistics")
        print("6. View recent feedback")
        print("7. Show feedback by rating")
        print("8. Search feedback")
        print("9. Export feedback to JSON")
        print("10. Export feedback to CSV")
        print("\nQUERY ANALYTICS:")
        print("11. Show query analytics")
        print("12. Show query history table info")
        print("13. Test analytics API")
        print("\nDATABASE INFO:")
        print("14. Show all tables")
        print("\nTEST DATA:")
        print("15. Create test feedback entries")
        print("\nDOCUMENT MANAGEMENT:")
        print("16. Check for orphaned documents")
        print("17. Cleanup orphaned documents")
        print("\n18. Exit")
        
        choice = input("\nSelect option (1-18): ").strip()
        
        if choice == '1':
            show_connection_info()
        elif choice == '2':
            limit = input("Number of queries to show (default 5): ").strip()
            limit = int(limit) if limit.isdigit() else 5
            show_recent_queries(limit)
        elif choice == '3':
            limit = input("Number of queries to export (default 100): ").strip()
            limit = int(limit) if limit.isdigit() else 100
            export_to_json(limit=limit)
        elif choice == '4':
            limit = input("Number of queries to export (default 100): ").strip()
            limit = int(limit) if limit.isdigit() else 100
            export_to_csv(limit=limit)
        elif choice == '5':
            days = input("Number of days for stats (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            show_feedback_stats(days)
        elif choice == '6':
            limit = input("Number of feedback entries to show (default 10): ").strip()
            limit = int(limit) if limit.isdigit() else 10
            show_recent_feedback(limit)
        elif choice == '7':
            rating = input("Show specific rating (1-5) or press Enter for distribution: ").strip()
            rating = int(rating) if rating.isdigit() and 1 <= int(rating) <= 5 else None
            show_feedback_by_rating(rating)
        elif choice == '8':
            search_term = input("Enter search term: ").strip()
            if search_term:
                limit = input("Number of results to show (default 20): ").strip()
                limit = int(limit) if limit.isdigit() else 20
                search_feedback(search_term, limit)
            else:
                print("❌ Search term cannot be empty.")
        elif choice == '9':
            limit = input("Number of feedback entries to export (default 1000): ").strip()
            limit = int(limit) if limit.isdigit() else 1000
            export_feedback_to_json(limit=limit)
        elif choice == '10':
            limit = input("Number of feedback entries to export (default 1000): ").strip()
            limit = int(limit) if limit.isdigit() else 1000
            export_feedback_to_csv(limit=limit)
        elif choice == '11':
            days = input("Number of days for analytics (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            show_query_analytics(days)
        elif choice == '12':
            show_query_history_table_info()
        elif choice == '13':
            test_analytics_api()
        elif choice == '14':
            show_all_tables()
        elif choice == '15':
            create_test_feedback()
        elif choice == '16':
            check_orphaned_documents()
        elif choice == '17':
            cleanup_orphaned_documents()
        elif choice == '18':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please select 1-18.")

if __name__ == "__main__":
    print("🚀 Database Access Utility")
    print("=" * 35)
    
    if len(sys.argv) > 1:
        # Command line mode
        command = sys.argv[1].lower()
        if command == 'info':
            show_connection_info()
        elif command == 'recent':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            show_recent_queries(limit)
        elif command == 'json':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            export_to_json(limit=limit)
        elif command == 'csv':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            export_to_csv(limit=limit)
        elif command == 'feedback-stats':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            show_feedback_stats(days)
        elif command == 'feedback-recent':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            show_recent_feedback(limit)
        elif command == 'feedback-search':
            if len(sys.argv) > 2:
                search_term = sys.argv[2]
                limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
                search_feedback(search_term, limit)
            else:
                print("Usage: python quick_db_access.py feedback-search <search_term> [limit]")
        elif command == 'feedback-json':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            export_feedback_to_json(limit=limit)
        elif command == 'feedback-csv':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            export_feedback_to_csv(limit=limit)
        elif command == 'analytics':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            show_query_analytics(days)
        elif command == 'table-info':
            show_query_history_table_info()
        elif command == 'test-api':
            test_analytics_api()
        else:
            print(f"Usage: python {sys.argv[0]} [command] [options]")
            print("Commands:")
            print("  info                    - Show database connection info")
            print("  recent [limit]          - Show recent queries")
            print("  json [limit]            - Export queries to JSON")
            print("  csv [limit]             - Export queries to CSV")
            print("  feedback-stats [days]   - Show feedback statistics")
            print("  feedback-recent [limit] - Show recent feedback")
            print("  feedback-search <term>  - Search feedback")
            print("  feedback-json [limit]   - Export feedback to JSON")
            print("  feedback-csv [limit]    - Export feedback to CSV")
            print("  analytics [days]        - Show query analytics")
            print("  table-info              - Show query history table info")
            print("  test-api                - Test analytics API functionality")
    else:
        # Interactive mode
        interactive_menu()
#
 ============================================================================
# FEEDBACK DATA QUERIES
# ============================================================================

def show_feedback_stats(days=30):
    """Show feedback statistics for the specified number of days."""
    print(f"\n📊 Feedback Statistics (Last {days} days)")
    print("=" * 50)
    
    try:
        from api.feedback_clean import get_clean_feedback_dao
        feedback_dao = get_clean_feedback_dao()
        
        stats = feedback_dao.get_stats(days)
        
        if 'error' in stats:
            print(f"❌ Error: {stats['error']}")
            return False
        
        print(f"Total Feedback: {stats.get('total_feedback', 0)}")
        print(f"Average Rating: {stats.get('avg_rating', 0):.2f}/5")
        print(f"Accurate Responses: {stats.get('accurate_count', 0)} ({stats.get('accuracy_rate', 0):.1f}%)")
        print(f"Helpful Responses: {stats.get('helpful_count', 0)} ({stats.get('helpfulness_rate', 0):.1f}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get feedback stats: {e}")
        return False

def show_recent_feedback(limit=10):
    """Show recent feedback entries."""
    print(f"\n📝 Recent Feedback (Last {limit} entries)")
    print("=" * 60)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id, created_at, query_text, rating, 
                        is_accurate, is_helpful, comments
                    FROM user_feedback 
                    ORDER BY created_at DESC 
                    LIMIT %s;
                """, (limit,))
                
                rows = cur.fetchall()
                
                if not rows:
                    print("No feedback found.")
                    return True
                
                for row in rows:
                    id, created_at, query_text, rating, is_accurate, is_helpful, comments = row
                    
                    print(f"\n📋 ID: {id}")
                    print(f"   Date: {created_at}")
                    print(f"   Query: {query_text[:100]}{'...' if len(query_text) > 100 else ''}")
                    print(f"   Rating: {rating}/5" if rating else "   Rating: Not rated")
                    print(f"   Accurate: {'✅' if is_accurate else '❌' if is_accurate is False else '❓'}")
                    print(f"   Helpful: {'✅' if is_helpful else '❌' if is_helpful is False else '❓'}")
                    if comments:
                        print(f"   Comments: {comments[:150]}{'...' if len(comments) > 150 else ''}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get recent feedback: {e}")
        return False

def show_feedback_by_rating(rating=None):
    """Show feedback filtered by rating."""
    if rating:
        print(f"\n⭐ Feedback with {rating}-star rating")
    else:
        print(f"\n⭐ Feedback by Rating Distribution")
    print("=" * 50)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                if rating:
                    # Show specific rating
                    cur.execute("""
                        SELECT 
                            id, created_at, query_text, comments
                        FROM user_feedback 
                        WHERE rating = %s
                        ORDER BY created_at DESC 
                        LIMIT 20;
                    """, (rating,))
                    
                    rows = cur.fetchall()
                    
                    if not rows:
                        print(f"No {rating}-star feedback found.")
                        return True
                    
                    for row in rows:
                        id, created_at, query_text, comments = row
                        print(f"\n📋 ID: {id} | {created_at}")
                        print(f"   Query: {query_text[:100]}{'...' if len(query_text) > 100 else ''}")
                        if comments:
                            print(f"   Comments: {comments[:150]}{'...' if len(comments) > 150 else ''}")
                else:
                    # Show rating distribution
                    cur.execute("""
                        SELECT 
                            rating, COUNT(*) as count,
                            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
                        FROM user_feedback 
                        WHERE rating IS NOT NULL
                        GROUP BY rating 
                        ORDER BY rating DESC;
                    """)
                    
                    rows = cur.fetchall()
                    
                    if not rows:
                        print("No rated feedback found.")
                        return True
                    
                    print("Rating Distribution:")
                    for rating, count, percentage in rows:
                        stars = "⭐" * rating
                        print(f"   {stars} ({rating}/5): {count} responses ({percentage}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get feedback by rating: {e}")
        return False

def export_feedback_to_json(filename="feedback_data.json", limit=1000):
    """Export feedback data to JSON file."""
    print(f"\n📄 Exporting feedback to JSON: {filename}")
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id, created_at, query_text, response_text, rating,
                        is_accurate, is_helpful, missing_info, incorrect_info,
                        comments, user_session, sources_used, search_strategy
                    FROM user_feedback 
                    ORDER BY created_at DESC 
                    LIMIT %s;
                """, (limit,))
                
                rows = cur.fetchall()
                
                # Convert to JSON-serializable format
                data = []
                for row in rows:
                    data.append({
                        'id': row[0],
                        'created_at': row[1].isoformat() if row[1] else None,
                        'query_text': row[2],
                        'response_text': row[3],
                        'rating': row[4],
                        'is_accurate': row[5],
                        'is_helpful': row[6],
                        'missing_info': row[7],
                        'incorrect_info': row[8],
                        'comments': row[9],
                        'user_session': row[10],
                        'sources_used': row[11],
                        'search_strategy': row[12]
                    })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(data)} feedback entries to {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def export_feedback_to_csv(filename="feedback_data.csv", limit=1000):
    """Export feedback data to CSV file."""
    print(f"\n📊 Exporting feedback to CSV: {filename}")
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id, created_at, query_text, response_text, rating,
                        is_accurate, is_helpful, missing_info, incorrect_info,
                        comments, user_session
                    FROM user_feedback 
                    ORDER BY created_at DESC 
                    LIMIT %s;
                """, (limit,))
                
                rows = cur.fetchall()
                
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    writer.writerow([
                        'ID', 'Created At', 'Query Text', 'Response Text', 'Rating',
                        'Is Accurate', 'Is Helpful', 'Missing Info', 'Incorrect Info',
                        'Comments', 'User Session'
                    ])
                    
                    # Write data
                    for row in rows:
                        writer.writerow([
                            row[0],  # id
                            row[1].isoformat() if row[1] else '',  # created_at
                            row[2],  # query_text
                            row[3][:500] if row[3] else '',  # response_text (truncated)
                            row[4],  # rating
                            row[5],  # is_accurate
                            row[6],  # is_helpful
                            row[7],  # missing_info
                            row[8],  # incorrect_info
                            row[9],  # comments
                            row[10]  # user_session
                        ])
        
        print(f"✅ Exported {len(rows)} feedback entries to {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def search_feedback(search_term, limit=20):
    """Search feedback by query text or comments."""
    print(f"\n🔍 Searching feedback for: '{search_term}'")
    print("=" * 60)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id, created_at, query_text, rating, comments
                    FROM user_feedback 
                    WHERE 
                        query_text ILIKE %s 
                        OR comments ILIKE %s
                        OR response_text ILIKE %s
                    ORDER BY created_at DESC 
                    LIMIT %s;
                """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', limit))
                
                rows = cur.fetchall()
                
                if not rows:
                    print(f"No feedback found containing '{search_term}'.")
                    return True
                
                print(f"Found {len(rows)} matching feedback entries:")
                
                for row in rows:
                    id, created_at, query_text, rating, comments = row
                    
                    print(f"\n📋 ID: {id} | {created_at}")
                    print(f"   Rating: {rating}/5" if rating else "   Rating: Not rated")
                    print(f"   Query: {query_text[:150]}{'...' if len(query_text) > 150 else ''}")
                    if comments:
                        print(f"   Comments: {comments[:150]}{'...' if len(comments) > 150 else ''}")
        
        return True
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return False
#
 ============================================================================
# QUERY ANALYTICS FUNCTIONS
# ============================================================================

def show_query_analytics(days=30):
    """Show query analytics for the specified number of days."""
    print(f"\n📊 Query Analytics (Last {days} days)")
    print("=" * 50)
    
    try:
        from api.query_history_dao import get_query_history_dao
        query_dao = get_query_history_dao()
        
        analytics = query_dao.get_query_analytics(days)
        usage_stats = query_dao.get_usage_stats(days)
        
        print("📈 Usage Statistics:")
        print(f"   Total Queries: {usage_stats.get('total_queries', 0)}")
        print(f"   Unique Sessions: {usage_stats.get('unique_sessions', 0)}")
        print(f"   Average Response Time: {usage_stats.get('avg_response_time', 0):.2f}ms")
        print(f"   Successful Queries: {usage_stats.get('successful_queries', 0)}")
        print(f"   Failed Queries: {usage_stats.get('failed_queries', 0)}")
        print(f"   Success Rate: {usage_stats.get('success_rate', 0):.1f}%")
        
        print(f"\n🔍 Top Queries:")
        if not analytics:
            print("   No query data found.")
        else:
            for i, query in enumerate(analytics[:10], 1):
                print(f"\n   {i}. Query: {query['query_text'][:100]}{'...' if len(query['query_text']) > 100 else ''}")
                print(f"      Count: {query['query_count']}")
                print(f"      Avg Response Time: {query['avg_response_time']:.2f}ms")
                print(f"      Success Rate: {query['success_count']}/{query['query_count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get query analytics: {e}")
        return False

def show_query_history_table_info():
    """Show information about the query_history table."""
    print(f"\n🗄️  Query History Table Information")
    print("=" * 50)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'query_history'
                    );
                """)
                
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    print("❌ query_history table does not exist!")
                    return False
                
                print("✅ query_history table exists")
                
                # Get table structure
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'query_history'
                    ORDER BY ordinal_position;
                """)
                
                columns = cur.fetchall()
                print(f"\n📋 Table Structure ({len(columns)} columns):")
                for col_name, data_type, is_nullable in columns:
                    nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                    print(f"   {col_name}: {data_type} ({nullable})")
                
                # Get row count
                cur.execute("SELECT COUNT(*) FROM query_history;")
                total_rows = cur.fetchone()[0]
                print(f"\n📊 Total Records: {total_rows}")
                
                if total_rows > 0:
                    # Get date range
                    cur.execute("""
                        SELECT 
                            MIN(created_at) as earliest,
                            MAX(created_at) as latest
                        FROM query_history;
                    """)
                    earliest, latest = cur.fetchone()
                    print(f"   Date Range: {earliest} to {latest}")
                    
                    # Get recent activity
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM query_history 
                        WHERE created_at >= NOW() - INTERVAL '7 days';
                    """)
                    recent_count = cur.fetchone()[0]
                    print(f"   Recent (7 days): {recent_count} queries")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get table info: {e}")
        return False

def test_analytics_api():
    """Test the analytics API endpoint functionality."""
    print(f"\n🧪 Testing Analytics API")
    print("=" * 40)
    
    try:
        from api.query_history_dao import get_query_history_dao
        
        print("1. Testing query_history_dao import... ✅")
        
        query_dao = get_query_history_dao()
        print("2. Testing DAO initialization... ✅")
        
        # Test get_usage_stats
        usage_stats = query_dao.get_usage_stats(30)
        print("3. Testing get_usage_stats... ✅")
        print(f"   Result: {usage_stats}")
        
        # Test get_query_analytics
        analytics = query_dao.get_query_analytics(30)
        print("4. Testing get_query_analytics... ✅")
        print(f"   Result count: {len(analytics)} queries")
        
        if analytics:
            print(f"   Sample query: {analytics[0]['query_text'][:50]}...")
        
        print("\n✅ All analytics API components working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Analytics API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
def sh
ow_all_tables():
    """Show all tables in the database."""
    print(f"\n🗄️  Database Tables")
    print("=" * 40)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                
                tables = cur.fetchall()
                
                if not tables:
                    print("No tables found.")
                    return True
                
                print(f"Found {len(tables)} tables:")
                for table in tables:
                    table_name = table[0]
                    
                    # Get row count for each table
                    cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                    count = cur.fetchone()[0]
                    
                    print(f"   📋 {table_name}: {count} records")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get tables: {e}")
        return False

def create_test_feedback():
    """Create some test feedback entries to verify the system works with real data."""
    print(f"\n🧪 Creating Test Feedback Entries")
    print("=" * 45)
    
    try:
        from api.feedback_clean import get_clean_feedback_dao, SimpleFeedback
        feedback_dao = get_clean_feedback_dao()
        
        # Create a few test feedback entries
        test_feedback = [
            {
                "query_text": "How do I apply for the program?",
                "response_text": "To apply for the program, you need to complete the online application form.",
                "rating": 5,
                "is_accurate": True,
                "is_helpful": True,
                "comments": "Very helpful and clear instructions!"
            },
            {
                "query_text": "What are the eligibility requirements?",
                "response_text": "The eligibility requirements include being 18 years or older and having completed high school.",
                "rating": 4,
                "is_accurate": True,
                "is_helpful": True,
                "comments": "Good information, could use more details."
            },
            {
                "query_text": "When is the deadline?",
                "response_text": "The deadline for applications is December 31st.",
                "rating": 3,
                "is_accurate": False,
                "is_helpful": False,
                "comments": "The deadline information seems outdated.",
                "incorrect_info": "The deadline mentioned is from last year."
            }
        ]
        
        created_count = 0
        for feedback_data in test_feedback:
            try:
                feedback = SimpleFeedback(
                    query_text=feedback_data["query_text"],
                    response_text=feedback_data["response_text"],
                    rating=feedback_data.get("rating"),
                    is_accurate=feedback_data.get("is_accurate"),
                    is_helpful=feedback_data.get("is_helpful"),
                    comments=feedback_data.get("comments"),
                    incorrect_info=feedback_data.get("incorrect_info"),
                    user_session=f"test_session_{created_count + 1}"
                )
                
                feedback_id = feedback_dao.save_feedback(feedback)
                print(f"✅ Created feedback entry {feedback_id}: {feedback_data['query_text'][:50]}...")
                created_count += 1
                
            except Exception as e:
                print(f"❌ Failed to create feedback entry: {e}")
        
        print(f"\n🎉 Successfully created {created_count} test feedback entries!")
        
        # Show updated stats
        print(f"\n📊 Updated Feedback Statistics:")
        stats = feedback_dao.get_stats(30)
        print(f"   Total Feedback: {stats.get('total_feedback', 0)}")
        print(f"   Average Rating: {stats.get('avg_rating', 0):.2f}/5")
        print(f"   Positive Feedback: {stats.get('positive_feedback', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create test feedback: {e}")
        import traceback
        traceback.print_exc()
        return Falsedef check_or
phaned_documents():
    """Check for documents in database whose source files no longer exist."""
    print(f"\n🔍 Checking for Orphaned Documents")
    print("=" * 45)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        # Get all unique source files from database
        source_files = dao.count_documents_by_source()
        
        if not source_files:
            print("No documents found in database.")
            return True
        
        orphaned_files = []
        existing_files = []
        total_orphaned_chunks = 0
        
        print(f"Checking {len(source_files)} source files...")
        
        for source_file, chunk_count in source_files:
            if source_file:
                try:
                    file_path = Path(source_file)
                    if file_path.exists():
                        existing_files.append((source_file, chunk_count))
                        print(f"✅ {source_file} ({chunk_count} chunks)")
                    else:
                        orphaned_files.append((source_file, chunk_count))
                        total_orphaned_chunks += chunk_count
                        print(f"❌ {source_file} ({chunk_count} chunks) - FILE NOT FOUND")
                except Exception as e:
                    orphaned_files.append((source_file, chunk_count))
                    total_orphaned_chunks += chunk_count
                    print(f"⚠️  {source_file} ({chunk_count} chunks) - ERROR: {e}")
        
        print(f"\n📊 Summary:")
        print(f"   Existing files: {len(existing_files)}")
        print(f"   Orphaned files: {len(orphaned_files)}")
        print(f"   Total orphaned chunks: {total_orphaned_chunks}")
        
        if orphaned_files:
            print(f"\n🧹 Orphaned Files (should be cleaned up):")
            for source_file, chunk_count in orphaned_files:
                print(f"   - {source_file} ({chunk_count} chunks)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to check orphaned documents: {e}")
        return False

def cleanup_orphaned_documents():
    """Remove documents from database whose source files no longer exist."""
    print(f"\n🧹 Cleaning Up Orphaned Documents")
    print("=" * 45)
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        # Get all unique source files from database
        source_files = dao.count_documents_by_source()
        
        if not source_files:
            print("No documents found in database.")
            return True
        
        orphaned_files = []
        
        for source_file, chunk_count in source_files:
            if source_file:
                try:
                    file_path = Path(source_file)
                    if not file_path.exists():
                        orphaned_files.append((source_file, chunk_count))
                except Exception:
                    orphaned_files.append((source_file, chunk_count))
        
        if not orphaned_files:
            print("✅ No orphaned documents found. Database is clean!")
            return True
        
        print(f"Found {len(orphaned_files)} orphaned files:")
        total_chunks = 0
        for source_file, chunk_count in orphaned_files:
            print(f"   - {source_file} ({chunk_count} chunks)")
            total_chunks += chunk_count
        
        print(f"\nTotal chunks to be deleted: {total_chunks}")
        
        confirm = input(f"\n⚠️  Are you sure you want to delete {total_chunks} chunks from {len(orphaned_files)} files? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("❌ Cleanup cancelled.")
            return True
        
        deleted_total = 0
        for source_file, expected_count in orphaned_files:
            try:
                deleted_count = dao.delete_documents_by_source(source_file)
                print(f"✅ Deleted {deleted_count} chunks from {source_file}")
                deleted_total += deleted_count
            except Exception as e:
                print(f"❌ Failed to delete {source_file}: {e}")
        
        print(f"\n🎉 Cleanup complete! Deleted {deleted_total} orphaned chunks.")
        return True
        
    except Exception as e:
        print(f"❌ Failed to cleanup orphaned documents: {e}")
        return False