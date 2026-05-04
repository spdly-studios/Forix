# forix/ui/pages/settings_page.py
"""
Forix — Settings Page  (redesigned v3)

Four tabs:
  ⚙  Automation   — file handling, versioning, dedup
  🔧  Tools & IDEs — auto-detected tools, custom overrides
  ⚡  Background   — startup, monitoring, cleanup
  ℹ  About        — full developer + app info
"""

import sys
import logging
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, QRectF, QPointF, QSize
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QLinearGradient, QRadialGradient,
    QPainter, QPainterPath, QPixmap, QBrush, QPen, QPalette,
)
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QCheckBox, QComboBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

import config as C
import design as D
from services.launcher import TOOLS
from utils.config import get_config

log = logging.getLogger("forix.settings")


# ══════════════════════════════════════════════════════════════════════════════
#  REFINED COLOUR PALETTE  (richer dark theme with warm-tinted neutrals)
# ══════════════════════════════════════════════════════════════════════════════

class _P:
    """Local palette overrides — deeper, warmer, more intentional."""
    BG        = "#0D0F14"      # near-black, slightly warm
    SURF      = "#13161E"      # card surface
    SURF2     = "#191D28"      # slightly lighter card
    SURF3     = "#1F2433"      # hovered / focused input
    BDR       = "#252B3B"      # subtle divider
    BDR2      = "#2E3550"      # stronger border
    ACC       = "#5B8DEF"      # cool blue accent
    ACC_DK    = "#3A66CC"      # darker accent
    ACC_TINT  = "#5B8DEF18"    # accent ghost bg
    ACC2      = "#7ECBA1"      # green secondary accent
    OK        = "#7ECBA1"
    OK_TINT   = "#7ECBA115"
    WRN       = "#F0B860"
    WRN_TINT  = "#F0B86015"
    ERR       = "#E0605A"
    TXT_HEAD  = "#EEF1F8"
    TXT       = "#C4C9D9"
    TXT2      = "#7A8199"
    TXT_DIS   = "#454C62"
    WHITE     = "#FFFFFF"
    MONO      = getattr(D, "FONT_MONO", "Consolas")
    UI        = getattr(D, "FONT_UI",   "Segoe UI")


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED STYLE SHEETS
# ══════════════════════════════════════════════════════════════════════════════

_INPUT_STYLE = (
    f"QLineEdit, QSpinBox, QComboBox {{"
    f"  background: {_P.SURF2};"
    f"  border: 1px solid {_P.BDR2};"
    f"  border-radius: 6px;"
    f"  color: {_P.TXT};"
    f"  font-size: {D.FSIZE_SM}pt;"
    f"  padding: 0 {D.SP_2}px;"
    f"  min-height: {D.H_BTN}px;"
    f"}}"
    f"QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{"
    f"  border: 1.5px solid {_P.ACC};"
    f"  background: {_P.SURF3};"
    f"}}"
    f"QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 16px; }}"
    f"QComboBox::drop-down {{ border: none; width: 20px; }}"
    f"QComboBox QAbstractItemView {{"
    f"  background: {_P.SURF};"
    f"  border: 1px solid {_P.BDR2};"
    f"  border-radius: 6px;"
    f"  color: {_P.TXT};"
    f"  selection-background-color: {_P.ACC_TINT};"
    f"  selection-color: {_P.ACC};"
    f"  outline: none;"
    f"}}"
)

_CHECK_STYLE = (
    f"QCheckBox {{"
    f"  color: {_P.TXT};"
    f"  font-size: {D.FSIZE_SM}pt;"
    f"  background: transparent;"
    f"  border: none;"
    f"  spacing: 8px;"
    f"}}"
    f"QCheckBox::indicator {{"
    f"  width: 16px; height: 16px;"
    f"  border: 1.5px solid {_P.BDR2};"
    f"  border-radius: 4px;"
    f"  background: {_P.SURF2};"
    f"}}"
    f"QCheckBox::indicator:hover {{"
    f"  border-color: {_P.ACC};"
    f"  background: {_P.ACC_TINT};"
    f"}}"
    f"QCheckBox::indicator:checked {{"
    f"  background: {_P.ACC};"
    f"  border-color: {_P.ACC};"
    f"}}"
    f"QCheckBox::indicator:checked:hover {{ background: {_P.ACC_DK}; }}"
)

_TABLE_STYLE = (
    f"QTableWidget {{"
    f"  background: {_P.BG};"
    f"  border: none;"
    f"  gridline-color: transparent;"
    f"  color: {_P.TXT};"
    f"  font-size: {D.FSIZE_SM}pt;"
    f"}}"
    f"QTableWidget::item {{ padding: 0 {D.SP_2}px; border: none; }}"
    f"QTableWidget::item:alternate {{ background: {_P.SURF}; }}"
    f"QTableWidget::item:selected {{"
    f"  background: {_P.ACC_TINT}; color: {_P.TXT}; }}"
    f"QHeaderView::section {{"
    f"  background: {_P.SURF}; color: {_P.TXT2};"
    f"  font-size: {D.FSIZE_XS}pt; font-weight: 700; letter-spacing: 0.5px;"
    f"  border: none; border-bottom: 1px solid {_P.BDR};"
    f"  padding: {D.SP_1}px {D.SP_2}px; }}"
)

_TAB_STYLE = (
    f"QTabWidget::pane {{ border: none; background: {_P.BG}; }}"
    f"QTabBar {{ background: {_P.SURF}; border-bottom: 1px solid {_P.BDR}; }}"
    f"QTabBar::tab {{"
    f"  background: transparent; color: {_P.TXT2};"
    f"  font-size: {D.FSIZE_SM}pt; padding: {D.SP_2}px {D.SP_5}px;"
    f"  border: none; border-bottom: 2px solid transparent; min-height: 38px; }}"
    f"QTabBar::tab:selected {{"
    f"  color: {_P.TXT_HEAD}; border-bottom: 2px solid {_P.ACC}; font-weight: 700; }}"
    f"QTabBar::tab:hover:!selected {{ color: {_P.TXT}; background: {_P.SURF2}; }}"
)

_SCROLL_STYLE = (
    f"QScrollArea {{ background: {_P.BG}; border: none; }}"
    f"QScrollBar:vertical {{ background: transparent; width: 5px; border: none; }}"
    f"QScrollBar::handle:vertical {{ background: {_P.BDR2};"
    f" border-radius: 3px; min-height: 28px; }}"
    f"QScrollBar::handle:vertical:hover {{ background: {_P.ACC}; }}"
    f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {_P.TXT2}; font-size: {D.FSIZE_XS}pt; font-weight: 700;"
        f" letter-spacing: 0.5px; background: transparent; border: none;"
    )
    return lbl


def _section_card(title: str, subtitle: str = "") -> tuple[QWidget, QVBoxLayout]:
    """Returns (card_widget, inner_layout) — a titled card section."""
    card = QWidget()
    card.setStyleSheet(
        f"QWidget#settingsCard {{"
        f"  background: {_P.SURF};"
        f"  border: 1px solid {_P.BDR};"
        f"  border-radius: 10px;"
        f"}}"
    )
    card.setObjectName("settingsCard")
    outer = QVBoxLayout(card)
    outer.setContentsMargins(D.SP_5, D.SP_4, D.SP_5, D.SP_5)
    outer.setSpacing(D.SP_3)

    if title:
        # Header row: accent dot + title
        head = QWidget()
        head.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(D.SP_2)

        # Accent pill
        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background: {_P.ACC}; border: none; border-radius: 4px;"
        )
        hl.addWidget(dot)
        hl.setAlignment(dot, Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {_P.TXT_HEAD}; font-size: {D.FSIZE_SM}pt; font-weight: 800;"
            " background: transparent; border: none;"
        )
        col.addWidget(title_lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(
                f"color: {_P.TXT2}; font-size: {D.FSIZE_XS}pt;"
                " background: transparent; border: none;"
            )
            col.addWidget(sub)
        hl.addLayout(col)
        hl.addStretch()
        outer.addWidget(head)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_P.BDR}; border: none;")
        outer.addWidget(sep)

    return card, outer


def _info_banner(text: str, level: str = "info") -> QWidget:
    colors = {
        "info":    (_P.ACC,  _P.ACC_TINT),
        "warn":    (_P.WRN,  _P.WRN_TINT),
        "success": (_P.OK,   _P.OK_TINT),
    }
    fg, bg = colors.get(level, colors["info"])

    w = QWidget()
    w.setStyleSheet(
        f"background: {bg}; border: 1px solid {fg}40;"
        f" border-radius: 8px;"
    )
    lay = QHBoxLayout(w)
    lay.setContentsMargins(D.SP_3, D.SP_2, D.SP_3, D.SP_2)
    lay.setSpacing(D.SP_2)

    dot = QLabel("●")
    dot.setStyleSheet(
        f"color: {fg}; font-size: 8pt; background: transparent; border: none;"
    )
    dot.setFixedWidth(16)
    dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(dot)

    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"background: transparent; border: none; color: {fg};"
        f" font-size: {D.FSIZE_SM}pt;"
    )
    lay.addWidget(lbl, 1)
    return w


def _scrollable_tab() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(_SCROLL_STYLE)
    body = QWidget()
    body.setStyleSheet(f"background: {_P.BG};")
    lay = QVBoxLayout(body)
    lay.setContentsMargins(D.SP_6, D.SP_5, D.SP_6, D.SP_8)
    lay.setSpacing(D.SP_4)
    scroll.setWidget(body)
    return scroll, body, lay


def _tag_chip(text: str, fg: str, bg: str = None) -> QLabel:
    chip = QLabel(f"  {text}  ")
    chip.setStyleSheet(
        f"color: {fg};"
        f"font-size: {D.FSIZE_XS}pt;"
        f"font-weight: 700;"
        f"background: {_P.SURF3};"
        f"border: 1px solid {fg};"
        f"border-radius: 5px;"
        f"padding: 2px 0px;"
    )
    chip.setFixedHeight(22)
    return chip


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ══════════════════════════════════════════════════════════════════════════════

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = get_config()
        self._tool_edits: dict[str, QLineEdit] = {}
        self._build()
        self._load()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setObjectName("pageHeader")
        hdr.setFixedHeight(58)
        hdr.setStyleSheet(f"#pageHeader {{ background: {_P.SURF}; border: none; }}")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(D.SP_6, 0, D.SP_6, 0)
        hl.setSpacing(D.SP_3)

        # Icon + title
        t = QLabel("Settings")
        t.setObjectName("pageTitle")
        t.setStyleSheet(
            f"color: {_P.TXT_HEAD}; font-size: {D.FSIZE_LG}pt; font-weight: 800;"
            " background: transparent; border: none;"
        )
        hl.addWidget(t)
        hl.addStretch()

        hint = QLabel(f"v{C.APP_VERSION}  ·  {C.SETTINGS_FILE.name}")
        hint.setStyleSheet(
            f"color: {_P.TXT_DIS}; font-size: {D.FSIZE_XS}pt;"
            " background: transparent; border: none;"
        )
        hl.addWidget(hint)

        self._save_btn = QPushButton("  💾  Save Changes")
        self._save_btn.setObjectName("accentBtn")
        self._save_btn.setFixedHeight(D.H_BTN)
        self._save_btn.setMinimumWidth(155)
        self._save_btn.setStyleSheet(
            f"QPushButton#accentBtn {{"
            f"  background: {_P.ACC}; color: {_P.WHITE};"
            f"  border: none; border-radius: 7px;"
            f"  font-size: {D.FSIZE_SM}pt; font-weight: 700;"
            f"  padding: 0 {D.SP_4}px;"
            f"}}"
            f"QPushButton#accentBtn:hover {{ background: {_P.ACC_DK}; }}"
            f"QPushButton#accentBtn:disabled {{ background: {_P.BDR2}; color: {_P.TXT_DIS}; }}"
        )
        self._save_btn.clicked.connect(self._save)
        hl.addWidget(self._save_btn)

        root.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_P.BDR}; border: none;")
        root.addWidget(sep)

        # ── Tabs ──────────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet(_TAB_STYLE)
        tabs.addTab(self._tab_automation(), "⚙  Automation")
        tabs.addTab(self._tab_tools(),      "🔧  Tools & IDEs")
        tabs.addTab(self._tab_background(), "⚡  Background")
        tabs.addTab(AboutPage(),            "ℹ  About")
        root.addWidget(tabs)

    # ── Tab: Automation ───────────────────────────────────────────────────────

    def _tab_automation(self):
        scroll, _, lay = _scrollable_tab()

        # ── File Handling card ────────────────────────────────────────────────
        c1, l1 = _section_card(
            "File Handling",
            "Control how Forix moves, copies, and organises your files.",
        )
        f1 = QFormLayout()
        f1.setSpacing(D.SP_3)
        f1.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._auto_level = QComboBox()
        self._auto_level.addItems(["high", "medium", "low"])
        self._auto_level.setStyleSheet(_INPUT_STYLE)
        self._auto_level.setToolTip(
            "high: auto-organises\nmedium: copies, asks on ambiguous\nlow: track only"
        )
        f1.addRow(_field_label("Automation level:"), self._auto_level)

        self._auto_move = QCheckBox("Move files instead of copy when importing")
        self._auto_move.setStyleSheet(_CHECK_STYLE)
        f1.addRow(_field_label("Import mode:"), self._auto_move)

        self._auto_create = QCheckBox("Auto-create projects from newly detected folders")
        self._auto_create.setStyleSheet(_CHECK_STYLE)
        f1.addRow(_field_label("Project creation:"), self._auto_create)

        l1.addLayout(f1)
        lay.addWidget(c1)

        # ── Version Control card ──────────────────────────────────────────────
        c2, l2 = _section_card(
            "Version Control",
            "Snapshot settings — Forix auto-saves versions of your src/ folder.",
        )
        f2 = QFormLayout()
        f2.setSpacing(D.SP_3)
        f2.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._ver_deb = QSpinBox()
        self._ver_deb.setRange(5, 600)
        self._ver_deb.setSuffix("  sec")
        self._ver_deb.setStyleSheet(_INPUT_STYLE)
        self._ver_deb.setToolTip("Wait this long after the last file change before snapshotting.")
        f2.addRow(_field_label("Snapshot delay:"), self._ver_deb)

        self._max_ver = QSpinBox()
        self._max_ver.setRange(5, 500)
        self._max_ver.setStyleSheet(_INPUT_STYLE)
        f2.addRow(_field_label("Max snapshots / project:"), self._max_ver)

        self._ver_sz = QSpinBox()
        self._ver_sz.setRange(10, 5000)
        self._ver_sz.setSuffix("  MB")
        self._ver_sz.setStyleSheet(_INPUT_STYLE)
        f2.addRow(_field_label("Max snapshot size:"), self._ver_sz)

        self._merge_thr = QSpinBox()
        self._merge_thr.setRange(50, 100)
        self._merge_thr.setSuffix("  %")
        self._merge_thr.setStyleSheet(_INPUT_STYLE)
        f2.addRow(_field_label("Auto-merge threshold:"), self._merge_thr)

        self._dedup = QCheckBox("Enable duplicate file detection  (SHA-256 hash comparison)")
        self._dedup.setStyleSheet(_CHECK_STYLE)
        f2.addRow(_field_label("Duplicates:"), self._dedup)

        l2.addLayout(f2)
        lay.addWidget(c2)
        lay.addStretch()
        return scroll

    # ── Tab: Tools & IDEs ─────────────────────────────────────────────────────

    def _tab_tools(self):
        scroll, _, lay = _scrollable_tab()

        lay.addWidget(_info_banner(
            "Forix auto-detects installed tools from the Windows registry and common "
            "install paths. Enter a full path only if auto-detection fails for a tool.",
            "info",
        ))

        # ── Detected Tools card ───────────────────────────────────────────────
        c1, l1 = _section_card(
            "Detected Tools",
            "These tools were found on your system.",
        )
        self._det = QTableWidget(0, 3)
        self._det.setHorizontalHeaderLabels(["Tool", "Status", "Path"])
        self._det.setStyleSheet(_TABLE_STYLE)
        hh = self._det.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._det.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._det.setFixedHeight(200)
        self._det.setShowGrid(False)
        self._det.setAlternatingRowColors(True)
        self._det.verticalHeader().setVisible(False)
        self._det.verticalHeader().setDefaultSectionSize(D.H_ROW)
        l1.addWidget(self._det)

        rescan_row = QHBoxLayout()
        rescan_btn = QPushButton("↻  Re-scan Tools")
        rescan_btn.setObjectName("outlineBtn")
        rescan_btn.setFixedWidth(155)
        rescan_btn.setFixedHeight(D.H_BTN)
        rescan_btn.setStyleSheet(
            f"QPushButton#outlineBtn {{"
            f"  background: transparent; color: {_P.ACC};"
            f"  border: 1px solid {_P.ACC}40; border-radius: 7px;"
            f"  font-size: {D.FSIZE_SM}pt;"
            f"}}"
            f"QPushButton#outlineBtn:hover {{"
            f"  background: {_P.ACC_TINT}; border-color: {_P.ACC};"
            f"}}"
        )
        rescan_btn.clicked.connect(self._rescan)
        rescan_row.addWidget(rescan_btn)
        rescan_row.addStretch()
        l1.addLayout(rescan_row)
        lay.addWidget(c1)

        # ── Custom Paths card ─────────────────────────────────────────────────
        c2, l2 = _section_card(
            "Custom Executable Paths",
            "Override auto-detection by specifying the exact path to an executable.",
        )
        pf = QFormLayout()
        pf.setSpacing(D.SP_2)
        pf.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        tool_entries = [
            ("vscode",      "VS Code"),
            ("vscodium",    "VSCodium"),
            ("cursor",      "Cursor"),
            ("windsurf",    "Windsurf"),
            ("arduino",     "Arduino IDE"),
            ("kicad",       "KiCad"),
            ("freecad",     "FreeCAD"),
            ("pycharm",     "PyCharm"),
            ("webstorm",    "WebStorm"),
            ("clion",       "CLion"),
            ("notepadpp",   "Notepad++"),
            ("sublime",     "Sublime Text"),
            ("inkscape",    "Inkscape"),
            ("gimp",        "GIMP"),
            ("blender",     "Blender"),
            ("excel",       "Excel"),
            ("word",        "Word"),
            ("powerpoint",  "PowerPoint"),
            ("chrome",      "Chrome"),
            ("firefox",     "Firefox"),
            ("postman",     "Postman"),
            ("dbeaver",     "DBeaver"),
            ("obsidian",    "Obsidian"),
            ("figma",       "Figma"),
            ("docker",      "Docker Desktop"),
            ("terminal",    "Terminal"),
        ]
        for key, label in tool_entries:
            edit = self._path_row(pf, f"{label}:")
            self._tool_edits[key] = edit

        l2.addLayout(pf)
        lay.addWidget(c2)
        lay.addStretch()

        QTimer.singleShot(400, self._rescan)
        return scroll

    def _path_row(self, form: QFormLayout, label: str) -> QLineEdit:
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row_w)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(D.SP_1)

        edit = QLineEdit()
        edit.setPlaceholderText("Leave blank to auto-detect…")
        edit.setStyleSheet(_INPUT_STYLE)
        edit.setFixedHeight(D.H_BTN)
        rl.addWidget(edit, 1)

        _ghost_btn_style = (
            f"QPushButton {{ background: transparent; color: {_P.TXT2};"
            f" border: 1px solid {_P.BDR2}; border-radius: 6px;"
            f" font-size: {D.FSIZE_SM}pt; }}"
            f"QPushButton:hover {{ color: {_P.TXT}; border-color: {_P.ACC};"
            f" background: {_P.ACC_TINT}; }}"
        )

        browse = QPushButton("…")
        browse.setStyleSheet(_ghost_btn_style)
        browse.setFixedSize(D.H_BTN, D.H_BTN)
        browse.setToolTip("Browse for executable")
        browse.clicked.connect(lambda _, e=edit: self._browse(e))
        rl.addWidget(browse)

        clr = QPushButton("✕")
        clr.setStyleSheet(_ghost_btn_style)
        clr.setFixedSize(D.H_BTN, D.H_BTN)
        clr.setToolTip("Clear")
        clr.clicked.connect(lambda _, e=edit: e.clear())
        rl.addWidget(clr)

        form.addRow(_field_label(label), row_w)
        return edit

    # ── Tab: Background ───────────────────────────────────────────────────────

    def _tab_background(self):
        scroll, _, lay = _scrollable_tab()

        c1, l1 = _section_card(
            "Startup & Tray",
            "Control how Forix starts and behaves when minimised.",
        )
        f1 = QFormLayout()
        f1.setSpacing(D.SP_3)
        f1.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._sw = QCheckBox("Launch Forix automatically when Windows starts")
        self._sw.setStyleSheet(_CHECK_STYLE)
        f1.addRow(_field_label("Auto-start:"), self._sw)

        self._mt = QCheckBox("Minimise to system tray when window is closed")
        self._mt.setStyleSheet(_CHECK_STYLE)
        f1.addRow(_field_label("On close:"), self._mt)

        self._notif = QCheckBox("Show desktop notification popups for file events")
        self._notif.setStyleSheet(_CHECK_STYLE)
        f1.addRow(_field_label("Notifications:"), self._notif)

        l1.addLayout(f1)
        lay.addWidget(c1)

        c2, l2 = _section_card(
            "File Monitoring",
            "Configure how Forix watches for changes on your drive.",
        )
        f2 = QFormLayout()
        f2.setSpacing(D.SP_3)
        f2.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._wd = QCheckBox("Monitor entire E:\\ drive continuously (recommended)")
        self._wd.setStyleSheet(_CHECK_STYLE)
        f2.addRow(_field_label("Watch scope:"), self._wd)

        self._poll = QSpinBox()
        self._poll.setRange(500, 10000)
        self._poll.setSuffix("  ms")
        self._poll.setStyleSheet(_INPUT_STYLE)
        self._poll.setToolTip("How often to check if an Explorer window is open in a project folder.")
        f2.addRow(_field_label("Explorer poll:"), self._poll)

        self._health_int = QSpinBox()
        self._health_int.setRange(1, 60)
        self._health_int.setSuffix("  min")
        self._health_int.setStyleSheet(_INPUT_STYLE)
        f2.addRow(_field_label("Health refresh:"), self._health_int)

        self._clean = QCheckBox("Auto-delete files in Temp/ older than 30 days")
        self._clean.setStyleSheet(_CHECK_STYLE)
        f2.addRow(_field_label("Temp cleanup:"), self._clean)

        l2.addLayout(f2)
        lay.addWidget(c2)

        # Quick Actions
        c3, l3 = _section_card("Quick Actions", "Open Forix system folders and files.")
        btn_row = QHBoxLayout()
        btn_row.setSpacing(D.SP_2)

        _qa_style = (
            f"QPushButton {{ background: {_P.SURF2}; color: {_P.TXT};"
            f" border: 1px solid {_P.BDR2}; border-radius: 7px;"
            f" font-size: {D.FSIZE_SM}pt; padding: 0 {D.SP_3}px; }}"
            f"QPushButton:hover {{ background: {_P.SURF3}; border-color: {_P.ACC}; color: {_P.ACC}; }}"
        )

        for label, path in [
            ("📋  Logs",      C.LOGS_DIR),
            ("🗄  DB Folder",  C.SYSTEM_DIR),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(_qa_style)
            b.setFixedHeight(D.H_BTN)
            b.clicked.connect(lambda _, p=path: self._open_folder(p))
            btn_row.addWidget(b)

        cfg_btn = QPushButton("⚙  config.py")
        cfg_btn.setStyleSheet(_qa_style)
        cfg_btn.setFixedHeight(D.H_BTN)
        cfg_btn.clicked.connect(
            lambda: self._open_file(Path(__file__).parent.parent.parent / "config.py")
        )
        btn_row.addWidget(cfg_btn)
        btn_row.addStretch()
        l3.addLayout(btn_row)
        lay.addWidget(c3)

        lay.addStretch()
        return scroll

    # ── Actions ───────────────────────────────────────────────────────────────

    def _rescan(self):
        try:
            self._det.setRowCount(0)
            for k, t in TOOLS.items():
                exe = None
                try:
                    exe = t.find_exe()
                except Exception:
                    pass
                r = self._det.rowCount()
                self._det.insertRow(r)

                n_item = QTableWidgetItem(t.name)
                s_item = QTableWidgetItem("✓  Found" if exe else "—  Not found")
                p_item = QTableWidgetItem(str(exe) if exe else "—")

                s_item.setForeground(QColor(_P.OK if exe else _P.TXT_DIS))
                if exe:
                    n_item.setForeground(QColor(_P.TXT_HEAD))
                else:
                    n_item.setForeground(QColor(_P.TXT2))

                self._det.setItem(r, 0, n_item)
                self._det.setItem(r, 1, s_item)
                self._det.setItem(r, 2, p_item)
        except Exception as exc:
            log.error("Rescan: %s", exc)

    def _browse(self, edit: QLineEdit):
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Executable", "", "Executables (*.exe);;All Files (*)"
            )
            if path:
                edit.setText(path)
        except Exception as exc:
            log.error("Browse: %s", exc)

    def _open_folder(self, p: Path):
        try:
            subprocess.Popen(f'explorer "{p}"')
        except Exception as exc:
            log.error("Open folder: %s", exc)
            self._err(str(exc))

    def _open_file(self, p: Path):
        try:
            subprocess.Popen(f'notepad "{p}"')
        except Exception as exc:
            log.error("Open file: %s", exc)

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load(self):
        try:
            self._auto_level.setCurrentText(self._cfg.get("automation_level", "high"))
            self._auto_move.setChecked(self._cfg.get("auto_move_files", False))
            self._auto_create.setChecked(self._cfg.get("auto_create_projects", True))
            self._ver_deb.setValue(int(self._cfg.get("version_debounce_secs", 30)))
            self._max_ver.setValue(int(self._cfg.get("max_versions", 50)))
            self._ver_sz.setValue(int(self._cfg.get("version_size_limit_mb", 100)))
            self._merge_thr.setValue(int(self._cfg.get("auto_merge_threshold", 80)))
            self._dedup.setChecked(self._cfg.get("dedup_enabled", True))
            self._sw.setChecked(self._cfg.get("start_with_windows", False))
            self._mt.setChecked(self._cfg.get("minimize_to_tray", True))
            self._notif.setChecked(self._cfg.get("show_notifications", True))
            self._wd.setChecked(self._cfg.get("watch_entire_drive", True))
            self._poll.setValue(int(self._cfg.get("folder_open_poll_ms", 2000)))
            self._health_int.setValue(int(self._cfg.get("health_refresh_min", 5)))
            self._clean.setChecked(int(self._cfg.get("auto_clean_temp_days", 0)) > 0)
            for k, edit in self._tool_edits.items():
                edit.setText(self._cfg.get(f"{k}_path", "") or "")
        except Exception as exc:
            log.error("Load settings: %s", exc)

    def _save(self):
        try:
            updates = {
                "automation_level":      self._auto_level.currentText(),
                "auto_move_files":       self._auto_move.isChecked(),
                "auto_create_projects":  self._auto_create.isChecked(),
                "version_debounce_secs": self._ver_deb.value(),
                "max_versions":          self._max_ver.value(),
                "version_size_limit_mb": self._ver_sz.value(),
                "auto_merge_threshold":  self._merge_thr.value(),
                "dedup_enabled":         self._dedup.isChecked(),
                "start_with_windows":    self._sw.isChecked(),
                "minimize_to_tray":      self._mt.isChecked(),
                "show_notifications":    self._notif.isChecked(),
                "watch_entire_drive":    self._wd.isChecked(),
                "folder_open_poll_ms":   self._poll.value(),
                "health_refresh_min":    self._health_int.value(),
                "auto_clean_temp_days":  30 if self._clean.isChecked() else 0,
            }
            for k, edit in self._tool_edits.items():
                updates[f"{k}_path"] = edit.text().strip()

            self._cfg.set_many(updates)
            self._apply_startup(self._sw.isChecked())

            orig = self._save_btn.text()
            self._save_btn.setText("  ✓  Saved!")
            self._save_btn.setEnabled(False)
            QTimer.singleShot(2200, lambda: (
                self._save_btn.setText(orig),
                self._save_btn.setEnabled(True),
            ))
            self._ok("Settings saved successfully")
        except Exception as exc:
            log.error("Save settings: %s", exc)
            self._err(str(exc))

    def _apply_startup(self, enable: bool):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            if enable:
                script = str(Path(__file__).parent.parent.parent / "main.py")
                winreg.SetValueEx(
                    key, "Forix", 0, winreg.REG_SZ,
                    f'"{sys.executable}" "{script}"',
                )
            else:
                try:
                    winreg.DeleteValue(key, "Forix")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    def _ok(self, msg: str):
        win = self.window()
        if hasattr(win, "_notify"):
            win._notify("success", msg)

    def _err(self, msg: str):
        win = self.window()
        if hasattr(win, "_notify"):
            win._notify("error", msg)


# ══════════════════════════════════════════════════════════════════════════════
#  ABOUT PAGE
# ══════════════════════════════════════════════════════════════════════════════

class _AvatarWidget(QWidget):
    """
    Square avatar (1:1) with large rounded corners and a thin accent border.
    Width == Height.  Default size: 148 px.
    """
 
    def __init__(self, width: int = 148, parent=None):
        super().__init__(parent)
        self._sz = width
        self._pixmap: QPixmap | None = None
        self.setFixedSize(self._sz, self._sz)
        self.setStyleSheet("background: transparent; border: none;")
 
    def set_pixmap(self, pm: QPixmap):
        self._pixmap = pm
        self.update()
 
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sz = self._sz
        radius = 16          # generous rounded corners
 
        # ── Outer ring: single 1.5px accent line ────────────────────────────
        ring_pen = QPen(QColor(_P.ACC), 1.5)
        ring_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(ring_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, sz - 2, sz - 2, radius, radius)
 
        # ── Clip path for the image fill ─────────────────────────────────────
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(3, 3, sz - 6, sz - 6), radius - 2, radius - 2)
        p.setClipPath(clip)
 
        if self._pixmap and not self._pixmap.isNull():
            fill_w = sz - 6
            fill_h = sz - 6
            scaled = self._pixmap.scaled(
                fill_w, fill_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = max(0, (scaled.width()  - fill_w) // 2)
            oy = max(0, (scaled.height() - fill_h) // 2)
            p.drawPixmap(3, 3, scaled, ox, oy, fill_w, fill_h)
        else:
            # Placeholder: flat dark fill + centred initials
            p.fillRect(3, 3, sz - 6, sz - 6, QColor(_P.SURF2))
            p.setClipping(False)
            p.setPen(QColor(_P.TXT2))
            fnt = QFont(_P.UI, int(sz * 0.22))
            fnt.setBold(True)
            p.setFont(fnt)
            initials = "".join(w[0] for w in C.DEV_NAME.split()[:2]).upper()
            p.drawText(0, 0, sz, sz, Qt.AlignmentFlag.AlignCenter, initials)
 
        p.end()

class _LinkButton(QPushButton):
    def __init__(self, icon: str, label: str, url: str, parent=None):
        super().__init__(f"  {icon}  {label}", parent)
        self._url = url
        self.setFixedHeight(D.H_BTN)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(url)
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background: {_P.SURF2}; color: {_P.TXT};"
            f"  border: 1px solid {_P.BDR2}; border-radius: 7px;"
            f"  font-size: {D.FSIZE_SM}pt; padding: 0 {D.SP_3}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {_P.ACC_TINT}; color: {_P.ACC}; border-color: {_P.ACC};"
            f"}}"
        )
        self.clicked.connect(self._open)

    def _open(self):
        QDesktopServices.openUrl(QUrl(self._url))


class _CopyableRow(QWidget):
    def __init__(self, icon: str, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(D.SP_2)

        ic = QLabel(icon)
        ic.setFixedWidth(22)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(
            f"color: {_P.ACC}; font-size: {D.FSIZE_SM}pt;"
            " background: transparent; border: none;"
        )
        lay.addWidget(ic)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {_P.TXT2}; font-size: {D.FSIZE_XS}pt; font-weight: 700;"
            " background: transparent; border: none; min-width: 72px;"
        )
        lay.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(
            f"color: {_P.TXT}; font-size: {D.FSIZE_SM}pt;"
            " background: transparent; border: none;"
        )
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(val, 1)

        copy = QPushButton("⎘")
        copy.setFixedSize(26, 26)
        copy.setToolTip("Copy to clipboard")
        copy.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_P.TXT_DIS};"
            f" border: none; font-size: {D.FSIZE_SM}pt; border-radius: 4px; }}"
            f"QPushButton:hover {{ color: {_P.ACC}; background: {_P.ACC_TINT}; }}"
        )
        copy.clicked.connect(lambda: self._copy(value))
        lay.addWidget(copy)

    @staticmethod
    def _copy(text: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)


class _StatPill(QWidget):
    def __init__(self, value: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(D.SP_3, D.SP_3, D.SP_3, D.SP_3)
        lay.setSpacing(3)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._val = QLabel(value)
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setStyleSheet(
            f"color: {color}; font-size: {D.FSIZE_LG}pt; font-weight: 800;"
            " background: transparent; border: none;"
        )
        lay.addWidget(self._val)

        lbl = QLabel(label.upper())
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {_P.TXT_DIS}; font-size: {D.FSIZE_XS}pt; font-weight: 700;"
            " letter-spacing: 0.6px; background: transparent; border: none;"
        )
        lay.addWidget(lbl)

    def set_value(self, v: str):
        self._val.setText(v)


class AboutPage(QWidget):
    """
    Redesigned About page.
 
    Layout changes vs original:
    • Banner is clean dark (no green) — _GradientBanner above
    • App description + meta row sit inside the hero card with more padding
    • Developer section: avatar 148 px square, info on the right with better
      spacing; contact rows have explicit height so they're never cramped
    • Stats pills: fully opaque SURF2 background, larger value label
    • Feature highlights: unchanged layout, slightly refined row style
    • Tech stack / Licence / Paths: minimal tweaks for consistency
    """
 
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
 
    # ── Build ─────────────────────────────────────────────────────────────────
 
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
 
        scroll, _, lay = _scrollable_tab()
 
        # ════════════════════════════════════════════
        # HERO CARD
        # ════════════════════════════════════════════
        hero_card = QWidget()
        hero_card.setObjectName("settingsCard")
        hero_card.setStyleSheet(
            f"#settingsCard {{"
            f"  background: {_P.SURF};"
            f"  border: 1px solid {_P.BDR};"
            f"  border-radius: 10px;"
            f"}}"
        )
        hero_lay = QVBoxLayout(hero_card)
        hero_lay.setContentsMargins(0, 0, 0, D.SP_5)
        hero_lay.setSpacing(0)
 
        # Banner (redesigned — dark, no green)
        banner = _GradientBanner(C.APP_NAME, C.APP_TAGLINE)
        banner.setFixedHeight(112)
        hero_lay.addWidget(banner)
 
        # Body below banner
        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        blay = QVBoxLayout(body_w)
        blay.setContentsMargins(D.SP_5, D.SP_4, D.SP_5, 0)
        blay.setSpacing(D.SP_3)
 
        # Description text
        desc = QLabel(C.APP_DESCRIPTION)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {_P.TXT};"
            f"font-size: {D.FSIZE_SM}pt;"
            f"line-height: 1.65;"
            f"background: transparent;"
            f"border: none;"
        )
        blay.addWidget(desc)
 
        # Meta row: tags + Project Page button
        meta_row = QHBoxLayout()
        meta_row.setSpacing(D.SP_2)
        meta_row.setContentsMargins(0, 0, 0, 0)
 
        for txt, color in [
            (f"v{C.APP_VERSION}",     _P.ACC),
            ("Free for Personal Use", _P.WRN),
            (f"© {C.APP_YEAR}",      _P.TXT2),
        ]:
            chip = _tag_chip(txt, color)
            meta_row.addWidget(chip)
 
        meta_row.addStretch()
 
        if C.APP_WEBSITE:
            site_btn = _LinkButton("🌐", "Project Page", C.APP_WEBSITE)
            meta_row.addWidget(site_btn)
 
        blay.addLayout(meta_row)
        hero_lay.addWidget(body_w)
        lay.addWidget(hero_card)
 
        # ════════════════════════════════════════════
        # DEVELOPER CARD
        # ════════════════════════════════════════════
        dev_card, dl = _section_card(
            "Developer",
            "The person who built and maintains Forix.",
        )
 
        dev_body = QHBoxLayout()
        dev_body.setSpacing(D.SP_5)
        dev_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        dev_body.setContentsMargins(0, D.SP_2, 0, 0)
 
        # ── Avatar (148 px square) ─────────────────
        self._avatar = _AvatarWidget(width=148)
        self._load_avatar()
        dev_body.addWidget(self._avatar)
        dev_body.setAlignment(self._avatar, Qt.AlignmentFlag.AlignTop)
 
        # ── Info column ────────────────────────────
        info_col = QVBoxLayout()
        info_col.setSpacing(0)
        info_col.setAlignment(Qt.AlignmentFlag.AlignTop)
 
        name_lbl = QLabel(C.DEV_NAME)
        name_lbl.setStyleSheet(
            f"color: {_P.TXT_HEAD};"
            f"font-size: {D.FSIZE_LG}pt;"
            f"font-weight: 800;"
            f"background: transparent;"
            f"border: none;"
        )
        info_col.addWidget(name_lbl)
 
        title_lbl = QLabel(C.DEV_TITLE)
        title_lbl.setStyleSheet(
            f"color: {_P.ACC};"
            f"font-size: {D.FSIZE_SM}pt;"
            f"font-weight: 600;"
            f"background: transparent;"
            f"border: none;"
        )
        info_col.addWidget(title_lbl)
 
        # Thin separator
        info_col.addSpacing(D.SP_3)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_P.BDR}; border: none;")
        info_col.addWidget(sep)
        info_col.addSpacing(D.SP_3)
 
        # Contact rows
        if C.DEV_EMAIL:
            info_col.addWidget(_CopyableRow("✉", "Email", C.DEV_EMAIL))
            info_col.addSpacing(D.SP_1)
        if C.DEV_LINKEDIN:
            info_col.addWidget(_CopyableRow("in", "LinkedIn", C.DEV_LINKEDIN))
            info_col.addSpacing(D.SP_1)
        if C.DEV_GITHUB:
            info_col.addWidget(_CopyableRow("⌥", "GitHub", C.DEV_GITHUB))
 
        info_col.addSpacing(D.SP_4)
 
        # Link buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(D.SP_2)
        if C.DEV_LINKEDIN:
            btn_row.addWidget(_LinkButton("in", "LinkedIn", C.DEV_LINKEDIN))
        if C.DEV_EMAIL:
            btn_row.addWidget(_LinkButton("✉", "Email", f"mailto:{C.DEV_EMAIL}"))
        if C.DEV_GITHUB:
            btn_row.addWidget(_LinkButton("⌥", "GitHub", C.DEV_GITHUB))
        btn_row.addStretch()
        info_col.addLayout(btn_row)
        info_col.addStretch()
 
        dev_body.addLayout(info_col, 1)
        dl.addLayout(dev_body)
        lay.addWidget(dev_card)
 
        # ════════════════════════════════════════════
        # DATABASE STATS CARD
        # ════════════════════════════════════════════
        stats_card, sl = _section_card(
            "Database Statistics",
            "Live counts from your Forix database.",
        )
 
        stats_row = QHBoxLayout()
        stats_row.setSpacing(D.SP_2)
 
        pill_data = [
            ("_sp_proj",  "—", "Projects",  _P.ACC),
            ("_sp_files", "—", "Files",      _P.ACC2),
            ("_sp_snaps", "—", "Snapshots",  _P.OK),
            ("_sp_items", "—", "Inventory",  _P.WRN),
            ("_sp_db",    "—", "DB Size",    _P.TXT),
        ]
        for attr, val, lbl, col in pill_data:
            pill = _StatPill(val, lbl, col)
            # Fully opaque background — no more invisible ghost bg
            pill.setStyleSheet(
                f"background: {_P.SURF2};"
                f"border-radius: 8px;"
                f"border: 1px solid {_P.BDR2};"
            )
            setattr(self, attr, pill)
            stats_row.addWidget(pill, 1)
 
        sl.addLayout(stats_row)
        sl.addSpacing(D.SP_3)
 
        _action_btn_style = (
            f"QPushButton {{"
            f"  background: {_P.SURF2};"
            f"  color: {_P.TXT};"
            f"  border: 1px solid {_P.BDR2};"
            f"  border-radius: 7px;"
            f"  font-size: {D.FSIZE_SM}pt;"
            f"  padding: 0 {D.SP_3}px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {_P.SURF3};"
            f"  border-color: {_P.ACC};"
            f"  color: {_P.ACC};"
            f"}}"
        )
        rebuild_row = QHBoxLayout()
        rb_btn = QPushButton("🗄  Rebuild Database")
        rb_btn.setStyleSheet(_action_btn_style)
        rb_btn.setFixedHeight(D.H_BTN)
        rb_btn.setFixedWidth(185)
        rb_btn.clicked.connect(self._rebuild_db)
        rebuild_row.addWidget(rb_btn)
 
        refresh_btn = QPushButton("↻  Refresh Stats")
        refresh_btn.setStyleSheet(_action_btn_style)
        refresh_btn.setFixedHeight(D.H_BTN)
        refresh_btn.setFixedWidth(150)
        refresh_btn.clicked.connect(self._load_stats)
        rebuild_row.addWidget(refresh_btn)
        rebuild_row.addStretch()
        sl.addLayout(rebuild_row)
        lay.addWidget(stats_card)
 
        # ════════════════════════════════════════════
        # FEATURE HIGHLIGHTS CARD
        # ════════════════════════════════════════════
        feat_card, fl = _section_card(
            "Feature Highlights",
            "What Forix does for you automatically.",
        )
        features = [
            ("⊞", "Smart Dashboard",        "Live overview of all projects, file counts, and recent activity."),
            ("◈", "Project Management",      "Full lifecycle — create, import, archive, and version projects."),
            ("▤", "Inventory Tracking",      "Parts & components with low-stock alerts and usage history."),
            ("📸", "Auto Versioning",         "Debounced snapshots of src/ on every meaningful file change."),
            ("🔍", "Natural Language Search", "Query projects and files with plain English — no syntax needed."),
            ("⊕", "Duplicate Detection",     "SHA-256 based duplicate finder with one-click cleanup."),
            ("♥", "Health Monitor",          "Ranked project health scores with trend indicators."),
            ("⚡", "Live Activity Feed",      "Real-time event stream with 7-day sparkline chart."),
            ("🗂", "Scratch & Archive",       "Built-in anti-clutter workflow — dead-ends go to scratch/, not trash."),
            ("🔒", "Secure Notes",            "AES-256 encrypted storage for sensitive project notes and keys."),
        ]
        grid = QGridLayout()
        grid.setSpacing(D.SP_2)
        for i, (icon, title, desc_text) in enumerate(features):
            row_w = QWidget()
            row_w.setStyleSheet(
                f"background: {_P.SURF2};"
                f"border-radius: 8px;"
                f"border: 1px solid {_P.BDR};"
            )
            row_w.setFixedHeight(56)
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(D.SP_3, 0, D.SP_3, 0)
            rl.setSpacing(D.SP_2)
 
            ic = QLabel(icon)
            ic.setFixedWidth(26)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet(
                f"color: {_P.ACC};"
                f"font-size: {D.FSIZE_MD}pt;"
                f"background: transparent;"
                f"border: none;"
            )
            rl.addWidget(ic)
 
            txt_col = QVBoxLayout()
            txt_col.setSpacing(2)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(
                f"color: {_P.TXT_HEAD};"
                f"font-size: {D.FSIZE_SM}pt;"
                f"font-weight: 700;"
                f"background: transparent;"
                f"border: none;"
            )
            d_lbl = QLabel(desc_text)
            d_lbl.setStyleSheet(
                f"color: {_P.TXT2};"
                f"font-size: {D.FSIZE_XS}pt;"
                f"background: transparent;"
                f"border: none;"
            )
            txt_col.addWidget(t_lbl)
            txt_col.addWidget(d_lbl)
            rl.addLayout(txt_col, 1)
 
            grid.addWidget(row_w, i // 2, i % 2)
 
        fl.addLayout(grid)
        lay.addWidget(feat_card)
 
        # ════════════════════════════════════════════
        # TECH STACK CARD
        # ════════════════════════════════════════════
        tech_card, tl = _section_card(
            "Technology Stack",
            "Built with modern Python and a custom Qt6 dark UI.",
        )
        tech_items = [
            ("Python 3.11+",           "Core language"),
            ("PyQt6",                  "Desktop UI framework"),
            ("SQLAlchemy + SQLite",    "Database ORM — WAL mode for concurrent access"),
            ("Watchdog",               "Cross-platform filesystem event monitoring"),
            ("cryptography (Fernet)",  "AES-256 secure storage"),
            ("rapidfuzz",              "Fuzzy search and project-name matching"),
        ]
        tech_grid = QGridLayout()
        tech_grid.setSpacing(D.SP_2)
        for i, (name, purpose) in enumerate(tech_items):
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(D.SP_2)
 
            dot = QLabel("▸")
            dot.setStyleSheet(
                f"color: {_P.ACC}; font-size: {D.FSIZE_XS}pt;"
                " background: transparent; border: none;"
            )
            rl.addWidget(dot)
 
            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(
                f"color: {_P.TXT_HEAD}; font-size: {D.FSIZE_SM}pt; font-weight: 700;"
                " background: transparent; border: none; min-width: 200px;"
            )
            rl.addWidget(n_lbl)
 
            p_lbl = QLabel(purpose)
            p_lbl.setStyleSheet(
                f"color: {_P.TXT2}; font-size: {D.FSIZE_SM}pt;"
                " background: transparent; border: none;"
            )
            rl.addWidget(p_lbl, 1)
            tech_grid.addWidget(row_w, i // 2, i % 2)
 
        tl.addLayout(tech_grid)
        lay.addWidget(tech_card)
 
        # ════════════════════════════════════════════
        # LICENCE CARD
        # ════════════════════════════════════════════
        lic_card, ll = _section_card("Licence", "Free for Personal Use")
        lic_text = QLabel(
            "This software is provided free of charge for personal, non-commercial use only.\n"
            "Redistribution, sublicensing, modification, or use in commercial products\n"
            "is strictly prohibited without prior written permission from the developer.\n\n"
            'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.'
        )
        lic_text.setWordWrap(True)
        lic_text.setStyleSheet(
            f"font-family: '{_P.MONO}';"
            f"font-size: {D.FSIZE_SM}pt;"
            f"color: {_P.TXT2};"
            f"background: {_P.SURF2};"
            f"border: 1px solid {_P.BDR2};"
            f"border-radius: 8px;"
            f"padding: {D.SP_3}px {D.SP_4}px;"
        )
        ll.addWidget(lic_text)
        lay.addWidget(lic_card)
 
        # ════════════════════════════════════════════
        # SYSTEM PATHS CARD
        # ════════════════════════════════════════════
        paths_card, pl = _section_card(
            "System Paths",
            "Where Forix stores its data on your machine.",
        )
        paths_info = QLabel(
            f"Settings:    {C.SETTINGS_FILE}\n"
            f"Database:   {C.SYSTEM_DB}\n"
            f"Logs:          {C.LOGS_DIR}\n"
            f"Cache:        {C.CACHE_DIR}"
        )
        paths_info.setStyleSheet(
            f"font-family: '{_P.MONO}';"
            f"font-size: {D.FSIZE_SM}pt;"
            f"color: {_P.TXT2};"
            f"background: {_P.SURF2};"
            f"border: 1px solid {_P.BDR2};"
            f"border-radius: 8px;"
            f"padding: {D.SP_3}px {D.SP_4}px;"
        )
        pl.addWidget(paths_info)
        lay.addWidget(paths_card)
 
        lay.addStretch()
        root.addWidget(scroll)
 
        QTimer.singleShot(500, self._load_stats)
 
    # ── Helpers ───────────────────────────────────────────────────────────────
 
    def _load_avatar(self):
        assets_dir = Path(__file__).parent.parent.parent / "assets"
        avatar_path = assets_dir / C.DEV_PROFILE_IMG
        if avatar_path.exists():
            pm = QPixmap(str(avatar_path))
            if not pm.isNull():
                self._avatar.set_pixmap(pm)
                return
        self._avatar.set_pixmap(QPixmap())
 
    def _load_stats(self):
        try:
            from core.database import (
                get_session, Project, TrackedFile, Version, InventoryItem,
            )
            s = get_session()
            try:
                np = s.query(Project).count()
                nf = s.query(TrackedFile).count()
                nv = s.query(Version).count()
                ni = s.query(InventoryItem).count()
            finally:
                s.close()
 
            db_kb = (
                C.SYSTEM_DB.stat().st_size / 1024
                if C.SYSTEM_DB.exists() else 0
            )
            db_str = f"{db_kb:.0f} KB" if db_kb < 1024 else f"{db_kb/1024:.1f} MB"
 
            self._sp_proj.set_value(str(np))
            self._sp_files.set_value(str(nf))
            self._sp_snaps.set_value(str(nv))
            self._sp_items.set_value(str(ni))
            self._sp_db.set_value(db_str)
        except Exception as exc:
            log.error("About stats: %s", exc)
 
    def _rebuild_db(self):
        try:
            from core.database import init_db
            init_db()
            self._load_stats()
            win = self.window()
            if hasattr(win, "_notify"):
                win._notify("success", "Database rebuilt successfully")
        except Exception as exc:
            log.error("Rebuild DB: %s", exc)
            win = self.window()
            if hasattr(win, "_notify"):
                win._notify("error", f"Rebuild failed: {exc}")

# ══════════════════════════════════════════════════════════════════════════════
#  GRADIENT BANNER
# ══════════════════════════════════════════════════════════════════════════════

class _GradientBanner(QWidget):
    """
    Minimal dark banner:
    - Near-black background matching _P.SURF
    - Subtle dot-grid texture
    - 4 px left accent bar in _P.ACC (blue)
    - Large app-initial monogram on the right as a watermark
    - App name + tagline on the left
    Top corners rounded; bottom corners square to flush against card body.
    """
 
    def __init__(self, app_name: str, tagline: str, parent=None):
        super().__init__(parent)
        self._app_name = app_name
        self._tagline  = tagline
        self.setStyleSheet("border: none;")
 
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
 
        # ── Clip: only round top corners ─────────────────────────────────────
        clip = QPainterPath()
        r = 10
        clip.moveTo(r, 0)
        clip.lineTo(w - r, 0)
        clip.quadTo(w, 0, w, r)
        clip.lineTo(w, h)
        clip.lineTo(0, h)
        clip.lineTo(0, r)
        clip.quadTo(0, 0, r, 0)
        clip.closeSubpath()
        p.setClipPath(clip)
 
        # ── Background: flat dark, very subtle horizontal gradient ────────────
        bg = QLinearGradient(QPointF(0, 0), QPointF(w, 0))
        bg.setColorAt(0.0, QColor(_P.SURF))
        bg.setColorAt(1.0, QColor(_P.SURF2))
        p.fillRect(0, 0, w, h, QBrush(bg))
 
        # ── Dot-grid texture ─────────────────────────────────────────────────
        dot_c = QColor(_P.BDR)
        dot_c.setAlpha(55)
        p.setPen(QPen(dot_c, 1))
        for x in range(0, w, 18):
            for y in range(0, h, 18):
                p.drawPoint(x, y)
 
        # ── Bottom divider line ───────────────────────────────────────────────
        div = QColor(_P.BDR2)
        p.setPen(QPen(div, 1))
        p.drawLine(0, h - 1, w, h - 1)
 
        # ── Left accent bar (4 px solid blue) ────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(_P.ACC)))
        p.drawRect(0, 0, 4, h)
 
        # ── Watermark monogram (large, right side, very low opacity) ─────────
        p.setClipping(False)
        mono_fnt = QFont(_P.UI, int(h * 0.9))
        mono_fnt.setBold(True)
        mono_fnt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -2)
        p.setFont(mono_fnt)
        mono_c = QColor(_P.ACC)
        mono_c.setAlpha(12)
        p.setPen(mono_c)
        initials = (self._app_name[:2]).upper()
        p.drawText(
            w - int(h * 1.6), 0, int(h * 1.8), h,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            initials,
        )
 
        # ── App name ──────────────────────────────────────────────────────────
        pad = 20
        name_fnt = QFont(_P.UI, D.FSIZE_XL)
        name_fnt.setBold(True)
        name_fnt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        p.setFont(name_fnt)
        p.setPen(QColor(_P.TXT_HEAD))
        p.drawText(
            pad, 0, w - pad * 2, int(h * 0.58),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            self._app_name,
        )
 
        # ── Tagline ───────────────────────────────────────────────────────────
        tag_fnt = QFont(_P.UI, D.FSIZE_SM)
        p.setFont(tag_fnt)
        p.setPen(QColor(_P.TXT2))
        p.drawText(
            pad, int(h * 0.60), w - pad * 2, int(h * 0.40),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            self._tagline,
        )
        p.end()