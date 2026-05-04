# forix/ui/pages/duplicate_manager.py
"""
Forix — Duplicate File Manager
Reviews SHA-256 duplicate groups detected by the organiser,
lets the user keep one copy and delete (or move to scratch) the rest.
"""
import logging
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.database import DuplicateGroup, TrackedFile, get_session
import design as D

log = logging.getLogger("forix.duplicates")

_SS_TABLE = (
    f"QTableWidget{{background:{D.COLOR_SURF};border:none;"
    f"gridline-color:{D.COLOR_BDR};color:{D.COLOR_TXT};"
    f"font-size:{D.FSIZE_SM}pt;}}"
    f"QTableWidget::item{{padding:0 {D.SP_2}px;border:none;}}"
    f"QTableWidget::item:selected{{background:{D.COLOR_ACC_TINT};color:{D.COLOR_TXT};}}"
    f"QTableWidget::item:alternate{{background:{D.COLOR_SURF2};}}"
    f"QHeaderView::section{{background:{D.COLOR_SURF2};color:{D.COLOR_TXT2};"
    f"font-size:{D.FSIZE_XS}pt;font-weight:700;border:none;"
    f"border-bottom:1px solid {D.COLOR_BDR2};padding:{D.SP_1}px {D.SP_2}px;}}"
)
_SS_LIST = (
    f"QListWidget{{background:{D.COLOR_BG};border:none;color:{D.COLOR_TXT};"
    f"font-size:{D.FSIZE_SM}pt;}}"
    f"QListWidget::item{{padding:{D.SP_2}px {D.SP_3}px;border-bottom:1px solid {D.COLOR_BDR};}}"
    f"QListWidget::item:selected{{background:{D.COLOR_ACC_TINT};color:{D.COLOR_TXT};}}"
    f"QListWidget::item:hover:!selected{{background:{D.COLOR_SURF2};}}"
)


def _sz(n):
    if not n: return "0 B"
    for u in ["B","KB","MB","GB"]:
        if float(n) < 1024: return f"{float(n):.1f} {u}"
        n = float(n) / 1024
    return f"{float(n):.1f} TB"


class DuplicateManagerPage(QWidget):
    """Full-page duplicate file manager."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: list[dict] = []    # list of {checksum, paths, id, resolved}
        self._sel_group: Optional[dict] = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Toolbar
        hdr = QWidget(); hdr.setObjectName("pageHeader"); hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(D.SP_6,0,D.SP_6,0); hl.setSpacing(D.SP_3)
        title = QLabel("Duplicate Files"); title.setObjectName("pageTitle"); hl.addWidget(title)
        self._cnt = QLabel(""); self._cnt.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_SM}pt;background:transparent;border:none;")
        hl.addWidget(self._cnt); hl.addStretch()

        self._show_resolved = QPushButton("Show Resolved")
        self._show_resolved.setObjectName("ghostBtn"); self._show_resolved.setCheckable(True)
        self._show_resolved.setFixedHeight(D.H_BTN_LG)
        self._show_resolved.toggled.connect(lambda _: self.refresh())
        hl.addWidget(self._show_resolved)

        rescan = QPushButton("↻ Re-scan")
        rescan.setObjectName("ghostBtn"); rescan.setFixedHeight(D.H_BTN_LG)
        rescan.clicked.connect(self._rescan); hl.addWidget(rescan)
        root.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep)

        # Stats banner
        self._banner = QLabel("")
        self._banner.setFixedHeight(36)
        self._banner.setStyleSheet(
            f"background:{D.COLOR_WRN_TINT};color:{D.COLOR_WRN};"
            f"font-size:{D.FSIZE_SM}pt;font-weight:700;padding:0 {D.SP_6}px;"
            "border:none;"
        )
        self._banner.hide()
        root.addWidget(self._banner)

        # Splitter: group list | file list + actions
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: groups
        left = QWidget(); left.setStyleSheet(f"background:{D.COLOR_SURF};")
        ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        gl = QLabel("  Duplicate Groups"); gl.setFixedHeight(32)
        gl.setStyleSheet(
            f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_XS}pt;font-weight:700;"
            f"background:{D.COLOR_SURF2};border-bottom:1px solid {D.COLOR_BDR};border:none;"
            f"padding-left:{D.SP_3}px;"
        )
        ll.addWidget(gl)
        self._group_list = QListWidget(); self._group_list.setStyleSheet(_SS_LIST)
        self._group_list.currentRowChanged.connect(self._on_group_select)
        ll.addWidget(self._group_list)
        splitter.addWidget(left)

        # Right: file details + action buttons
        right = QWidget(); right.setStyleSheet(f"background:{D.COLOR_BG};")
        rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)

        # File table
        self._file_tbl = QTableWidget(0, 4)
        self._file_tbl.setHorizontalHeaderLabels(["File","Size","Category","Full Path"])
        self._file_tbl.setStyleSheet(_SS_TABLE)
        self._file_tbl.setAlternatingRowColors(True)
        self._file_tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._file_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._file_tbl.setShowGrid(False)
        self._file_tbl.verticalHeader().setVisible(False)
        self._file_tbl.verticalHeader().setDefaultSectionSize(D.H_ROW)
        hh = self._file_tbl.horizontalHeader()
        for i in range(3): hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._file_tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_tbl.customContextMenuRequested.connect(self._file_ctx)
        rl.addWidget(self._file_tbl, 1)

        # Action bar
        act_w = QWidget(); act_w.setFixedHeight(52)
        act_w.setStyleSheet(
            f"background:{D.COLOR_SURF};border-top:1px solid {D.COLOR_BDR2};")
        al = QHBoxLayout(act_w); al.setContentsMargins(D.SP_4,0,D.SP_4,0); al.setSpacing(D.SP_3)

        keep_btn = QPushButton("✓  Keep Selected, Delete Others")
        keep_btn.setObjectName("accentBtn"); keep_btn.setFixedHeight(D.H_BTN)
        keep_btn.clicked.connect(self._keep_selected)
        al.addWidget(keep_btn)

        del_all = QPushButton("✕  Delete All Duplicates")
        del_all.setStyleSheet(
            f"QPushButton{{background:{D.COLOR_ERR_TINT};border:1px solid {D.COLOR_ERR};"
            f"border-radius:{D.R_MD}px;color:{D.COLOR_ERR};font-size:{D.FSIZE_SM}pt;"
            f"padding:0 {D.SP_3}px;height:{D.H_BTN}px;}}"
            f"QPushButton:hover{{background:{D.COLOR_ERR};color:#fff;}}"
        )
        del_all.setFixedHeight(D.H_BTN)
        del_all.clicked.connect(self._delete_all_in_group)
        al.addWidget(del_all)

        resolve_btn = QPushButton("◈  Mark Resolved")
        resolve_btn.setObjectName("ghostBtn"); resolve_btn.setFixedHeight(D.H_BTN)
        resolve_btn.clicked.connect(self._mark_resolved)
        al.addWidget(resolve_btn); al.addStretch()

        self._action_hint = QLabel("← Select a group to review")
        self._action_hint.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;background:transparent;border:none;")
        al.addWidget(self._action_hint)
        rl.addWidget(act_w)
        splitter.addWidget(right)
        splitter.setSizes([240, 600])
        root.addWidget(splitter, 1)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        try:
            show_res = self._show_resolved.isChecked()
            s = get_session()
            try:
                q = s.query(DuplicateGroup)
                if not show_res:
                    q = q.filter_by(resolved=False)
                groups = q.order_by(DuplicateGroup.created_at.desc()).all()

                self._groups = []
                for g in groups:
                    paths = [p for p in (g.paths or []) if Path(p).exists()]
                    self._groups.append({
                        "id": g.id, "checksum": g.checksum,
                        "paths": paths, "resolved": g.resolved,
                        "all_paths": g.paths or [],
                    })
            finally:
                s.close()

            unres = sum(1 for g in self._groups if not g["resolved"])
            total_waste = 0  # bytes saved if one copy kept per group
            for g in self._groups:
                if len(g["paths"]) > 1:
                    try:
                        sz = Path(g["paths"][0]).stat().st_size
                        total_waste += sz * (len(g["paths"]) - 1)
                    except Exception:
                        pass

            n = len(self._groups)
            self._cnt.setText(f"{n} group{'s' if n!=1 else ''}")
            if unres and total_waste:
                self._banner.setText(
                    f"  ⚠  {unres} unresolved duplicate group{'s' if unres!=1 else ''} "
                    f"— potential space saving: {_sz(total_waste)}")
                self._banner.show()
            else:
                self._banner.hide()

            self._group_list.clear()
            for g in self._groups:
                n_copies = len(g["paths"])
                prefix = "✓ " if g["resolved"] else "⊕ "
                lbl = f"{prefix}  {n_copies} copies  ·  {g['checksum'][:12]}…"
                item = QListWidgetItem(lbl)
                item.setForeground(QColor(D.COLOR_TXT2 if g["resolved"] else D.COLOR_WRN))
                item.setData(Qt.ItemDataRole.UserRole, g)
                self._group_list.addItem(item)

            self._file_tbl.setRowCount(0)
            self._sel_group = None
        except Exception as exc:
            log.error("Duplicate refresh: %s", exc)

    def _on_group_select(self, row: int):
        if row < 0: return
        item = self._group_list.item(row)
        if not item: return
        g = item.data(Qt.ItemDataRole.UserRole)
        self._sel_group = g
        self._action_hint.setText(f"{len(g['paths'])} live copies — select one to keep")
        self._file_tbl.setRowCount(0)
        for path_str in g["paths"]:
            p = Path(path_str)
            r = self._file_tbl.rowCount(); self._file_tbl.insertRow(r)
            exists = p.exists()
            try:
                sz = p.stat().st_size if exists else 0
            except Exception:
                sz = 0
            for col, val in enumerate([
                p.name, _sz(sz), "", path_str
            ]):
                cell = QTableWidgetItem(val or "")
                cell.setData(Qt.ItemDataRole.UserRole, path_str)
                if not exists:
                    cell.setForeground(QColor(D.COLOR_TXT_DIS))
                self._file_tbl.setItem(r, col, cell)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _keep_selected(self):
        if not self._sel_group: return
        row = self._file_tbl.currentRow()
        if row < 0:
            QMessageBox.information(self,"Select File","Select the file to KEEP in the table above.")
            return
        keep_path = self._file_tbl.item(row, 3).data(Qt.ItemDataRole.UserRole)
        to_delete = [p for p in self._sel_group["paths"] if p != keep_path]
        if not to_delete: return
        if QMessageBox.question(
            self, "Delete Duplicates",
            f"Keep:\n  {keep_path}\n\nDelete {len(to_delete)} duplicate(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._delete_paths(to_delete)
        self._mark_resolved()

    def _delete_all_in_group(self):
        if not self._sel_group: return
        paths = self._sel_group["paths"]
        if QMessageBox.question(
            self, "Delete ALL",
            f"Delete ALL {len(paths)} copies?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._delete_paths(paths)
        self._mark_resolved()

    def _delete_paths(self, paths: list[str]):
        s = get_session()
        errors = []
        try:
            for path_str in paths:
                try:
                    Path(path_str).unlink(missing_ok=True)
                    tf = s.query(TrackedFile).filter_by(path=path_str).first()
                    if tf:
                        tf.is_deleted = True
                        s.commit()
                except Exception as exc:
                    errors.append(f"{path_str}: {exc}")
        finally:
            s.close()
        if errors:
            QMessageBox.warning(self, "Some deletions failed", "\n".join(errors))

    def _mark_resolved(self):
        if not self._sel_group: return
        s = get_session()
        try:
            g = s.query(DuplicateGroup).filter_by(id=self._sel_group["id"]).first()
            if g: g.resolved = True; s.commit()
        finally:
            s.close()
        self.refresh()

    def _rescan(self):
        """Re-hash all tracked files and rebuild duplicate groups."""
        try:
            from core.classifier import compute_checksum
            s = get_session()
            try:
                from collections import defaultdict
                by_hash: dict[str, list[str]] = defaultdict(list)
                files = s.query(TrackedFile).filter_by(is_deleted=False).all()
                for tf in files:
                    if tf.checksum:
                        by_hash[tf.checksum].append(tf.path)
                added = 0
                for cksum, paths in by_hash.items():
                    if len(paths) < 2: continue
                    existing = s.query(DuplicateGroup).filter_by(checksum=cksum).first()
                    if existing:
                        existing.paths = paths
                    else:
                        s.add(DuplicateGroup(checksum=cksum, paths=paths))
                        added += 1
                s.commit()
                self.refresh()
                if added:
                    win = self.window()
                    if hasattr(win, "_notify"):
                        win._notify("info", f"Found {added} new duplicate group(s)")
            finally:
                s.close()
        except Exception as exc:
            log.error("Rescan: %s", exc)

    def _file_ctx(self, pos):
        item = self._file_tbl.itemAt(pos)
        if not item: return
        path_str = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        oa = menu.addAction("📂  Open in Explorer")
        ca = menu.addAction("⎘  Copy Path")
        da = menu.addAction("🗑  Delete This File")
        act = menu.exec(self._file_tbl.viewport().mapToGlobal(pos))
        if act == oa:
            import subprocess; subprocess.Popen(f'explorer /select,"{path_str}"')
        elif act == ca:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(path_str)
        elif act == da:
            self._delete_paths([path_str]); self._on_group_select(self._group_list.currentRow())


# Needed for type hint in _build
from typing import Optional