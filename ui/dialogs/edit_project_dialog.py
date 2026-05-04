# forix/ui/dialogs/edit_project_dialog.py
"""
Forix — Edit Project Dialog
Pre-fills all fields from an existing Project object.
"""

from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QDate

from ui.dialogs.new_project_dialog import NewProjectDialog
from core.database import Project


class EditProjectDialog(NewProjectDialog):
    def __init__(self, project: Project, parent=None):
        super().__init__(
            parent=parent,
            prefill_name=project.name,
            prefill_type=project.project_type or "generic",
        )
        self.setWindowTitle(f"Edit Project — {project.name}")
        self._prefill_from_project(project)

    def _prefill_from_project(self, p: Project):
        # Description
        if p.description:
            self._desc.setPlainText(p.description)

        # Category
        idx = self._cat_cb.findText(p.category or "General")
        if idx >= 0:
            self._cat_cb.setCurrentIndex(idx)

        # Status
        idx = self._status_cb.findText(p.status or "active")
        if idx >= 0:
            self._status_cb.setCurrentIndex(idx)

        # Tags
        if p.tags:
            self._tags.set_tags(p.tags)

        # Extra metadata stored in tags/description as JSON is not yet implemented —
        # additional fields like priority, client etc. will be blank on edit
        # (future: store in a metadata JSON column)
