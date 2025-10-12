#!/usr/bin/env python3
"""
Manual document ingestion script.
Use this if auto-ingest isn't working or you want to ingest specific files.
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.config import get_settings
from api.ingest_files import ingest_path


def manual_ingest():
    """Manually ingest documents."""
    print("📁 Manual Document Ingestion")
    print("=" * 40)
    
    settings = get_settings()
    
    # Check if auto-ingest path is configured
    if settings.auto_ingest_path:
        default_path = Path(settings.auto_ingest_path)
        print(f"Default path from config: {default_path}")
    else:
        default_path = None
        print("No default path configured")
    
    # Ask user for path
    while True:
        if default_path and default_path.exists():
            user_input = input(f"\nEnter path to ingest (or press Enter for default: {default_path}): ").strip()
            if not user_input:
                target_path = default_path
                break
            else:
                target_path = Path(user_input)
        else:
            user_input = input("\nEnter path to ingest: ").strip()
            if not user_input:
                print("❌ No path provided!")
                continue
            target_path = Path(user_input)
        
        if target_path.exists():
            break
        else:
            print(f"❌ Path does not exist: {target_path}")
    
    print(f"\n🔍 Scanning: {target_path}")
    
    # Find supported files
    supported_files = []
    if target_path.is_file():
        if target_path.suffix.lower() in {'.txt', '.md', '.pdf', '.docx'}:
            supported_files = [target_path]
    else:
        for ext in ['.txt', '.md', '.pdf', '.docx']:
            supported_files.extend(target_path.glob(f"**/*{ext}"))
    
    print(f"📄 Found {len(supported_files)} supported files:")
    for i, file_path in enumerate(supported_files[:10]):
        print(f"   {i+1}. {file_path.name}")
    if len(supported_files) > 10:
        print(f"   ... and {len(supported_files) - 10} more")
    
    if len(supported_files) == 0:
        print("❌ No supported files found!")
        print("💡 Supported formats: .txt, .md, .pdf, .docx")
        return False
    
    # Confirm ingestion
    confirm = input(f"\n🚀 Ingest {len(supported_files)} files? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Ingestion cancelled")
        return False
    
    # Perform ingestion
    print("\n🔄 Starting ingestion...")
    try:
        total_chunks = ingest_path(target_path)
        print("\n✅ SUCCESS!")
        print(f"   📊 Ingested {total_chunks} chunks from {len(supported_files)} files")
        
        # Show some stats
        from api.dao import get_dao
        dao = get_dao()
        total_docs = dao.count_documents()
        docs_by_source = dao.count_documents_by_source()
        
        print(f"   📈 Total documents in database: {total_docs}")
        print(f"   📁 Files in database: {len(docs_by_source)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
        return False


if __name__ == "__main__":
    success = manual_ingest()
    if success:
        print("\n💡 Next steps:")
        print("   1. Restart your FastAPI application")
        print("   2. Try asking questions - you should now get responses!")
    else:
        sys.exit(1)