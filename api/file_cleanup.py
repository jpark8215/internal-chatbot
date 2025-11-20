"""
File cleanup utilities for maintaining database sync with file system.
"""

import os
from pathlib import Path
from typing import List, Set, Tuple
from .dao import get_dao
from .logging_config import get_logger
from .ingest_files import SUPPORTED_EXTENSIONS

logger = get_logger(__name__)


def cleanup_orphaned_documents(base_path: Path) -> Tuple[int, List[str], int]:
    """
    Remove documents from database that no longer exist in the file system and invalidate related caches.
    
    Returns:
        Tuple of (documents_removed, list_of_removed_files, cache_entries_invalidated)
    """
    dao = get_dao()
    
    # Get all source files from database
    db_sources = dao.count_documents_by_source()
    db_source_files = {source_file for source_file, _ in db_sources if source_file}
    
    # Get all actual files in the directory
    actual_files = set()
    for ext in SUPPORTED_EXTENSIONS:
        try:
            actual_files.update(str(f.absolute()) for f in base_path.rglob(f'*{ext}'))
        except Exception as e:
            logger.warning(f"Error scanning for {ext} files: {e}")
    
    # Find orphaned files (in database but not on disk)
    orphaned_files = db_source_files - actual_files
    
    total_removed = 0
    removed_files = []
    total_cache_invalidated = 0
    
    logger.info(f"Found {len(orphaned_files)} orphaned files to clean up")
    
    for orphaned_file in orphaned_files:
        if orphaned_file:  # Skip None values
            try:
                # Remove from database
                removed_count = dao.delete_documents_by_source(orphaned_file)
                total_removed += removed_count
                removed_files.append(orphaned_file)
                
                # Invalidate related cache entries
                cache_invalidated = 0
                try:
                    from .response_cache import get_response_cache
                    response_cache = get_response_cache()
                    response_invalidated = response_cache.invalidate_by_source(orphaned_file)
                    cache_invalidated += response_invalidated
                except ImportError:
                    logger.debug("Response cache not available")
                except Exception as cache_error:
                    logger.warning(f"Failed to invalidate response cache for {orphaned_file}: {cache_error}")
                
                try:
                    from .query_result_cache import get_query_result_cache
                    query_cache = get_query_result_cache()
                    query_invalidated = query_cache.invalidate_by_source(orphaned_file)
                    cache_invalidated += query_invalidated
                except ImportError:
                    logger.debug("Query result cache not available")
                except Exception as cache_error:
                    logger.warning(f"Failed to invalidate query cache for {orphaned_file}: {cache_error}")
                
                total_cache_invalidated += cache_invalidated
                
                logger.info(f"Removed {removed_count} orphaned documents and invalidated {cache_invalidated} cache entries from: {orphaned_file}")
                    
            except Exception as e:
                logger.error(f"Failed to remove orphaned documents from {orphaned_file}: {e}")
    
    if total_removed > 0:
        logger.info(f"Cleanup completed: removed {total_removed} documents from {len(removed_files)} orphaned files")
    else:
        logger.info("No orphaned documents found - database is in sync with filesystem")
    
    return total_removed, removed_files, total_cache_invalidated


def sync_database_with_filesystem(base_path: Path) -> dict:
    """
    Comprehensive sync of database with file system.
    
    Returns:
        Dictionary with sync results
    """
    dao = get_dao()
    
    # Step 1: Clean up orphaned documents
    removed_count, removed_files, cache_invalidated = cleanup_orphaned_documents(base_path)
    
    # Step 2: Get current state
    current_db_sources = dao.count_documents_by_source()
    current_files = set()
    from .ingest_files import SUPPORTED_EXTENSIONS
    for ext in SUPPORTED_EXTENSIONS:
        current_files.update(str(f.absolute()) for f in base_path.rglob(f'*{ext}'))
    
    # Step 3: Find files that need re-ingestion (modified)
    files_needing_update = []
    for file_path_str in current_files:
        file_path = Path(file_path_str)
        if file_path.exists():
            # Check if file exists in database
            file_in_db = any(source == file_path_str for source, _ in current_db_sources)
            if file_in_db:
                # Check if file was modified (this is a simple check - could be enhanced)
                # For now, we'll just note files that exist in both
                continue
            else:
                files_needing_update.append(file_path_str)
    
    return {
        "orphaned_documents_removed": removed_count,
        "orphaned_files": removed_files,
        "files_needing_ingestion": files_needing_update,
        "current_db_files": len(current_db_sources),
        "current_filesystem_files": len(current_files)
    }


def get_database_file_status(base_path: Path) -> dict:
    """
    Get detailed status of database vs filesystem sync.
    """
    dao = get_dao()
    
    # Database state
    db_sources = dao.count_documents_by_source()
    db_files = {source: count for source, count in db_sources if source}
    
    # Filesystem state
    fs_files = {}
    from .ingest_files import SUPPORTED_EXTENSIONS
    for ext in SUPPORTED_EXTENSIONS:
        for file_path in base_path.rglob(f'*{ext}'):
            fs_files[str(file_path.absolute())] = {
                'size': file_path.stat().st_size,
                'modified': file_path.stat().st_mtime,
                'exists': True
            }
    
    # Analysis
    orphaned_in_db = set(db_files.keys()) - set(fs_files.keys())
    missing_from_db = set(fs_files.keys()) - set(db_files.keys())
    in_sync = set(db_files.keys()) & set(fs_files.keys())
    
    return {
        "database_files": db_files,
        "filesystem_files": {k: v for k, v in fs_files.items()},
        "orphaned_in_database": list(orphaned_in_db),
        "missing_from_database": list(missing_from_db),
        "synchronized_files": list(in_sync),
        "total_db_documents": sum(db_files.values()),
        "sync_status": "out_of_sync" if (orphaned_in_db or missing_from_db) else "synchronized"
    }