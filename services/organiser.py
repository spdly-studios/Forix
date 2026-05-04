# forix/services/organiser.py
"""
Forix — Auto-Organiser Service
Processes file events, classifies files, assigns to projects,
creates versions, and maintains the E:\\ structure.

This runs on a background thread via an event queue.
"""

import queue
import logging
import threading
import datetime
from pathlib import Path
from typing import Optional

from core.database import get_session, Project, TrackedFile, DuplicateGroup
from core.constants import PROJECTS_DIR, SYSTEM_DIR, BACKUPS_DIR, TEMP_DIR
from core.classifier import (
    classify_file, compute_checksum, should_ignore,
    score_folder_as_project, infer_project_name, detect_project_type,
    infer_project_category,
)
from core.project_manager import (
    create_project, import_file_to_project, create_version_snapshot,
    auto_detect_and_create_project, _log_event,
)

log = logging.getLogger("forix.organiser")

# Event types pushed into the queue
EV_FILE_CREATED  = "file_created"
EV_FILE_MODIFIED = "file_modified"
EV_FILE_DELETED  = "file_deleted"
EV_DIR_CREATED   = "dir_created"
EV_FILE_MOVED    = "file_moved"

_QUEUE_MAX = 5000


class Organiser:
    """
    Consumes filesystem events from a queue and organises accordingly.
    Designed to run on a single background thread.
    """

    def __init__(self, ui_signal_callback=None):
        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._signal  = ui_signal_callback   # callable(level, message)

        # Pending version snapshots: project_id → Timer
        self._snap_timers: dict[int, threading.Timer] = {}
        self._snap_lock = threading.Lock()

    # ── Public event ingestion ─────────────────────────────────────────────

    def on_file_created(self, path: Path):
        self._enqueue(EV_FILE_CREATED, path, None)

    def on_file_modified(self, path: Path):
        self._enqueue(EV_FILE_MODIFIED, path, None)

    def on_file_deleted(self, path: Path):
        self._enqueue(EV_FILE_DELETED, path, None)

    def on_dir_created(self, path: Path):
        self._enqueue(EV_DIR_CREATED, path, None)

    def on_file_moved(self, src: Path, dst: Path):
        self._enqueue(EV_FILE_MOVED, src, dst)

    def _enqueue(self, event_type: str, path: Path, extra):
        """Put an event on the queue; log and drop gracefully if full."""
        try:
            self._queue.put_nowait((event_type, path, extra))
        except queue.Full:
            log.warning(
                f"Event queue full ({_QUEUE_MAX}), dropping {event_type}: {path.name}"
            )

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="Forix-Organiser"
        )
        self._thread.start()
        log.info("Organiser started")

    def stop(self):
        self._running = False
        self._queue.put_nowait(None)   # sentinel to unblock the loop
        if self._thread:
            self._thread.join(timeout=10)
        # Cancel any pending snapshot timers
        with self._snap_lock:
            for t in self._snap_timers.values():
                t.cancel()
            self._snap_timers.clear()
        log.info("Organiser stopped")

    # ── Event loop ─────────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                item = self._queue.get(timeout=2)
                if item is None:
                    break
                event_type, path, extra = item
                self._dispatch(event_type, path, extra)
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"Organiser loop error: {e}", exc_info=True)

    def _dispatch(self, event_type: str, path: Path, extra):
        try:
            if event_type == EV_FILE_CREATED:
                self._handle_file_created(path)
            elif event_type == EV_FILE_MODIFIED:
                self._handle_file_modified(path)
            elif event_type == EV_FILE_DELETED:
                self._handle_file_deleted(path)
            elif event_type == EV_DIR_CREATED:
                self._handle_dir_created(path)
            elif event_type == EV_FILE_MOVED:
                self._handle_file_moved(path, extra)
        except Exception as e:
            log.error(f"Error handling {event_type} for {path}: {e}", exc_info=True)

    # ── Individual handlers ────────────────────────────────────────────────

    def _handle_file_created(self, path: Path):
        """
        A new file appeared somewhere on E:\\.
        1. Ignore system/temp paths immediately.
        2. If already inside a managed project → track it.
        3. Otherwise find the best matching project → import.
        4. If no match, auto-create a project from the parent folder.
        """
        if not path.exists() or not path.is_file():
            return
        if should_ignore(path):
            return
        # Guard: already inside the managed projects tree — just track
        if _is_under(path, PROJECTS_DIR):
            s = get_session()
            try:
                proj = self._find_project_for_path(path, s)
                if proj:
                    self._track_file(path, proj, s)
                    self._schedule_snapshot(proj)
            finally:
                s.close()
            return

        # Outside managed area — decide what to do
        s = get_session()
        try:
            checksum = compute_checksum(path)
            if checksum and self._is_duplicate(checksum, path, s):
                log.info(f"Duplicate detected: {path.name} — skipping")
                return

            best = self._find_best_project_match(path, s)
            if best:
                # Import into the matched project (don't move by default)
                import_file_to_project(path, best, move=False, session=s)
                self._schedule_snapshot(best)
                self._notify(f"📁 {path.name} → {best.name}")
            else:
                # Auto-create a project from the parent folder
                proj = auto_detect_and_create_project(path.parent, s)
                if proj:
                    self._notify(f"✨ New project: {proj.name}")
        finally:
            s.close()

    def _handle_file_modified(self, path: Path):
        """File was modified → update DB record + schedule version snapshot."""
        if not path.exists() or not path.is_file():
            return
        if should_ignore(path):
            return

        s = get_session()
        try:
            tf = s.query(TrackedFile).filter_by(path=str(path)).first()
            if tf:
                stat = path.stat()
                tf.modified_at = datetime.datetime.fromtimestamp(stat.st_mtime)
                tf.size_bytes  = stat.st_size
                tf.checksum    = compute_checksum(path)
                if tf.project_id:
                    proj = s.query(Project).filter_by(id=tf.project_id).first()
                    if proj:
                        proj.last_activity = datetime.datetime.utcnow()
                        s.commit()
                        self._schedule_snapshot(proj)
                    return
                s.commit()
        finally:
            s.close()

    def _handle_file_deleted(self, path: Path):
        """File deleted → mark as deleted in DB."""
        s = get_session()
        try:
            tf = s.query(TrackedFile).filter_by(path=str(path)).first()
            if tf:
                tf.is_deleted = True
                s.commit()
                _log_event(
                    tf.project_id, "file_deleted",
                    f"Deleted: {path.name}", str(path), s,
                )
        finally:
            s.close()

    def _handle_dir_created(self, path: Path):
        """
        A new directory appeared.
        If it scores highly as a project folder, auto-register it.

        Guards:
          • should_ignore() — OS noise, hidden dirs, Forix scaffold names.
          • System/Backups/Temp dirs — never contain user projects.
          • Direct subdirs of an existing project path — these are scaffold
            dirs being created by ensure_project_structure() and must be
            ignored here; auto_detect also guards, but catching it here is
            cheaper and avoids a DB round-trip entirely.
        """
        if should_ignore(path):
            return
        if _is_under(path, SYSTEM_DIR):
            return
        if _is_under(path, BACKUPS_DIR):
            return
        if _is_under(path, TEMP_DIR):
            return

        # If this new dir's immediate parent is an already-tracked project,
        # it's a scaffold subdir being created (scratch/, notes/, src/, etc.).
        # Skip the expensive score + DB lookup entirely.
        s = get_session()
        try:
            parent_is_project = s.query(Project).filter_by(
                path=str(path.parent)
            ).first() is not None
        finally:
            s.close()

        if parent_is_project:
            log.debug("_handle_dir_created: skipping scaffold dir '%s'", path)
            return

        score = score_folder_as_project(path)
        if score >= 40:
            s = get_session()
            try:
                auto_detect_and_create_project(path, s)
            finally:
                s.close()

    def _handle_file_moved(self, src: Path, dst: Path):
        """File was renamed/moved — update the DB record's path."""
        s = get_session()
        try:
            tf = s.query(TrackedFile).filter_by(path=str(src)).first()
            if tf:
                tf.path = str(dst)
                tf.name = dst.name
                tf.extension = dst.suffix.lower()
                s.commit()
        finally:
            s.close()

    # ── Path matching helpers ──────────────────────────────────────────────

    def _find_project_for_path(self, path: Path, session) -> Optional[Project]:
        """
        Return the project whose directory contains this path.
        Uses proper Path comparison to avoid prefix false-matches
        (e.g. /projects/foo matching /projects/foobar).
        """
        resolved = path.resolve()
        for proj in session.query(Project).all():
            try:
                resolved.relative_to(Path(proj.path).resolve())
                return proj
            except ValueError:
                continue
        return None

    def _find_best_project_match(self, path: Path, session) -> Optional[Project]:
        """
        Heuristic: find the project whose name best matches
        the incoming file's parent folder hierarchy.
        """
        parent_str = str(path.parent).lower()
        best_proj  = None
        best_score = 0

        for proj in session.query(Project).all():
            name_lower = proj.name.lower()
            if name_lower in parent_str:
                score = len(name_lower)
                if score > best_score:
                    best_score = score
                    best_proj  = proj

        # Require at least a 4-character name match to avoid false positives
        return best_proj if best_score >= 4 else None

    # ── File tracking helpers ──────────────────────────────────────────────

    def _track_file(self, path: Path, project: Project, session):
        """Track a file that's already inside a managed project folder."""
        existing = session.query(TrackedFile).filter_by(path=str(path)).first()
        if existing:
            return
        try:
            stat = path.stat()
            tf = TrackedFile(
                project_id=project.id,
                path=str(path),
                name=path.name,
                extension=path.suffix.lower(),
                category=classify_file(path),
                size_bytes=stat.st_size,
                checksum=compute_checksum(path),
                modified_at=datetime.datetime.fromtimestamp(stat.st_mtime),
            )
            session.add(tf)
            session.commit()
        except Exception as e:
            session.rollback()
            log.warning(f"Could not track {path}: {e}")

    def _is_duplicate(self, checksum: str, path: Path, session) -> bool:
        """Check if this checksum already exists; record in duplicate group."""
        existing_tf = session.query(TrackedFile).filter_by(checksum=checksum).first()
        if not existing_tf:
            return False

        dg = session.query(DuplicateGroup).filter_by(checksum=checksum).first()
        if dg:
            paths = list(dg.paths or [])
            if str(path) not in paths:
                paths.append(str(path))
                dg.paths = paths
                session.commit()
        else:
            dg = DuplicateGroup(
                checksum=checksum,
                paths=[existing_tf.path, str(path)],
            )
            session.add(dg)
            session.commit()
        return True

    # ── Snapshot scheduling ────────────────────────────────────────────────

    def _schedule_snapshot(self, project: Project):
        """
        Debounced: create a version snapshot after 30s of quiet activity.
        Captures project.id immediately so we don't hold a reference to
        the ORM object across threads.
        """
        pid = project.id
        with self._snap_lock:
            existing = self._snap_timers.get(pid)
            if existing:
                existing.cancel()
            t = threading.Timer(30.0, self._do_snapshot, args=(pid,))
            t.daemon = True
            self._snap_timers[pid] = t
        # Start outside the lock — cancel() on an un-started timer is safe
        t.start()

    def _do_snapshot(self, project_id: int):
        with self._snap_lock:
            self._snap_timers.pop(project_id, None)
        s = get_session()
        try:
            proj = s.query(Project).filter_by(id=project_id).first()
            if proj:
                create_version_snapshot(proj, s)
        except Exception as e:
            log.error(f"Auto-snapshot failed for project {project_id}: {e}")
        finally:
            s.close()

    # ── UI notifications ───────────────────────────────────────────────────

    def _notify(self, message: str, level: str = "info"):
        log.info(message)
        if self._signal:
            try:
                self._signal(level, message)
            except Exception:
                pass


# ── Initial scan ───────────────────────────────────────────────────────────────

def run_initial_scan(organiser: Organiser):
    """
    Scan the managed projects directory on startup and register any
    untracked folders. Runs in a background thread — does not block startup.
    """
    def _scan():
        log.info("Running initial project scan…")
        if not PROJECTS_DIR.exists():
            try:
                PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                log.error(f"Could not create PROJECTS_DIR: {e}")
            return

        from core.project_manager import _FORIX_SCAFFOLD_DIRS
        for child in PROJECTS_DIR.iterdir():
            if not child.is_dir():
                continue
            # Skip OS noise and hidden dirs
            if should_ignore(child):
                continue
            # Skip any scaffold dir that ended up directly in PROJECTS_DIR
            # (can happen if an earlier buggy run created them there).
            if child.name.lower() in _FORIX_SCAFFOLD_DIRS:
                log.warning(
                    "Initial scan: skipping stray scaffold dir '%s' in PROJECTS_DIR",
                    child.name,
                )
                continue
            organiser._enqueue(EV_DIR_CREATED, child, None)
        log.info("Initial scan complete")

    t = threading.Thread(target=_scan, daemon=True, name="Forix-InitScan")
    t.start()


# ── Module-level utility ───────────────────────────────────────────────────────

def _is_under(path: Path, parent: Path) -> bool:
    """
    Return True if `path` is at or below `parent`, using proper
    Path resolution to avoid string-prefix false matches.
    """
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False