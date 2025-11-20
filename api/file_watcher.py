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
from .ingest_files import ingest_path, SUPPORTED_EXTENSIONS
from .logging_config import get_logger

logger = get_logger(__name__)


def _wait_for_file_ready(file_path: Path, settings) -> bool:
    """Ensure the file is stable before ingestion."""
    if not file_path.exists():
        return False

    timeout = getattr(settings, "auto_ingest_file_ready_timeout", 30.0)
    poll_interval = max(0.1, getattr(settings, "auto_ingest_file_ready_poll_interval", 1.0))
    stability_checks = max(1, getattr(settings, "auto_ingest_file_ready_stability_checks", 2))

    deadline = time.time() + timeout
    last_fingerprint = None
    stable_count = 0

    while time.time() < deadline:
        try:
            stat = file_path.stat()
        except FileNotFoundError:
            return False

        fingerprint = (stat.st_size, stat.st_mtime)
        if fingerprint == last_fingerprint:
            stable_count += 1
        else:
            stable_count = 1
            last_fingerprint = fingerprint

        if stable_count >= stability_checks:
            return True

        time.sleep(poll_interval)

    logger.warning(f"[file-watcher] Timed out waiting for file to stabilize: {file_path.name}")
    return False


def _is_file_already_ingested(dao, abs_path: str) -> bool:
    """Check if a file already has documents stored."""
    with dao.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM documents WHERE source_file = %s LIMIT 1", (abs_path,))
            return cur.fetchone() is not None


class DocumentFileHandler(FileSystemEventHandler):
    """Handle file system events for document ingestion."""

    def __init__(self):
        self.settings = get_settings()
        self.supported_extensions = SUPPORTED_EXTENSIONS
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
        """Handle deletion of a file by removing its documents from database and invalidating caches."""
        # Check if it was a supported file type
        if file_path.suffix.lower() not in self.supported_extensions:
            return

        source_file = str(file_path.absolute())
        
        try:
            # Step 1: Remove documents from database
            dao = get_dao()
            deleted_count = dao.delete_documents_by_source(source_file)
            
            # Step 2: Invalidate related cache entries
            cache_invalidations = 0
            
            # Try to invalidate response cache
            try:
                from .response_cache import get_response_cache
                response_cache = get_response_cache()
                response_invalidated = response_cache.invalidate_by_source(source_file)
                cache_invalidations += response_invalidated
            except ImportError:
                logger.debug(f"[file-watcher] Response cache not available")
            except Exception as cache_error:
                logger.warning(f"[file-watcher] Failed to invalidate response cache for {file_path}: {cache_error}")
            
            # Try to invalidate query result cache
            try:
                from .query_result_cache import get_query_result_cache
                query_cache = get_query_result_cache()
                query_invalidated = query_cache.invalidate_by_source(source_file)
                cache_invalidations += query_invalidated
            except ImportError:
                logger.debug(f"[file-watcher] Query result cache not available")
            except Exception as cache_error:
                logger.warning(f"[file-watcher] Failed to invalidate query cache for {file_path}: {cache_error}")
            
            if deleted_count > 0:
                logger.info(f"[file-watcher] Removed {deleted_count} chunks and invalidated {cache_invalidations} cache entries for deleted file: {file_path}")
            else:
                logger.debug(f"[file-watcher] No chunks found for deleted file: {file_path}")
                
        except Exception as e:
            logger.error(f"[file-watcher] Failed to handle deletion of {file_path}: {e}")

    def _process_file(self, file_path: Path, attempt: int = 0):
        """Process a new file for ingestion."""
        # Check if it's a supported file type
        if file_path.suffix.lower() not in self.supported_extensions:
            return

        # Avoid processing the same file multiple times
        file_str = str(file_path)
        with self.processing_lock:
            if attempt == 0:
                if file_str in self.processing_files:
                    return
            self.processing_files.add(file_str)

        settings = self.settings
        max_retries = max(0, getattr(settings, "auto_ingest_max_retries", 0))
        base_delay = max(0.1, getattr(settings, "auto_ingest_retry_initial_delay", 1.0))
        max_delay = max(base_delay, getattr(settings, "auto_ingest_retry_max_delay", base_delay))

        retry_scheduled = False
        try:
            if not _wait_for_file_ready(file_path, self.settings):
                raise RuntimeError(f"File not ready for ingestion: {file_path}")

            logger.info(f"[file-watcher] New file detected: {file_path.name}")

            # Quick check if file is already ingested (optimized)
            dao = get_dao()
            abs_path = str(file_path.absolute())
            
            # Simple existence check instead of loading all sources
            if _is_file_already_ingested(dao, abs_path):
                logger.info(f"[file-watcher] File already ingested: {file_path.name}")
                return

            # Ingest the new file
            chunks_ingested = ingest_path(file_path)
            logger.info(f"[file-watcher] Successfully ingested {chunks_ingested} chunks from {file_path.name}")

        except Exception as e:
            if attempt < max_retries:
                delay = min(max_delay, base_delay * (2 ** attempt))
                logger.warning(
                    f"[file-watcher] Ingestion attempt {attempt + 1} failed for {file_path.name}: {e}. "
                    f"Retrying in {delay:.1f}s"
                )
                self._schedule_retry(file_path, attempt + 1, delay)
                retry_scheduled = True
            else:
                logger.error(f"[file-watcher] Failed to ingest {file_path} after {attempt + 1} attempts: {e}")
        finally:
            # Remove from processing set
            if not retry_scheduled:
                with self.processing_lock:
                    self.processing_files.discard(file_str)

    def _schedule_retry(self, file_path: Path, attempt: int, delay: float) -> None:
        """Schedule a retry for file ingestion."""

        def _retry():
            self._process_file(file_path, attempt=attempt)

        timer = threading.Timer(delay, _retry)
        timer.daemon = True
        timer.start()


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
            # Clean up on failure
            if self.observer:
                try:
                    self.observer.stop()
                except:
                    pass
                self.observer = None
            self.running = False
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
        self.supported_extensions = SUPPORTED_EXTENSIONS

    def start(self):
        """Start periodic file checking."""
        if self.running:
            logger.debug("[file-checker] Periodic checker already running")
            return True

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

        for ext in self.supported_extensions:
            for file_path in watch_path.glob(f"**/*{ext}"):
                self.known_files.add(str(file_path.absolute()))

    def _check_for_new_files(self):
        """Check for new files and ingest them."""
        watch_path = Path(self.settings.auto_ingest_path)
        if not watch_path.exists():
            return

        current_files = set()

        # Scan current files
        for ext in self.supported_extensions:
            for file_path in watch_path.glob(f"**/*{ext}"):
                current_files.add(str(file_path.absolute()))

        dao = get_dao()
        existing_sources = {
            source for source, _ in dao.count_documents_by_source() if source
        }

        missing_files = [Path(f) for f in current_files if f not in existing_sources]

        if missing_files:
            logger.info(
                "[file-checker] Found %d filesystem files missing from database",
                len(missing_files)
            )

        for file_path in missing_files:
            file_str = str(file_path)
            try:
                if not _wait_for_file_ready(file_path, self.settings):
                    logger.warning(
                        "[file-checker] File not ready for ingestion, will retry later: %s",
                        file_path.name
                    )
                    continue

                abs_path = str(file_path.absolute())
                if _is_file_already_ingested(dao, abs_path):
                    logger.debug(
                        "[file-checker] File already ingested by the time of check: %s",
                        file_path.name
                    )
                    continue

                chunks_ingested = ingest_path(file_path)
                if chunks_ingested > 0:
                    logger.info(
                        "[file-checker] Successfully ingested %d chunks from %s",
                        chunks_ingested,
                        file_path.name
                    )
                else:
                    logger.info(
                        "[file-checker] No new chunks created for %s (possibly empty or already ingested)",
                        file_path.name
                    )

            except Exception as e:
                logger.error(f"[file-checker] Failed to ingest {file_path}: {e}")

        # Update known files for tracking
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
    file_watcher_started = False
    try:
        import watchdog
        _file_watcher = FileWatcher()
        if _file_watcher.start():
            logger.info("[file-monitor] Using real-time file watcher")
            file_watcher_started = True
        else:
            logger.warning("[file-monitor] File watcher failed to start, falling back to periodic checking")
    except ImportError:
        logger.info("[file-monitor] watchdog not available, falling back to periodic checking")
    except Exception as e:
        logger.warning(f"[file-monitor] File watcher failed: {e}, falling back to periodic checking")

    # Start periodic checker if requested (even alongside real-time watcher)
    should_run_periodic = getattr(settings, "auto_ingest_run_periodic_checker", True)
    periodic_started = False

    if should_run_periodic:
        if not _periodic_checker:
            _periodic_checker = PeriodicFileChecker()
        if _periodic_checker.start():
            logger.info("[file-monitor] Periodic file checker running")
            periodic_started = True
        else:
            logger.warning("[file-monitor] Failed to start periodic checker")

    if file_watcher_started or periodic_started:
        return True

    # Fallback to periodic checker only when watchdog failed and it's not already running
    if not periodic_started and should_run_periodic:
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
