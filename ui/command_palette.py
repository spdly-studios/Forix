# forix/ui/command_palette.py
"""
Forix — Command Palette  (Ctrl+K)
Fuzzy-search across projects, commands, and pages.
Appears as a centred floating overlay; Escape or click-outside dismisses it.
"""
import logging
from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QWidget, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QIcon
from core.database import get_session, Project
import design as D

log = logging.getLogger("forix.palette")

# ── Built-in commands ─────────────────────────────────────────────────────────
# Each entry: (display label, subtitle, icon, callable)
_COMMANDS: list[tuple[str, str, str]] = [
    ("Go to Dashboard",          "Navigate",         "◉"),
    ("Go to Projects",           "Navigate",         "◈"),
    ("Go to Inventory",          "Navigate",         "▤"),
    ("Go to Search",             "Navigate",         "⌕"),
    ("Go to Settings",           "Navigate",         "⚙"),
    ("New Project",              "Action",           "＋"),
    ("Import Folder as Project", "Action",           "↑"),
    ("Create Snapshot",          "Action · Current project", "📸"),
    ("Open in Explorer",         "Action · Current project", "📂"),
    ("Open AI Assistant",        "Action",           "✦"),
    ("Open Duplicate Manager",   "Action",           "⊕"),
]

_CMD_NAV = {
    "Go to Dashboard":          "dashboard",
    "Go to Projects":           "projects",
    "Go to Inventory":          "inventory",
    "Go to Search":             "search",
    "Go to Settings":           "settings",
}


class CommandPalette(QDialog):
    """
    Modal command palette overlay.

    Usage:
        palette = CommandPalette(main_window, navigate_fn, action_fn)
        palette.show_palette()

    navigate_fn(page_name: str) — called to switch pages
    action_fn(command: str)     — called for non-nav commands
    """

    def __init__(self, parent, navigate_fn: Callable, action_fn: Callable):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._nav    = navigate_fn
        self._action = action_fn
        self._items: list[tuple[str, str, str, Optional[int]]] = []  # label,sub,icon,pid
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Outer card
        card = QWidget()
        card.setFixedWidth(560)
        card.setStyleSheet(
            f"background:{D.COLOR_SURF};"
            f"border:1px solid {D.COLOR_BDR2};"
            f"border-radius:{D.R_LG}px;"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Search input
        search_w = QWidget()
        search_w.setStyleSheet(
            f"background:{D.COLOR_SURF2};"
            f"border-radius:{D.R_LG}px {D.R_LG}px 0 0;"
        )
        sl = QHBoxLayout(search_w)
        sl.setContentsMargins(D.SP_4, 0, D.SP_4, 0)
        sl.setSpacing(D.SP_2)

        lupe = QLabel("⌕")
        lupe.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_LG}pt;"
            "background:transparent;border:none;"
        )
        sl.addWidget(lupe)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or project name…")
        self._input.setFixedHeight(48)
        self._input.setStyleSheet(
            f"background:transparent;border:none;"
            f"color:{D.COLOR_TXT};font-size:{D.FSIZE_MD}pt;"
            "padding:0;"
        )
        self._input.textChanged.connect(self._filter)
        self._input.installEventFilter(self)
        sl.addWidget(self._input)

        kl = QLabel("Esc to close")
        kl.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
            "background:transparent;border:none;"
        )
        sl.addWidget(kl)
        cl.addWidget(search_w)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;")
        cl.addWidget(sep)

        # Results list
        self._list = QListWidget()
        self._list.setFixedHeight(320)
        self._list.setStyleSheet(
            f"QListWidget{{background:{D.COLOR_SURF};border:none;"
            f"color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;}}"
            f"QListWidget::item{{padding:10px {D.SP_4}px;"
            f"border-bottom:1px solid {D.COLOR_BDR};}}"
            f"QListWidget::item:selected{{background:{D.COLOR_ACC_TINT};"
            f"color:{D.COLOR_TXT};}}"
            f"QListWidget::item:hover:!selected{{background:{D.COLOR_SURF2};}}"
        )
        self._list.itemActivated.connect(self._execute)
        cl.addWidget(self._list)

        # Footer hint
        foot = QWidget()
        foot.setFixedHeight(30)
        foot.setStyleSheet(
            f"background:{D.COLOR_SURF2};"
            f"border-radius:0 0 {D.R_LG}px {D.R_LG}px;"
            f"border-top:1px solid {D.COLOR_BDR};"
        )
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(D.SP_4, 0, D.SP_4, 0)
        for key, desc in [("↑↓", "navigate"), ("Enter", "select"), ("Esc", "close")]:
            kw = QLabel(f" {key} ")
            kw.setStyleSheet(
                f"background:{D.COLOR_SURF3};color:{D.COLOR_TXT};"
                f"border-radius:{D.R_SM}px;font-size:{D.FSIZE_XS}pt;"
                "font-weight:700;border:none;padding:0 2px;"
            )
            dw = QLabel(desc)
            dw.setStyleSheet(
                f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                "background:transparent;border:none;"
            )
            fl.addWidget(kw); fl.addWidget(dw); fl.addSpacing(D.SP_3)
        fl.addStretch()
        cl.addWidget(foot)

        root.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    # ── Show ───────────────────────────────────────────────────────────────────

    def show_palette(self):
        # Position centred horizontally, 20% from top of parent
        parent = self.parent()
        if parent:
            pw, ph = parent.width(), parent.height()
            self.setFixedWidth(pw)          # full-width transparent overlay
            self.setFixedHeight(ph)
            self.move(parent.mapToGlobal(parent.rect().topLeft()))
        self._input.clear()
        self._populate_all()
        self.show()
        self._input.setFocus()

    # ── Data ───────────────────────────────────────────────────────────────────

    def _populate_all(self):
        self._items = []
        # Commands
        for label, sub, icon in _COMMANDS:
            self._items.append((label, sub, icon, None))
        # Projects
        try:
            s = get_session()
            try:
                projs = (s.query(Project)
                         .filter(Project.is_deleted.is_(False))
                         .order_by(Project.last_activity.desc())
                         .limit(40).all())
                for p in projs:
                    self._items.append((p.name, f"Project · {p.project_type}", "◈", p.id))
            finally:
                s.close()
        except Exception as exc:
            log.warning("Palette: could not load projects: %s", exc)
        self._render(self._items)

    def _filter(self, text: str):
        q = text.strip().lower()
        if not q:
            self._render(self._items)
            return
        try:
            from fuzzywuzzy import fuzz
            def score(label): return max(
                fuzz.partial_ratio(q, label.lower()),
                100 if q in label.lower() else 0)
        except ImportError:
            def score(label): return 80 if q in label.lower() else 0

        matched = [(l, s, i, pid) for l, s, i, pid in self._items
                   if score(l) >= 40 or q in l.lower()]
        matched.sort(key=lambda x: (-score(x[0]), x[0].lower()))
        self._render(matched)

    def _render(self, items):
        self._list.clear()
        for label, sub, icon, pid in items[:20]:
            col = D.COLOR_ACC if pid is None else D.COLOR_TXT_HEAD
            item = QListWidgetItem(f"  {icon}   {label}    ·    {sub}")
            item.setForeground(QColor(col))
            item.setData(Qt.ItemDataRole.UserRole, (label, pid))
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    # ── Execute ────────────────────────────────────────────────────────────────

    def _execute(self, item: QListWidgetItem):
        label, pid = item.data(Qt.ItemDataRole.UserRole)
        self.hide()
        self._input.clear()
        if pid is not None:
            # It's a project — open its detail page
            win = self.parent()
            if hasattr(win, '_open_project'):
                win._open_project(pid)
        elif label in _CMD_NAV:
            self._nav(_CMD_NAV[label])
        else:
            self._action(label)

    # ── Key handling ───────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._input and isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hide(); return True
            if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
                cur = self._list.currentItem()
                if cur: self._execute(cur)
                return True
            if key == Qt.Key.Key_Down:
                r = self._list.currentRow()
                self._list.setCurrentRow(min(r + 1, self._list.count() - 1))
                return True
            if key == Qt.Key.Key_Up:
                r = self._list.currentRow()
                self._list.setCurrentRow(max(r - 1, 0))
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, e):
        # Click outside the card → close
        child = self.childAt(e.position().toPoint())
        if child is None:
            self.hide()
        else:
            super().mousePressEvent(e)