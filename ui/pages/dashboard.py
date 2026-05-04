# forix/ui/pages/dashboard.py
"""Forix — Dashboard Page"""
import datetime, logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.database import get_session, Project, ActivityEvent, TrackedFile, Version, InventoryItem
import design as D
from ui.widgets.project_card import ProjectCard
from ui.widgets.stat_tile import StatTile
from ui.widgets.activity_feed import ActivityFeed

log = logging.getLogger("forix.dashboard")


def _section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_XS}pt; font-weight: 700; "
        f"letter-spacing: 0.6px; background: transparent; border: none;"
    )
    return l


def _section_rule() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
    return f


class DashboardPage(QWidget):
    project_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setObjectName("pageHeader")
        hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(D.SP_6, 0, D.SP_6, 0)
        hl.setSpacing(D.SP_3)

        t = QLabel("Dashboard")
        t.setObjectName("pageTitle")
        hl.addWidget(t)
        hl.addStretch()

        self._date = QLabel()
        self._date.setStyleSheet(
            f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_SM}pt; "
            f"background: transparent; border: none;"
        )
        hl.addWidget(self._date)
        root.addWidget(hdr)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
        root.addWidget(rule)

        # ── Scrollable body ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 4px; border-radius: 2px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {D.COLOR_BDR2}; border-radius: 2px; min-height: 24px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        body_w = QWidget()
        body_w.setStyleSheet(f"background: {D.COLOR_BG};")
        body = QVBoxLayout(body_w)
        body.setContentsMargins(D.SP_6, D.SP_5, D.SP_6, D.SP_8)
        body.setSpacing(D.SP_6)

        # ── Stat tiles ────────────────────────────────────────────────
        tiles = QHBoxLayout()
        tiles.setSpacing(D.SP_3)
        self._t_proj = StatTile("Projects",      "0", D.COLOR_ACC)
        self._t_file = StatTile("Files Tracked", "0", D.COLOR_ACC2)
        self._t_snap = StatTile("Snapshots",     "0", D.COLOR_OK)
        self._t_evnt = StatTile("Events Today",  "0", D.COLOR_WRN)
        for tile in [self._t_proj, self._t_file, self._t_snap, self._t_evnt]:
            tiles.addWidget(tile)
        body.addLayout(tiles)

        # ── Mid split: recent projects | activity + low stock ─────────
        mid = QHBoxLayout()
        mid.setSpacing(D.SP_5)

        # Left column — recent projects
        left = QVBoxLayout()
        left.setSpacing(D.SP_2)

        lhdr = QHBoxLayout()
        lhdr.setSpacing(D.SP_2)
        lhdr.addWidget(_section_label("RECENT PROJECTS"))
        lhdr.addWidget(_section_rule_h())
        lhdr.addStretch()
        va = QPushButton("View All →")
        va.setObjectName("ghostBtn")
        va.clicked.connect(lambda: self.project_selected.emit(-1))
        lhdr.addWidget(va)
        left.addLayout(lhdr)

        proj_scroll = QScrollArea()
        proj_scroll.setWidgetResizable(True)
        proj_scroll.setFrameShape(QFrame.Shape.NoFrame)
        proj_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        proj_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 3px; border-radius: 1px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {D.COLOR_BDR2}; border-radius: 1px; min-height: 20px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self._proj_cont = QWidget()
        self._proj_cont.setStyleSheet("background: transparent;")
        self._proj_lay = QVBoxLayout(self._proj_cont)
        self._proj_lay.setSpacing(D.SP_2)
        self._proj_lay.setContentsMargins(0, 0, 0, 0)
        self._proj_lay.addStretch()
        proj_scroll.setWidget(self._proj_cont)
        left.addWidget(proj_scroll)
        mid.addLayout(left, 3)

        # Right column — activity feed + low stock
        right = QVBoxLayout()
        right.setSpacing(D.SP_3)

        act_hdr = QHBoxLayout()
        act_hdr.setSpacing(D.SP_2)
        act_hdr.addWidget(_section_label("LIVE ACTIVITY"))
        act_hdr.addWidget(_section_rule_h())
        right.addLayout(act_hdr)

        self._feed = ActivityFeed()
        self._feed.setMinimumHeight(180)
        right.addWidget(self._feed, 1)

        # Low stock panel
        self._low_w = QWidget()
        self._low_w.setVisible(False)
        self._low_w.setStyleSheet("background: transparent;")
        lw_lay = QVBoxLayout(self._low_w)
        lw_lay.setContentsMargins(0, 0, 0, 0)
        lw_lay.setSpacing(D.SP_2)

        low_hdr = QHBoxLayout()
        low_hdr.setSpacing(D.SP_2)
        low_hdr.addWidget(_section_label("⚠  LOW STOCK"))
        low_hdr.addWidget(_section_rule_h())
        lw_lay.addLayout(low_hdr)

        self._low_lay = QVBoxLayout()
        self._low_lay.setSpacing(D.SP_1)
        lw_lay.addLayout(self._low_lay)
        right.addWidget(self._low_w)

        mid.addLayout(right, 2)
        body.addLayout(mid)

        scroll.setWidget(body_w)
        root.addWidget(scroll)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        try:
            self._date.setText(datetime.datetime.now().strftime("%A, %d %B %Y"))
            s = get_session()
            try:
                self._t_proj.set_value(str(s.query(Project).count()))
                self._t_file.set_value(str(s.query(TrackedFile).count()))
                self._t_snap.set_value(str(s.query(Version).count()))
                today = datetime.datetime.utcnow().date()
                n_ev = s.query(ActivityEvent).filter(
                    ActivityEvent.created_at >= datetime.datetime(today.year, today.month, today.day)
                ).count()
                self._t_evnt.set_value(str(n_ev))

                projects = (
                    s.query(Project)
                    .order_by(Project.last_activity.desc())
                    .limit(8)
                    .all()
                )
                while self._proj_lay.count() > 1:
                    item = self._proj_lay.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                for p in projects:
                    card = ProjectCard(p.to_dict())
                    card.clicked.connect(lambda pid=p.id: self.project_selected.emit(pid))
                    self._proj_lay.insertWidget(self._proj_lay.count() - 1, card)

                events = (
                    s.query(ActivityEvent)
                    .order_by(ActivityEvent.created_at.desc())
                    .limit(50)
                    .all()
                )
                self._feed.set_events([
                    (e.event_type, e.description, e.created_at) for e in events
                ])

                low = [i for i in s.query(InventoryItem).all() if i.is_low()]
                self._update_low(low)
            finally:
                s.close()
        except Exception as e:
            log.error(f"Dashboard refresh: {e}")
            self._notify_error(str(e))

    def _update_low(self, items):
        while self._low_lay.count():
            item = self._low_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not items:
            self._low_w.setVisible(False)
            return
        self._low_w.setVisible(True)
        for inv in items[:5]:
            row = QWidget()
            row.setFixedHeight(28)
            row.setStyleSheet(
                f"background: {D.COLOR_WRN_TINT}; border-radius: {D.R_SM}px;"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(D.SP_2, 0, D.SP_2, 0)
            rl.setSpacing(D.SP_2)

            n = QLabel(f"⚠ {inv.name}")
            n.setStyleSheet(
                f"font-size: {D.FSIZE_SM}pt; color: {D.COLOR_WRN}; "
                f"background: transparent; border: none;"
            )
            rl.addWidget(n, 1)

            q = QLabel(f"{inv.quantity} {inv.unit}")
            q.setStyleSheet(
                f"font-size: {D.FSIZE_SM}pt; font-weight: 700; color: {D.COLOR_WRN}; "
                f"background: transparent; border: none;"
            )
            rl.addWidget(q)
            self._low_lay.addWidget(row)

    def _notify_error(self, msg):
        win = self.window()
        if hasattr(win, "_notify"):
            win._notify("error", msg)


# ── Inline helpers (defined after class to avoid forward-ref issues) ──────────

def _section_rule_h() -> QFrame:
    """Horizontal expander rule for section headers."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    f.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
    return f