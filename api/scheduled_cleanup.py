"""
Scheduled cleanup service for automatic orphaned document removal.
Runs periodically to clean up documents that no longer exist in the filesystem.
"""

import time
import threading
from pathlib import Path
from typing import Optional

from .config import get_settings
from .file_cleanup import cleanup_orphaned_documents
from .logging_config import get_logger

logger = get_logger(__name__)


class ScheduledCleanupService:
    """Service that periodically cleans up orphaned documents."""

    def __init__(self, cleanup_interval: int = 3600):  # Default: 1 hour
        self.cleanup_interval = cleanup_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.settings = get_settings()

    def start(self):
        """Start the scheduled cleanup service."""
        if self.running:
            logger.warning("[cleanup-service] Service is already running")
            return False

        if not self.settings.auto_ingest_path:
            logger.warning("[cleanup-service] No auto-ingest path configured")
            return False

        base_path = Path(self.settings.auto_ingest_path)
        if not base_path.exists():
            logger.error(f"[cleanup-service] Auto-ingest path does not exist: {base_path}")
            return False

        self.running = True
        self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.thread.start()

        logger.info(f"[cleanup-service] Started scheduled cleanup (interval: {self.cleanup_interval}s)")
        return True

    def stop(self):
        """Stop the scheduled cleanup service."""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)  # Wait up to 5 seconds
        
        logger.info("[cleanup-service] Stopped scheduled cleanup")

    def _cleanup_loop(self):
        """Main cleanup loop that runs periodically."""
        # Wait a bit before first cleanup to let the system settle
        time.sleep(60)  # Wait 1 minute after startup
        
        while self.running:
            try:
                self._perform_cleanup()
                
                # Sleep in small intervals to allow for quick shutdown
                sleep_time = 0
                while sleep_time < self.cleanup_interval and self.running:
                    time.sleep(min(30, self.cleanup_interval - sleep_time))  # Check every 30s
                    sleep_time += 30
                    
            except Exception as e:
                logger.error(f"[cleanup-service] Error in cleanup loop: {e}")
                # Wait a bit before retrying
                time.sleep(300)  # Wait 5 minutes on error

    def _perform_cleanup(self):
        """Perform the actual cleanup operation."""
        try:
            base_path = Path(self.settings.auto_ingest_path)
            
            # Run cleanup
            removed_count, removed_files, cache_invalidated = cleanup_orphaned_documents(base_path)
            
            if removed_count > 0:
                logger.info(f"[cleanup-service] Cleaned up {removed_count} orphaned documents from {len(removed_files)} files")
                logger.info(f"[cleanup-service] Invalidated {cache_invalidated} cache entries")
                
                # Log the cleaned files for audit purposes
                for removed_file in removed_files[:5]:  # Log first 5
                    logger.info(f"[cleanup-service] Removed orphaned file: {Path(removed_file).name}")
                    
                if len(removed_files) > 5:
                    logger.info(f"[cleanup-service] ... and {len(removed_files) - 5} more files")
            else:
                logger.debug("[cleanup-service] No orphaned documents found")
                
        except Exception as e:
            logger.error(f"[cleanup-service] Failed to perform cleanup: {e}")


# Global instance
_cleanup_service: Optional[ScheduledCleanupService] = None


def start_scheduled_cleanup(cleanup_interval: int = 3600):
    """Start the scheduled cleanup service."""
    global _cleanup_service
    
    if _cleanup_service and _cleanup_service.running:
        logger.warning("[cleanup-service] Service is already running")
        return True
    
    _cleanup_service = ScheduledCleanupService(cleanup_interval)
    return _cleanup_service.start()


def stop_scheduled_cleanup():
    """Stop the scheduled cleanup service."""
    global _cleanup_service
    
    if _cleanup_service:
        _cleanup_service.stop()
        _cleanup_service = None


def is_scheduled_cleanup_active() -> bool:
    """Check if scheduled cleanup is active."""
    global _cleanup_service
    return _cleanup_service is not None and _cleanup_service.running


def get_cleanup_service_status() -> dict:
    """Get the status of the cleanup service."""
    global _cleanup_service
    
    if not _cleanup_service:
        return {
            "active": False,
            "interval": None,
            "message": "Service not started"
        }
    
    return {
        "active": _cleanup_service.running,
        "interval": _cleanup_service.cleanup_interval,
        "message": "Service running" if _cleanup_service.running else "Service stopped"
    }