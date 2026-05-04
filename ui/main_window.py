# forix/ui/main_window.py
"""Forix — Main Application Window v4"""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QLabel, QStatusBar, QSystemTrayIcon, QMenu,
    QApplication, QSplitter, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSettings
from PyQt6.QtGui import QIcon, QPixmap, QColor

import design as D
from core.constants import APP_NAME, APP_VERSION
from ui.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.projects import ProjectsPage
from ui.pages.project_detail import ProjectDetailPage
from ui.pages.inventory import InventoryPage
from ui.pages.search_page import SearchPage
from ui.pages.settings_page import SettingsPage
from ui.pages.activity_page import ActivityPage
from ui.pages.health_page import HealthPage
from ui.pages.duplicate_manager import DuplicateManagerPage
from ui.command_palette import CommandPalette
from ui.stylesheet import GLOBAL_STYLESHEET

log = logging.getLogger("forix.ui")

_NAV_MAP = {
    "dashboard":  0,
    "projects":   1,
    # 2 = project detail (no sidebar entry)
    "inventory":  3,
    "search":     4,
    "settings":   5,
    "activity":   6,
    "health":     7,
    "duplicates": 8,
}
_NAV_REV = {v: k for k, v in _NAV_MAP.items()}


class MainWindow(QMainWindow):
    notify_signal  = pyqtSignal(str, str)
    project_opened = pyqtSignal(int)

    def __init__(self, app_icon: QIcon = None, organiser=None):
        super().__init__()
        self._app_icon  = app_icon
        self._organiser = organiser
        self._prev_idx  = 0
        self._setup_window()
        self._build_ui()
        self._setup_tray()
        self._setup_extras()
        self._connect_signals()
        self._start_timers()

    # ── Window ────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME}  ·  v{APP_VERSION}")
        self.setMinimumSize(D.WIN_MIN_W, D.WIN_MIN_H)
        self.resize(D.WIN_DEFAULT_W, D.WIN_DEFAULT_H)
        self.setStyleSheet(GLOBAL_STYLESHEET)
        if self._app_icon:
            self.setWindowIcon(self._app_icon)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack   = QStackedWidget()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        root.addWidget(self.splitter)

        self._load_geometry()

        # Pages — index must match _NAV_MAP
        self.page_dashboard  = DashboardPage()        # 0
        self.page_projects   = ProjectsPage()         # 1
        self.page_detail     = ProjectDetailPage()    # 2
        self.page_inventory  = InventoryPage()        # 3
        self.page_search     = SearchPage()           # 4
        self.page_settings   = SettingsPage()         # 5
        self.page_activity   = ActivityPage()         # 6
        self.page_health     = HealthPage()           # 7
        self.page_duplicates = DuplicateManagerPage() # 8

        for pg in [
            self.page_dashboard, self.page_projects,   self.page_detail,
            self.page_inventory, self.page_search,     self.page_settings,
            self.page_activity,  self.page_health,     self.page_duplicates,
        ]:
            self.stack.addWidget(pg)

        self._build_statusbar()

    def _build_statusbar(self):
        sb = QStatusBar()
        sb.setFixedHeight(D.STATUSBAR_H)
        sb.setSizeGripEnabled(False)
        sb.setStyleSheet(
            f"QStatusBar {{"
            f"  background: {D.COLOR_SURF};"
            f"  border: none;"
            f"  border-top: 1px solid {D.COLOR_BDR};"
            f"}}"
            f"QStatusBar::item {{ border: none; }}"
        )
        self.setStatusBar(sb)

        self._status_msg = QLabel("Ready")
        self._status_msg.setStyleSheet(
            f"color: {D.COLOR_TXT2}; background: transparent; border: none; "
            f"font-size: {D.FSIZE_SM}pt;"
        )
        sb.addWidget(self._status_msg)

        sb.addPermanentWidget(_vline())

        self._counts_lbl = QLabel("")
        self._counts_lbl.setStyleSheet(
            f"color: {D.COLOR_TXT2}; background: transparent; border: none; "
            f"font-size: {D.FSIZE_SM}pt;"
        )
        sb.addPermanentWidget(self._counts_lbl)

        sb.addPermanentWidget(_vline())

        self._live_dot = QLabel("● LIVE")
        self._live_dot.setStyleSheet(
            f"color: {D.COLOR_OK}; background: transparent; border: none; "
            f"font-size: {D.FSIZE_XS}pt; font-weight: 700; letter-spacing: 0.5px;"
        )
        sb.addPermanentWidget(self._live_dot)

        pad = QLabel()
        pad.setFixedWidth(D.SP_3)
        pad.setStyleSheet("background: transparent; border: none;")
        sb.addPermanentWidget(pad)

    # ── Tray ──────────────────────────────────────────────────────────────────

    def _setup_extras(self):
        """Set up command palette and keyboard shortcuts."""
        from PyQt6.QtGui import QShortcut, QKeySequence

        # Command palette (Ctrl+K)
        self._palette = CommandPalette(self, self._on_nav, self._palette_action)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(
            self._palette.show_palette)

        # Number key shortcuts 1–7
        for num, page in enumerate(
            ["dashboard", "projects", "inventory", "search",
             "activity", "health", "duplicates"],
            start=1,
        ):
            # FIX: use a named slot instead of a lambda so the signal's
            # implicit argument (Qt passes pos for some signals) never
            # accidentally lands on a parameter named '_'.
            QShortcut(QKeySequence(str(num)), self).activated.connect(
                self._make_nav_slot(page))

        # Help / shortcuts modal (? key)
        QShortcut(QKeySequence("?"), self).activated.connect(
            self._show_shortcuts)

    def _make_nav_slot(self, page: str):
        """Return a zero-argument callable that navigates to `page`.

        Using a dedicated factory avoids the classic loop-lambda closure bug
        and keeps the slot signature clean (no accidental extra arguments).
        """
        def _slot():
            self._on_nav(page)
        return _slot

    def _palette_action(self, cmd: str):
        actions = {
            "New Project":              lambda: (self._on_nav("projects"),
                                                 self.page_projects._new()),
            "Import Folder as Project": lambda: (self._on_nav("projects"),
                                                 self.page_projects._import()),
            "Create Snapshot":          lambda: (
                self.page_detail._snapshot()
                if self.stack.currentIndex() == 2 else None),
            "Open in Explorer":         lambda: (
                self.page_detail._explorer()
                if self.stack.currentIndex() == 2 else None),
            "Open Duplicate Manager":   lambda: self._on_nav("duplicates"),
            "Open Activity Log":        lambda: self._on_nav("activity"),
            "Open Health Monitor":      lambda: self._on_nav("health"),
        }
        fn = actions.get(cmd)
        if fn:
            fn()

    def _show_shortcuts(self):
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(f"background:{D.COLOR_SURF};")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(D.SP_5, D.SP_4, D.SP_5, D.SP_4)
        lay.setSpacing(D.SP_3)

        title = QLabel("⌨  Keyboard Shortcuts")
        title.setStyleSheet(
            f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_LG}pt;"
            "font-weight:800;background:transparent;border:none;")
        lay.addWidget(title)

        shortcuts = [
            ("Ctrl+K",       "Open Command Palette"),
            ("?",            "Show this help"),
            ("1",            "Go to Dashboard"),
            ("2",            "Go to Projects"),
            ("3",            "Go to Inventory"),
            ("4",            "Go to Search"),
            ("5",            "Go to Activity Log"),
            ("6",            "Go to Health Monitor"),
            ("7",            "Go to Duplicates"),
            ("Esc",          "Close palettes / panels"),
        ]
        for key, desc in shortcuts:
            row = QWidget()
            row.setStyleSheet("background:transparent;border:none;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(D.SP_3)
            kl = QLabel(f" {key} ")
            kl.setStyleSheet(
                f"background:{D.COLOR_SURF2};color:{D.COLOR_TXT};"
                f"border:1px solid {D.COLOR_BDR2};border-radius:{D.R_SM}px;"
                f"font-family:'{D.FONT_MONO}';font-size:{D.FSIZE_SM}pt;"
                f"padding:2px 4px;")
            dl = QLabel(desc)
            dl.setStyleSheet(
                f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_SM}pt;"
                "background:transparent;border:none;")
            rl.addWidget(kl)
            rl.addWidget(dl)
            rl.addStretch()
            lay.addWidget(row)

        ok = QPushButton("Close")
        ok.setObjectName("accentBtn")
        ok.setFixedHeight(D.H_BTN)
        ok.clicked.connect(dlg.accept)
        lay.addWidget(ok)
        dlg.exec()

    def _setup_tray(self):
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            # Guard: if a tray icon already exists and is visible, tear it
            # down cleanly before creating a new one.  Without this, any
            # code path that calls _setup_tray() more than once (or a second
            # MainWindow instance created during a restart) leaves orphaned
            # icons in the system tray that persist until the OS session ends.
            if hasattr(self, "_tray") and self._tray is not None:
                self._tray.hide()
                self._tray = None

            self._tray = QSystemTrayIcon(self)
            if self._app_icon:
                self._tray.setIcon(self._app_icon)
            else:
                px = QPixmap(16, 16)
                px.fill(QColor(D.COLOR_ACC))
                self._tray.setIcon(QIcon(px))
            self._tray.setToolTip(f"{APP_NAME} — Running in background")

            menu = QMenu()
            menu.addAction("Show Forix", self.show_and_raise)
            menu.addSeparator()
            menu.addAction("Dashboard",
                           lambda: (self.show_and_raise(),
                                    self._on_nav("dashboard")))
            menu.addAction("Projects",
                           lambda: (self.show_and_raise(),
                                    self._on_nav("projects")))
            menu.addSeparator()
            menu.addAction("Quit Forix", self._quit_app)

            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._tray_activated)
            self._tray.show()
        except Exception as e:
            log.warning(f"Tray setup failed: {e}")

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_and_raise()

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        """Clean shutdown from the tray menu.

        QApplication.quit() does not call closeEvent when triggered from the
        tray context menu (the window may be hidden), so the tray icon would
        linger in the notification area until the OS recycles it.  Hiding it
        explicitly here ensures it disappears immediately on every platform.
        """
        if hasattr(self, "_tray") and self._tray is not None:
            self._tray.hide()
        self._save_geometry()
        QApplication.quit()

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _save_geometry(self):
        try:
            s = QSettings("Forix", "ForixApp")
            s.setValue("geometry", self.saveGeometry())
            s.setValue("splitter", self.splitter.saveState())
        except Exception as e:
            log.warning(f"Save geometry: {e}")

    def _load_geometry(self):
        try:
            s = QSettings("Forix", "ForixApp")
            geo = s.value("geometry")
            if geo:
                self.restoreGeometry(geo)
            sp = s.value("splitter")
            if sp:
                self.splitter.restoreState(sp)
            else:
                self.splitter.setSizes(
                    [D.SIDEBAR_W, D.WIN_DEFAULT_W - D.SIDEBAR_W])
        except Exception as e:
            log.warning(f"Load geometry: {e}")
            self.splitter.setSizes(
                [D.SIDEBAR_W, D.WIN_DEFAULT_W - D.SIDEBAR_W])

    # ── Signals ───────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.sidebar.nav_changed.connect(self._on_nav)
        self.sidebar.collapsed_changed.connect(self._on_sidebar_toggle)
        # splitterMoved(pos: int, index: int) — both args forwarded correctly
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self.page_projects.project_selected.connect(self._open_project)
        self.page_dashboard.project_selected.connect(self._open_project)
        self.page_health.project_selected.connect(self._open_project)
        self.page_detail.back_signal.connect(self._go_back)
        self.notify_signal.connect(self._notify)
        self.project_opened.connect(self._open_project)

    def _on_sidebar_toggle(self, collapsed: bool):
        w = D.SIDEBAR_W_MIN if collapsed else D.SIDEBAR_W
        self.splitter.setSizes([w, self.width() - w])

    def _on_splitter_moved(self, pos: int, index: int):
        self.sidebar.handle_resize(pos)

    def _on_nav(self, page_name: str):
        idx = _NAV_MAP.get(page_name, 0)
        self._prev_idx = self.stack.currentIndex()
        self.stack.setCurrentIndex(idx)
        self.sidebar.set_active(page_name)
        self._refresh_page(idx)

    def _open_project(self, project_id: int):
        if project_id == -1:
            self._on_nav("projects")
            return
        try:
            self._prev_idx = self.stack.currentIndex()
            self.page_detail.load_project(project_id)
            self.stack.setCurrentIndex(2)
            self.sidebar.set_active("projects")
        except Exception as e:
            log.error(f"Open project: {e}")
            self._notify("error", f"Failed to open project: {e}")

    def _go_back(self):
        target = self._prev_idx if self._prev_idx != 2 else 1
        self.stack.setCurrentIndex(target)
        self.sidebar.set_active(_NAV_REV.get(target, "projects"))
        self._refresh_page(target)

    # ── Notifications ─────────────────────────────────────────────────────────

    def _notify(self, level: str, message: str):
        color = {
            "info":    D.COLOR_ACC,
            "success": D.COLOR_OK,
            "warn":    D.COLOR_WRN,
            "warning": D.COLOR_WRN,
            "error":   D.COLOR_ERR,
        }.get(level, D.COLOR_TXT2)

        self._status_msg.setText(message)
        self._status_msg.setStyleSheet(
            f"color: {color}; background: transparent; border: none; "
            f"font-size: {D.FSIZE_SM}pt;"
        )
        QTimer.singleShot(8000, self._reset_status)

        if level in ("warn", "error") and hasattr(self, "_tray"):
            try:
                self._tray.showMessage(
                    APP_NAME, message,
                    QSystemTrayIcon.MessageIcon.Warning, 4000,
                )
            except Exception:
                pass

    def _reset_status(self):
        self._status_msg.setText("Ready")
        self._status_msg.setStyleSheet(
            f"color: {D.COLOR_TXT2}; background: transparent; border: none; "
            f"font-size: {D.FSIZE_SM}pt;"
        )

    # ── Timers ────────────────────────────────────────────────────────────────

    def _start_timers(self):
        QTimer.singleShot(400, lambda: self._refresh_page(0))

        t = QTimer(self)
        t.setInterval(30_000)
        t.timeout.connect(
            lambda: self._refresh_page(self.stack.currentIndex()))
        t.start()

        t2 = QTimer(self)
        t2.setInterval(15_000)
        t2.timeout.connect(self._update_counts)
        t2.start()
        QTimer.singleShot(1500, self._update_counts)

    def _refresh_page(self, idx: int):
        try:
            if   idx == 0: self.page_dashboard.refresh()
            elif idx == 1: self.page_projects.refresh()
            elif idx == 3: self.page_inventory.refresh()
            elif idx == 6: self.page_activity.refresh()
            elif idx == 7: self.page_health.refresh()
            elif idx == 8: self.page_duplicates.refresh()
            self._update_badges()
        except Exception as e:
            log.warning(f"Page refresh idx={idx}: {e}")
            self._notify("error", f"Refresh error: {e}")

    def _update_badges(self):
        """Update sidebar badges for low-stock, stale, and duplicate counts."""
        try:
            # FIX: get_session was used but never imported in this method.
            # All database symbols must be imported together in the same block.
            from core.database import (
                get_session, InventoryItem, Project, DuplicateGroup,
            )
            s = get_session()
            try:
                low   = sum(1 for i in s.query(InventoryItem).all()
                            if i.is_low())
                stale = s.query(Project).filter(
                    Project.status.in_(["stale", "on-hold"]),
                    Project.is_deleted.is_(False),
                ).count()
                dupes = s.query(DuplicateGroup).filter_by(
                    resolved=False).count()
            finally:
                s.close()
            self.sidebar.set_badge("inventory",  low)
            self.sidebar.set_badge("health",     stale)
            self.sidebar.set_badge("duplicates", dupes)
        except Exception:
            pass

    def _update_counts(self):
        try:
            from core.database import get_session, Project, TrackedFile
            s = get_session()
            try:
                np = s.query(Project).count()
                nf = s.query(TrackedFile).count()
                self._counts_lbl.setText(f"{np} projects · {nf} files")
            finally:
                s.close()
        except Exception:
            pass

    # ── External hooks ────────────────────────────────────────────────────────

    def on_organiser_event(self, level: str, message: str):
        self.notify_signal.emit(level, message)

    def closeEvent(self, event):
        self._save_geometry()
        if hasattr(self, "_tray") and self._tray is not None and self._tray.isVisible():
            self.hide()
            try:
                self._tray.showMessage(
                    APP_NAME, "Forix is running in the background.",
                    QSystemTrayIcon.MessageIcon.Information, 2000,
                )
            except Exception:
                pass
            event.ignore()
        else:
            # Real quit — hide the tray icon immediately so it doesn't linger
            # in the system tray after the process exits.  Qt only removes it
            # reliably when .hide() is called explicitly before destruction.
            if hasattr(self, "_tray") and self._tray is not None:
                self._tray.hide()
            event.accept()


# ── Module-level helpers ──────────────────────────────────────────────────────

def _vline() -> QLabel:
    """Thin vertical separator for the status bar."""
    sep = QLabel()
    sep.setFixedWidth(1)
    sep.setFixedHeight(14)
    sep.setStyleSheet(f"background: {D.COLOR_BDR2}; border: none;")
    return sep