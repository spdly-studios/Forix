# forix/utils/icon_manager.py
"""
Forix — Icon Manager
Priority: assets/logo.png (or .ico) → programmatic fallback

Ensures the Forix icon appears everywhere:
  • Window title bar
  • Taskbar / Dock (Windows, macOS, Linux)
  • Alt-Tab switcher
  • Windows taskbar grouping (via AppUserModelID)
  • HiDPI / Retina displays (multiple pixmap sizes including 512 px)

Works in both dev mode and when frozen by PyInstaller.
"""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication

log = logging.getLogger("forix.icon_manager")

# Ordered by preference: prefer .ico on Windows (multi-resolution container),
# prefer .png everywhere else.
_SEARCH_NAMES = [
    "logo.png", "logo.ico",
    "forix_icon.ico", "forix_icon.png",
    "icon.ico", "icon.png",
    "forix.ico", "forix.png",
]

# All sizes needed for complete OS coverage.
# 16/24/32 → small UI elements; 48/64 → taskbar; 128/256/512 → HiDPI / macOS Dock.
_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

# Font preference list — first available font wins.
_LABEL_FONTS = ["Segoe UI", "SF Pro Display", "Helvetica Neue", "DejaVu Sans", "Arial"]


# ─── ASSET DISCOVERY ──────────────────────────────────────────────────────────

def _assets_dirs() -> list[Path]:
    """Return candidate asset directories, handling PyInstaller frozen bundles."""
    candidates: list[Path] = []

    # PyInstaller frozen: sys._MEIPASS is the temp extraction directory.
    if hasattr(sys, "_MEIPASS"):
        mei = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidates += [mei / "assets", mei]

    # Dev mode: two levels up from this file (project root).
    here = Path(__file__).resolve().parent.parent
    candidates += [here / "assets", here]

    # One-folder PyInstaller build: alongside the .exe.
    if hasattr(sys, "frozen"):
        exe_dir = Path(sys.executable).parent
        candidates += [exe_dir / "assets", exe_dir]

    return candidates


def find_user_icon() -> Optional[Path]:
    """
    Search all candidate directories for a recognised icon file.
    Returns the first match, or None if nothing is found.
    """
    for directory in _assets_dirs():
        for name in _SEARCH_NAMES:
            candidate = directory / name
            if candidate.is_file():
                log.info("Icon found: %s", candidate)
                return candidate

    log.warning("No icon file found — using programmatic fallback.")
    return None


# ─── PROGRAMMATIC FALLBACK ────────────────────────────────────────────────────

def _pick_font(size_pt: int) -> QFont:
    """Return the first available font from the preference list."""
    from PyQt6.QtGui import QFontDatabase  # imported here to avoid early Qt init
    available = set(QFontDatabase.families())
    for name in _LABEL_FONTS:
        if name in available:
            font = QFont(name, size_pt)
            font.setBold(True)
            return font
    # Last resort: let Qt pick the default system font.
    font = QFont()
    font.setPointSize(size_pt)
    font.setBold(True)
    return font


def make_programmatic_icon(size: int = 256) -> QPixmap:
    """
    Render an indigo circular fallback icon with a white 'F' centred inside.
    The painter is always ended cleanly even if drawing raises an exception.
    """
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    painter = QPainter(px)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ── Background circle with indigo gradient ──
        cx = cy = size / 2
        r = size * 0.44
        gradient = QLinearGradient(QPointF(0, 0), QPointF(size, size))
        gradient.setColorAt(0, QColor("#6366f1"))  # indigo-500
        gradient.setColorAt(1, QColor("#4338ca"))  # indigo-700
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ── Centred 'F' label ──
        font = _pick_font(int(size * 0.36))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "F")
    except Exception:
        log.exception("make_programmatic_icon: drawing failed at size=%d", size)
    finally:
        painter.end()  # always release the painter

    return px


# ─── ICON CONSTRUCTION ────────────────────────────────────────────────────────

def _icon_from_file(path: Path) -> Optional[QIcon]:
    """
    Load an icon from *path*.

    For .ico files we extract each embedded size individually so no resolution
    is silently dropped by Qt's single-size loader.
    For other formats we load the file directly, then verify it is non-null.
    """
    try:
        if path.suffix.lower() == ".ico":
            # QIcon(".ico") only loads the first embedded size on some platforms.
            # Load as QPixmap at each target size to extract all resolutions.
            icon = QIcon()
            for sz in _ICON_SIZES:
                pm = QPixmap(str(path))
                if not pm.isNull():
                    icon.addPixmap(
                        pm.scaled(
                            sz, sz,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            # Confirm at least one size loaded successfully.
            if not icon.availableSizes():
                log.warning("_icon_from_file: .ico loaded but has no usable sizes: %s", path)
                return None
            return icon

        # PNG / other raster formats.
        icon = QIcon(str(path))
        if icon.isNull():
            log.warning("_icon_from_file: QIcon reports null for %s", path)
            return None

        # Extra sanity check: make sure Qt actually decoded at least one pixmap.
        test_pm = icon.pixmap(32, 32)
        if test_pm.isNull():
            log.warning("_icon_from_file: pixmap() returned null for %s", path)
            return None

        return icon

    except Exception:
        log.exception("_icon_from_file: unexpected error loading %s", path)
        return None


def _build_programmatic_icon() -> QIcon:
    """Build a multi-resolution programmatic icon covering all target sizes."""
    icon = QIcon()
    for sz in _ICON_SIZES:
        try:
            icon.addPixmap(make_programmatic_icon(sz))
        except Exception:
            log.warning("_build_programmatic_icon: failed at size=%d", sz, exc_info=True)
    return icon


def get_app_icon() -> QIcon:
    """
    Return the best available Forix QIcon.
    Tries the user-supplied asset first; falls back to the programmatic icon.
    """
    user_path = find_user_icon()
    if user_path is not None:
        icon = _icon_from_file(user_path)
        if icon is not None:
            return icon

    log.info("get_app_icon: using programmatic fallback icon.")
    return _build_programmatic_icon()


# ─── APPLICATION-WIDE ICON INSTALLATION ──────────────────────────────────────

def _set_windows_app_id(app_id: str = "forix.app") -> None:
    """
    Tell Windows to group all Forix windows under a single taskbar button
    and use Forix's icon rather than Python's.

    Must be called *before* any window is shown.
    No-op on non-Windows platforms.
    """
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        log.debug("Windows AppUserModelID set to %r", app_id)
    except Exception:
        log.warning("Could not set Windows AppUserModelID.", exc_info=True)


def apply_icon_to_app(
    app: QApplication,
    *,
    windows_app_id: str = "forix.app",
) -> QIcon:
    """
    Install the Forix icon on the QApplication instance so it propagates to:
      • Every QMainWindow / QDialog title bar
      • The OS taskbar / Dock entry
      • The Alt-Tab / Mission Control switcher

    Also configures the Windows AppUserModelID so the taskbar button is grouped
    correctly and shows Forix's icon instead of the Python interpreter's.

    Call this *once*, immediately after creating QApplication and before
    showing any window:

        app = QApplication(sys.argv)
        icon = apply_icon_to_app(app)
        window = MainWindow()
        window.show()

    Returns the QIcon that was applied (useful for setting on individual
    windows if needed).
    """
    _set_windows_app_id(windows_app_id)

    icon = get_app_icon()
    app.setWindowIcon(icon)
    log.debug("App icon applied (%d sizes).", len(icon.availableSizes()))
    return icon