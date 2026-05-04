# forix/ui/pages/projects.py
"""
Forix — Projects Page (redesigned)
Responsive card grid, stats bar, sort/filter toolbar,
custom-painted cards with health rings and type-colour accents.
"""
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QMenu, QGridLayout,
    QComboBox, QFileDialog, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.database import get_session, Project
from core.project_manager import create_project, create_version_snapshot
import design as D
from ui.widgets.project_card import ProjectCard

log = logging.getLogger("forix.ui.projects")

_SS_SEARCH = (
    f"QLineEdit{{background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
    f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
    f"padding:0 {D.SP_3}px;}}"
    f"QLineEdit:focus{{border-color:{D.COLOR_ACC};}}"
)
_SS_COMBO = (
    f"QComboBox{{background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
    f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
    f"padding:0 {D.SP_3}px;}}"
    f"QComboBox:hover{{border-color:{D.COLOR_ACC};}}"
    f"QComboBox::drop-down{{border:none;width:20px;}}"
    f"QComboBox QAbstractItemView{{background:{D.COLOR_SURF2};"
    f"border:1px solid {D.COLOR_BDR2};border-radius:{D.R_MD}px;"
    f"color:{D.COLOR_TXT};selection-background-color:{D.COLOR_ACC_TINT};"
    f"selection-color:{D.COLOR_ACC};outline:none;}}"
)


class _StatsBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(
            f"background:{D.COLOR_SURF};border-bottom:1px solid {D.COLOR_BDR};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(D.SP_6, 0, D.SP_6, 0)
        lay.setSpacing(D.SP_6)
        self._vals = {}
        for key, icon, label in [
            ("total",    "◉", "Total"),
            ("active",   "●", "Active"),
            ("stale",    "○", "Stale"),
            ("archived", "◌", "Archived"),
            ("health",   "♥", "Avg Health"),
        ]:
            tile = QWidget()
            tile.setStyleSheet("background:transparent;border:none;")
            tl = QHBoxLayout(tile)
            tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(D.SP_1)
            ic = QLabel(icon)
            ic.setStyleSheet("background:transparent;border:none;font-size:11px;")
            val = QLabel("—")
            val.setStyleSheet(
                f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_SM}pt;"
                "font-weight:700;background:transparent;border:none;")
            desc = QLabel(label)
            desc.setStyleSheet(
                f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                "background:transparent;border:none;")
            tl.addWidget(ic); tl.addWidget(val); tl.addWidget(desc)
            self._vals[key] = (val, ic)
            lay.addWidget(tile)
        lay.addStretch()

    def update_stats(self, projects: list[dict]):
        total    = len(projects)
        active   = sum(1 for p in projects if p.get("status") == "active")
        stale    = sum(1 for p in projects if p.get("status") in ("stale","on-hold"))
        archived = sum(1 for p in projects if p.get("status") == "archived")
        avg_h    = int(sum(p.get("health", 0) for p in projects) / total) if total else 0

        data = [("total",total,""), ("active",active,D.COLOR_OK),
                ("stale",stale,D.COLOR_WRN), ("archived",archived,D.COLOR_TXT2),
                ("health",f"{avg_h}%",D.COLOR_ACC)]
        for key, val, col in data:
            lbl, ic = self._vals[key]
            lbl.setText(str(val))
            if col:
                lbl.setStyleSheet(
                    f"color:{col};font-size:{D.FSIZE_SM}pt;font-weight:700;"
                    "background:transparent;border:none;")
                ic.setStyleSheet(f"color:{col};background:transparent;border:none;font-size:11px;")


class ProjectsPage(QWidget):
    project_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all = []
        self._last_cols = -1
        self._cached: list[dict] = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────
        hdr = QWidget(); hdr.setObjectName("pageHeader"); hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(D.SP_6, 0, D.SP_6, 0); hl.setSpacing(D.SP_3)

        title = QLabel("Projects"); title.setObjectName("pageTitle")
        hl.addWidget(title)

        self._cnt = QLabel("")
        self._cnt.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_SM}pt;"
            "background:transparent;border:none;")
        hl.addWidget(self._cnt); hl.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search projects…")
        self._search.setFixedSize(200, D.H_BTN_LG)
        self._search.setStyleSheet(_SS_SEARCH)
        self._search.textChanged.connect(self._filter)
        hl.addWidget(self._search)

        self._type_cb = QComboBox(); self._type_cb.setFixedSize(130, D.H_BTN_LG)
        self._type_cb.setStyleSheet(_SS_COMBO)
        self._type_cb.addItems(["All Types","python","arduino","kicad","node",
                                  "web","cad","embedded","document","data","generic"])
        self._type_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self._type_cb)

        self._stat_cb = QComboBox(); self._stat_cb.setFixedSize(130, D.H_BTN_LG)
        self._stat_cb.setStyleSheet(_SS_COMBO)
        self._stat_cb.addItems(["All Status","active","planning","on-hold","stale","archived"])
        self._stat_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self._stat_cb)

        self._sort_cb = QComboBox(); self._sort_cb.setFixedSize(145, D.H_BTN_LG)
        self._sort_cb.setStyleSheet(_SS_COMBO)
        self._sort_cb.addItems(["Last Active","Name A–Z","Health ↓","File Count ↓"])
        self._sort_cb.currentTextChanged.connect(self._filter)
        hl.addWidget(self._sort_cb)

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine); div.setFixedWidth(1)
        div.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); hl.addWidget(div)

        imp = QPushButton("↑ Import"); imp.setObjectName("ghostBtn")
        imp.setFixedHeight(D.H_BTN_LG); imp.clicked.connect(self._import)
        hl.addWidget(imp)

        new = QPushButton("＋ New Project"); new.setObjectName("accentBtn")
        new.setFixedHeight(D.H_BTN_LG); new.clicked.connect(self._new)
        hl.addWidget(new)
        root.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep)

        # Stats bar
        self._stats = _StatsBar(); root.addWidget(self._stats)

        # ── Scroll area + card grid ────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{D.COLOR_BG};border:none;}}"
            f"QScrollBar:vertical{{background:{D.COLOR_BG};width:6px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{D.COLOR_SURF3};"
            f"border-radius:3px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        self._grid_w = QWidget(); self._grid_w.setStyleSheet(f"background:{D.COLOR_BG};")
        self._grid = QGridLayout(self._grid_w)
        self._grid.setSpacing(D.SP_4)
        self._grid.setContentsMargins(D.SP_6, D.SP_5, D.SP_6, D.SP_8)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_w)
        root.addWidget(self._scroll)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        try:
            s = get_session()
            try:
                self._all = [p.to_dict() for p in
                             s.query(Project).filter(Project.is_deleted.is_(False)).all()]
            finally:
                s.close()
            self._filter()
        except Exception as e:
            log.error("Projects refresh: %s", e)

    def _filter(self):
        try:
            q  = self._search.text().lower().strip()
            ty = self._type_cb.currentText()
            st = self._stat_cb.currentText()
            so = self._sort_cb.currentText()
            f  = [
                p for p in self._all
                if (not q or q in p["name"].lower()
                    or q in (p.get("description") or "").lower()
                    or q in (p.get("category") or "").lower())
                and (ty == "All Types"   or p["type"]   == ty)
                and (st == "All Status"  or p["status"] == st)
            ]
            if   so == "Name A–Z":     f.sort(key=lambda x: x["name"].lower())
            elif so == "Health ↓":     f.sort(key=lambda x: x.get("health",0), reverse=True)
            elif so == "File Count ↓": f.sort(key=lambda x: x.get("file_count",0), reverse=True)
            else:                       f.sort(key=lambda x: x.get("last_activity","") or "", reverse=True)

            n = len(f)
            self._cnt.setText(f"{n} project{'s' if n!=1 else ''}")
            self._stats.update_stats(f)
            self._cached = f
            self._render(f)
        except Exception as e:
            log.error("Filter: %s", e)

    def _render(self, projects: list[dict]):
        try:
            while self._grid.count():
                item = self._grid.takeAt(0)
                if item.widget(): item.widget().deleteLater()

            if not projects:
                lbl = QLabel("No projects found.\n\nCreate a new project or import a folder.")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_BASE}pt;"
                    "padding:80px;background:transparent;border:none;")
                self._grid.addWidget(lbl, 0, 0, 1, 4)
                return

            # Responsive columns based on available width
            vw    = self._scroll.viewport().width()
            avail = (vw if vw > 100 else self.width()) - D.SP_6*2
            card_w = ProjectCard._W + D.SP_4
            cols  = max(1, avail // card_w)
            self._last_cols = cols

            for idx, pd in enumerate(projects):
                row, col = divmod(idx, cols)
                card = ProjectCard(pd)
                card.clicked.connect(lambda pid=pd["id"]: self.project_selected.emit(pid))
                card.customContextMenuRequested.connect(
                    lambda pos, c=card, pid=pd["id"],
                           pt=pd.get("type","generic"),
                           pp=pd.get("path",""): self._ctx(c,pid,pos,pt,pp)
                )
                self._grid.addWidget(card, row, col)

            self._grid.setColumnStretch(cols, 1)

        except Exception as e:
            log.error("Render: %s", e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        vw    = self._scroll.viewport().width()
        avail = (vw if vw > 100 else self.width()) - D.SP_6*2
        new_cols = max(1, avail // (ProjectCard._W + D.SP_4))
        if new_cols != self._last_cols:
            self._last_cols = new_cols
            self._render(self._cached)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new(self):
        try:
            from ui.dialogs.new_project_dialog import NewProjectDialog
            dlg = NewProjectDialog(self)
            if dlg.exec():
                data = dlg.get_data()
                s = get_session()
                try:
                    p = create_project(data["name"], auto_created=False, session=s)
                    if p:
                        p.description  = data.get("description","")
                        p.project_type = data.get("project_type","generic")
                        p.category     = data.get("category","General")
                        p.status       = data.get("status","active")
                        tags = list(data.get("tags",[]))
                        if data.get("priority","Normal") != "Normal":
                            tags.append(f"priority:{data['priority'].lower()}")
                        if data.get("client"):
                            tags.append(f"client:{data['client']}")
                        p.tags = tags; s.commit()
                        self.refresh(); self.project_selected.emit(p.id)
                finally:
                    s.close()
        except Exception as e:
            log.error("New: %s", e)

    def _import(self):
        try:
            folder = QFileDialog.getExistingDirectory(self,"Select Folder")
            if not folder: return
            from pathlib import Path
            from ui.dialogs.new_project_dialog import NewProjectDialog
            from core.classifier import infer_project_name, detect_project_type
            fp = Path(folder)
            dlg = NewProjectDialog(self, prefill_name=infer_project_name(fp),
                                   prefill_type=detect_project_type(fp))
            if dlg.exec():
                data = dlg.get_data()
                s = get_session()
                try:
                    p = create_project(data["name"], source_path=fp, auto_created=False, session=s)
                    if p:
                        p.description  = data.get("description","")
                        p.project_type = data.get("project_type","generic")
                        p.category     = data.get("category","General")
                        p.status       = data.get("status","active")
                        p.tags         = data.get("tags",[]); s.commit()
                        self.refresh()
                finally:
                    s.close()
        except Exception as e:
            log.error("Import: %s", e)

    def _ctx(self, card, pid, pos, ptype, ppath):
        try:
            from services.launcher import get_available_tools_for_project, TOOLS
            from pathlib import Path
            import subprocess

            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};"
                f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;padding:4px;}}"
                f"QMenu::item{{padding:6px 20px;border-radius:{D.R_SM}px;}}"
                f"QMenu::item:selected{{background:{D.COLOR_ACC_TINT};color:{D.COLOR_ACC};}}"
                f"QMenu::separator{{background:{D.COLOR_BDR2};height:1px;margin:4px 8px;}}"
            )
            open_a   = menu.addAction("◈  Open Project")
            menu.addSeparator()
            ide_m    = menu.addMenu("▶  Open in Tool")
            avail    = get_available_tools_for_project(ptype)
            if avail:
                for k, t in avail:
                    a = ide_m.addAction(t.name); a.setData((k, ppath))
            else:
                ide_m.addAction("No tools detected").setEnabled(False)
            folder_a = menu.addAction("📂  Open in Explorer")
            snap_a   = menu.addAction("📸  Create Snapshot")
            menu.addSeparator()
            arch_a   = menu.addAction("Archive")
            del_a    = menu.addAction("Remove from Forix")

            act = menu.exec(card.mapToGlobal(pos))
            if not act: return

            if act == open_a:
                self.project_selected.emit(pid)
            elif act.parent() == ide_m:
                d = act.data()
                if d:
                    k, pp = d
                    t = TOOLS.get(k)
                    if t: t.launch(Path(pp))
            elif act == folder_a:
                import subprocess; subprocess.Popen(f'explorer "{ppath}"')
            elif act == snap_a:
                s = get_session()
                try:
                    p = s.query(Project).filter_by(id=pid).first()
                    if p:
                        v = create_version_snapshot(p, s)
                        if v: QMessageBox.information(self,"Snapshot",f"Created {v.label}")
                finally: s.close()
            elif act == arch_a:
                s = get_session()
                try:
                    p = s.query(Project).filter_by(id=pid).first()
                    if p: p.status = "archived"; s.commit(); self.refresh()
                finally: s.close()
            elif act == del_a:
                if QMessageBox.question(
                    self,"Remove","Remove from Forix? Files stay on disk.",
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes:
                    s = get_session()
                    try:
                        p = s.query(Project).filter_by(id=pid).first()
                        if p: s.delete(p); s.commit(); self.refresh()
                    finally: s.close()
        except Exception as e:
            log.error("Ctx: %s", e)