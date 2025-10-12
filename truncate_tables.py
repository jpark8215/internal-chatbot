#!/usr/bin/env python3
"""Utility to truncate database tables with safety confirmations."""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def show_table_info():
    """Show current table information before truncation."""
    print("📊 Current Database Table Information")
    print("=" * 45)
    
    try:
        # Query history table
        from api.query_history_dao import get_query_history_dao
        query_dao = get_query_history_dao()
        query_count = len(query_dao.get_recent_queries(limit=10000))  # Get all
        
        print(f"📝 query_history table:")
        print(f"   Records: {query_count}")
        print(f"   Contains: Search queries, responses, timestamps, performance metrics")
        
        # Documents table
        from api.dao import get_dao
        doc_dao = get_dao()
        doc_count = doc_dao.count_documents()
        sources = doc_dao.count_documents_by_source()
        
        print(f"\n📄 documents table:")
        print(f"   Records: {doc_count}")
        print(f"   Contains: Document chunks, embeddings, source files")
        print(f"   Source files: {len(sources)}")
        for source, count in sources:
            filename = source.split('/')[-1].split('\\')[-1] if source else 'Unknown'
            print(f"     - {filename}: {count} chunks")
        
        return query_count, doc_count
        
    except Exception as e:
        print(f"❌ Failed to get table info: {e}")
        return 0, 0

def truncate_query_history():
    """Truncate the query_history table."""
    print("\n🗑️ Truncating query_history table...")
    
    try:
        from api.query_history_dao import get_query_history_dao
        dao = get_query_history_dao()
        
        with dao.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE query_history RESTART IDENTITY CASCADE;")
                conn.commit()
        
        print("✅ query_history table truncated successfully")
        print("   - All search history cleared")
        print("   - ID counter reset to 1")
        return True
        
    except Exception as e:
        print(f"❌ Failed to truncate query_history: {e}")
        return False

def truncate_documents():
    """Truncate the documents table."""
    print("\n🗑️ Truncating documents table...")
    
    try:
        from api.dao import get_dao
        dao = get_dao()
        
        with dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE documents RESTART IDENTITY CASCADE;")
                conn.commit()
        
        print("✅ documents table truncated successfully")
        print("   - All document chunks cleared")
        print("   - All embeddings cleared")
        print("   - ID counter reset to 1")
        print("   ⚠️  You'll need to re-ingest your documents!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to truncate documents: {e}")
        return False

def confirm_action(message):
    """Get user confirmation for destructive actions."""
    while True:
        response = input(f"\n{message} (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")

def truncate_all_tables():
    """Truncate all tables with confirmations."""
    print("🚨 DESTRUCTIVE OPERATION WARNING")
    print("=" * 40)
    print("This will permanently delete ALL data from the selected tables!")
    print("This action CANNOT be undone!")
    
    # Show current data
    query_count, doc_count = show_table_info()
    
    if query_count == 0 and doc_count == 0:
        print("\n✅ Tables are already empty - nothing to truncate")
        return
    
    print(f"\n📋 What will be deleted:")
    if query_count > 0:
        print(f"   - {query_count} search history records")
    if doc_count > 0:
        print(f"   - {doc_count} document chunks and embeddings")
    
    # Get confirmations
    tables_to_truncate = []
    
    if query_count > 0:
        if confirm_action("🗑️ Delete ALL search history?"):
            tables_to_truncate.append('query_history')
    
    if doc_count > 0:
        if confirm_action("🗑️ Delete ALL documents and embeddings?"):
            tables_to_truncate.append('documents')
    
    if not tables_to_truncate:
        print("\n✅ No tables selected for truncation")
        return
    
    # Final confirmation
    print(f"\n⚠️  FINAL CONFIRMATION")
    print(f"Tables to truncate: {', '.join(tables_to_truncate)}")
    
    if not confirm_action("🚨 Are you ABSOLUTELY SURE you want to proceed?"):
        print("\n✅ Operation cancelled")
        return
    
    # Perform truncations
    success_count = 0
    
    if 'query_history' in tables_to_truncate:
        if truncate_query_history():
            success_count += 1
    
    if 'documents' in tables_to_truncate:
        if truncate_documents():
            success_count += 1
    
    # Summary
    print(f"\n📊 Truncation Summary:")
    print(f"   Tables processed: {success_count}/{len(tables_to_truncate)}")
    
    if success_count == len(tables_to_truncate):
        print("   🎉 All selected tables truncated successfully!")
        
        if 'documents' in tables_to_truncate:
            print(f"\n💡 Next steps:")
            print(f"   1. Re-ingest your documents using the file watcher or manual ingestion")
            print(f"   2. Check /database-debug to verify document counts")
    else:
        print("   ⚠️  Some truncations failed - check errors above")

def interactive_menu():
    """Interactive menu for table truncation."""
    while True:
        print(f"\n🗑️  Database Table Truncation Utility")
        print("=" * 45)
        print("1. Show current table information")
        print("2. Truncate query_history table only")
        print("3. Truncate documents table only") 
        print("4. Truncate ALL tables")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == '1':
            show_table_info()
        elif choice == '2':
            query_count, _ = show_table_info()
            if query_count > 0:
                if confirm_action(f"🗑️ Delete {query_count} search history records?"):
                    truncate_query_history()
            else:
                print("✅ query_history table is already empty")
        elif choice == '3':
            _, doc_count = show_table_info()
            if doc_count > 0:
                if confirm_action(f"🗑️ Delete {doc_count} document chunks? (You'll need to re-ingest!)"):
                    truncate_documents()
            else:
                print("✅ documents table is already empty")
        elif choice == '4':
            truncate_all_tables()
        elif choice == '5':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please select 1-5.")

if __name__ == "__main__":
    print("🚨 Database Table Truncation Utility")
    print("=" * 40)
    print("⚠️  WARNING: This tool can permanently delete data!")
    
    if len(sys.argv) > 1:
        # Command line mode
        command = sys.argv[1].lower()
        if command == 'info':
            show_table_info()
        elif command == 'history':
            query_count, _ = show_table_info()
            if query_count > 0:
                if confirm_action(f"🗑️ Delete {query_count} search history records?"):
                    truncate_query_history()
        elif command == 'documents':
            _, doc_count = show_table_info()
            if doc_count > 0:
                if confirm_action(f"🗑️ Delete {doc_count} document chunks?"):
                    truncate_documents()
        elif command == 'all':
            truncate_all_tables()
        else:
            print(f"Usage: python {sys.argv[0]} [info|history|documents|all]")
    else:
        # Interactive mode
        interactive_menu()