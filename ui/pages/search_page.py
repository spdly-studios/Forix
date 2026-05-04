# forix/ui/pages/search_page.py
"""
Forix — Search Page  (natural language v2)

Features:
  • Natural-language query parsing (stale python projects, low stock items, etc.)
  • Example query chips to teach the syntax
  • Grouped results: Projects / Files / Inventory with counts
  • Each result shows matched filters as chips
  • Double-click navigates to the item (projects open detail, files open explorer)
"""
import logging
import subprocess

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from services.search import SearchResult, search
import design as D

log = logging.getLogger("forix.search")

# Example queries shown as clickable chips to teach natural-language syntax
EXAMPLE_QUERIES = [
    "stale python projects",
    "arduino projects with no snapshots",
    "files modified this week",
    "active kicad projects over 20 files",
    "low stock components",
    "projects tagged embedded",
]

_KIND_META = {
    "project":   ("◈", D.COLOR_ACC,  "Projects"),
    "file":      ("◧", D.COLOR_ACC2, "Files"),
    "inventory": ("▤", D.COLOR_WRN,  "Inventory"),
}

_SS_INPUT = (
    f"QLineEdit{{background:{D.COLOR_SURF2};border:none;"
    f"border-bottom:2px solid {D.COLOR_ACC};"
    f"color:{D.COLOR_TXT};font-size:{D.FSIZE_MD}pt;padding:0 {D.SP_3}px;}}"
    f"QLineEdit:focus{{background:{D.COLOR_SURF3};}}"
)


class SearchPage(QWidget):
    project_selected = pyqtSignal(int)   # emitted when a project result is activated

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(); self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_search)
        self._results: list[SearchResult] = []
        self._result_widgets: list[QWidget] = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Toolbar
        hdr = QWidget(); hdr.setObjectName("pageHeader"); hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(D.SP_6,0,D.SP_6,0)
        t = QLabel("Search"); t.setObjectName("pageTitle"); hl.addWidget(t)
        root.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep)

        # Search bar panel
        bar_w = QWidget(); bar_w.setStyleSheet(f"background:{D.COLOR_SURF};")
        bl = QVBoxLayout(bar_w); bl.setContentsMargins(D.SP_6,D.SP_4,D.SP_6,D.SP_3); bl.setSpacing(D.SP_2)

        sub = QLabel("Natural language search across all projects, files, and inventory")
        sub.setStyleSheet(f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_SM}pt;"
                           "background:transparent;border:none;")
        bl.addWidget(sub)

        sr = QHBoxLayout(); sr.setSpacing(D.SP_2)
        self._box = QLineEdit()
        self._box.setPlaceholderText(
            "Try: \"stale python projects\"  ·  \"low stock components\"  ·  \"files modified this week\"")
        self._box.setFixedHeight(44)
        self._box.setStyleSheet(_SS_INPUT)
        self._box.textChanged.connect(self._on_text)
        self._box.returnPressed.connect(self._do_search)
        sr.addWidget(self._box)
        clr = QPushButton("✕ Clear"); clr.setObjectName("ghostBtn")
        clr.setFixedHeight(44); clr.clicked.connect(lambda: self._box.clear())
        sr.addWidget(clr)
        bl.addLayout(sr)

        # Example query chips
        chips_w = QWidget(); chips_w.setStyleSheet("background:transparent;")
        chips_l = QHBoxLayout(chips_w)
        chips_l.setContentsMargins(0,0,0,0); chips_l.setSpacing(D.SP_2)
        chips_l.addWidget(QLabel("Try:").setStyleSheet("") or self._tiny("Try:"))
        for q in EXAMPLE_QUERIES[:6]:
            chip = QPushButton(q)
            chip.setStyleSheet(
                f"QPushButton{{background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};"
                f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT2};"
                f"font-size:{D.FSIZE_XS}pt;padding:3px 8px;}}"
                f"QPushButton:hover{{border-color:{D.COLOR_ACC};color:{D.COLOR_ACC};}}"
            )
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _, qq=q: self._set_query(qq))
            chips_l.addWidget(chip)
        chips_l.addStretch()
        bl.addWidget(chips_w)
        root.addWidget(bar_w)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep2)

        # Status bar
        self._status_w = QWidget(); self._status_w.setFixedHeight(32)
        self._status_w.setStyleSheet(f"background:{D.COLOR_SURF};border-bottom:1px solid {D.COLOR_BDR};")
        sl = QHBoxLayout(self._status_w); sl.setContentsMargins(D.SP_6,0,D.SP_6,0)
        self._cnt = QLabel("Enter a search query above")
        self._cnt.setStyleSheet(f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_SM}pt;"
                                 "background:transparent;border:none;")
        sl.addWidget(self._cnt); sl.addStretch()
        self._hint = QLabel("Double-click to open · Enter to search")
        self._hint.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                                  "background:transparent;border:none;")
        sl.addWidget(self._hint)
        root.addWidget(self._status_w)

        # Scrollable results
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{D.COLOR_BG};border:none;}}"
            f"QScrollBar:vertical{{background:{D.COLOR_BG};width:6px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{D.COLOR_SURF3};"
            f"border-radius:3px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self._res_w = QWidget(); self._res_w.setStyleSheet(f"background:{D.COLOR_BG};")
        self._res_lay = QVBoxLayout(self._res_w)
        self._res_lay.setContentsMargins(D.SP_6, D.SP_4, D.SP_6, D.SP_8)
        self._res_lay.setSpacing(D.SP_3)
        self._res_lay.addStretch()
        self._scroll.setWidget(self._res_w)
        root.addWidget(self._scroll, 1)

    @staticmethod
    def _tiny(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                         "background:transparent;border:none;")
        return l

    # ── Query handling ─────────────────────────────────────────────────────────

    def _set_query(self, q: str):
        self._box.setText(q)
        self._do_search()

    def _on_text(self, text: str):
        self._debounce.stop()
        if text.strip():
            self._debounce.start(350)
        else:
            self._clear_results()
            self._cnt.setText("Enter a search query above")

    def _do_search(self):
        q = self._box.text().strip()
        if not q: return
        try:
            self._results = search(q, limit=100)
            n = len(self._results)
            proj_n = sum(1 for r in self._results if r.kind=="project")
            file_n = sum(1 for r in self._results if r.kind=="file")
            inv_n  = sum(1 for r in self._results if r.kind=="inventory")
            parts  = [f"{n} result{'s' if n!=1 else ''}"]
            if proj_n: parts.append(f"{proj_n} projects")
            if file_n: parts.append(f"{file_n} files")
            if inv_n:  parts.append(f"{inv_n} items")
            self._cnt.setText("  ·  ".join(parts))
            self._render(self._results)
        except Exception as exc:
            log.error("Search: %s", exc)
            self._cnt.setText(f"Error: {exc}")

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _clear_results(self):
        while self._res_lay.count() > 1:
            item = self._res_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _render(self, results: list[SearchResult]):
        self._clear_results()
        if not results:
            empty = QLabel("No results found. Try different keywords.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_MD}pt;"
                                  "background:transparent;border:none;padding:60px;")
            self._res_lay.insertWidget(0, empty)
            return

        # Group by kind
        by_kind: dict[str, list[SearchResult]] = {"project":[],"file":[],"inventory":[]}
        for r in results:
            by_kind.get(r.kind, by_kind["file"]).append(r)

        idx = 0
        for kind in ["project","file","inventory"]:
            group = by_kind[kind]
            if not group: continue

            icon, color, label = _KIND_META[kind]
            # Section header
            sec = self._section_header(f"{icon}  {label}", color, len(group))
            self._res_lay.insertWidget(idx, sec); idx += 1

            for r in group:
                row = self._result_row(r, color, icon)
                self._res_lay.insertWidget(idx, row); idx += 1

    def _section_header(self, label: str, color: str, count: int) -> QWidget:
        w = QWidget(); w.setFixedHeight(32)
        w.setStyleSheet(f"background:{D.COLOR_SURF2};border-radius:{D.R_SM}px;border:none;")
        lay = QHBoxLayout(w); lay.setContentsMargins(D.SP_3,0,D.SP_3,0)
        t = QLabel(label)
        t.setStyleSheet(f"color:{color};font-size:{D.FSIZE_SM}pt;font-weight:700;"
                         "background:transparent;border:none;")
        c = QLabel(str(count))
        c.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                         "background:transparent;border:none;")
        lay.addWidget(t); lay.addWidget(c); lay.addStretch()
        return w

    def _result_row(self, r: SearchResult, color: str, icon: str) -> QWidget:
        w = QWidget(); w.setFixedHeight(52)
        w.setStyleSheet(
            f"background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
            f"border-radius:{D.R_MD}px;")
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(w); lay.setContentsMargins(D.SP_3,0,D.SP_3,0); lay.setSpacing(D.SP_3)

        ic = QLabel(icon)
        ic.setFixedSize(24,24); ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(f"color:{color};font-size:{D.FSIZE_MD}pt;"
                          "background:transparent;border:none;")
        lay.addWidget(ic)

        info = QVBoxLayout(); info.setSpacing(0)
        lbl = QLabel(r.label)
        lbl.setStyleSheet(f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_SM}pt;"
                           "font-weight:700;background:transparent;border:none;")
        sub = QLabel(r.subtitle)
        sub.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                           "background:transparent;border:none;")
        info.addWidget(lbl); info.addWidget(sub)
        lay.addLayout(info, 1)

        # Matched filter chips
        if r.matched_filters:
            for f_txt in r.matched_filters[:3]:
                chip = QLabel(f" {f_txt} ")
                chip.setStyleSheet(
                    f"background:{color}22;color:{color};"
                    f"border:1px solid {color}55;border-radius:{D.R_SM}px;"
                    f"font-size:{D.FSIZE_XS}pt;font-weight:700;")
                lay.addWidget(chip)

        # Score badge
        score_lbl = QLabel(f"{r.score}%")
        score_lbl.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                                  "background:transparent;border:none;min-width:30px;")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(score_lbl)

        # Store result for double-click
        w._result = r
        w.mouseDoubleClickEvent = lambda _, rr=r: self._open_result(rr)
        # Hover effect
        w.enterEvent = lambda _, ww=w: ww.setStyleSheet(
            f"background:{D.COLOR_SURF2};border:1px solid {color};"
            f"border-radius:{D.R_MD}px;")
        w.leaveEvent = lambda _, ww=w: ww.setStyleSheet(
            f"background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
            f"border-radius:{D.R_MD}px;")
        return w

    def _open_result(self, r: SearchResult):
        try:
            if r.kind == "project":
                if hasattr(r.data, "id"):
                    self.project_selected.emit(r.data.id)
            elif r.kind == "file" and r.path:
                subprocess.Popen(f'explorer /select,"{r.path}"')
            elif r.kind == "inventory":
                win = self.window()
                if hasattr(win, "_on_nav"):
                    win._on_nav("inventory")
        except Exception as exc:
            log.error("Open result: %s", exc)