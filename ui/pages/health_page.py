# forix/ui/pages/health_page.py
"""
Forix — Project Health Monitor
All projects ranked by health score with visual rings, trend indicators,
quick re-score button, and one-click archive/open actions.
"""
import datetime
import logging

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from core.database import Project, TrackedFile, Version, get_session
from core.project_manager import refresh_project_health
import design as D

log = logging.getLogger("forix.health")

_TYPE_ICONS = {
    "arduino":"⚡","kicad":"◻","python":"🐍","node":"⬡",
    "web":"◈","cad":"◧","embedded":"⚙","document":"📄",
    "data":"📊","generic":"◉",
}
_TYPE_COLS = {
    "arduino":D.CTYPE_ARDUINO,"kicad":D.CTYPE_KICAD,"python":D.CTYPE_PYTHON,
    "node":D.CTYPE_NODE,"web":D.CTYPE_WEB,"cad":D.CTYPE_CAD,
    "embedded":D.CTYPE_EMBEDDED,"document":D.CTYPE_DOC,"data":D.CTYPE_DATA,
    "generic":D.CTYPE_GENERIC,
}


def _health_color(h: int) -> str:
    if h >= 70: return D.COLOR_OK
    if h >= 40: return D.COLOR_WRN
    return D.COLOR_ERR


def _ago(dt) -> str:
    if not dt: return "never"
    try:
        d = (datetime.datetime.utcnow() - dt).days
        if d == 0: return "today"
        if d == 1: return "yesterday"
        if d < 7:  return f"{d}d ago"
        if d < 30: return f"{d//7}w ago"
        return f"{d//30}mo ago"
    except Exception:
        return "—"


class _HealthRing(QWidget):
    """Circular health gauge."""
    def __init__(self, size=56, parent=None):
        super().__init__(parent)
        self._h = 0; self._sz = size
        self.setFixedSize(size, size)
        self.setStyleSheet("background:transparent;border:none;")

    def set_health(self, h: int): self._h = h; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = h = self._sz; pw = 6
        r = (w - pw) / 2
        cx, cy = w/2, h/2
        col = QColor(_health_color(self._h))

        # Track
        p.setPen(QPen(QColor(D.COLOR_SURF3), pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        # Arc
        p.setPen(QPen(col, pw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(-self._h/100 * 360 * 16)
        p.drawArc(QRectF(cx-r, cy-r, r*2, r*2), 90*16, span)

        # Value
        p.setPen(col)
        fnt = QFont(D.FONT_UI, D.FSIZE_SM if self._sz > 48 else D.FSIZE_XS)
        fnt.setBold(True); p.setFont(fnt)
        p.drawText(QRectF(0,0,w,h), Qt.AlignmentFlag.AlignCenter, str(self._h))
        p.end()


class _HealthCard(QWidget):
    sig_open    = pyqtSignal(int)
    sig_archive = pyqtSignal(int)
    sig_refresh = pyqtSignal(int)

    def __init__(self, data: dict, rank: int, parent=None):
        super().__init__(parent)
        self._pid = data["id"]
        self.setStyleSheet(
            f"background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
            f"border-radius:{D.R_LG}px;")
        self.setFixedHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build(data, rank)

    def _build(self, d: dict, rank: int):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(D.SP_3, D.SP_2, D.SP_3, D.SP_2)
        lay.setSpacing(D.SP_3)

        # Rank badge
        rk = QLabel(f"#{rank}")
        rk.setFixedWidth(32)
        rk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rk.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;font-weight:700;"
            "background:transparent;border:none;")
        lay.addWidget(rk)

        # Health ring
        ring = _HealthRing(52)
        ring.set_health(int(d.get("health", 0)))
        lay.addWidget(ring)

        # Info
        info = QWidget(); info.setStyleSheet("background:transparent;border:none;")
        il = QVBoxLayout(info); il.setContentsMargins(0,0,0,0); il.setSpacing(2)

        # Row 1: icon + name + status badge
        r1 = QHBoxLayout(); r1.setSpacing(D.SP_1)
        ptype = d.get("type","generic")
        icon_c = _TYPE_COLS.get(ptype, D.CTYPE_GENERIC)
        ic = QLabel(_TYPE_ICONS.get(ptype,"◉"))
        ic.setStyleSheet(f"color:{icon_c};font-size:{D.FSIZE_MD}pt;background:transparent;border:none;")
        r1.addWidget(ic)
        nm = QLabel(d.get("name",""))
        nm.setStyleSheet(f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_MD}pt;font-weight:700;"
                          "background:transparent;border:none;")
        r1.addWidget(nm, 1)
        st = d.get("status","active")
        st_col = {"active":D.COLOR_OK,"on-hold":D.COLOR_WRN,"stale":D.COLOR_WRN,
                   "archived":D.COLOR_TXT2}.get(st, D.COLOR_TXT2)
        badge = QLabel(f" {st} ")
        badge.setStyleSheet(
            f"color:{st_col};font-size:{D.FSIZE_XS}pt;font-weight:700;"
            f"background:transparent;border:1px solid {st_col};"
            f"border-radius:{D.R_SM}px;padding:0 3px;")
        r1.addWidget(badge)
        il.addLayout(r1)

        # Row 2: health bar + metrics
        h = int(d.get("health",0))
        bar = QProgressBar(); bar.setRange(0,100); bar.setValue(h)
        bar.setFixedHeight(3); bar.setTextVisible(False)
        hc = _health_color(h)
        bar.setStyleSheet(
            f"QProgressBar{{background:{D.COLOR_SURF2};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{hc};border-radius:2px;}}")
        il.addWidget(bar)

        # Row 3: last active + files + versions
        r3 = QHBoxLayout(); r3.setSpacing(D.SP_3)
        for txt in [f"⏱ {_ago(d.get('last_activity_dt'))}",
                    f"📄 {d.get('file_count',0)} files",
                    f"📸 {d.get('version_count',0)} snapshots"]:
            lb = QLabel(txt)
            lb.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                              "background:transparent;border:none;")
            r3.addWidget(lb)
        r3.addStretch()
        il.addLayout(r3)
        lay.addWidget(info, 1)

        # Actions
        act = QVBoxLayout(); act.setSpacing(D.SP_1)
        open_b = QPushButton("▶ Open"); open_b.setObjectName("ghostBtn")
        open_b.setFixedHeight(D.H_BTN_SM)
        open_b.clicked.connect(lambda: self.sig_open.emit(self._pid))
        ref_b = QPushButton("↻"); ref_b.setObjectName("ghostBtn")
        ref_b.setFixedSize(D.H_BTN_SM, D.H_BTN_SM)
        ref_b.setToolTip("Re-score health")
        ref_b.clicked.connect(lambda: self.sig_refresh.emit(self._pid))
        row_a = QHBoxLayout(); row_a.setSpacing(D.SP_1)
        row_a.addWidget(open_b); row_a.addWidget(ref_b)
        act.addLayout(row_a)
        arch_b = QPushButton("Archive"); arch_b.setObjectName("ghostBtn")
        arch_b.setFixedHeight(D.H_BTN_SM)
        arch_b.clicked.connect(lambda: self.sig_archive.emit(self._pid))
        act.addWidget(arch_b)
        lay.addLayout(act)


class HealthPage(QWidget):
    project_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        hdr = QWidget(); hdr.setObjectName("pageHeader"); hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(D.SP_6,0,D.SP_6,0); hl.setSpacing(D.SP_3)
        title = QLabel("Project Health"); title.setObjectName("pageTitle"); hl.addWidget(title)
        self._cnt = QLabel(""); self._cnt.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_SM}pt;background:transparent;border:none;")
        hl.addWidget(self._cnt); hl.addStretch()

        rescore = QPushButton("↻ Re-score All")
        rescore.setObjectName("ghostBtn"); rescore.setFixedHeight(D.H_BTN_LG)
        rescore.clicked.connect(self._rescore_all); hl.addWidget(rescore)
        root.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep)

        # Summary band
        band = QWidget(); band.setFixedHeight(44)
        band.setStyleSheet(f"background:{D.COLOR_SURF};border-bottom:1px solid {D.COLOR_BDR};")
        bl = QHBoxLayout(band); bl.setContentsMargins(D.SP_6,0,D.SP_6,0); bl.setSpacing(D.SP_6)
        self._bnd = {}
        for key, label, col in [("healthy","Healthy",D.COLOR_OK),
                                  ("warning","Need Attention",D.COLOR_WRN),
                                  ("critical","Critical",D.COLOR_ERR),
                                  ("avg","Avg Score",D.COLOR_ACC)]:
            tile = QWidget(); tile.setStyleSheet("background:transparent;border:none;")
            tl = QHBoxLayout(tile); tl.setContentsMargins(0,0,0,0); tl.setSpacing(D.SP_1)
            v = QLabel("—"); v.setStyleSheet(
                f"color:{col};font-size:{D.FSIZE_SM}pt;font-weight:700;"
                "background:transparent;border:none;")
            lb = QLabel(label); lb.setStyleSheet(
                f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                "background:transparent;border:none;")
            tl.addWidget(v); tl.addWidget(lb)
            self._bnd[key] = v; bl.addWidget(tile)
        bl.addStretch()
        root.addWidget(band)

        # Card grid
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{D.COLOR_BG};border:none;}}"
            f"QScrollBar:vertical{{background:{D.COLOR_BG};width:6px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{D.COLOR_SURF3};"
            f"border-radius:3px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self._cont = QWidget(); self._cont.setStyleSheet(f"background:{D.COLOR_BG};")
        self._lay  = QVBoxLayout(self._cont)
        self._lay.setContentsMargins(D.SP_6, D.SP_4, D.SP_6, D.SP_8)
        self._lay.setSpacing(D.SP_2)
        self._lay.addStretch()
        self._scroll.setWidget(self._cont)
        root.addWidget(self._scroll, 1)

    def refresh(self):
        try:
            s = get_session()
            try:
                projs = (s.query(Project)
                         .filter(Project.is_deleted.is_(False))
                         .order_by(Project.health.desc().nullslast()).all())
                data = []
                for p in projs:
                    fc = s.query(TrackedFile).filter_by(project_id=p.id,is_deleted=False).count()
                    vc = s.query(Version).filter_by(project_id=p.id).count()
                    data.append({
                        "id": p.id, "name": p.name,
                        "health": int(p.health or 0),
                        "status": p.status or "active",
                        "type": p.project_type or "generic",
                        "category": p.category or "",
                        "last_activity": (p.last_activity.isoformat()
                                          if p.last_activity else ""),
                        "last_activity_dt": p.last_activity,
                        "file_count": fc, "version_count": vc,
                    })
            finally:
                s.close()

            # Summary band
            healthy  = sum(1 for d in data if d["health"] >= 70)
            warning  = sum(1 for d in data if 40 <= d["health"] < 70)
            critical = sum(1 for d in data if d["health"] < 40)
            avg = int(sum(d["health"] for d in data) / len(data)) if data else 0
            self._bnd["healthy"].setText(str(healthy))
            self._bnd["warning"].setText(str(warning))
            self._bnd["critical"].setText(str(critical))
            self._bnd["avg"].setText(f"{avg}%")
            self._cnt.setText(f"{len(data)} projects")

            # Rebuild card list
            while self._lay.count() > 1:
                item = self._lay.takeAt(0)
                if item.widget(): item.widget().deleteLater()

            for rank, d in enumerate(data, 1):
                card = _HealthCard(d, rank, self._cont)
                card.sig_open.connect(self.project_selected.emit)
                card.sig_archive.connect(self._archive)
                card.sig_refresh.connect(self._rescore_one)
                self._lay.insertWidget(self._lay.count()-1, card)
        except Exception as exc:
            log.error("Health refresh: %s", exc)

    def _rescore_all(self):
        s = get_session()
        try:
            ids = [p.id for p in s.query(Project).filter(Project.is_deleted.is_(False)).all()]
        finally: s.close()
        for pid in ids:
            try: refresh_project_health(pid)
            except Exception: pass
        self.refresh()

    def _rescore_one(self, pid: int):
        try: refresh_project_health(pid)
        except Exception as exc: log.error("Rescore: %s", exc)
        self.refresh()

    def _archive(self, pid: int):
        s = get_session()
        try:
            p = s.query(Project).filter_by(id=pid).first()
            if p: p.status = "archived"; s.commit()
        finally: s.close()
        self.refresh()