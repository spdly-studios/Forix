# forix/services/folder_detector.py
"""
Forix — Folder Open Detector (Windows)
Polls for Explorer windows that are open inside E:\\Projects\\
and emits a signal so the UI can jump to that project.

Uses pywin32 (win32gui / win32com) on Windows.
Gracefully no-ops on non-Windows.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Set
from urllib.parse import unquote   # Bug fix: file:/// URLs may be percent-encoded

from core.constants import PROJECTS_DIR, FOLDER_OPEN_POLL_MS

log = logging.getLogger("forix.folder_detector")


class FolderOpenDetector:
    """
    Periodically checks open Explorer windows.
    If one is inside E:\\Projects\\<ProjectName>, fires
    `on_project_folder_opened(project_path)`.
    """

    def __init__(self, on_project_folder_opened: Callable[[Path], None]):
        self._callback  = on_project_folder_opened
        self._running   = False
        self._stop_evt  = threading.Event()          # Bug fix: clean stop signal
        self._thread: Optional[threading.Thread] = None
        self._seen: Set[str] = set()
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            import win32gui   # noqa
            import win32com.client  # noqa
            return True
        except ImportError:
            log.info("pywin32 not available — folder-open detection disabled")
            return False

    def start(self):
        if not self._available or self._running:
            return
        self._running = True
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="Forix-FolderDetector"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_evt.set()      # Unblock the sleep immediately
        if self._thread:
            self._thread.join(timeout=5)

    # ── Poll loop ─────────────────────────────────────────────────────────────

    def _poll_loop(self):
        # Bug fix: COM must be initialised on the thread that uses it
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass   # pythoncom may not be present in all pywin32 installs

        interval = max(FOLDER_OPEN_POLL_MS, 500) / 1000.0   # floor at 500 ms
        try:
            while self._running:
                try:
                    self._check_explorer_windows()
                except Exception as e:
                    log.debug(f"FolderDetector poll error: {e}")
                # Bug fix: use Event.wait() so stop() unblocks immediately
                if self._stop_evt.wait(timeout=interval):
                    break
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except ImportError:
                pass

    # ── Explorer window enumeration ───────────────────────────────────────────

    def _check_explorer_windows(self):
        import win32gui

        hwnds: list[int] = []

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                cls = win32gui.GetClassName(hwnd)
                if cls in ("CabinetWClass", "ExploreWClass"):
                    hwnds.append(hwnd)

        win32gui.EnumWindows(enum_cb, None)

        current_paths: Set[str] = set()
        for hwnd in hwnds:
            path = self._get_explorer_path(hwnd)
            if path:
                current_paths.add(path)

        # Only react to windows that are newly opened since last poll
        new_paths = current_paths - self._seen
        self._seen = current_paths

        for path_str in new_paths:
            p = Path(path_str)
            try:
                rel = p.resolve().relative_to(PROJECTS_DIR.resolve())
                parts = rel.parts
                if parts:
                    project_path = PROJECTS_DIR / parts[0]
                    self._callback(project_path)
            except ValueError:
                pass   # Not under Projects dir

    # ── Path extraction ───────────────────────────────────────────────────────

    def _get_explorer_path(self, hwnd: int) -> Optional[str]:
        """
        Extract the current folder path from an Explorer window handle.

        Bugs fixed:
        - LocationURL may be percent-encoded (e.g. spaces as %20) — unquote() needed.
        - file:/// prefix on Windows uses forward slashes AND may start with
          'file:///C:/...' (3 slashes, then drive letter) — strip correctly.
        - str.replace("/", "\\") was used to normalise; use Path() instead so
          it handles mixed separators robustly.
        """
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            for window in shell.Windows():
                try:
                    if window.HWND != hwnd:
                        continue
                    loc = window.LocationURL
                    if not loc:
                        continue
                    # Decode percent-encoding first (e.g. "My%20Project" → "My Project")
                    loc = unquote(loc)
                    # Strip the file:/// scheme — on Windows this gives 'C:/...'
                    if loc.startswith("file:///"):
                        loc = loc[8:]
                    elif loc.startswith("file://"):
                        loc = loc[7:]
                    else:
                        continue   # Not a local path
                    # Normalise to a proper Windows path string via Path
                    return str(Path(loc))
                except Exception:
                    continue
        except Exception as e:
            log.debug(f"Shell.Application error: {e}")
        return None