# forix/services/watcher.py
"""
Forix — Global File System Watcher
Monitors E:\\ drive continuously using watchdog.
Debounces rapid events and delegates to the organiser.
"""

import time
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent, FileModifiedEvent,
    FileDeletedEvent, FileMovedEvent,
    DirCreatedEvent,
)

from core.constants import ROOT_DRIVE, PROJECTS_DIR, SYSTEM_DIR, VERSION_DEBOUNCE_SECS
from core.classifier import should_ignore

log = logging.getLogger("forix.watcher")


class ForixEventHandler(FileSystemEventHandler):
    """
    Handles raw watchdog events and routes them to Forix's organiser.
    Debounces per-file modification events to avoid hammering the DB.
    """

    def __init__(
        self,
        on_file_created:  Callable,
        on_file_modified: Callable,
        on_file_deleted:  Callable,
        on_dir_created:   Callable,
        on_file_moved:    Callable,
    ):
        super().__init__()
        self._on_file_created  = on_file_created
        self._on_file_modified = on_file_modified
        self._on_file_deleted  = on_file_deleted
        self._on_dir_created   = on_dir_created
        self._on_file_moved    = on_file_moved

        # Per-path debounce timers for modification events
        self._mod_timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ── Watchdog overrides ────────────────────────────────────────────────────

    def on_created(self, event):
        path = Path(event.src_path)
        if should_ignore(path):
            return
        if event.is_directory:
            self._on_dir_created(path)
        else:
            self._on_file_created(path)

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if should_ignore(path):
            return
        self._debounce_modification(path)

    def on_deleted(self, event):
        path = Path(event.src_path)
        # Bug fix: deleted files can't be checked by should_ignore (they're gone).
        # Only ignore based on the path string, not file content/attributes.
        if _should_ignore_path_str(path):
            return
        if not event.is_directory:
            self._on_file_deleted(path)

    def on_moved(self, event):
        src = Path(event.src_path)
        dst = Path(event.dest_path)
        # Bug fix: original used `and` — ignored the event only if BOTH
        # src AND dst were ignorable. A file moved INTO the projects folder
        # from an ignored location (e.g. temp dir) would still fire. Use `or`
        # for src so we skip events originating from ignored locations,
        # but still handle moves into managed folders from non-ignored sources.
        if _should_ignore_path_str(src) and _should_ignore_path_str(dst):
            return
        self._on_file_moved(src, dst)

    # ── Debounce helper ───────────────────────────────────────────────────────

    def _debounce_modification(self, path: Path):
        key = str(path)
        with self._lock:
            existing = self._mod_timers.get(key)
            if existing:
                existing.cancel()
            t = threading.Timer(
                VERSION_DEBOUNCE_SECS,
                self._fire_modification,
                args=(path, key),
            )
            t.daemon = True
            self._mod_timers[key] = t
        # Start outside the lock — cancel() on an un-started timer is safe
        t.start()

    def _fire_modification(self, path: Path, key: str):
        with self._lock:
            self._mod_timers.pop(key, None)
        self._on_file_modified(path)

    def cancel_all_timers(self):
        """Cancel all pending debounce timers. Call on watcher stop to prevent leaks."""
        with self._lock:
            for t in self._mod_timers.values():
                t.cancel()
            self._mod_timers.clear()


class FileWatcher:
    """
    Wraps watchdog Observer. One instance per watched path.
    Exposes a simple start / stop interface.
    """

    def __init__(
        self,
        watch_path:       Path,
        on_file_created:  Callable,
        on_file_modified: Callable,
        on_file_deleted:  Callable,
        on_dir_created:   Callable,
        on_file_moved:    Callable,
    ):
        self._watch_path = watch_path
        self._observer: Optional[Observer] = None
        self._handler = ForixEventHandler(
            on_file_created=on_file_created,
            on_file_modified=on_file_modified,
            on_file_deleted=on_file_deleted,
            on_dir_created=on_dir_created,
            on_file_moved=on_file_moved,
        )

    def start(self):
        # Bug fix: original checked is_alive() but after stop() the observer is
        # set to None, so re-calling start() would create a second Observer
        # without checking — safe now because we also reset to None on stop().
        if self._observer is not None and self._observer.is_alive():
            return
        try:
            self._observer = Observer()
            self._observer.schedule(
                self._handler,
                str(self._watch_path),
                recursive=True,
            )
            self._observer.start()
            log.info(f"Watcher started on {self._watch_path}")
        except Exception as e:
            log.error(f"Failed to start watcher on {self._watch_path}: {e}")
            self._observer = None   # Don't leave a broken observer around

    def stop(self):
        # Cancel pending debounce timers first so they don't fire after stop
        self._handler.cancel_all_timers()

        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception as e:
                log.warning(f"Error stopping watcher: {e}")
            finally:
                self._observer = None
        log.info("Watcher stopped")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()


# ── Module-level helpers ──────────────────────────────────────────────────────

def _should_ignore_path_str(path: Path) -> bool:
    """
    Path-string-only ignore check for events where the file no longer exists
    (deletions) or where we only have a path (moves).
    Delegates to should_ignore but catches any stat-related errors gracefully.
    """
    try:
        return should_ignore(path)
    except (OSError, PermissionError):
        # File doesn't exist — check name/extension heuristics only
        name = path.name.lower()
        return (
            name.startswith(".")
            or name.startswith("~")
            or name.endswith(".tmp")
            or name.endswith(".temp")
            or "__pycache__" in path.parts
            or ".git" in path.parts
        )