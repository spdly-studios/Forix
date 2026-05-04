# forix/ui/notifications.py
"""
Forix — Notification System

Components:
  NotificationManager  — singleton; publish/subscribe event bus
  ToastWidget          — animated corner popup (auto-dismisses after N seconds)
  NotificationBell     — status-bar widget showing unread count, opens history panel
  NotificationHistory  — scrollable panel listing all notifications

Usage:
    # Anywhere in the app:
    from ui.notifications import get_notif_manager
    nm = get_notif_manager()
    nm.post("info",    "Snapshot v3 created for MyBot")
    nm.post("warning", "Inventory: Resistors 10kΩ is low (2 left)")
    nm.post("error",   "Watcher failed to start on E:\\\\")
    nm.post("success", "Project imported successfully")

    # In main_window, connect the bell to the toolbar and attach toasts:
    bell   = NotificationBell(main_window)
    toasts = ToastManager(main_window)
    nm.posted.connect(toasts.show_toast)
    nm.posted.connect(bell.on_notification)
"""

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve, QObject, QPoint, QPropertyAnimation,
    QRect, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QBrush, QPen
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import design as D

log = logging.getLogger("forix.notifications")

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Notification:
    level:   str          # info | success | warning | error
    message: str
    ts:      datetime.datetime = field(default_factory=datetime.datetime.now)
    read:    bool = False
    id:      int = 0      # assigned by manager

_LEVEL_META = {
    "info":    ("ℹ",  D.COLOR_ACC,  D.COLOR_ACC_TINT),
    "success": ("✓",  D.COLOR_OK,   D.COLOR_OK_TINT),
    "warning": ("⚠",  D.COLOR_WRN,  D.COLOR_WRN_TINT),
    "error":   ("✕",  D.COLOR_ERR,  D.COLOR_ERR_TINT),
}


# ── Manager (event bus) ───────────────────────────────────────────────────────

class NotificationManager(QObject):
    """
    Singleton event bus.  Call post() to emit a notification; all connected
    widgets (toasts, bell, history) update automatically.
    """
    posted = pyqtSignal(object)   # emits Notification instance

    def __init__(self):
        super().__init__()
        self._history: list[Notification] = []
        self._counter = 0

    def post(self, level: str, message: str) -> Notification:
        self._counter += 1
        n = Notification(level=level, message=message, id=self._counter)
        self._history.append(n)
        if len(self._history) > 200:
            self._history = self._history[-200:]
        self.posted.emit(n)
        log.debug("Notification [%s]: %s", level, message)
        return n

    def mark_all_read(self):
        for n in self._history:
            n.read = True

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self._history if not n.read)

    @property
    def history(self) -> list[Notification]:
        return list(reversed(self._history))

    def clear(self):
        self._history.clear()


_manager: Optional[NotificationManager] = None

def get_notif_manager() -> NotificationManager:
    global _manager
    if _manager is None:
        _manager = NotificationManager()
    return _manager


# ── Toast widget ──────────────────────────────────────────────────────────────

class _ToastWidget(QWidget):
    """Single auto-dismissing toast popup."""

    TOAST_W = 340
    TOAST_H = 64

    def __init__(self, notif: Notification, parent: QWidget):
        super().__init__(parent)
        self.setFixedSize(self.TOAST_W, self.TOAST_H)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._notif = notif
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._build(notif)
        self._animate_in()

    def _build(self, n: Notification):
        icon_s, color, bg = _LEVEL_META.get(n.level, _LEVEL_META["info"])
        lay = QHBoxLayout(self)
        lay.setContentsMargins(D.SP_3, 0, D.SP_3, 0)
        lay.setSpacing(D.SP_2)

        icon = QLabel(icon_s)
        icon.setFixedSize(24, 24)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color:{color};font-size:{D.FSIZE_MD}pt;font-weight:700;"
            "background:transparent;border:none;")
        lay.addWidget(icon)

        msg = QLabel(n.message)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
            "background:transparent;border:none;")
        lay.addWidget(msg, 1)

        close = QPushButton("✕")
        close.setFixedSize(18, 18)
        close.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;}}"
            f"QPushButton:hover{{color:{D.COLOR_TXT};}}")
        close.clicked.connect(self._dismiss)
        lay.addWidget(close)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_s, color, bg = _LEVEL_META.get(self._notif.level, _LEVEL_META["info"])
        w, h = self.width(), self.height()
        r = float(D.R_LG)
        path = QPainterPath(); path.addRoundedRect(0, 0, w, h, r, r)
        # Shadow suggestion via dark border
        p.fillPath(path, QBrush(QColor(D.COLOR_SURF2)))
        p.setPen(QPen(QColor(color), 1.5))
        p.drawPath(path)
        # Left accent bar
        bar = QPainterPath()
        bar.moveTo(r, 0); bar.lineTo(4, 0); bar.lineTo(4, h); bar.lineTo(r, h)
        bar.quadTo(0, h, 0, h-r); bar.lineTo(0, r); bar.quadTo(0, 0, r, 0)
        bar.closeSubpath()
        p.fillPath(bar, QBrush(QColor(color)))
        p.end()

    def _animate_in(self):
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        QTimer.singleShot(5000, self._dismiss)

    def _dismiss(self):
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()


class ToastManager(QObject):
    """
    Manages a stack of toast popups anchored to the bottom-right of parent.
    Attach to NotificationManager.posted signal.
    """
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent  = parent
        self._toasts: list[_ToastWidget] = []

    def show_toast(self, notif: Notification):
        toast = _ToastWidget(notif, self._parent)
        self._toasts.append(toast)
        self._reposition()
        toast.show()
        # Clean up dismissed toasts
        QTimer.singleShot(6000, self._cleanup)

    def _cleanup(self):
        self._toasts = [t for t in self._toasts if not t.isHidden() and t.isVisible()]
        self._reposition()

    def _reposition(self):
        parent = self._parent
        pw, ph = parent.width(), parent.height()
        margin = D.SP_3
        x = pw - _ToastWidget.TOAST_W - margin
        y = ph - margin
        for toast in reversed(self._toasts):
            if toast.isVisible():
                y -= _ToastWidget.TOAST_H + D.SP_2
                toast.move(parent.mapToGlobal(QPoint(x, y)))

    def reposition(self):
        self._cleanup()


# ── Notification Bell ─────────────────────────────────────────────────────────

class NotificationBell(QWidget):
    """
    Status-bar widget: bell icon + unread badge.
    Click to open/close the notification history panel.
    """
    toggled = pyqtSignal(bool)   # True = open

    def __init__(self, parent=None):
        super().__init__(parent)
        self._open = False
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Notifications")
        lay = QHBoxLayout(self); lay.setContentsMargins(D.SP_2,0,D.SP_2,0); lay.setSpacing(2)

        self._bell = QLabel("🔔")
        self._bell.setStyleSheet(
            f"color:{D.COLOR_TXT2};font-size:10pt;background:transparent;border:none;")
        lay.addWidget(self._bell)

        self._badge = QLabel("")
        self._badge.setFixedSize(16,16)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"background:{D.COLOR_ERR};color:#fff;border-radius:8px;"
            f"font-size:{D.FSIZE_XS}pt;font-weight:700;border:none;")
        self._badge.hide()
        lay.addWidget(self._badge)

    def on_notification(self, notif: Notification):
        nm = get_notif_manager()
        n = nm.unread_count
        if n > 0:
            self._badge.setText(str(min(n, 99)))
            self._badge.show()
            self._bell.setStyleSheet(
                f"color:{D.COLOR_WRN};font-size:10pt;background:transparent;border:none;")
        else:
            self._badge.hide()
            self._bell.setStyleSheet(
                f"color:{D.COLOR_TXT2};font-size:10pt;background:transparent;border:none;")

    def clear_badge(self):
        self._badge.hide()
        self._bell.setStyleSheet(
            f"color:{D.COLOR_TXT2};font-size:10pt;background:transparent;border:none;")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self.toggled.emit(self._open)
            if self._open:
                get_notif_manager().mark_all_read()
                self.clear_badge()
        super().mousePressEvent(e)


# ── Notification History Panel ─────────────────────────────────────────────────

class NotificationPanel(QWidget):
    """
    Slide-in panel listing all notifications.
    Wire to NotificationBell.toggled to show/hide.
    """
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(360)
        self.setStyleSheet(
            f"background:{D.COLOR_SURF};"
            f"border-left:1px solid {D.COLOR_BDR2};")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{D.COLOR_SURF2};border-bottom:1px solid {D.COLOR_BDR2};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(D.SP_4,0,D.SP_2,0)
        t = QLabel("🔔  Notifications")
        t.setStyleSheet(f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_MD}pt;font-weight:700;"
                         "background:transparent;border:none;")
        hl.addWidget(t); hl.addStretch()
        clr = QPushButton("Clear all"); clr.setObjectName("ghostBtn")
        clr.setFixedHeight(D.H_BTN); clr.clicked.connect(self._clear)
        cb = QPushButton("✕"); cb.setObjectName("ghostBtn")
        cb.setFixedSize(D.H_BTN,D.H_BTN); cb.clicked.connect(self.closed.emit)
        hl.addWidget(clr); hl.addWidget(cb); lay.addWidget(hdr)

        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{D.COLOR_SURF};border:none;}}"
            f"QScrollBar:vertical{{background:{D.COLOR_SURF};width:4px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{D.COLOR_SURF3};"
            f"border-radius:2px;min-height:16px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self._body = QWidget(); self._body.setStyleSheet(f"background:{D.COLOR_SURF};")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0,0,0,0); self._body_lay.setSpacing(0)
        self._body_lay.addStretch()
        self._scroll.setWidget(self._body); lay.addWidget(self._scroll)

    def refresh(self):
        while self._body_lay.count() > 1:
            item = self._body_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        history = get_notif_manager().history
        if not history:
            empty = QLabel("No notifications yet")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_SM}pt;"
                "background:transparent;border:none;padding:40px;")
            self._body_lay.insertWidget(0, empty)
            return

        for n in history:
            icon_s, color, bg = _LEVEL_META.get(n.level, _LEVEL_META["info"])
            row = QWidget(); row.setFixedHeight(56)
            rc = QColor(bg); rc.setAlpha(60) if n.read else None
            row.setStyleSheet(
                f"background:{'transparent' if n.read else bg};"
                f"border-bottom:1px solid {D.COLOR_BDR};border:none;")
            rl = QHBoxLayout(row); rl.setContentsMargins(D.SP_4,0,D.SP_4,0); rl.setSpacing(D.SP_2)
            ic = QLabel(icon_s)
            ic.setFixedSize(24,24); ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet(f"color:{color};font-size:{D.FSIZE_MD}pt;font-weight:700;"
                              "background:transparent;border:none;")
            rl.addWidget(ic)
            ml = QVBoxLayout(); ml.setSpacing(0)
            msg = QLabel(n.message); msg.setWordWrap(True)
            msg.setStyleSheet(f"color:{D.COLOR_TXT};font-size:{D.FSIZE_XS}pt;"
                               "background:transparent;border:none;")
            ts_s = n.ts.strftime("%H:%M  %d %b")
            ts = QLabel(ts_s)
            ts.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                              "background:transparent;border:none;")
            ml.addWidget(msg); ml.addWidget(ts)
            rl.addLayout(ml, 1)
            self._body_lay.insertWidget(self._body_lay.count()-1, row)

    def _clear(self):
        get_notif_manager().clear()
        self.refresh()