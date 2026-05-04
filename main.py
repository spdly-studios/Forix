#!/usr/bin/env python3
# forix/main.py  — Application Entry Point
"""
Boots Forix:
  1. Sets a full dark QPalette BEFORE any window is created
     (covers native Qt widgets: QComboBox popup, QMenu, QScrollBar, QToolTip)
  2. Applies the QSS stylesheet on top
  3. Creates MainWindow + BackgroundService
"""

import sys
import os
import logging
import importlib
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

(_HERE / "assets").mkdir(exist_ok=True)

from utils.logging_setup import setup_logging
setup_logging(logging.INFO)
log = logging.getLogger("forix.main")
log.info("=" * 60)
log.info("Forix starting")


# ── Drive / path fallback ──────────────────────────────────────
def _configure_fallback_paths() -> None:
    r"""
    If E:\ is unavailable (e.g. dev machine without the drive), patch every
    config path to a temp directory.  Must run before any module that reads
    config at import time is imported.
    """
    _ROOT = Path("E:/")
    if _ROOT.exists():
        return

    import tempfile
    import config as _cfg

    _fallback = Path(tempfile.gettempdir()) / "Forix_Dev"
    _fallback.mkdir(exist_ok=True)
    log.warning("E:\\ not found — dev fallback: %s", _fallback)

    _cfg.ROOT_DRIVE    = _fallback
    _cfg.PROJECTS_DIR  = _fallback / "Projects"
    _cfg.SYSTEM_DIR    = _fallback / "System"
    _cfg.BACKUPS_DIR   = _fallback / "Backups"
    _cfg.TEMP_DIR      = _fallback / "Temp"
    _cfg.SYSTEM_DB     = _fallback / "System" / "system.db"
    _cfg.SETTINGS_FILE = _fallback / "System" / "settings.json"
    _cfg.LOGS_DIR      = _fallback / "System" / "logs"
    _cfg.CACHE_DIR     = _fallback / "System" / "cache"
    _cfg.WATCHERS_DIR  = _fallback / "System" / "watchers"

    # Reload modules that captured config values at import time.
    import core.constants as _const
    import core.database as _db
    importlib.reload(_const)
    importlib.reload(_db)


_configure_fallback_paths()


# ── Qt ─────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QFont, QPixmap, QColor, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPalette, QPainterPath,
)

import design as D
from core.constants import APP_NAME, APP_VERSION


# ── Dark palette ───────────────────────────────────────────────

def _apply_dark_palette(app: QApplication) -> None:
    """
    Force every native Qt widget to use Forix dark colors.
    This replaces the system/style palette completely so that
    QComboBox popups, QMenu, QScrollBar, QToolTip, QCalendar etc.
    are all dark — even if QSS can't fully override them.
    """
    def c(h: str) -> QColor:
        return QColor(h)

    pal = QPalette()

    # Window backgrounds
    pal.setColor(QPalette.ColorRole.Window,          c(D.COLOR_BG))
    pal.setColor(QPalette.ColorRole.WindowText,      c(D.COLOR_TXT))
    pal.setColor(QPalette.ColorRole.Base,            c(D.COLOR_SURF))
    pal.setColor(QPalette.ColorRole.AlternateBase,   c(D.COLOR_SURF2))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     c(D.COLOR_SURF2))
    pal.setColor(QPalette.ColorRole.ToolTipText,     c(D.COLOR_TXT))

    # Text
    pal.setColor(QPalette.ColorRole.Text,            c(D.COLOR_TXT))
    pal.setColor(QPalette.ColorRole.BrightText,      c(D.COLOR_TXT_HEAD))
    pal.setColor(QPalette.ColorRole.PlaceholderText, c(D.COLOR_TXT_DIS))

    # Buttons
    pal.setColor(QPalette.ColorRole.Button,          c(D.COLOR_SURF2))
    pal.setColor(QPalette.ColorRole.ButtonText,      c(D.COLOR_TXT))

    # Selection / highlight
    pal.setColor(QPalette.ColorRole.Highlight,       c(D.COLOR_ACC))
    pal.setColor(QPalette.ColorRole.HighlightedText, c(D.COLOR_WHITE))

    # Links
    pal.setColor(QPalette.ColorRole.Link,            c(D.COLOR_ACC))
    pal.setColor(QPalette.ColorRole.LinkVisited,     c(D.COLOR_ACC_DK))

    # Depth shading
    pal.setColor(QPalette.ColorRole.Light,           c(D.COLOR_SURF2))
    pal.setColor(QPalette.ColorRole.Midlight,        c(D.COLOR_SURF3))
    pal.setColor(QPalette.ColorRole.Mid,             c(D.COLOR_BDR2))
    pal.setColor(QPalette.ColorRole.Dark,            c(D.COLOR_BDR3))
    pal.setColor(QPalette.ColorRole.Shadow,          c(D.COLOR_BLACK))

    # Disabled group — all muted
    disabled_roles = [
        (QPalette.ColorRole.WindowText,      D.COLOR_TXT_DIS),
        (QPalette.ColorRole.Text,            D.COLOR_TXT_DIS),
        (QPalette.ColorRole.ButtonText,      D.COLOR_TXT_DIS),
        (QPalette.ColorRole.Base,            D.COLOR_SURF2),
        (QPalette.ColorRole.Button,          D.COLOR_SURF2),
        (QPalette.ColorRole.Highlight,       D.COLOR_SURF3),
        (QPalette.ColorRole.HighlightedText, D.COLOR_TXT_DIS),
    ]
    for role, col in disabled_roles:
        pal.setColor(QPalette.ColorGroup.Disabled, role, c(col))

    app.setPalette(pal)


# ── Splash screen ──────────────────────────────────────────────

class _SplashScreen(QSplashScreen):
    """
    Extended splash that draws a polished dark card with:
      • Smooth antialiased rounded corners (clip-path, not binary mask)
      • Geometry derived entirely from named constants — zero magic numbers
      • Icon and text column both vertically centred within the content zone
      • Radial glow behind the icon
      • Progress bar + status text in a reserved footer zone
      • Gradient accent bar drawn after the grid so it stays crisp
    """

    STEPS = [
        "Initialising database…",
        "Building interface…",
        "Starting background service…",
        "Ready",
    ]

    # Card dimensions
    _W: int = 640
    _H: int = 360

    # Layout constants — all derived; change these to re-flow everything
    _PAD:         int = 40    # outer horizontal margin
    _ACCENT_H:    int = 3     # top accent bar height
    _FOOTER_H:    int = 44    # reserved for status text + progress bar
    _BAR_H:       int = 3     # progress bar height (inside footer)
    _STATUS_H:    int = 22    # status text row height (inside footer)
    _ICON_SIZE:   int = 80    # icon square
    _ICON_GAP:    int = 28    # gap between icon and text column
    _LINE_GAP:    int = 10    # gap between divider line and badge top
    _BADGE_PAD_X: int = 10   # badge horizontal inner padding
    _BADGE_PAD_Y: int = 5    # badge vertical inner padding

    def __init__(self, icon_px: QPixmap) -> None:
        px = self._render(icon_px, progress=0, step_text="")
        super().__init__(px, Qt.WindowType.WindowStaysOnTopHint)
        self._icon_px   = icon_px
        self._progress  = 0
        self._step_text = ""

    # ── public API ────────────────────────────────────────────

    def set_step(self, index: int) -> None:
        """Advance to step *index* (0-based) and repaint."""
        total = max(len(self.STEPS) - 1, 1)
        self._progress  = int(index / total * 100)
        self._step_text = self.STEPS[index] if index < len(self.STEPS) else ""
        self._repaint()

    # ── internal rendering ────────────────────────────────────

    @classmethod
    def _render(cls, icon_px: QPixmap, progress: int, step_text: str) -> QPixmap:
        px = QPixmap(cls._W, cls._H)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        try:
            cls._draw(p, cls._W, cls._H, icon_px, progress, step_text)
        finally:
            p.end()
        return px

    def _repaint(self) -> None:
        px = QPixmap(self._W, self._H)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        try:
            self._draw(p, self._W, self._H,
                       self._icon_px, self._progress, self._step_text)
        finally:
            p.end()
        self.setPixmap(px)

    @classmethod
    def _draw(
        cls,
        p: QPainter,
        w: int, h: int,
        icon_px: QPixmap,
        progress: int,
        step_text: str,
    ) -> None:
        # ── Derived geometry ──────────────────────────────────────────────
        #
        #  Card layout (top → bottom):
        #  ┌─────────────────────────────────────┐  ← y=0
        #  │░░░░░░░ accent bar (_ACCENT_H) ░░░░░░│
        #  ├─────────────────────────────────────┤  ← content_top
        #  │                                     │
        #  │  [icon]   App Name                  │
        #  │           Tagline                   │  ← content zone
        #  │           ─────────────────         │
        #  │           [v1.0 badge]              │
        #  │                                     │
        #  ├─────────────────────────────────────┤  ← footer_top
        #  │  status text…          [progress──] │
        #  │░░░░░░░░░░░░░░ bar (_BAR_H) ░░░░░░░░│
        #  └─────────────────────────────────────┘  ← y=h

        radius     = 16.0
        content_top = cls._ACCENT_H
        footer_top  = h - cls._FOOTER_H
        content_h   = footer_top - content_top   # usable middle zone height

        # Icon: centred vertically within the content zone
        icon_x = cls._PAD
        icon_y = content_top + (content_h - cls._ICON_SIZE) // 2

        # Text column: starts right of icon
        text_x     = icon_x + cls._ICON_SIZE + cls._ICON_GAP
        text_max_w = w - text_x - cls._PAD     # right-bounded by card margin

        # ── Render hints ──────────────────────────────────────────────────
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # ── Clip to card shape ────────────────────────────────────────────
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        p.setClipPath(clip)

        # ── Background ───────────────────────────────────────────────────
        bg = QLinearGradient(QPointF(0, 0), QPointF(w, h))
        bg.setColorAt(0.0, QColor(D.COLOR_BG))
        bg.setColorAt(1.0, QColor(D.COLOR_SURF))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRect(0, 0, w, h)

        # ── Grid texture (only in content zone, not over accent bar) ──────
        grid_col = QColor(D.COLOR_BDR2)
        grid_col.setAlpha(22)
        p.setPen(QPen(grid_col, 0.5))
        grid_step = 28
        for x in range(0, w, grid_step):
            p.drawLine(x, content_top, x, footer_top)
        for y in range(content_top, footer_top, grid_step):
            p.drawLine(0, y, w, y)
        p.setPen(Qt.PenStyle.NoPen)

        # ── Accent bar (drawn after grid — stays crisp) ───────────────────
        acc = QLinearGradient(QPointF(0, 0), QPointF(w, 0))
        acc.setColorAt(0.0, QColor(D.COLOR_ACC))
        acc.setColorAt(1.0, QColor(D.COLOR_ACC_DK))
        p.setBrush(QBrush(acc))
        p.drawRect(0, 0, w, cls._ACCENT_H)

        # ── Radial glow behind icon ───────────────────────────────────────
        icon_cx = icon_x + cls._ICON_SIZE / 2
        icon_cy = icon_y + cls._ICON_SIZE / 2
        glow_r  = cls._ICON_SIZE * 0.9
        glow = QRadialGradient(QPointF(icon_cx, icon_cy), glow_r)
        c_on  = QColor(D.COLOR_ACC); c_on.setAlpha(60)
        c_off = QColor(D.COLOR_ACC); c_off.setAlpha(0)
        glow.setColorAt(0.0, c_on)
        glow.setColorAt(1.0, c_off)
        p.setBrush(QBrush(glow))
        p.drawEllipse(
            QRectF(icon_cx - glow_r, icon_cy - glow_r, glow_r * 2, glow_r * 2)
        )

        # ── Icon ──────────────────────────────────────────────────────────
        if not icon_px.isNull():
            scaled = icon_px.scaled(
                cls._ICON_SIZE, cls._ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(icon_x, icon_y, scaled)

        # ── Text column — measure each row then stack top-down ────────────
        #
        # We measure the full text-block height first, then centre it
        # vertically within the content zone so it aligns with the icon.

        name_font = QFont(D.FONT_UI, D.FSIZE_2XL)
        name_font.setBold(True)
        name_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)

        tag_font  = QFont(D.FONT_UI, D.FSIZE_BASE)
        ver_font  = QFont(D.FONT_MONO, D.FSIZE_SM)

        # Measure row heights via font metrics
        p.setFont(name_font)
        name_fm   = p.fontMetrics()
        name_h    = name_fm.height()

        p.setFont(tag_font)
        tag_fm    = p.fontMetrics()
        tag_h     = tag_fm.height()

        p.setFont(ver_font)
        ver_fm    = p.fontMetrics()
        ver_text  = f"v{APP_VERSION}"
        badge_w   = ver_fm.horizontalAdvance(ver_text) + cls._BADGE_PAD_X * 2
        badge_h   = ver_fm.height() + cls._BADGE_PAD_Y * 2

        # Row spacing
        name_to_tag  = 6    # px between name baseline and tagline top
        tag_to_div   = 12   # px between tagline baseline and divider
        div_to_badge = cls._LINE_GAP

        # Total text-block height (cap-to-badge-bottom)
        block_h = (name_h + name_to_tag
                   + tag_h + tag_to_div
                   + 1                   # divider line
                   + div_to_badge
                   + badge_h)

        # Vertically centre the block within the content zone
        block_top = content_top + (content_h - block_h) // 2

        # ── Row positions (y = top of each row's bounding box) ────────────
        name_top  = block_top
        tag_top   = name_top  + name_h + name_to_tag
        div_y     = tag_top   + tag_h  + tag_to_div
        badge_top = div_y     + 1      + div_to_badge

        # App name (use QRect so Qt clips to text_max_w)
        p.setFont(name_font)
        p.setPen(QColor(D.COLOR_TXT_HEAD))
        p.drawText(
            QRect(text_x, name_top, text_max_w, name_h + 4),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            APP_NAME,
        )

        # Tagline
        p.setFont(tag_font)
        p.setPen(QColor(D.COLOR_ACC))
        p.drawText(
            QRect(text_x, tag_top, text_max_w, tag_h + 4),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "Intelligent Self-Organizing Project Manager",
        )

        # Divider line
        div_col = QColor(D.COLOR_BDR2)
        div_col.setAlpha(90)
        p.setPen(QPen(div_col, 1))
        p.drawLine(text_x, div_y, text_x + text_max_w, div_y)
        p.setPen(Qt.PenStyle.NoPen)

        # Version badge
        badge_bg  = QColor(D.COLOR_SURF3); badge_bg.setAlpha(180)
        badge_bdr = QColor(D.COLOR_BDR2)
        p.setBrush(QBrush(badge_bg))
        p.setPen(QPen(badge_bdr, 1))
        p.drawRoundedRect(
            QRectF(text_x, badge_top, badge_w, badge_h), 4.0, 4.0
        )
        p.setFont(ver_font)
        p.setPen(QColor(D.COLOR_TXT_DIS))
        p.drawText(
            QRect(text_x, badge_top, badge_w, badge_h),
            Qt.AlignmentFlag.AlignCenter,
            ver_text,
        )

        # ── Footer separator ──────────────────────────────────────────────
        sep_col = QColor(D.COLOR_BDR2); sep_col.setAlpha(50)
        p.setPen(QPen(sep_col, 1))
        p.drawLine(0, footer_top, w, footer_top)
        p.setPen(Qt.PenStyle.NoPen)

        # ── Status text (vertically centred in footer, above bar) ─────────
        status_zone_h = cls._FOOTER_H - cls._BAR_H
        if step_text:
            p.setFont(QFont(D.FONT_UI, D.FSIZE_SM))
            p.setPen(QColor(D.COLOR_TXT_DIS))
            p.drawText(
                QRect(cls._PAD, footer_top, w - cls._PAD * 2, status_zone_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                step_text,
            )

        # ── Progress bar (flush at card bottom, inside clip) ──────────────
        bar_y      = h - cls._BAR_H
        bar_filled = int(w * progress / 100)

        track_col = QColor(D.COLOR_SURF3); track_col.setAlpha(100)
        p.setBrush(QBrush(track_col))
        p.drawRect(0, bar_y, w, cls._BAR_H)

        if bar_filled > 0:
            fill = QLinearGradient(QPointF(0, 0), QPointF(w, 0))
            fill.setColorAt(0.0, QColor(D.COLOR_ACC))
            fill.setColorAt(1.0, QColor(D.COLOR_ACC_DK))
            p.setBrush(QBrush(fill))
            p.drawRect(0, bar_y, bar_filled, cls._BAR_H)

        # ── Border (last — drawn on top of everything) ────────────────────
        p.setClipping(False)
        bdr_col = QColor(D.COLOR_BDR2); bdr_col.setAlpha(110)
        p.setPen(QPen(bdr_col, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)


# ── Main ───────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Forix")

    # When the last window is closed normally the app should exit.
    # Set to False only if a system-tray icon keeps the app alive intentionally.
    app.setQuitOnLastWindowClosed(True)

    # Base font — before palette so all widgets inherit it
    app.setFont(QFont(D.FONT_UI, D.FSIZE_BASE))

    # CRITICAL: apply dark palette before ANY window is created
    _apply_dark_palette(app)

    # Icon — use apply_icon_to_app so Windows AppUserModelID is set correctly
    from utils.icon_manager import apply_icon_to_app
    app_icon = apply_icon_to_app(app)

    # Splash — show immediately so the user sees feedback during slow imports
    splash = _SplashScreen(app_icon.pixmap(128, 128))
    splash.show()
    app.processEvents()

    # Step 0 — database: MUST run before any other module queries the DB.
    # init_db() creates all tables (idempotent) and runs column migrations.
    # BackgroundService and MainWindow both trigger DB queries at import time
    # via forix.settings, so this must precede both imports.
    splash.set_step(0)
    app.processEvents()
    from core.database import init_db
    init_db()
    from services.background_service import BackgroundService

    # Step 1 — UI
    splash.set_step(1)
    app.processEvents()
    from ui.main_window import MainWindow
    from ui.stylesheet import GLOBAL_STYLESHEET
    app.setStyleSheet(GLOBAL_STYLESHEET)

    window = MainWindow(app_icon=app_icon)
    # Propagate icon explicitly to the window as well (covers edge cases where
    # QApplication.setWindowIcon doesn't reach already-constructed windows).
    window.setWindowIcon(app_icon)

    # Step 2 — background service
    splash.set_step(2)
    app.processEvents()
    service = BackgroundService(
        ui_notify_callback=window.on_organiser_event,
        ui_project_opened_callback=lambda pid: window.project_opened.emit(pid),
    )
    service.start()
    window._bg_service = service

    # Step 3 — done
    splash.set_step(3)
    app.processEvents()

    def _show() -> None:
        splash.finish(window)
        window.show()
        window.raise_()
        window.activateWindow()

    QTimer.singleShot(900, _show)
    app.aboutToQuit.connect(lambda: service.stop())

    log.info("Forix event loop starting")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()