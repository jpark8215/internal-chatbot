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
        print(f"\n🗄️  Search History Database Access")
        print("=" * 40)
        print("1. Show connection info")
        print("2. View recent queries")
        print("3. Export to JSON")
        print("4. Export to CSV")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
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
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please select 1-5.")

if __name__ == "__main__":
    print("🚀 Search History Database Access Utility")
    print("=" * 45)
    
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
        else:
            print(f"Usage: python {sys.argv[0]} [info|recent|json|csv] [limit]")
    else:
        # Interactive mode
        interactive_menu()