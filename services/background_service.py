# forix/services/background_service.py
"""
Forix — Background Service Coordinator
Starts and manages all background threads:
  - FileWatcher (watchdog)
  - Organiser (event processor)
  - FolderOpenDetector (Explorer integration)
  - Periodic health refresh
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable

from core.constants import ROOT_DRIVE, PROJECTS_DIR, SYSTEM_DIR, BACKUPS_DIR, TEMP_DIR
from core.database import init_db, get_session, Project
from core.project_manager import refresh_project_health
from services.watcher import FileWatcher
from services.organiser import Organiser, run_initial_scan
from services.folder_detector import FolderOpenDetector

log = logging.getLogger("forix.background")


def _ensure_directories():
    """Create the mandatory E:\\ structure on first run."""
    for d in [PROJECTS_DIR, SYSTEM_DIR, BACKUPS_DIR, TEMP_DIR,
              SYSTEM_DIR / "logs", SYSTEM_DIR / "cache", SYSTEM_DIR / "watchers"]:
        d.mkdir(parents=True, exist_ok=True)
    log.info("Directory structure verified")


class BackgroundService:
    """
    Single entry point for all background operations.
    Call start() once from main(). Call stop() on shutdown.
    """

    def __init__(
        self,
        ui_notify_callback: Optional[Callable[[str, str], None]] = None,
        ui_project_opened_callback: Optional[Callable[[int], None]] = None,
    ):
        self._notify  = ui_notify_callback
        self._proj_cb = ui_project_opened_callback

        # Ensure E:\\ structure exists
        _ensure_directories()

        # Initialise DB
        init_db()

        # Organiser (file event processor)
        self._organiser = Organiser(ui_signal_callback=ui_notify_callback)

        # Watchdog watcher
        self._watcher = FileWatcher(
            watch_path=ROOT_DRIVE,
            on_file_created =self._organiser.on_file_created,
            on_file_modified=self._organiser.on_file_modified,
            on_file_deleted =self._organiser.on_file_deleted,
            on_dir_created  =self._organiser.on_dir_created,
            on_file_moved   =self._organiser.on_file_moved,
        )

        # Explorer folder-open detector
        self._folder_detector = FolderOpenDetector(
            on_project_folder_opened=self._on_folder_opened
        )

        # Periodic health refresh thread
        self._health_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def organiser(self) -> Organiser:
        return self._organiser

    def start(self):
        log.info("BackgroundService starting…")
        self._running = True

        self._organiser.start()
        self._watcher.start()
        self._folder_detector.start()

        # Run initial project scan
        run_initial_scan(self._organiser)

        # Start periodic health refresh (every 5 minutes)
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True, name="Forix-HealthRefresh"
        )
        self._health_thread.start()

        log.info("BackgroundService started — monitoring E:\\ drive")

    def stop(self):
        log.info("BackgroundService stopping…")
        self._running = False
        self._watcher.stop()
        self._organiser.stop()
        self._folder_detector.stop()
        log.info("BackgroundService stopped")

    # ── Explorer folder-open callback ─────────────────────────────────────

    def _on_folder_opened(self, project_path: Path):
        """Called when user opens a project folder in Explorer."""
        s = get_session()
        try:
            proj = s.query(Project).filter_by(path=str(project_path)).first()
            if proj and self._proj_cb:
                log.info(f"Explorer opened project folder: {proj.name}")
                self._proj_cb(proj.id)
        finally:
            s.close()

    # ── Periodic health refresh ───────────────────────────────────────────

    def _health_loop(self):
        time.sleep(60)  # Wait 1 minute after startup
        while self._running:
            try:
                self._refresh_all_health()
            except Exception as e:
                log.error(f"Health refresh error: {e}")
            time.sleep(300)  # Every 5 minutes

    def _refresh_all_health(self):
        s = get_session()
        try:
            project_ids = [p.id for p in s.query(Project).all()]
        finally:
            s.close()

        for pid in project_ids:
            try:
                refresh_project_health(pid)
            except Exception:
                pass
