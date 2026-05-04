# forix/ui/sidebar.py
"""
Forix — Sidebar Navigation (v5)

Fixes vs v4:
  • Collapsed state properly constrains widget width to SIDEBAR_W_MIN so the
    icon-only view does not leave dead space or clip content.
  • Toggle button is always visible in both states.
  • Header centres the logo icon correctly when collapsed.
  • Section labels have zero height (not just hidden) when collapsed so they
    don't contribute to layout spacing.
  • _NavButton icon is centred within the collapsed width exactly.
"""

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QRectF, Qt, pyqtSignal, QSize
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget,
)

import design as D
from core.constants import APP_NAME, APP_VERSION

log = logging.getLogger("forix.sidebar")

# ── Nav item definitions ──────────────────────────────────────────────────────
# (key, label, icon, section)
NAV_ITEMS = [
    # Workspace
    ("dashboard",  "Dashboard",   "⊞",  "workspace"),
    ("projects",   "Projects",    "◈",  "workspace"),
    ("inventory",  "Inventory",   "▤",  "workspace"),
    # Tools
    ("search",     "Search",      "⌕",  "tools"),
    ("activity",   "Activity",    "⚡",  "tools"),
    ("health",     "Health",      "♥",  "tools"),
    ("duplicates", "Duplicates",  "⊕",  "tools"),
    # System (bottom)
    ("settings",   "Settings",    "⚙",  "system"),
]

_SECTION_LABELS = {
    "workspace": "WORKSPACE",
    "tools":     "TOOLS",
    "system":    "",
}


class _NavButton(QWidget):
    """
    Custom-painted nav button.
    Expanded: 3-px left active-bar | icon | label | optional badge
    Collapsed: icon centred, full tooltip
    """
    clicked = pyqtSignal(str)

    BAR_W = 3
    H     = D.SIDEBAR_H_BTN

    def __init__(self, key: str, label: str, icon: str, parent=None):
        super().__init__(parent)
        self.key        = key
        self.label      = label
        self.icon       = icon
        self._active    = False
        self._hovered   = False
        self._badge     = 0
        self._collapsed = False
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("")   # tooltip managed by set_collapsed

    # ── State setters ────────────────────────────────────────────────────────

    def set_active(self, active: bool):
        self._active = active
        self.update()

    def set_badge(self, n: int):
        self._badge = n
        self.update()

    def set_collapsed(self, c: bool):
        self._collapsed = c
        self.setToolTip(self.label if c else "")
        self.update()

    # ── Paint ────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()

        # ── Background ───────────────────────────────────────────────────────
        if self._active:
            bg = QColor(D.COLOR_SB_ACTIVE)
        elif self._hovered:
            bg = QColor(D.COLOR_SB_HOVER)
        else:
            bg = QColor(D.COLOR_SB)
        p.fillRect(0, 0, w, h, bg)

        # ── Active / hover left bar ──────────────────────────────────────────
        if self._active:
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(D.COLOR_ACC))
            grad.setColorAt(1.0, QColor(D.COLOR_ACC_DK))
            p.fillRect(0, 0, self.BAR_W, h, QBrush(grad))
        elif self._hovered:
            p.fillRect(0, 0, self.BAR_W, h, QBrush(QColor(D.COLOR_BDR2)))

        # ── Icon ─────────────────────────────────────────────────────────────
        icon_font = QFont(D.FONT_UI, D.FSIZE_MD)
        p.setFont(icon_font)
        icon_col = (
            QColor(D.COLOR_ACC)    if self._active  else
            QColor(D.COLOR_SB_TXTH) if self._hovered else
            QColor(D.COLOR_SB_TXT)
        )
        p.setPen(icon_col)

        if self._collapsed:
            # Centre the icon across the entire (narrow) widget width.
            # Reserve the 3-px bar on the left so it still draws correctly.
            icon_zone_x = self.BAR_W
            icon_zone_w = w - self.BAR_W
            p.drawText(
                icon_zone_x, 0, icon_zone_w, h,
                Qt.AlignmentFlag.AlignCenter,
                self.icon,
            )
        else:
            icon_x = self.BAR_W + D.SP_3
            icon_w = 20
            p.drawText(icon_x, 0, icon_w, h, Qt.AlignmentFlag.AlignCenter, self.icon)

            # ── Label ─────────────────────────────────────────────────────────
            lbl_x   = icon_x + icon_w + D.SP_2
            lbl_font = QFont(D.FONT_UI, D.FSIZE_BASE)
            if self._active:
                lbl_font.setBold(True)
            p.setFont(lbl_font)
            lbl_col = (
                QColor(D.COLOR_SB_TXTA) if self._active  else
                QColor(D.COLOR_SB_TXTH) if self._hovered else
                QColor(D.COLOR_SB_TXT)
            )
            p.setPen(lbl_col)
            lbl_w = w - lbl_x - D.SP_3 - (28 if self._badge else 0)
            p.drawText(
                lbl_x, 0, lbl_w, h,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.label,
            )

        # ── Badge ─────────────────────────────────────────────────────────────
        if self._badge > 0:
            btxt  = str(min(self._badge, 99))
            bfont = QFont(D.FONT_UI, D.FSIZE_XS)
            bfont.setBold(True)
            p.setFont(bfont)
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(btxt) + 8
            bh = fm.height() + 4
            bx = w - bw - D.SP_2
            by = (h - bh) // 2
            bbg = QColor(D.COLOR_ERR)
            bbg.setAlpha(200)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(bbg))
            p.drawRoundedRect(bx, by, bw, bh, 4, 4)
            p.setPen(QColor(D.COLOR_WHITE))
            p.drawText(bx, by, bw, bh, Qt.AlignmentFlag.AlignCenter, btxt)

        p.end()

    def enterEvent(self, _):
        self._hovered = True
        self.update()

    def leaveEvent(self, _):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(e)


class _SectionLabel(QLabel):
    """Section header label that collapses to zero height rather than just hiding."""

    _EXPANDED_H = 28   # pixels when visible

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setContentsMargins(D.SP_4, D.SP_3, D.SP_4, D.SP_1)
        self.setStyleSheet(
            f"color:{D.COLOR_SB_LBL};font-size:{D.FSIZE_XS}pt;"
            "font-weight:700;letter-spacing:0.8px;"
            "background:transparent;border:none;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_collapsed(self, c: bool):
        if c:
            self.setFixedHeight(0)
            self.setVisible(False)
        else:
            self.setFixedHeight(self._EXPANDED_H)
            self.setVisible(True)


class Sidebar(QWidget):
    nav_changed       = pyqtSignal(str)
    collapsed_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._collapsed = False
        self._btns: dict[str, _NavButton] = {}
        self._sec_labels: list[_SectionLabel] = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        self._hdr = QWidget()
        self._hdr.setObjectName("sidebarHeader")
        self._hdr.setFixedHeight(D.SIDEBAR_H_HDR)
        self._hdr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._hl = QHBoxLayout(self._hdr)
        self._hl.setContentsMargins(D.SP_3, 0, D.SP_2, 0)
        self._hl.setSpacing(D.SP_2)

        # Logo icon
        self._icon_lbl = QLabel()
        icon_path = Path(__file__).parent.parent / "assets" / "logo.png"
        if icon_path.exists():
            px = QPixmap(str(icon_path)).scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_lbl.setPixmap(px)
        else:
            self._icon_lbl.setText("◈")
            self._icon_lbl.setStyleSheet(
                f"color:{D.COLOR_ACC};font-size:{D.FSIZE_LG}pt;"
                "background:transparent;border:none;"
            )
        self._icon_lbl.setFixedSize(24, 24)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hl.addWidget(self._icon_lbl)

        # Name + version block (hidden when collapsed)
        self._name_ver = QWidget()
        self._name_ver.setStyleSheet("background:transparent;")
        nvl = QVBoxLayout(self._name_ver)
        nvl.setContentsMargins(0, 0, 0, 0)
        nvl.setSpacing(0)

        self._name_lbl = QLabel(APP_NAME)
        self._name_lbl.setStyleSheet(
            f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_BASE}pt;font-weight:800;"
            "background:transparent;border:none;"
        )
        self._ver_lbl = QLabel(f"v{APP_VERSION}")
        self._ver_lbl.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
            "background:transparent;border:none;"
        )
        nvl.addWidget(self._name_lbl)
        nvl.addWidget(self._ver_lbl)
        self._hl.addWidget(self._name_ver, 1)

        # Toggle button — always visible
        self._toggle = QPushButton("‹")
        self._toggle.setObjectName("toggleBtn")
        self._toggle.setFixedSize(24, 24)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setToolTip("Collapse sidebar")
        self._toggle.clicked.connect(self._do_toggle)
        self._hl.addWidget(self._toggle)

        root.addWidget(self._hdr)
        root.addWidget(_rule())

        # ── Nav sections ──────────────────────────────────────────────────────
        current_section = None
        for key, label, icon, section in NAV_ITEMS:
            if section == "system":
                continue  # placed at bottom

            if section != current_section:
                current_section = section
                sec_text = _SECTION_LABELS.get(section, section.upper())
                if sec_text:
                    sec_lbl = _SectionLabel(sec_text)
                    self._sec_labels.append(sec_lbl)
                    root.addWidget(sec_lbl)

            btn = _NavButton(key, label, icon, self)
            btn.clicked.connect(self._on_click)
            self._btns[key] = btn
            root.addWidget(btn)

        root.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # ── Bottom: system section ────────────────────────────────────────────
        root.addWidget(_rule())
        for key, label, icon, section in NAV_ITEMS:
            if section != "system":
                continue
            btn = _NavButton(key, label, icon, self)
            btn.clicked.connect(self._on_click)
            self._btns[key] = btn
            root.addWidget(btn)

        # ── Footer ────────────────────────────────────────────────────────────
        self._foot = _FooterWidget()
        root.addWidget(self._foot)

        self.set_active("dashboard")

    # ── Collapse / expand ─────────────────────────────────────────────────────

    def _do_toggle(self):
        self._collapsed = not self._collapsed
        self._apply_collapsed(self._collapsed)
        self.collapsed_changed.emit(self._collapsed)

    def handle_resize(self, width: int):
        """Called by main window when the splitter is dragged."""
        narrow = width < (D.SIDEBAR_W_MIN + 30)
        if narrow != self._collapsed:
            self._apply_collapsed(narrow)

    def _apply_collapsed(self, c: bool):
        self._collapsed = c

        # ── Toggle button arrow ───────────────────────────────────────────────
        self._toggle.setText("›" if c else "‹")
        self._toggle.setToolTip("Expand sidebar" if c else "Collapse sidebar")

        # ── Header layout ─────────────────────────────────────────────────────
        if c:
            # Collapsed: icon + toggle centred, no name/ver
            self._name_ver.setVisible(False)
            self._hl.setContentsMargins(0, 0, 0, 0)
            self._hl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        else:
            self._name_ver.setVisible(True)
            self._hl.setContentsMargins(D.SP_3, 0, D.SP_2, 0)
            self._hl.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

        # ── Section labels ────────────────────────────────────────────────────
        for sec_lbl in self._sec_labels:
            sec_lbl.set_collapsed(c)

        # ── Nav buttons ───────────────────────────────────────────────────────
        for btn in self._btns.values():
            btn.set_collapsed(c)

        # ── Footer ────────────────────────────────────────────────────────────
        self._foot.set_collapsed(c)

        # ── Width constraint — this is the key fix ────────────────────────────
        # Force the sidebar to snap to the correct fixed width immediately
        # instead of relying solely on the splitter.  Without this, the icon-
        # only state can leave the sidebar wider than SIDEBAR_W_MIN, resulting
        # in dead space around the icons.
        if c:
            self.setFixedWidth(D.SIDEBAR_W_MIN)
        else:
            self.setMinimumWidth(D.SIDEBAR_W_MIN)
            self.setMaximumWidth(D.SIDEBAR_W * 2)   # allow splitter to resize

    # ── Active state ──────────────────────────────────────────────────────────

    def _on_click(self, key: str):
        self.set_active(key)
        self.nav_changed.emit(key)

    def set_active(self, key: str):
        for k, btn in self._btns.items():
            btn.set_active(k == key)

    def set_badge(self, key: str, count: int):
        if key in self._btns:
            self._btns[key].set_badge(count)


# ── Footer widget ─────────────────────────────────────────────────────────────

class _FooterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarFooter")
        self.setFixedHeight(D.SIDEBAR_H_FOOT + 8)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(D.SP_4, 0, D.SP_4, 0)
        lay.setSpacing(D.SP_1)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(
            f"color:{D.COLOR_OK};font-size:7pt;background:transparent;border:none;"
        )
        lay.addWidget(self._dot)

        self._live = QLabel("LIVE")
        self._live.setStyleSheet(
            f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_XS}pt;font-weight:700;"
            "letter-spacing:0.6px;background:transparent;border:none;"
        )
        lay.addWidget(self._live)

        lay.addStretch()

        self._hint = QLabel("Ctrl+K")
        self._hint.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
            "background:transparent;border:none;"
        )
        lay.addWidget(self._hint)

    def set_collapsed(self, c: bool):
        self._live.setVisible(not c)
        self._hint.setVisible(not c)
        # Keep the green dot visible so there's always a status indicator
        self._dot.setVisible(True)
        if c:
            self.layout().setContentsMargins(0, 0, 0, 0)
            self.layout().setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        else:
            self.layout().setContentsMargins(D.SP_4, 0, D.SP_4, 0)
            self.layout().setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )


def _rule() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{D.COLOR_SB_BDR};border:none;")
    return f