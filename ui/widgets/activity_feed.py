# forix/ui/widgets/activity_feed.py
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QHBoxLayout, QLabel, QFrame,
)
from PyQt6.QtCore import Qt
import design as D

log = logging.getLogger("forix.activity_feed")

_EV = {
    "project_created": ("✦", D.COLOR_ACC),
    "version_created": ("📸", D.COLOR_ACC2),
    "file_added":      ("＋", D.COLOR_OK),
    "file_modified":   ("~",  D.COLOR_WRN),
    "file_deleted":    ("−",  D.COLOR_ERR),
    "default":         ("·",  D.COLOR_TXT2),
}


class ActivityFeed(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 3px; border-radius: 1px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {D.COLOR_BDR2}; border-radius: 1px; min-height: 20px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        self._cont = QWidget()
        self._cont.setStyleSheet(f"background: {D.COLOR_SURF};")
        self._inner = QVBoxLayout(self._cont)
        self._inner.setContentsMargins(0, 0, 0, 0)
        self._inner.setSpacing(0)
        self._inner.addStretch()

        scroll.setWidget(self._cont)
        lay.addWidget(scroll)

    def set_events(self, events):
        try:
            while self._inner.count() > 1:
                item = self._inner.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for i, (ev_type, desc, created_at) in enumerate(events):
                icon, color = _EV.get(ev_type, _EV["default"])
                self._inner.insertWidget(
                    self._inner.count() - 1,
                    self._row(icon, color, desc, created_at, i),
                )
        except Exception as e:
            log.error(f"Activity feed error: {e}")

    def _row(self, icon: str, color: str, text: str, dt, idx: int) -> QWidget:
        row = QWidget()
        row.setFixedHeight(30)
        bg = D.COLOR_SURF if idx % 2 == 0 else D.COLOR_SURF2
        row.setStyleSheet(
            f"QWidget {{ background: {bg}; border: none; }}"
            f"QWidget:hover {{ background: {D.COLOR_SURF3}; }}"
        )

        rl = QHBoxLayout(row)
        rl.setContentsMargins(D.SP_3, 0, D.SP_3, 0)
        rl.setSpacing(D.SP_2)

        # Icon dot
        dot = QLabel(icon)
        dot.setFixedWidth(16)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: {D.FSIZE_SM}pt;"
            f" background: transparent; border: none;"
        )
        rl.addWidget(dot)

        # Thin accent left rule on the icon column
        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.VLine)
        rule.setFixedWidth(1)
        rule.setFixedHeight(14)
        rule.setStyleSheet(f"background: {color}; border: none; opacity: 0.5;")
        rl.addWidget(rule)

        # Description
        desc_lbl = QLabel(text[:80] + ("…" if len(text) > 80 else ""))
        desc_lbl.setStyleSheet(
            f"font-size: {D.FSIZE_SM}pt; color: {D.COLOR_TXT};"
            f" background: transparent; border: none;"
        )
        rl.addWidget(desc_lbl, 1)

        # Timestamp
        if dt:
            try:
                ts = dt.strftime("%H:%M")
            except Exception:
                ts = ""
            ts_lbl = QLabel(ts)
            ts_lbl.setStyleSheet(
                f"font-size: {D.FSIZE_XS}pt; color: {D.COLOR_TXT2};"
                f" background: transparent; border: none;"
                f" font-variant: tabular-nums;"
            )
            rl.addWidget(ts_lbl)

        return row