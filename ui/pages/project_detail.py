# forix/ui/pages/project_detail.py
import subprocess, datetime, logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QTextEdit, QProgressBar, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QScrollArea, QGridLayout, QToolButton, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from core.database import get_session, Project, TrackedFile, Version, ActivityEvent
from core.project_manager import create_version_snapshot, refresh_project_health
import design as D
from services.launcher import launch_project, launch_file, get_available_tools_for_project, get_best_tool_name_for_project

log = logging.getLogger("forix.detail")

_TICONS = {
    "arduino": "⚡", "kicad": "◻", "python": "🐍", "node": "⬡",
    "web": "◈", "cad": "◧", "embedded": "⚙", "document": "📄",
    "data": "📊", "generic": "◉",
}
_SCOLS = {
    "active": D.COLOR_OK, "planning": D.COLOR_ACC, "on-hold": D.COLOR_WRN,
    "archived": D.COLOR_TXT2, "stale": D.COLOR_WRN,
}
_CCOLS = {
    "code": D.CTYPE_PYTHON, "hardware": D.COLOR_WRN,
    "docs": D.COLOR_TXT2, "images": D.CTYPE_WEB, "data": D.COLOR_ACC,
}

_TABLE_STYLE = (
    f"QTableWidget {{"
    f"  background: {D.COLOR_BG};"
    f"  border: none;"
    f"  gridline-color: transparent;"
    f"  color: {D.COLOR_TXT};"
    f"  font-size: {D.FSIZE_SM}pt;"
    f"}}"
    f"QTableWidget::item {{"
    f"  padding: 0 {D.SP_2}px;"
    f"  border: none;"
    f"}}"
    f"QTableWidget::item:selected {{"
    f"  background: {D.COLOR_ACC_TINT};"
    f"  color: {D.COLOR_TXT};"
    f"}}"
    f"QTableWidget::item:alternate {{"
    f"  background: {D.COLOR_SURF};"
    f"}}"
    f"QHeaderView::section {{"
    f"  background: {D.COLOR_SURF};"
    f"  color: {D.COLOR_TXT2};"
    f"  font-size: {D.FSIZE_XS}pt;"
    f"  font-weight: 700;"
    f"  letter-spacing: 0.4px;"
    f"  border: none;"
    f"  border-bottom: 1px solid {D.COLOR_BDR};"
    f"  padding: {D.SP_1}px {D.SP_2}px;"
    f"}}"
)

_LIST_STYLE = (
    f"QListWidget {{"
    f"  background: {D.COLOR_BG};"
    f"  border: none;"
    f"  color: {D.COLOR_TXT};"
    f"  font-size: {D.FSIZE_SM}pt;"
    f"}}"
    f"QListWidget::item {{"
    f"  padding: {D.SP_1}px {D.SP_3}px;"
    f"  border: none;"
    f"}}"
    f"QListWidget::item:alternate {{"
    f"  background: {D.COLOR_SURF};"
    f"}}"
    f"QListWidget::item:selected {{"
    f"  background: {D.COLOR_ACC_TINT};"
    f"  color: {D.COLOR_TXT};"
    f"}}"
)

_SEARCH_STYLE = (
    f"QLineEdit {{"
    f"  background: transparent;"
    f"  border: none;"
    f"  border-bottom: 1.5px solid {D.COLOR_BDR};"
    f"  color: {D.COLOR_TXT};"
    f"  font-size: {D.FSIZE_SM}pt;"
    f"  padding: 0 {D.SP_1}px;"
    f"}}"
    f"QLineEdit:focus {{"
    f"  border-bottom: 2px solid {D.COLOR_ACC};"
    f"}}"
)


def _sz(n):
    if not n:
        return "0 B"
    for u in ["B", "KB", "MB", "GB"]:
        if float(n) < 1024:
            return f"{float(n):.1f} {u}"
        n = float(n) / 1024
    return f"{float(n):.1f} TB"


def _ago(dt):
    if not dt:
        return "—"
    try:
        d = (datetime.datetime.utcnow() - dt).days
        s = (datetime.datetime.utcnow() - dt).seconds
        if d == 0:
            return f"{s // 3600}h ago" if s // 3600 else f"{s // 60}m ago"
        if d == 1:
            return "Yesterday"
        if d < 7:
            return f"{d}d ago"
        if d < 30:
            return f"{d // 7}w ago"
        return f"{d // 30}mo ago"
    except:
        return "—"


class ProjectDetailPage(QWidget):
    back_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pid = None
        self._ptype = "generic"
        self._files = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setObjectName("pageHeader")
        hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(D.SP_3, 0, D.SP_6, 0)
        hl.setSpacing(D.SP_2)

        bk = QPushButton("← Back")
        bk.setObjectName("ghostBtn")
        bk.setFixedWidth(70)
        bk.clicked.connect(self.back_signal)
        hl.addWidget(bk)

        # Thin vertical separator
        sep_l = QFrame()
        sep_l.setFrameShape(QFrame.Shape.VLine)
        sep_l.setFixedWidth(1)
        sep_l.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
        hl.addWidget(sep_l)

        self._tico = QLabel("◉")
        self._tico.setStyleSheet(
            f"font-size: {D.FSIZE_LG}pt; color: {D.COLOR_ACC}; "
            f"background: transparent; border: none;"
        )
        hl.addWidget(self._tico)

        self._ttl = QLabel("—")
        self._ttl.setObjectName("pageTitle")
        hl.addWidget(self._ttl)

        self._sbdg = QLabel("")
        self._sbdg.setStyleSheet("background: transparent; border: none;")
        hl.addWidget(self._sbdg)

        hl.addStretch()

        self._ide_btn = QPushButton("▶ Open in IDE")
        self._ide_btn.setObjectName("accentBtn")
        self._ide_btn.setFixedWidth(140)
        self._ide_btn.clicked.connect(self._open_ide)
        hl.addWidget(self._ide_btn)

        self._ide_arrow = QToolButton()
        self._ide_arrow.setText("▾")
        self._ide_arrow.setFixedSize(D.H_BTN, D.H_BTN)
        self._ide_arrow.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._ide_drop = QMenu(self._ide_arrow)
        self._ide_arrow.setMenu(self._ide_drop)
        hl.addWidget(self._ide_arrow)

        snap = QPushButton("📸 Snapshot")
        snap.setObjectName("ghostBtn")
        snap.clicked.connect(self._snapshot)
        hl.addWidget(snap)

        exp = QPushButton("📂 Explorer")
        exp.setObjectName("ghostBtn")
        exp.clicked.connect(self._explorer)
        hl.addWidget(exp)

        edit = QPushButton("✎ Edit")
        edit.setObjectName("outlineBtn")
        edit.clicked.connect(self._edit_proj)
        hl.addWidget(edit)

        root.addWidget(hdr)

        # Thin rule below header
        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
        root.addWidget(rule)

        # ── Body: meta panel | tabs ───────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background-color: {D.COLOR_BG};")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(self._build_meta())
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
        bl.addWidget(sep)
        self._tabs = self._build_tabs()
        bl.addWidget(self._tabs, 1)
        root.addWidget(body)

    def _build_meta(self):
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setFixedWidth(204)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 3px; border-radius: 1px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {D.COLOR_BDR2}; border-radius: 1px; min-height: 20px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        inner = QWidget()
        inner.setStyleSheet(f"background-color: {D.COLOR_SURF};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(D.SP_3, D.SP_4, D.SP_3, D.SP_3)
        lay.setSpacing(2)

        def sec(t):
            lbl = QLabel(t.upper())
            lbl.setStyleSheet(
                f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_XS}pt; font-weight: 700; "
                f"letter-spacing: 0.6px; background: transparent; border: none;"
            )
            lbl.setContentsMargins(0, D.SP_3, 0, D.SP_1)
            return lbl

        # Health
        lay.addWidget(sec("Health"))
        self._hbar = QProgressBar()
        self._hbar.setRange(0, 100)
        self._hbar.setFixedHeight(4)
        self._hbar.setTextVisible(False)
        lay.addWidget(self._hbar)
        self._hlbl = QLabel("—")
        self._hlbl.setStyleSheet(
            f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_XS}pt; "
            f"background: transparent; border: none;"
        )
        self._hlbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self._hlbl)

        # Details
        lay.addWidget(sec("Details"))
        self._mf: dict[str, QLabel] = {}
        for k, l in [
            ("type", "Type"), ("category", "Category"), ("status", "Status"),
            ("files", "Files"), ("versions", "Snapshots"), ("size", "Size"),
            ("created", "Created"), ("last_active", "Last Active"),
        ]:
            kl = QLabel(l)
            kl.setStyleSheet(
                f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_XS}pt; font-weight: 600; "
                f"background: transparent; border: none; margin-top: {D.SP_1}px;"
            )
            lay.addWidget(kl)
            vl = QLabel("—")
            vl.setStyleSheet(
                f"color: {D.COLOR_TXT}; font-size: {D.FSIZE_SM}pt; "
                f"background: transparent; border: none;"
            )
            vl.setWordWrap(True)
            lay.addWidget(vl)
            self._mf[k] = vl

        # Tags
        lay.addWidget(sec("Tags"))
        self._tags_w = QWidget()
        self._tags_w.setStyleSheet("background: transparent;")
        self._tags_l = QGridLayout(self._tags_w)
        self._tags_l.setSpacing(D.SP_1)
        self._tags_l.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._tags_w)

        # Open With
        lay.addWidget(sec("Open With"))
        self._ide_list_w = QWidget()
        self._ide_list_w.setStyleSheet("background: transparent;")
        self._ide_list_l = QVBoxLayout(self._ide_list_w)
        self._ide_list_l.setSpacing(D.SP_1)
        self._ide_list_l.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._ide_list_w)

        # Actions
        lay.addWidget(sec("Actions"))
        arch = QPushButton("Archive Project")
        arch.setObjectName("ghostBtn")
        arch.clicked.connect(self._archive)
        lay.addWidget(arch)

        rem = QPushButton("Remove from Forix")
        rem.setObjectName("dangerBtn")
        rem.clicked.connect(self._delete)
        lay.addWidget(rem)

        lay.addStretch()
        panel.setWidget(inner)
        return panel

    def _build_tabs(self):
        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane {{"
            f"  border: none;"
            f"  background: {D.COLOR_BG};"
            f"}}"
            f"QTabBar::tab {{"
            f"  background: transparent;"
            f"  color: {D.COLOR_TXT2};"
            f"  font-size: {D.FSIZE_SM}pt;"
            f"  padding: {D.SP_2}px {D.SP_4}px;"
            f"  border: none;"
            f"  border-bottom: 2px solid transparent;"
            f"}}"
            f"QTabBar::tab:selected {{"
            f"  color: {D.COLOR_TXT};"
            f"  border-bottom: 2px solid {D.COLOR_ACC};"
            f"}}"
            f"QTabBar::tab:hover:!selected {{"
            f"  color: {D.COLOR_TXT};"
            f"}}"
        )

        # ── Files tab ─────────────────────────────────────────────────
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        ftb = QHBoxLayout()
        ftb.setContentsMargins(D.SP_3, D.SP_2, D.SP_3, D.SP_2)
        ftb.setSpacing(D.SP_2)
        self._fsrch = QLineEdit()
        self._fsrch.setPlaceholderText("Filter files…")
        self._fsrch.setFixedWidth(200)
        self._fsrch.setFixedHeight(D.H_BTN)
        self._fsrch.setStyleSheet(_SEARCH_STYLE)
        self._fsrch.textChanged.connect(self._filter_files)
        ftb.addWidget(self._fsrch)
        ftb.addStretch()
        ops = QPushButton("Open Selected")
        ops.setObjectName("outlineBtn")
        ops.clicked.connect(self._open_file)
        ftb.addWidget(ops)
        fl.addLayout(ftb)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {D.COLOR_BDR}; border: none;")
        fl.addWidget(rule)

        self._ftbl = QTableWidget(0, 6)
        self._ftbl.setHorizontalHeaderLabels(["Name", "Category", "Ext", "Size", "Modified", "Path"])
        self._ftbl.setStyleSheet(_TABLE_STYLE)
        hh = self._ftbl.horizontalHeader()
        for i in range(5):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._ftbl.setAlternatingRowColors(True)
        self._ftbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._ftbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ftbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._ftbl.customContextMenuRequested.connect(self._file_ctx)
        self._ftbl.doubleClicked.connect(self._open_file)
        self._ftbl.setShowGrid(False)
        self._ftbl.verticalHeader().setVisible(False)
        self._ftbl.verticalHeader().setDefaultSectionSize(D.H_ROW)
        fl.addWidget(self._ftbl)
        tabs.addTab(fw, "📁  Files")

        # ── Versions tab ──────────────────────────────────────────────
        vw = QWidget()
        vl = QVBoxLayout(vw)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        self._vtbl = QTableWidget(0, 5)
        self._vtbl.setHorizontalHeaderLabels(["Version", "Files", "Size", "Created", "Summary"])
        self._vtbl.setStyleSheet(_TABLE_STYLE)
        self._vtbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._vtbl.setAlternatingRowColors(True)
        self._vtbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._vtbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._vtbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._vtbl.customContextMenuRequested.connect(self._ver_ctx)
        self._vtbl.doubleClicked.connect(self._ver_dbl)
        self._vtbl.setShowGrid(False)
        self._vtbl.verticalHeader().setVisible(False)
        self._vtbl.verticalHeader().setDefaultSectionSize(D.H_ROW)
        vl.addWidget(self._vtbl)
        tabs.addTab(vw, "📸  Versions")

        # ── Activity tab ──────────────────────────────────────────────
        self._alist = QListWidget()
        self._alist.setStyleSheet(_LIST_STYLE)
        self._alist.setAlternatingRowColors(True)
        tabs.addTab(self._alist, "⚡  Activity")

        # ── Notes tab ─────────────────────────────────────────────────
        nw = QWidget()
        nl = QVBoxLayout(nw)
        nl.setContentsMargins(D.SP_4, D.SP_3, D.SP_4, D.SP_3)
        nl.setSpacing(D.SP_2)

        nh = QHBoxLayout()
        notes_title = QLabel("Project Notes")
        notes_title.setStyleSheet(
            f"color: {D.COLOR_TXT}; font-size: {D.FSIZE_BASE}pt; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        nh.addWidget(notes_title)
        nh.addStretch()
        self._nedit_btn = QPushButton("✎ Edit")
        self._nedit_btn.setObjectName("outlineBtn")
        self._nedit_btn.setFixedWidth(72)
        self._nedit_btn.clicked.connect(self._toggle_notes)
        nh.addWidget(self._nedit_btn)
        nl.addLayout(nh)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Notes, links, observations…")
        self._notes.setReadOnly(True)
        self._notes.setStyleSheet(
            f"QTextEdit {{"
            f"  background: {D.COLOR_SURF};"
            f"  border: none;"
            f"  border-radius: {D.R_MD}px;"
            f"  color: {D.COLOR_TXT};"
            f"  font-size: {D.FSIZE_BASE}pt;"
            f"  padding: {D.SP_3}px;"
            f"}}"
        )
        self._notes.textChanged.connect(self._save_notes)
        nl.addWidget(self._notes)
        tabs.addTab(nw, "📝  Notes")

        # ── Scratch / Archive tab ─────────────────────────────────────
        sw = QWidget()
        sl2 = QVBoxLayout(sw)
        sl2.setContentsMargins(D.SP_4, D.SP_3, D.SP_4, D.SP_3)
        sl2.setSpacing(D.SP_3)

        # Scratch section
        scratch_hdr = QHBoxLayout()
        scratch_title = QLabel("scratch/  — Work-in-progress attempts")
        scratch_title.setStyleSheet(
            f"color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;font-weight:700;"
            "background:transparent;border:none;")
        scratch_hdr.addWidget(scratch_title); scratch_hdr.addStretch()
        archive_btn = QPushButton("↓ Move to scratch")
        archive_btn.setObjectName("ghostBtn")
        archive_btn.setToolTip("Move all of src/ to a named attempt in scratch/")
        archive_btn.clicked.connect(self._move_to_scratch)
        scratch_hdr.addWidget(archive_btn)
        sl2.addLayout(scratch_hdr)

        scratch_desc = QLabel(
            "When you hit a wall: name your attempt below and click "
            "Move to scratch — Forix moves your src/ here intact "
            "and gives you a fresh start. Nothing is ever deleted.")
        scratch_desc.setWordWrap(True)
        scratch_desc.setStyleSheet(
            f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_XS}pt;"
            "background:transparent;border:none;")
        sl2.addWidget(scratch_desc)

        atname_row = QHBoxLayout(); atname_row.setSpacing(D.SP_2)
        self._attempt_name = QLineEdit()
        self._attempt_name.setPlaceholderText("Attempt name, e.g. attempt_01 or dead_end_async")
        self._attempt_name.setStyleSheet(
            f"background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};"
            f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};"
            f"font-size:{D.FSIZE_SM}pt;padding:0 {D.SP_2}px;"
            f"min-height:{D.H_BTN}px;")
        atname_row.addWidget(self._attempt_name, 1)
        sl2.addLayout(atname_row)

        self._scratch_list = QListWidget()
        self._scratch_list.setStyleSheet(
            f"QListWidget{{background:{D.COLOR_BG};border:none;color:{D.COLOR_TXT};"
            f"font-size:{D.FSIZE_SM}pt;}}"
            f"QListWidget::item{{padding:{D.SP_2}px {D.SP_3}px;"
            f"border-bottom:1px solid {D.COLOR_BDR};}}"
            f"QListWidget::item:selected{{background:{D.COLOR_ACC_TINT};"
            f"color:{D.COLOR_TXT};}}"
        )
        self._scratch_list.setFixedHeight(120)
        self._scratch_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._scratch_list.customContextMenuRequested.connect(self._scratch_ctx)
        sl2.addWidget(self._scratch_list)

        # Divider
        sdiv = QFrame(); sdiv.setFrameShape(QFrame.Shape.HLine)
        sdiv.setStyleSheet(f"background:{D.COLOR_BDR};border:none;")
        sdiv.setFixedHeight(1); sl2.addWidget(sdiv)

        # Archive section
        arch_hdr = QHBoxLayout()
        arch_title = QLabel("archive/  — Completed or abandoned attempts")
        arch_title.setStyleSheet(
            f"color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;font-weight:700;"
            "background:transparent;border:none;")
        arch_hdr.addWidget(arch_title); arch_hdr.addStretch()
        sl2.addLayout(arch_hdr)

        arch_desc = QLabel(
            "Move a scratch attempt here when it is fully done. "
            "Forix does not snapshot archive/.")
        arch_desc.setWordWrap(True)
        arch_desc.setStyleSheet(
            f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_XS}pt;"
            "background:transparent;border:none;")
        sl2.addWidget(arch_desc)

        self._archive_list = QListWidget()
        self._archive_list.setStyleSheet(
            f"QListWidget{{background:{D.COLOR_BG};border:none;color:{D.COLOR_TXT};"
            f"font-size:{D.FSIZE_SM}pt;}}"
            f"QListWidget::item{{padding:{D.SP_2}px {D.SP_3}px;"
            f"border-bottom:1px solid {D.COLOR_BDR};}}"
            f"QListWidget::item:selected{{background:{D.COLOR_ACC_TINT};"
            f"color:{D.COLOR_TXT};}}"
        )
        self._archive_list.setFixedHeight(100)
        self._archive_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._archive_list.customContextMenuRequested.connect(self._archive_ctx)
        sl2.addWidget(self._archive_list)
        sl2.addStretch()

        tabs.addTab(sw, "🗂  Scratch")

        return tabs

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_project(self, pid: int):
        try:
            self._pid = pid
            refresh_project_health(pid)
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=pid).first()
                if not p:
                    self._err(f"Project {pid} not found")
                    return
                self._ptype = p.project_type or "generic"
                self._tico.setText(_TICONS.get(self._ptype, "◉"))
                self._ttl.setText(p.name)

                sc = _SCOLS.get(p.status, D.COLOR_TXT2)
                self._sbdg.setText(f" {p.status} ")
                self._sbdg.setStyleSheet(
                    f"font-size: {D.FSIZE_XS}pt; font-weight: 700; color: {sc};"
                    f" background-color: {sc}22;"
                    f" border-radius: {D.R_SM}px; padding: 0px {D.SP_2}px;"
                    f" border: none;"
                )

                best = get_best_tool_name_for_project(self._ptype)
                self._ide_btn.setText(f"▶ Open in {best}")
                self._ide_drop.clear()
                for k, t in get_available_tools_for_project(self._ptype):
                    act = self._ide_drop.addAction(t.name)
                    act.triggered.connect(lambda _, kk=k, pp=p.path: self._open_tool(kk, pp))

                h = int(p.health or 0)
                hc = D.COLOR_OK if h >= 60 else (D.COLOR_WRN if h >= 30 else D.COLOR_ERR)
                self._hbar.setValue(h)
                self._hbar.setStyleSheet(
                    f"QProgressBar {{ background: {D.COLOR_SURF2}; border: none; border-radius: {D.R_SM}px; }}"
                    f"QProgressBar::chunk {{ background: {hc}; border-radius: {D.R_SM}px; }}"
                )
                self._hlbl.setText(f"{h}%")

                files = s.query(TrackedFile).filter_by(project_id=pid).all()
                vers  = s.query(Version).filter_by(project_id=pid).all()
                total = sum(f.size_bytes or 0 for f in files)

                for k, v in [
                    ("type",        p.project_type or "—"),
                    ("category",    p.category or "—"),
                    ("status",      p.status or "—"),
                    ("files",       str(len(files))),
                    ("versions",    str(len(vers))),
                    ("size",        _sz(total)),
                    ("created",     p.created_at.strftime("%Y-%m-%d") if p.created_at else "—"),
                    ("last_active", _ago(p.last_activity)),
                ]:
                    if k in self._mf:
                        self._mf[k].setText(v)

                # Tags
                while self._tags_l.count():
                    it = self._tags_l.takeAt(0)
                    if it.widget():
                        it.widget().deleteLater()
                for i, tag in enumerate(p.tags or []):
                    chip = QLabel(f" {tag} ")
                    chip.setStyleSheet(
                        f"font-size: {D.FSIZE_XS}pt; font-weight: 700; color: {D.COLOR_ACC2};"
                        f" background: {D.COLOR_ACC2_TINT};"
                        f" border-radius: {D.R_SM}px; padding: 0 {D.SP_1}px;"
                        f" border: none;"
                    )
                    self._tags_l.addWidget(chip, i // 2, i % 2)
                if not (p.tags or []):
                    no_tags = QLabel("No tags")
                    no_tags.setStyleSheet(
                        f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_SM}pt; "
                        f"background: transparent; border: none;"
                    )
                    self._tags_l.addWidget(no_tags, 0, 0)

                # Open With buttons
                while self._ide_list_l.count():
                    it = self._ide_list_l.takeAt(0)
                    if it.widget():
                        it.widget().deleteLater()
                avail = get_available_tools_for_project(self._ptype)
                for k, t in avail:
                    b = QPushButton(f"▶  {t.name}")
                    b.setObjectName("outlineBtn")
                    b.clicked.connect(lambda _, kk=k, pp=p.path: self._open_tool(kk, pp))
                    self._ide_list_l.addWidget(b)
                if not avail:
                    no = QLabel("No tools found.\nSet paths in Settings.")
                    no.setStyleSheet(
                        f"color: {D.COLOR_TXT2}; font-size: {D.FSIZE_SM}pt; "
                        f"background: transparent; border: none;"
                    )
                    no.setWordWrap(True)
                    self._ide_list_l.addWidget(no)

                # Notes
                self._notes.setReadOnly(True)
                self._nedit_btn.setText("✎ Edit")
                self._notes.setPlainText(p.description or "")

                # Scratch / Archive listings
                self._refresh_scratch_archive(p)

                # Files
                self._files = files
                self._fill_files(files)

                # Versions
                self._vtbl.setRowCount(0)
                for v in sorted(vers, key=lambda x: x.version_num, reverse=True):
                    r = self._vtbl.rowCount()
                    self._vtbl.insertRow(r)
                    dt = v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "—"
                    # Store "proj_path|rel_path" so contexts can resolve abs path
                    # v.path no longer exists — the column was renamed to rel_path
                    ver_key = f"{p.path}|{v.rel_path or ''}"
                    for c, (val, align) in enumerate([
                        (v.label,           Qt.AlignmentFlag.AlignCenter),
                        (str(v.file_count), Qt.AlignmentFlag.AlignCenter),
                        (_sz(v.size_bytes), Qt.AlignmentFlag.AlignRight),
                        (dt,                Qt.AlignmentFlag.AlignLeft),
                        (v.summary or "",   Qt.AlignmentFlag.AlignLeft),
                    ]):
                        cell = QTableWidgetItem(val)
                        cell.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                        cell.setData(Qt.ItemDataRole.UserRole, ver_key)
                        if c == 0:
                            cell.setForeground(QColor(D.COLOR_ACC))
                            f = QFont()
                            f.setBold(True)
                            cell.setFont(f)
                        self._vtbl.setItem(r, c, cell)

                # Activity
                self._alist.clear()
                EI = {
                    "project_created": "✦", "version_created": "📸",
                    "file_added": "＋", "file_modified": "~", "file_deleted": "−",
                }
                for ev in (
                    s.query(ActivityEvent)
                    .filter_by(project_id=pid)
                    .order_by(ActivityEvent.created_at.desc())
                    .limit(100)
                    .all()
                ):
                    dt = ev.created_at.strftime("%Y-%m-%d %H:%M") if ev.created_at else ""
                    item = QListWidgetItem(f"{EI.get(ev.event_type, '·')}  [{dt}]  {ev.description}")
                    self._alist.addItem(item)

            finally:
                s.close()
        except Exception as e:
            log.error(f"Load project: {e}")
            self._err(str(e))

    # ── File helpers ──────────────────────────────────────────────────────────

    def _fill_files(self, files):
        self._ftbl.setRowCount(0)
        for f in files:
            r = self._ftbl.rowCount()
            self._ftbl.insertRow(r)
            for c, (val, align) in enumerate([
                (f.name,      Qt.AlignmentFlag.AlignLeft),
                (f.category,  Qt.AlignmentFlag.AlignCenter),
                (f.extension, Qt.AlignmentFlag.AlignCenter),
                (_sz(f.size_bytes), Qt.AlignmentFlag.AlignRight),
                (f.modified_at.strftime("%Y-%m-%d %H:%M") if f.modified_at else "—",
                 Qt.AlignmentFlag.AlignLeft),
                (f.path,      Qt.AlignmentFlag.AlignLeft),
            ]):
                cell = QTableWidgetItem(val or "")
                cell.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                cell.setData(Qt.ItemDataRole.UserRole, f.path)
                if c == 1 and val:
                    cell.setForeground(QColor(_CCOLS.get(val, D.COLOR_TXT2)))
                self._ftbl.setItem(r, c, cell)

    def _filter_files(self, q):
        q = q.lower().strip()
        self._fill_files([
            f for f in self._files
            if not q or q in (f.name or "").lower() or q in (f.category or "").lower()
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_ide(self):
        if not self._pid:
            return
        try:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    ok, name = launch_project(p.project_type or "generic", Path(p.path))
                    self._toast(f"Opened in {name}" if ok else "No tool found")
            finally:
                s.close()
        except Exception as e:
            log.error(f"Open IDE: {e}")
            self._err(str(e))

    def _open_tool(self, k, pp):
        try:
            from services.launcher import TOOLS
            t = TOOLS.get(k)
            if t:
                t.launch(Path(pp))
                self._toast(f"Opened in {t.name}")
        except Exception as e:
            log.error(f"Tool: {e}")
            self._err(str(e))

    def _open_file(self):
        try:
            row = self._ftbl.currentRow()
            if row < 0:
                return
            item = self._ftbl.item(row, 5)
            if not item:
                return
            path = Path(item.data(Qt.ItemDataRole.UserRole) or item.text())
            if path.exists():
                ok, n = launch_file(path)
                self._toast(f"Opened in {n}" if ok else "Open failed")
            else:
                QMessageBox.warning(self, "Not Found", f"File not found:\n{path}")
        except Exception as e:
            log.error(f"Open file: {e}")
            self._err(str(e))

    def _snapshot(self):
        if not self._pid:
            return
        try:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    v = create_version_snapshot(p, s)
                    if v:
                        self._toast(f"Snapshot {v.label} created")
                        self.load_project(self._pid)
            finally:
                s.close()
        except Exception as e:
            log.error(f"Snapshot: {e}")
            self._err(str(e))

    def _explorer(self):
        if not self._pid:
            return
        try:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    subprocess.Popen(f'explorer "{p.path}"')
            finally:
                s.close()
        except Exception as e:
            log.error(f"Explorer: {e}")
            self._err(str(e))

    def _edit_proj(self):
        if not self._pid:
            return
        try:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    from ui.dialogs.edit_project_dialog import EditProjectDialog
                    dlg = EditProjectDialog(p, self)
                    if dlg.exec():
                        data = dlg.get_data()
                        p.name         = data["name"]
                        p.description  = data["description"]
                        p.project_type = data["project_type"]
                        p.category     = data["category"]
                        p.status       = data["status"]
                        p.tags         = data["tags"]
                        s.commit()
                        self.load_project(self._pid)
            finally:
                s.close()
        except Exception as e:
            log.error(f"Edit: {e}")
            self._err(str(e))

    def _toggle_notes(self):
        ro = self._notes.isReadOnly()
        self._notes.setReadOnly(not ro)
        self._nedit_btn.setText("💾 Save" if ro else "✎ Edit")
        if not ro:
            self._save_notes()

    def _save_notes(self):
        if self._pid and not self._notes.isReadOnly():
            try:
                s = get_session()
                try:
                    p = s.query(Project).filter_by(id=self._pid).first()
                    if p:
                        p.description = self._notes.toPlainText()
                        s.commit()
                finally:
                    s.close()
            except Exception as e:
                log.error(f"Save notes: {e}")

    def _archive(self):
        if not self._pid:
            return
        try:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    p.status = "archived"
                    s.commit()
                    self.load_project(self._pid)
            finally:
                s.close()
        except Exception as e:
            log.error(f"Archive: {e}")
            self._err(str(e))

    def _delete(self):
        try:
            if QMessageBox.question(
                self, "Remove", "Remove from Forix? (Files stay on disk)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                s = get_session()
                try:
                    p = s.query(Project).filter_by(id=self._pid).first()
                    if p:
                        s.delete(p)
                        s.commit()
                        self.back_signal.emit()
                finally:
                    s.close()
        except Exception as e:
            log.error(f"Delete: {e}")
            self._err(str(e))

    def _file_ctx(self, pos):
        try:
            item = self._ftbl.itemAt(pos)
            if not item:
                return
            path = Path(item.data(Qt.ItemDataRole.UserRole) or "")
            menu = QMenu(self)
            oa = menu.addAction("▶  Open File")
            fa = menu.addAction("📂  Open Containing Folder")
            menu.addSeparator()
            ca = menu.addAction("⎘  Copy Path")
            act = menu.exec(self._ftbl.viewport().mapToGlobal(pos))
            if act == oa and path.exists():
                launch_file(path)
            elif act == fa:
                subprocess.Popen(f'explorer /select,"{path}"')
            elif act == ca:
                from PyQt6.QtWidgets import QApplication
                QApplication.clipboard().setText(str(path))
        except Exception as e:
            log.error(f"File ctx: {e}")

    @staticmethod
    def _resolve_ver_path(key: str) -> Path:
        """Resolve a version key (proj_path|rel_path) to an absolute Path."""
        if "|" in key:
            proj, rel = key.split("|", 1)
            return Path(proj) / rel if rel else Path(proj)
        return Path(key)   # legacy absolute path fallback

    def _ver_ctx(self, pos):
        try:
            item = self._vtbl.itemAt(pos)
            if not item:
                return
            key = item.data(Qt.ItemDataRole.UserRole)
            menu = QMenu(self)
            oa = menu.addAction("📂  Open Snapshot Folder")
            ra = menu.addAction("↩  Restore This Version")
            act = menu.exec(self._vtbl.viewport().mapToGlobal(pos))
            if act == oa and key:
                path = self._resolve_ver_path(key)
                subprocess.Popen(f'explorer "{path}"')
            elif act == ra and key:
                self._restore(key)
        except Exception as e:
            log.error(f"Ver ctx: {e}")

    def _ver_dbl(self):
        try:
            row = self._vtbl.currentRow()
            if row < 0:
                return
            item = self._vtbl.item(row, 0)
            if item:
                key = item.data(Qt.ItemDataRole.UserRole)
                if key:
                    path = self._resolve_ver_path(key)
                    subprocess.Popen(f'explorer "{path}"')
        except Exception as e:
            log.error(f"Ver dbl: {e}")

    def _restore(self, ver_key):
        try:
            if QMessageBox.question(
                self, "Restore", "Overwrite current src/ files with this snapshot?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                import shutil
                s = get_session()
                try:
                    p = s.query(Project).filter_by(id=self._pid).first()
                    if p:
                        # Save current state first
                        create_version_snapshot(p, s)
                        snap_dir = self._resolve_ver_path(ver_key)
                        # Snapshots store files under <ver_dir>/src/
                        src = snap_dir / "src"
                        dst = Path(p.path) / "src"
                        if src.exists():
                            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
                            self._toast("Version restored")
                        else:
                            self._toast(f"Snapshot src/ not found: {src}")
                        self.load_project(self._pid)
                finally:
                    s.close()
        except Exception as e:
            log.error(f"Restore: {e}")
            self._err(str(e))

    def _refresh_scratch_archive(self, project):
        """Populate scratch/ and archive/ lists in the Scratch tab."""
        try:
            proj_path = Path(project.path)
            scratch = proj_path / "scratch"
            archive = proj_path / "archive"
            self._scratch_list.clear()
            if scratch.exists():
                for item in sorted(scratch.iterdir()):
                    if item.is_dir() and not item.name.startswith("."):
                        self._scratch_list.addItem(f"📁  {item.name}")
                    elif item.name not in (".gitkeep", "WORKFLOW.md"):
                        self._scratch_list.addItem(f"📄  {item.name}")
            self._archive_list.clear()
            if archive.exists():
                for item in sorted(archive.iterdir()):
                    if item.is_dir() and not item.name.startswith("."):
                        self._archive_list.addItem(f"📁  {item.name}")
                    elif item.name not in (".gitkeep",):
                        self._archive_list.addItem(f"📄  {item.name}")
        except Exception as exc:
            log.warning("Scratch/archive list: %s", exc)

    def _move_to_scratch(self):
        if not self._pid: return
        name = self._attempt_name.text().strip()
        if not name:
            QMessageBox.information(self, "Name required",
                "Enter a name for this attempt before moving to scratch.")
            return
        try:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    from core.project_manager import move_to_scratch
                    move_to_scratch(p, name, session=s)
                    self._attempt_name.clear()
                    self._refresh_scratch_archive(p)
                    self._toast(f"Moved src/ → scratch/{name} · Fresh start ready")
            finally:
                s.close()
        except Exception as exc:
            log.error("Move to scratch: %s", exc)
            self._err(str(exc))

    def _scratch_ctx(self, pos):
        item = self._scratch_list.itemAt(pos)
        if not item: return
        name = item.text().replace("📁  ","").replace("📄  ","").strip()
        menu = QMenu(self)
        oa = menu.addAction("📂  Open in Explorer")
        arch = menu.addAction("→  Move to archive")
        act = menu.exec(self._scratch_list.viewport().mapToGlobal(pos))
        if not act: return
        if not self._pid: return
        s = get_session()
        try:
            p = s.query(Project).filter_by(id=self._pid).first()
            if not p: return
            if act == oa:
                import subprocess
                subprocess.Popen(f'explorer "{Path(p.path) / "scratch" / name}"')
            elif act == arch:
                from core.project_manager import move_to_archive
                move_to_archive(p, name, source_subpath="scratch", session=s)
                self._refresh_scratch_archive(p)
                self._toast(f"Moved scratch/{name} → archive/")
        finally:
            s.close()

    def _archive_ctx(self, pos):
        item = self._archive_list.itemAt(pos)
        if not item: return
        name = item.text().replace("📁  ","").replace("📄  ","").strip()
        menu = QMenu(self)
        oa = menu.addAction("📂  Open in Explorer")
        act = menu.exec(self._archive_list.viewport().mapToGlobal(pos))
        if act == oa and self._pid:
            s = get_session()
            try:
                p = s.query(Project).filter_by(id=self._pid).first()
                if p:
                    import subprocess
                    subprocess.Popen(f'explorer "{Path(p.path) / "archive" / name}"')
            finally:
                s.close()

    def _toast(self, msg):
        win = self.window()
        if hasattr(win, "_notify"):
            win._notify("info", msg)

    def _err(self, msg):
        win = self.window()
        if hasattr(win, "_notify"):
            win._notify("error", msg)