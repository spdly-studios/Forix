# forix/ui/dialogs/new_project_dialog.py
"""Forix — New Project Dialog. All colors/spacing from theme.py."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QFrame,
    QFormLayout, QWidget, QDateEdit, QListWidget,
    QListWidgetItem, QCheckBox, QScrollArea, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QDate, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

import theme as T
from services.launcher import get_all_available_tools

_PROJECT_TYPES = [
    "generic", "python", "arduino", "kicad", "node", "web",
    "cad", "embedded", "document", "data",
]
_CATEGORIES = [
    "General", "Software", "Hardware", "Embedded", "Mechanical",
    "Documentation", "Data", "Research", "Personal", "Client Work",
    "Prototype", "Production",
]
_PRIORITIES = ["Normal", "Low", "High", "Critical"]
_STATUSES   = ["active", "planning", "on-hold", "archived"]

_TYPE_TO_CAT = {
    "python": "Software", "node": "Software", "web": "Software",
    "arduino": "Embedded", "kicad": "Hardware", "cad": "Mechanical",
    "embedded": "Embedded", "document": "Documentation",
    "data": "Data", "generic": "General",
}

# ── Shared widget style helpers ───────────────────────────────────────────────

_INPUT_BASE = (
    f"background: {T.surface}; "
    f"border: none; "
    f"border-bottom: 1.5px solid {T.border}; "
    f"border-radius: 0px; "
    f"color: {T.text_heading}; "
    f"font-size: {T.font_base}px; "
    f"padding: 0 {T.space_sm}px; "
    f"selection-background-color: {T.accent_tint};"
)

_INPUT_FOCUS = (
    f"background: {T.surface}; "
    f"border: none; "
    f"border-bottom: 2px solid {T.accent}; "
    f"border-radius: 0px; "
    f"color: {T.text_heading}; "
    f"font-size: {T.font_base}px; "
    f"padding: 0 {T.space_sm}px;"
)

_COMBO_STYLE = (
    f"QComboBox {{"
    f"  background: {T.surface};"
    f"  border: none;"
    f"  border-bottom: 1.5px solid {T.border};"
    f"  border-radius: 0px;"
    f"  color: {T.text_heading};"
    f"  font-size: {T.font_base}px;"
    f"  padding: 0 {T.space_sm}px;"
    f"}}"
    f"QComboBox:hover {{"
    f"  border-bottom-color: {T.accent};"
    f"}}"
    f"QComboBox::drop-down {{"
    f"  border: none;"
    f"  width: 24px;"
    f"}}"
    f"QComboBox QAbstractItemView {{"
    f"  background: {T.surface};"
    f"  border: 1px solid {T.border};"
    f"  border-radius: {T.radius_md}px;"
    f"  color: {T.text_heading};"
    f"  selection-background-color: {T.accent_tint};"
    f"  selection-color: {T.accent};"
    f"  outline: none;"
    f"}}"
)


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {T.text_secondary}; "
        f"font-size: {T.font_sm}px; "
        f"font-weight: 600; "
        f"background: transparent; "
        f"border: none; "
        f"letter-spacing: 0.4px; "
        f"text-transform: uppercase;"
    )
    lbl.setMinimumWidth(110)
    return lbl


def _field(widget: QWidget, height: int = None) -> QWidget:
    """Wrap a widget with consistent height."""
    if height:
        widget.setFixedHeight(height)
    return widget


def _lineedit(placeholder: str = "", height: int = None) -> QLineEdit:
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setFixedHeight(height or T.btn_height_md)
    w.setStyleSheet(_INPUT_BASE)
    return w


# ── TagInput ──────────────────────────────────────────────────────────────────

class TagInput(QWidget):
    """Chip-style tag editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.space_xs)

        self._tag_list = QListWidget()
        self._tag_list.setFlow(QListWidget.Flow.LeftToRight)
        self._tag_list.setWrapping(True)
        self._tag_list.setFixedHeight(52)
        self._tag_list.setStyleSheet(
            f"QListWidget {{"
            f"  background: {T.surface};"
            f"  border: none;"
            f"  border-bottom: 1.5px solid {T.border};"
            f"  border-radius: 0px;"
            f"  padding: {T.space_xs}px {T.space_sm}px;"
            f"}}"
            f"QListWidget::item {{"
            f"  background: {T.accent_tint};"
            f"  color: {T.accent};"
            f"  border: none;"
            f"  border-radius: {T.radius_sm}px;"
            f"  padding: 2px {T.space_sm}px;"
            f"  margin: 2px;"
            f"  font-size: {T.font_sm}px;"
            f"  font-weight: 700;"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {T.accent};"
            f"  color: #fff;"
            f"}}"
        )
        layout.addWidget(self._tag_list)

        row = QHBoxLayout()
        row.setSpacing(T.space_sm)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a tag and press Enter…")
        self._input.setFixedHeight(T.btn_height_md)
        self._input.setStyleSheet(_INPUT_BASE)
        self._input.returnPressed.connect(self._add)
        row.addWidget(self._input)

        rem_btn = QPushButton("✕ Remove")
        rem_btn.setObjectName("ghostBtn")
        rem_btn.setFixedHeight(T.btn_height_md)
        rem_btn.setFixedWidth(90)
        rem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rem_btn.clicked.connect(self._remove)
        row.addWidget(rem_btn)
        layout.addLayout(row)

    def _add(self):
        text = self._input.text().strip().strip(",")
        if text and text not in self._tags:
            self._tags.append(text)
            self._tag_list.addItem(QListWidgetItem(text))
        self._input.clear()

    def _remove(self):
        for item in self._tag_list.selectedItems():
            if item.text() in self._tags:
                self._tags.remove(item.text())
            self._tag_list.takeItem(self._tag_list.row(item))

    def get_tags(self) -> list: return list(self._tags)

    def set_tags(self, tags: list):
        self._tags = list(tags)
        self._tag_list.clear()
        for t in tags:
            self._tag_list.addItem(QListWidgetItem(t))


# ── NewProjectDialog ──────────────────────────────────────────────────────────

class NewProjectDialog(QDialog):
    def __init__(self, parent=None, prefill_name: str = "", prefill_type: str = "generic"):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(660)
        self.setMinimumHeight(720)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build(prefill_name, prefill_type)

    # ── Layout Build ──────────────────────────────────────────────────────────

    def _build(self, name: str, ptype: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(96)
        header.setStyleSheet(
            f"background: qlineargradient("
            f"  x1:0, y1:0, x2:1, y2:1,"
            f"  stop:0 {T.accent}, stop:1 {T.accent_tint_border}"
            f");"
        )
        h_lyt = QVBoxLayout(header)
        h_lyt.setContentsMargins(T.space_xl, T.space_lg, T.space_xl, T.space_lg)
        h_lyt.setSpacing(4)

        title_lbl = QLabel("Create New Project")
        title_lbl.setStyleSheet(
            "color: #ffffff; font-size: 22px; font-weight: 800; "
            "background: transparent; border: none; letter-spacing: 0.3px;"
        )
        h_lyt.addWidget(title_lbl)

        info_lbl = QLabel("Fill in the details below to set up your workspace.")
        info_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.72); font-size: 13px; "
            "background: transparent; border: none;"
        )
        h_lyt.addWidget(info_lbl)

        root.addWidget(header)

        # ── Scrollable Body ───────────────────────────────────────────
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
            f"  background: {T.border}; border-radius: 2px; min-height: 24px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0;"
            f"}}"
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_lyt = QVBoxLayout(body)
        b_lyt.setContentsMargins(T.space_xl, T.space_xl, T.space_xl, T.space_md)
        b_lyt.setSpacing(T.space_xl + T.space_md)

        # ── Section 1 — Basic Information ─────────────────────────────
        sec1 = self._create_section("Basic Information",
                                    "Name your project and describe its purpose.")
        b_lyt.addWidget(sec1["widget"])
        form1: QFormLayout = sec1["form"]

        self._name = QLineEdit(name)
        self._name.setPlaceholderText("e.g. Smart Irrigation Controller")
        self._name.setFixedHeight(T.btn_height_lg)
        self._name.setStyleSheet(
            f"font-size: 16px; font-weight: 600; padding: 0 {T.space_sm}px;"
            f"background: {T.surface}; "
            f"border: none; border-bottom: 2px solid {T.accent}; "
            f"border-radius: 0px; color: {T.text_heading};"
        )
        form1.addRow(_label("Name *"), self._name)

        self._desc = QTextEdit()
        self._desc.setPlaceholderText("Brief description of the project goals and scope…")
        self._desc.setFixedHeight(80)
        self._desc.setStyleSheet(
            f"background: {T.surface}; "
            f"border: none; border-bottom: 1.5px solid {T.border}; "
            f"border-radius: 0px; "
            f"padding: {T.space_sm}px {T.space_sm}px; "
            f"color: {T.text_heading}; font-size: {T.font_base}px;"
        )
        form1.addRow(_label("Description"), self._desc)

        # ── Section 2 — Environment & Workflow ────────────────────────
        sec2 = self._create_section("Environment & Workflow",
                                    "Choose the project type, tooling, and repository.")
        b_lyt.addWidget(sec2["widget"])
        form2: QFormLayout = sec2["form"]

        tc_row = QHBoxLayout()
        tc_row.setSpacing(T.space_lg)

        self._type_cb = QComboBox()
        self._type_cb.addItems(_PROJECT_TYPES)
        self._type_cb.setCurrentText(ptype)
        self._type_cb.setFixedHeight(T.btn_height_md)
        self._type_cb.setStyleSheet(_COMBO_STYLE)
        self._type_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._type_cb.currentTextChanged.connect(self._on_type_changed)
        tc_row.addWidget(self._type_cb)

        self._cat_cb = QComboBox()
        self._cat_cb.addItems(_CATEGORIES)
        self._cat_cb.setFixedHeight(T.btn_height_md)
        self._cat_cb.setStyleSheet(_COMBO_STYLE)
        self._cat_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        tc_row.addWidget(self._cat_cb)

        tc_w = QWidget()
        tc_w.setLayout(tc_row)
        tc_w.setStyleSheet("background: transparent;")
        form2.addRow(_label("Type / Category"), tc_w)

        self._ide_cb = QComboBox()
        self._ide_cb.setFixedHeight(T.btn_height_md)
        self._ide_cb.setStyleSheet(_COMBO_STYLE)
        self._ide_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ide_cb.addItem("⚡ Auto-detect", userData="auto")
        for key, tool in get_all_available_tools():
            self._ide_cb.addItem(tool.name, userData=key)
        form2.addRow(_label("Primary Tool"), self._ide_cb)

        self._repo = _lineedit("Repository URL or local path…")
        form2.addRow(_label("Repository"), self._repo)

        # ── Section 3 — Project Details ───────────────────────────────
        sec3 = self._create_section("Project Details",
                                    "Set status, priority, versioning, and metadata.")
        b_lyt.addWidget(sec3["widget"])
        form3: QFormLayout = sec3["form"]

        sp_row = QHBoxLayout()
        sp_row.setSpacing(T.space_lg)
        self._status_cb = QComboBox()
        self._status_cb.addItems(_STATUSES)
        self._status_cb.setFixedHeight(T.btn_height_md)
        self._status_cb.setStyleSheet(_COMBO_STYLE)
        self._status_cb.setCursor(Qt.CursorShape.PointingHandCursor)

        self._priority_cb = QComboBox()
        self._priority_cb.addItems(_PRIORITIES)
        self._priority_cb.setFixedHeight(T.btn_height_md)
        self._priority_cb.setStyleSheet(_COMBO_STYLE)
        self._priority_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        sp_row.addWidget(self._status_cb)
        sp_row.addWidget(self._priority_cb)
        sp_w = QWidget()
        sp_w.setLayout(sp_row)
        sp_w.setStyleSheet("background: transparent;")
        form3.addRow(_label("Status / Priority"), sp_w)

        vc_row = QHBoxLayout()
        vc_row.setSpacing(T.space_lg)
        self._ver = _lineedit("")
        self._ver.setText("1.0.0")
        self._client = _lineedit("Client or owner name…")
        vc_row.addWidget(self._ver)
        vc_row.addWidget(self._client)
        vc_w = QWidget()
        vc_w.setLayout(vc_row)
        vc_w.setStyleSheet("background: transparent;")
        form3.addRow(_label("Version / Client"), vc_w)

        self._tags = TagInput()
        if ptype and ptype != "generic":
            self._tags.set_tags([ptype])
        form3.addRow(_label("Tags"), self._tags)

        # Deadline row
        dl_row = QHBoxLayout()
        dl_row.setSpacing(T.space_lg)
        self._has_dl = QCheckBox("Set target deadline")
        self._has_dl.setStyleSheet(
            f"QCheckBox {{"
            f"  color: {T.text_heading}; font-size: {T.font_base}px;"
            f"  background: transparent; border: none;"
            f"}}"
            f"QCheckBox::indicator {{"
            f"  width: 16px; height: 16px;"
            f"  border: 1.5px solid {T.border}; border-radius: 4px;"
            f"  background: {T.surface};"
            f"}}"
            f"QCheckBox::indicator:checked {{"
            f"  background: {T.accent}; border-color: {T.accent};"
            f"}}"
        )
        self._dl_date = QDateEdit(QDate.currentDate().addMonths(1))
        self._dl_date.setCalendarPopup(True)
        self._dl_date.setFixedHeight(T.btn_height_md)
        self._dl_date.setEnabled(False)
        self._dl_date.setStyleSheet(
            f"QDateEdit {{"
            f"  background: {T.surface};"
            f"  border: none;"
            f"  border-bottom: 1.5px solid {T.border};"
            f"  border-radius: 0px;"
            f"  color: {T.text_heading};"
            f"  font-size: {T.font_base}px;"
            f"  padding: 0 {T.space_sm}px;"
            f"}}"
            f"QDateEdit:disabled {{ color: {T.text_secondary}; }}"
        )
        self._has_dl.stateChanged.connect(lambda s: self._dl_date.setEnabled(bool(s)))
        dl_row.addWidget(self._has_dl)
        dl_row.addWidget(self._dl_date)
        dl_row.addStretch()
        dl_w = QWidget()
        dl_w.setLayout(dl_row)
        dl_w.setStyleSheet("background: transparent;")
        form3.addRow(_label("Deadline"), dl_w)

        b_lyt.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── Footer / Buttons ──────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(68)
        footer.setStyleSheet(
            f"background: {T.surface}; "
            f"border-top: 1px solid {T.border};"
        )
        f_lyt = QHBoxLayout(footer)
        f_lyt.setContentsMargins(T.space_xl, 0, T.space_xl, 0)
        f_lyt.setSpacing(T.space_sm)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("ghostBtn")
        cancel.setFixedSize(100, T.btn_height_md)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        create = QPushButton("Create Project →")
        create.setObjectName("accentBtn")
        create.setFixedSize(160, T.btn_height_md)
        create.setCursor(Qt.CursorShape.PointingHandCursor)
        create.clicked.connect(self._on_create)

        f_lyt.addStretch()
        f_lyt.addWidget(cancel)
        f_lyt.addWidget(create)

        root.addWidget(footer)

        self._on_type_changed(ptype)

    # ── Section Builder ───────────────────────────────────────────────────────

    def _create_section(self, title: str, subtitle: str = "") -> dict:
        """Returns dict with 'widget' and 'form' (QFormLayout)."""
        sec = QWidget()
        # No border — just gentle background differentiation
        sec.setStyleSheet(
            f"background: {T.surface}; "
            f"border: none; "
            f"border-radius: {T.radius_md}px;"
        )
        outer = QVBoxLayout(sec)
        outer.setContentsMargins(T.space_lg, T.space_lg, T.space_lg, T.space_xl)
        outer.setSpacing(T.space_md)

        # Section heading
        head = QWidget()
        head.setStyleSheet("background: transparent;")
        head_lyt = QHBoxLayout(head)
        head_lyt.setContentsMargins(0, 0, 0, 0)
        head_lyt.setSpacing(T.space_md)

        # Accent left bar
        accent_bar = QFrame()
        accent_bar.setFixedWidth(3)
        accent_bar.setStyleSheet(
            f"background: {T.accent}; border: none; border-radius: 2px;"
        )
        head_lyt.addWidget(accent_bar)

        title_col = QWidget()
        title_col.setStyleSheet("background: transparent;")
        title_col_lyt = QVBoxLayout(title_col)
        title_col_lyt.setContentsMargins(0, 0, 0, 0)
        title_col_lyt.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {T.text_heading}; font-size: 13px; font-weight: 800; "
            f"background: transparent; border: none; letter-spacing: 0.3px;"
        )
        title_col_lyt.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(
                f"color: {T.text_secondary}; font-size: {T.font_sm}px; "
                f"background: transparent; border: none;"
            )
            title_col_lyt.addWidget(sub_lbl)

        head_lyt.addWidget(title_col)
        head_lyt.addStretch()
        outer.addWidget(head)

        # Thin separator — lighter, more subtle
        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(
            f"background: {T.border}; border: none; opacity: 0.5;"
        )
        outer.addWidget(rule)

        # Form layout
        form_w = QWidget()
        form_w.setStyleSheet("background: transparent;")
        form_lyt = QFormLayout(form_w)
        form_lyt.setContentsMargins(0, T.space_sm, 0, 0)
        form_lyt.setSpacing(T.space_lg)
        form_lyt.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_lyt.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        outer.addWidget(form_w)

        return {"widget": sec, "form": form_lyt}

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_type_changed(self, ptype: str):
        cat = _TYPE_TO_CAT.get(ptype, "General")
        idx = self._cat_cb.findText(cat)
        if idx >= 0:
            self._cat_cb.setCurrentIndex(idx)

    def _on_create(self):
        name = self._name.text().strip()
        if not name:
            self._name.setStyleSheet(
                f"font-size: 16px; font-weight: 600; padding: 0 {T.space_sm}px;"
                f"background: {T.danger_tint}; "
                f"border: none; border-bottom: 2px solid {T.danger}; "
                f"border-radius: 0px; color: {T.text_heading};"
            )
            self._name.setPlaceholderText("⚠  Name is required!")
            self._name.setFocus()
            return
        self.accept()

    # ── Data Accessor ─────────────────────────────────────────────────────────

    def get_data(self) -> dict:
        deadline = None
        if self._has_dl.isChecked():
            d = self._dl_date.date()
            deadline = f"{d.year()}-{d.month():02d}-{d.day():02d}"
        return {
            "name":          self._name.text().strip(),
            "description":   self._desc.toPlainText().strip(),
            "project_type":  self._type_cb.currentText(),
            "category":      self._cat_cb.currentText(),
            "status":        self._status_cb.currentText(),
            "priority":      self._priority_cb.currentText(),
            "version_str":   self._ver.text().strip(),
            "client":        self._client.text().strip(),
            "deadline":      deadline,
            "tags":          self._tags.get_tags(),
            "preferred_ide": self._ide_cb.currentData() or "auto",
            "repo_url":      self._repo.text().strip(),
        }