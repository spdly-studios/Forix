# forix/ui/pages/activity_page.py
"""
Forix — Activity Log Page
Full scrollable, filterable history of all system events with
a 7-day sparkline bar chart showing daily activity volume.
"""
import datetime
import logging
from collections import defaultdict

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import ActivityEvent, Project, get_session
import design as D

log = logging.getLogger("forix.activity")

_EV_ICONS = {
    "project_created": ("✦", D.COLOR_ACC),
    "version_created": ("📸", D.COLOR_ACC2),
    "file_added":      ("＋", D.COLOR_OK),
    "file_modified":   ("~",  D.COLOR_WRN),
    "file_deleted":    ("−",  D.COLOR_ERR),
    "scratch_created": ("🗂",  D.COLOR_INF),
    "archived":        ("◌",  D.COLOR_TXT2),
    "default":         ("·",  D.COLOR_TXT2),
}

_SS_TABLE = (
    f"QTableWidget{{background:{D.COLOR_BG};border:none;"
    f"gridline-color:{D.COLOR_BDR};color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;}}"
    f"QTableWidget::item{{padding:0 {D.SP_2}px;border:none;}}"
    f"QTableWidget::item:selected{{background:{D.COLOR_ACC_TINT};color:{D.COLOR_TXT};}}"
    f"QTableWidget::item:alternate{{background:{D.COLOR_SURF};}}"
    f"QHeaderView::section{{background:{D.COLOR_SURF2};color:{D.COLOR_TXT2};"
    f"font-size:{D.FSIZE_XS}pt;font-weight:700;border:none;"
    f"border-bottom:1px solid {D.COLOR_BDR2};padding:{D.SP_1}px {D.SP_2}px;}}"
)
_SS_COMBO = (
    f"QComboBox{{background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
    f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
    f"padding:0 {D.SP_3}px;}}"
    f"QComboBox:hover{{border-color:{D.COLOR_ACC};}}"
    f"QComboBox::drop-down{{border:none;width:20px;}}"
    f"QComboBox QAbstractItemView{{background:{D.COLOR_SURF2};"
    f"border:1px solid {D.COLOR_BDR2};border-radius:{D.R_MD}px;"
    f"color:{D.COLOR_TXT};selection-background-color:{D.COLOR_ACC_TINT};"
    f"selection-color:{D.COLOR_ACC};outline:none;}}"
)


class _SparkChart(QWidget):
    """7-day bar chart showing daily event counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._data: list[tuple[str, int]] = []   # [(day_label, count), ...]

    def set_data(self, data: list[tuple[str, int]]):
        self._data = data; self.update()

    def paintEvent(self, _):
        if not self._data: return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = 4; bar_gap = 4

        n = len(self._data)
        bar_w = max(4, (w - pad*2 - bar_gap*(n-1)) // n)
        max_v = max(v for _, v in self._data) or 1

        for i, (label, val) in enumerate(self._data):
            bx = pad + i*(bar_w+bar_gap)
            bh = max(2, int((val / max_v) * (h - 20)))
            by = h - bh - 14

            # Bar gradient
            is_today = (i == n - 1)
            grad = QLinearGradient(QPointF(bx, by), QPointF(bx, by+bh))
            c1 = QColor(D.COLOR_ACC if is_today else D.COLOR_SURF3)
            c2 = QColor(D.COLOR_ACC_DK if is_today else D.COLOR_BDR2)
            grad.setColorAt(0, c1); grad.setColorAt(1, c2)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bx, by, bar_w, bh), 2, 2)

            # Count above bar
            if val > 0:
                p.setPen(QColor(D.COLOR_ACC if is_today else D.COLOR_TXT_DIS))
                p.setFont(QFont(D.FONT_UI, D.FSIZE_XS - 1))
                p.drawText(int(bx), int(by) - 2, bar_w, 12,
                           Qt.AlignmentFlag.AlignCenter, str(val))

            # Day label below bar
            p.setPen(QColor(D.COLOR_TXT_DIS))
            p.setFont(QFont(D.FONT_UI, D.FSIZE_XS - 1))
            p.drawText(int(bx), h-13, bar_w, 12,
                       Qt.AlignmentFlag.AlignCenter, label)
        p.end()


class ActivityPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list = []
        self._project_map: dict[int, str] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Toolbar
        hdr = QWidget(); hdr.setObjectName("pageHeader"); hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(D.SP_6,0,D.SP_6,0); hl.setSpacing(D.SP_3)
        title = QLabel("Activity Log"); title.setObjectName("pageTitle"); hl.addWidget(title)
        self._cnt = QLabel(""); self._cnt.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_SM}pt;background:transparent;border:none;")
        hl.addWidget(self._cnt); hl.addStretch()

        self._proj_cb = QComboBox(); self._proj_cb.setFixedSize(180, D.H_BTN_LG)
        self._proj_cb.setStyleSheet(_SS_COMBO)
        self._proj_cb.addItem("All Projects")
        self._proj_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self._proj_cb)

        self._type_cb = QComboBox(); self._type_cb.setFixedSize(160, D.H_BTN_LG)
        self._type_cb.setStyleSheet(_SS_COMBO)
        self._type_cb.addItems(["All Events","project_created","version_created",
                                 "file_added","file_modified","file_deleted","scratch_created"])
        self._type_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self._type_cb)

        self._limit_cb = QComboBox(); self._limit_cb.setFixedSize(100, D.H_BTN_LG)
        self._limit_cb.setStyleSheet(_SS_COMBO)
        self._limit_cb.addItems(["Last 100","Last 500","Last 1000","All"])
        self._limit_cb.currentTextChanged.connect(self.refresh)
        hl.addWidget(self._limit_cb)

        clr = QPushButton("🗑 Clear All"); clr.setObjectName("ghostBtn")
        clr.setFixedHeight(D.H_BTN_LG); clr.clicked.connect(self._clear_all)
        hl.addWidget(clr)
        root.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep)

        # Spark chart + summary
        chart_w = QWidget(); chart_w.setFixedHeight(80)
        chart_w.setStyleSheet(f"background:{D.COLOR_SURF};border-bottom:1px solid {D.COLOR_BDR};")
        cl = QHBoxLayout(chart_w); cl.setContentsMargins(D.SP_6,D.SP_2,D.SP_6,D.SP_2); cl.setSpacing(D.SP_6)

        self._spark = _SparkChart(); self._spark.setMinimumWidth(200)
        cl.addWidget(self._spark, 1)

        # Quick stats
        self._stat_w = QWidget(); self._stat_w.setStyleSheet("background:transparent;")
        sl = QHBoxLayout(self._stat_w); sl.setContentsMargins(0,0,0,0); sl.setSpacing(D.SP_5)
        self._s_today = self._stat_tile("Today", "0", D.COLOR_ACC)
        self._s_week  = self._stat_tile("This Week", "0", D.COLOR_ACC2)
        self._s_total = self._stat_tile("Total", "0", D.COLOR_TXT2)
        for s in [self._s_today, self._s_week, self._s_total]:
            sl.addWidget(s)
        cl.addWidget(self._stat_w)
        root.addWidget(chart_w)

        # Event table
        self._tbl = QTableWidget(0, 5)
        self._tbl.setHorizontalHeaderLabels(["", "Event", "Description", "Project", "Time"])
        self._tbl.setStyleSheet(_SS_TABLE)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.setShowGrid(False)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.verticalHeader().setDefaultSectionSize(D.H_ROW)
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self._tbl.setColumnWidth(0, 28)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self._tbl, 1)

    def _stat_tile(self, label, value, color):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        v = QLabel(value)
        v.setStyleSheet(f"color:{color};font-size:{D.FSIZE_XL}pt;font-weight:800;"
                         "background:transparent;border:none;")
        lb = QLabel(label.upper())
        lb.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                          "font-weight:700;letter-spacing:0.6px;background:transparent;border:none;")
        l.addWidget(v); l.addWidget(lb)
        w._val = v
        return w

    def refresh(self):
        try:
            limit_text = self._limit_cb.currentText()
            limit = {"Last 100":100,"Last 500":500,"Last 1000":1000}.get(limit_text, 10000)
            s = get_session()
            try:
                projs = s.query(Project).filter(Project.is_deleted.is_(False)).all()
                self._project_map = {p.id: p.name for p in projs}

                cur_proj = self._proj_cb.currentText()
                self._proj_cb.blockSignals(True)
                self._proj_cb.clear(); self._proj_cb.addItem("All Projects")
                for p in sorted(projs, key=lambda x: x.name):
                    self._proj_cb.addItem(p.name)
                idx = self._proj_cb.findText(cur_proj)
                if idx >= 0: self._proj_cb.setCurrentIndex(idx)
                self._proj_cb.blockSignals(False)

                self._events = (s.query(ActivityEvent)
                                .order_by(ActivityEvent.created_at.desc())
                                .limit(limit).all())

                # Build spark chart (last 7 days)
                counts: dict[str, int] = defaultdict(int)
                today = datetime.date.today()
                for ev in self._events:
                    if ev.created_at:
                        d = ev.created_at.date()
                        if (today - d).days < 7:
                            counts[d.isoformat()] += 1
                spark_data = []
                for i in range(6, -1, -1):
                    d = today - datetime.timedelta(days=i)
                    label = d.strftime("%a") if i > 0 else "Today"
                    spark_data.append((label, counts.get(d.isoformat(), 0)))
                self._spark.set_data(spark_data)

                # Stats
                today_n = counts.get(today.isoformat(), 0)
                week_n  = sum(counts.values())
                self._s_today._val.setText(str(today_n))
                self._s_week._val.setText(str(week_n))
                self._s_total._val.setText(str(len(self._events)))
            finally:
                s.close()
            self._filter()
        except Exception as exc:
            log.error("Activity refresh: %s", exc)

    def _filter(self):
        try:
            proj_name = self._proj_cb.currentText()
            ev_type   = self._type_cb.currentText()

            filtered = []
            for ev in self._events:
                if proj_name != "All Projects":
                    pname = self._project_map.get(ev.project_id, "")
                    if pname != proj_name: continue
                if ev_type != "All Events" and ev.event_type != ev_type:
                    continue
                filtered.append(ev)

            n = len(filtered)
            self._cnt.setText(f"{n} event{'s' if n!=1 else ''}")
            self._tbl.setRowCount(0)

            for ev in filtered:
                icon, color = _EV_ICONS.get(ev.event_type, _EV_ICONS["default"])
                proj = self._project_map.get(ev.project_id, "—")
                ts   = ev.created_at.strftime("%Y-%m-%d %H:%M") if ev.created_at else ""

                r = self._tbl.rowCount(); self._tbl.insertRow(r)
                icon_cell = QTableWidgetItem(icon)
                icon_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                icon_cell.setForeground(QColor(color))

                for col, val in enumerate([icon_cell,
                    QTableWidgetItem(ev.event_type or ""),
                    QTableWidgetItem(ev.description or ""),
                    QTableWidgetItem(proj),
                    QTableWidgetItem(ts)]):
                    if col == 0:
                        self._tbl.setItem(r, col, val)
                    else:
                        val.setForeground(QColor(color if col == 1 else D.COLOR_TXT))
                        self._tbl.setItem(r, col, val)
        except Exception as exc:
            log.error("Activity filter: %s", exc)

    def _clear_all(self):
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Clear Activity Log",
            "Delete all activity events? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes: return
        s = get_session()
        try:
            s.query(ActivityEvent).delete(); s.commit()
        finally: s.close()
        self.refresh()