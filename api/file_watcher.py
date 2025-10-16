"""
File watcher for automatic document ingestion.
Monitors the auto-ingest directory for new files and ingests them automatically.
"""

import time
import threading
from pathlib import Path
from typing import Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import get_settings
from .dao import get_dao
from .ingest_files import ingest_path
from .logging_config import get_logger

logger = get_logger(__name__)


class DocumentFileHandler(FileSystemEventHandler):
    """Handle file system events for document ingestion."""

    def __init__(self):
        self.settings = get_settings()
        self.supported_extensions = {'.txt', '.md', '.pdf', '.docx'}
        self.processing_files: Set[str] = set()
        self.processing_lock = threading.Lock()

    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            self._process_file(Path(event.src_path))

    def on_moved(self, event):
        """Handle file move events (like drag & drop)."""
        if not event.is_directory:
            # Handle the old file as deleted
            self._handle_file_deletion(Path(event.src_path))
            # Handle the new file as created
            self._process_file(Path(event.dest_path))

    def on_deleted(self, event):
        """Handle file deletion events."""
        if not event.is_directory:
            self._handle_file_deletion(Path(event.src_path))

    def _handle_file_deletion(self, file_path: Path):
        """Handle deletion of a file by removing its documents from the database."""
        # Check if it was a supported file type
        if file_path.suffix.lower() not in self.supported_extensions:
            return

        try:
            dao = get_dao()
            source_file = str(file_path.absolute())
            deleted_count = dao.delete_documents_by_source(source_file)
            
            if deleted_count > 0:
                logger.info(f"[file-watcher] Removed {deleted_count} chunks for deleted file: {file_path}")
            else:
                logger.debug(f"[file-watcher] No chunks found for deleted file: {file_path}")
                
        except Exception as e:
            logger.error(f"[file-watcher] Failed to handle deletion of {file_path}: {e}")

    def _process_file(self, file_path: Path):
        """Process a new file for ingestion."""
        # Check if it's a supported file type
        if file_path.suffix.lower() not in self.supported_extensions:
            logger.debug(f"Ignoring unsupported file: {file_path}")
            return

        # Avoid processing the same file multiple times
        file_str = str(file_path)
        with self.processing_lock:
            if file_str in self.processing_files:
                return
            self.processing_files.add(file_str)

        try:
            # Wait a moment for file to be fully written
            time.sleep(2)

            if not file_path.exists():
                logger.warning(f"File disappeared before processing: {file_path}")
                return

            logger.info(f"[file-watcher] New file detected: {file_path.name}")

            # Check if file is already ingested
            dao = get_dao()
            docs_by_source = dao.count_documents_by_source()
            existing_sources = {source for source, count in docs_by_source}

            # Check both absolute path and filename
            abs_path = str(file_path.absolute())
            filename = file_path.name

            if abs_path in existing_sources or filename in existing_sources:
                logger.info(f"[file-watcher] File already ingested: {filename}")
                return

            # Ingest the new file
            chunks_ingested = ingest_path(file_path)
            logger.info(f"[file-watcher] Successfully ingested {chunks_ingested} chunks from {filename}")

        except Exception as e:
            logger.error(f"[file-watcher] Failed to ingest {file_path}: {e}")
        finally:
            # Remove from processing set
            with self.processing_lock:
                self.processing_files.discard(file_str)


class FileWatcher:
    """File watcher for automatic document ingestion."""

    def __init__(self):
        self.settings = get_settings()
        self.observer: Optional[Observer] = None
        self.handler: Optional[DocumentFileHandler] = None
        self.running = False

    def start(self):
        """Start watching for file changes."""
        if not self.settings.auto_ingest_path:
            logger.warning("[file-watcher] No auto-ingest path configured")
            return False

        watch_path = Path(self.settings.auto_ingest_path)
        if not watch_path.exists():
            logger.error(f"[file-watcher] Watch path does not exist: {watch_path}")
            return False

        try:
            self.handler = DocumentFileHandler()
            self.observer = Observer()
            self.observer.schedule(self.handler, str(watch_path), recursive=True)
            self.observer.start()
            self.running = True

            logger.info(f"[file-watcher] Started watching: {watch_path}")
            return True

        except Exception as e:
            logger.error(f"[file-watcher] Failed to start: {e}")
            return False

    def stop(self):
        """Stop watching for file changes."""
        if self.observer and self.running:
            self.observer.stop()
            self.observer.join()
            self.running = False
            logger.info("[file-watcher] Stopped file watching")

    def is_running(self) -> bool:
        """Check if file watcher is running."""
        return self.running and self.observer and self.observer.is_alive()


class PeriodicFileChecker:
    """Periodic file checker as fallback when watchdog is not available."""

    def __init__(self):
        self.settings = get_settings()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.known_files: Set[str] = set()

    def start(self):
        """Start periodic file checking."""
        if not self.settings.auto_ingest_path:
            logger.warning("[file-checker] No auto-ingest path configured")
            return False

        self.running = True
        self.thread = threading.Thread(target=self._check_loop, daemon=True)
        self.thread.start()

        logger.info(f"[file-checker] Started periodic checking every {self.settings.auto_ingest_watch_interval}s")
        return True

    def stop(self):
        """Stop periodic file checking."""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("[file-checker] Stopped periodic file checking")

    def _check_loop(self):
        """Main checking loop."""
        # Initialize known files
        self._scan_existing_files()

        while self.running:
            try:
                self._check_for_new_files()
                time.sleep(self.settings.auto_ingest_watch_interval)
            except Exception as e:
                logger.error(f"[file-checker] Error in check loop: {e}")
                time.sleep(60)  # Wait a minute before retrying

    def _scan_existing_files(self):
        """Scan for existing files to establish baseline."""
        watch_path = Path(self.settings.auto_ingest_path)
        if not watch_path.exists():
            return

        supported_extensions = {'.txt', '.md', '.pdf', '.docx'}
        for ext in supported_extensions:
            for file_path in watch_path.glob(f"**/*{ext}"):
                self.known_files.add(str(file_path.absolute()))

    def _check_for_new_files(self):
        """Check for new files and ingest them."""
        watch_path = Path(self.settings.auto_ingest_path)
        if not watch_path.exists():
            return

        supported_extensions = {'.txt', '.md', '.pdf', '.docx'}
        current_files = set()

        # Scan current files
        for ext in supported_extensions:
            for file_path in watch_path.glob(f"**/*{ext}"):
                current_files.add(str(file_path.absolute()))

        # Find new files
        new_files = current_files - self.known_files

        for file_str in new_files:
            file_path = Path(file_str)
            try:
                logger.info(f"[file-checker] New file detected: {file_path.name}")

                # Check if already ingested
                dao = get_dao()
                docs_by_source = dao.count_documents_by_source()
                existing_sources = {source for source, count in docs_by_source}

                if file_path.name not in existing_sources and file_str not in existing_sources:
                    chunks_ingested = ingest_path(file_path)
                    logger.info(f"[file-checker] Successfully ingested {chunks_ingested} chunks from {file_path.name}")
                else:
                    logger.info(f"[file-checker] File already ingested: {file_path.name}")

            except Exception as e:
                logger.error(f"[file-checker] Failed to ingest {file_path}: {e}")

        # Update known files
        self.known_files = current_files


# Global instances
_file_watcher: Optional[FileWatcher] = None
_periodic_checker: Optional[PeriodicFileChecker] = None


def start_file_monitoring():
    """Start file monitoring (watcher or periodic checker)."""
    global _file_watcher, _periodic_checker

    settings = get_settings()

    if not settings.auto_ingest_watch_mode:
        logger.info("[file-monitor] File watching disabled in configuration")
        return False

    # Try to use file watcher first (requires watchdog)
    try:
        import watchdog
        _file_watcher = FileWatcher()
        if _file_watcher.start():
            logger.info("[file-monitor] Using real-time file watcher")
            return True
    except ImportError:
        logger.info("[file-monitor] watchdog not available, falling back to periodic checking")
    except Exception as e:
        logger.warning(f"[file-monitor] File watcher failed: {e}, falling back to periodic checking")

    # Fallback to periodic checker
    _periodic_checker = PeriodicFileChecker()
    if _periodic_checker.start():
        logger.info("[file-monitor] Using periodic file checker")
        return True

    logger.error("[file-monitor] Failed to start any file monitoring")
    return False


def stop_file_monitoring():
    """Stop file monitoring."""
    global _file_watcher, _periodic_checker

    if _file_watcher:
        _file_watcher.stop()
        _file_watcher = None

    if _periodic_checker:
        _periodic_checker.stop()
        _periodic_checker = None

    logger.info("[file-monitor] File monitoring stopped")


def is_file_monitoring_active() -> bool:
    """Check if file monitoring is active."""
    global _file_watcher, _periodic_checker

    if _file_watcher and _file_watcher.is_running():
        return True

    if _periodic_checker and _periodic_checker.running:
        return True

    return False
