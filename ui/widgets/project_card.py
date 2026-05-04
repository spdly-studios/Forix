# forix/ui/widgets/project_card.py
"""
Forix — Project Card (redesigned)
Full custom-painted card with type colour bar, health ring,
hover glow, and quick-action footer.
"""
import datetime
import logging
from PyQt6.QtWidgets import QWidget, QSizePolicy, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QPoint
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QConicalGradient,
    QPainter, QPainterPath, QPen, QPixmap,
)
import design as D

log = logging.getLogger("forix.project_card")

_STATUS = {
    "active":   (D.COLOR_OK,   D.COLOR_OK_TINT),
    "planning": (D.COLOR_ACC,  D.COLOR_ACC_TINT),
    "on-hold":  (D.COLOR_WRN,  D.COLOR_WRN_TINT),
    "stale":    (D.COLOR_WRN,  D.COLOR_WRN_TINT),
    "archived": (D.COLOR_TXT2, D.COLOR_SURF2),
    "deleted":  (D.COLOR_ERR,  D.COLOR_ERR_TINT),
}
_TYPE = {
    "arduino":  ("⚡", D.CTYPE_ARDUINO),
    "kicad":    ("◻",  D.CTYPE_KICAD),
    "python":   ("🐍", D.CTYPE_PYTHON),
    "node":     ("⬡",  D.CTYPE_NODE),
    "web":      ("◈",  D.CTYPE_WEB),
    "cad":      ("◧",  D.CTYPE_CAD),
    "embedded": ("⚙",  D.CTYPE_EMBEDDED),
    "document": ("📄", D.CTYPE_DOC),
    "data":     ("📊", D.CTYPE_DATA),
    "generic":  ("◉",  D.CTYPE_GENERIC),
}

def _ago(dt):
    try:
        diff = datetime.datetime.utcnow() - dt
        d = diff.days
        if d == 0:
            h = diff.seconds // 3600
            return f"{h}h ago" if h else f"{diff.seconds // 60}m ago"
        if d == 1:  return "Yesterday"
        if d < 7:   return f"{d}d ago"
        if d < 30:  return f"{d // 7}w ago"
        return f"{d // 30}mo ago"
    except Exception:
        return ""


class ProjectCard(QWidget):
    clicked = pyqtSignal()

    _W = 280
    _H = 158

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._data    = data
        self._hovered = False
        self.setFixedSize(self._W, self._H)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    # ── Paint ──────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        d  = self._data
        w, h = self._W, self._H
        r  = float(D.R_LG)
        ptype  = d.get("type", "generic")
        status = d.get("status", "active")
        icon, tc = _TYPE.get(ptype, _TYPE["generic"])
        sc, _    = _STATUS.get(status, _STATUS["active"])

        # ── Card background ────────────────────────────────────────────────
        card_col = QColor(D.COLOR_SURF2 if self._hovered else D.COLOR_SURF)
        path = QPainterPath(); path.addRoundedRect(0, 0, w, h, r, r)
        p.fillPath(path, QBrush(card_col))

        # ── Type-colour left accent bar ────────────────────────────────────
        bar = QPainterPath()
        bar.addRoundedRect(0, 0, 4, h, r, r)
        bar.addRect(2, 0, 2, h)   # square off right side
        p.fillPath(bar, QBrush(QColor(tc)))

        # ── Hover glow ─────────────────────────────────────────────────────
        if self._hovered:
            glow_col = QColor(tc); glow_col.setAlpha(18)
            p.fillPath(path, QBrush(glow_col))

        # ── Border ─────────────────────────────────────────────────────────
        bdr = QColor(tc if self._hovered else D.COLOR_BDR2)
        bdr.setAlpha(200 if self._hovered else 255)
        p.setPen(QPen(bdr, 1.0)); p.drawPath(path)

        # ── Health ring (top-right) ────────────────────────────────────────
        health  = max(0, min(100, int(d.get("health", 0))))
        ring_cx = w - 28; ring_cy = 28; ring_r = 18.0
        # Track
        p.setPen(QPen(QColor(D.COLOR_SURF3), 3.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(ring_cx - ring_r, ring_cy - ring_r,
                              ring_r*2, ring_r*2))
        # Arc
        hc = D.COLOR_OK if health >= 60 else (D.COLOR_WRN if health >= 30 else D.COLOR_ERR)
        p.setPen(QPen(QColor(hc), 3.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        span = int(-health / 100 * 360 * 16)
        p.drawArc(QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r*2, ring_r*2),
                  90 * 16, span)
        # Health % text
        hfont = QFont(D.FONT_UI, D.FSIZE_XS - 1); hfont.setBold(True)
        p.setFont(hfont); p.setPen(QColor(hc))
        p.drawText(QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r*2, ring_r*2),
                   Qt.AlignmentFlag.AlignCenter, f"{health}")

        # ── Icon + Name ────────────────────────────────────────────────────
        tx = 16; ty = 14
        ifont = QFont(D.FONT_UI, D.FSIZE_MD); p.setFont(ifont)
        p.setPen(QColor(tc))
        p.drawText(tx, ty, 20, 24, Qt.AlignmentFlag.AlignCenter, icon)

        name = d.get("name", "Unknown")
        nfont = QFont(D.FONT_UI, D.FSIZE_MD); nfont.setBold(True)
        p.setFont(nfont); p.setPen(QColor(D.COLOR_TXT_HEAD))
        max_name_w = w - tx - 20 - 60   # leave space for health ring
        elided = p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, max_name_w)
        p.drawText(tx + 22, ty, max_name_w, 24,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        # ── Status + type chips ────────────────────────────────────────────
        ty2 = ty + 28
        chip_font = QFont(D.FONT_UI, D.FSIZE_XS); chip_font.setBold(True)
        p.setFont(chip_font)

        def _chip(label, fg, x, y):
            fm = p.fontMetrics(); cw = fm.horizontalAdvance(label) + 10; ch = fm.height() + 4
            bg = QColor(fg); bg.setAlpha(28)
            bdr2 = QColor(fg); bdr2.setAlpha(80)
            p.setPen(QPen(bdr2, 1)); p.setBrush(QBrush(bg))
            p.drawRoundedRect(QRectF(x, y, cw, ch), 3, 3)
            p.setPen(QColor(fg)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawText(int(x), int(y), cw, ch, Qt.AlignmentFlag.AlignCenter, label)
            return cw + 6

        cx = tx
        cx += _chip(status.upper(), sc, cx, ty2)
        cx += _chip(ptype, tc, cx, ty2)
        cat = d.get("category", "")
        if cat:
            cx += _chip(cat, D.COLOR_TXT2, cx, ty2)

        # ── Description (1 line) ───────────────────────────────────────────
        desc = (d.get("description") or "").strip()
        ty3  = ty2 + 26
        if desc:
            dfont = QFont(D.FONT_UI, D.FSIZE_XS); p.setFont(dfont)
            p.setPen(QColor(D.COLOR_TXT2))
            de = p.fontMetrics().elidedText(desc, Qt.TextElideMode.ElideRight, w - tx - 12)
            p.drawText(tx, ty3, w - tx - 12, p.fontMetrics().height(),
                       Qt.AlignmentFlag.AlignLeft, de)

        # ── Footer: time-ago + tags + file count ───────────────────────────
        fy = h - 36
        # Thin separator
        sep_col = QColor(D.COLOR_BDR); sep_col.setAlpha(80)
        p.setPen(QPen(sep_col, 1)); p.drawLine(tx, fy, w - 10, fy)

        fy += 8
        ffont = QFont(D.FONT_UI, D.FSIZE_XS); p.setFont(ffont)

        # Time ago
        la = d.get("last_activity", "")
        if la:
            try:
                ago_txt = _ago(datetime.datetime.fromisoformat(la))
                p.setPen(QColor(D.COLOR_TXT_DIS))
                p.drawText(tx, fy, 100, 18, Qt.AlignmentFlag.AlignLeft, f"⏱ {ago_txt}")
            except Exception:
                pass

        # Tags (up to 2)
        tag_x = tx + 110
        for tag in (d.get("tags") or [])[:2]:
            fm = p.fontMetrics(); tw2 = fm.horizontalAdvance(tag) + 8
            tbg = QColor(D.COLOR_ACC2); tbg.setAlpha(22)
            tbdr = QColor(D.COLOR_ACC2); tbdr.setAlpha(70)
            p.setPen(QPen(tbdr, 1)); p.setBrush(QBrush(tbg))
            p.drawRoundedRect(QRectF(tag_x, fy, tw2, 18), 3, 3)
            p.setPen(QColor(D.COLOR_ACC2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawText(int(tag_x), fy, tw2, 18, Qt.AlignmentFlag.AlignCenter, tag)
            tag_x += tw2 + 4

        # File count (right-aligned)
        fc = d.get("file_count", 0)
        fc_txt = f"{fc} file{'s' if fc != 1 else ''}"
        p.setPen(QColor(D.COLOR_TXT_DIS)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawText(w - 80, fy, 72, 18, Qt.AlignmentFlag.AlignRight, fc_txt)

        p.end()

    # ── Events ────────────────────────────────────────────────────────────────

    def enterEvent(self, _): self._hovered = True; self.update()
    def leaveEvent(self, _): self._hovered = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.clicked.emit(); e.accept()