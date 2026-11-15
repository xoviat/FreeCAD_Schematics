# -*- coding: utf-8 -*-
###############################################################################
#
#  QETImportDialog.py - batch import of QElectroTech element files.
#
###############################################################################
"""Import a folder of QElectroTech ``.elmt`` files into the symbol store.

Opened from the symbol manager's "Import QET…" button: pick a folder
(a``qelectrotech-elements`` checkout or an installed QET's ``elements/``
tree), filter the discovery list, tick what to take, choose the target
group and convert.  Existing names are skipped so re-running an import
is harmless.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from Schematics.Features.Utils.QETImport import (
    QETElementInfo,
    QETImportReport,
    importQETFiles,
    scanQETElements,
)
from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog

_NEW_GROUP = "(new group…)"
_INVALID_NAME_CHARS = set('\\/:*?"<>|')


class QETImportDialog(QtWidgets.QDialog):
    """Discovery list + target group + batch conversion."""

    def __init__(
        self,
        catalog: SymbolCatalog,
        parent: QtWidgets.QWidget | None = None,
        onImported: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import QElectroTech elements")
        self.setModal(True)
        self.catalog = catalog
        self.onImported = onImported
        self._folder = ""
        self._infos: list[QETElementInfo] = []
        self._checked: set[str] = set()
        self._groups: list[str] = []
        self._labels: list[str] = []

        self.folderEdit = QtWidgets.QLineEdit(self)
        self.folderEdit.setReadOnly(True)
        self.folderEdit.setPlaceholderText("Choose a folder of .elmt files…")
        browseBtn = QtWidgets.QPushButton("Browse…", self)
        browseBtn.clicked.connect(self._browse)

        self.filter = QtWidgets.QLineEdit(self)
        self.filter.setPlaceholderText("Filter by name or category…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _text: self._populate())

        self.groupCombo = QtWidgets.QComboBox(self)
        self._refreshGroups()

        self.table = QtWidgets.QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["", "Symbol", "Category"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.itemChanged.connect(self._onItemChanged)

        self.status = QtWidgets.QLabel("No folder chosen yet.", self)

        allBtn = QtWidgets.QPushButton("Select all visible", self)
        allBtn.clicked.connect(lambda: self._selectVisible(True))
        noneBtn = QtWidgets.QPushButton("Select none", self)
        noneBtn.clicked.connect(lambda: self._selectVisible(False))
        importBtn = QtWidgets.QPushButton("Import…", self)
        importBtn.clicked.connect(self._import)
        closeBtn = QtWidgets.QPushButton("Close", self)
        closeBtn.clicked.connect(self.reject)

        folderRow = QtWidgets.QHBoxLayout()
        folderRow.addWidget(QtWidgets.QLabel("Folder:", self))
        folderRow.addWidget(self.folderEdit, 1)
        folderRow.addWidget(browseBtn)
        filterRow = QtWidgets.QHBoxLayout()
        filterRow.addWidget(self.filter, 1)
        filterRow.addWidget(QtWidgets.QLabel("Target group:", self))
        filterRow.addWidget(self.groupCombo)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(allBtn)
        buttons.addWidget(noneBtn)
        buttons.addStretch(1)
        buttons.addWidget(importBtn)
        buttons.addWidget(closeBtn)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addLayout(folderRow)
        outer.addLayout(filterRow)
        outer.addWidget(self.table, 1)
        outer.addWidget(self.status)
        outer.addLayout(buttons)
        self.resize(780, 520)

    # ------------------------------------------------------------------
    def _refreshGroups(self) -> None:
        self._groups = list(self.catalog.groups())
        self._labels = [g if g else "(root)" for g in self._groups]
        current = self.groupCombo.currentText()
        self.groupCombo.clear()
        self.groupCombo.addItems(self._labels)
        self.groupCombo.addItem(_NEW_GROUP)
        index = self.groupCombo.findText(current)
        if index >= 0:
            self.groupCombo.setCurrentIndex(index)

    def _browse(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Folder of QElectroTech elements", self._folder
        )
        if not folder:
            return
        self._folder = folder
        self.folderEdit.setText(folder)
        self._scan()

    def _scan(self) -> None:
        self._checked.clear()
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor
        )
        try:
            self._infos = scanQETElements(self._folder)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._populate()
        if not self._infos:
            QtWidgets.QMessageBox.information(
                self,
                "Import QElectroTech elements",
                "No .elmt files found under:\n%s" % self._folder,
            )

    # ------------------------------------------------------------------
    def _visible(self) -> list[QETElementInfo]:
        needle = self.filter.text().strip().lower()
        if not needle:
            return list(self._infos)
        return [
            info
            for info in self._infos
            if needle in info.name.lower() or needle in info.category.lower()
        ]

    def _populate(self) -> None:
        rows = self._visible()
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for row, info in enumerate(rows):
            check = QtWidgets.QTableWidgetItem()
            check.setFlags(
                QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            check.setCheckState(
                QtCore.Qt.CheckState.Checked
                if info.path in self._checked
                else QtCore.Qt.CheckState.Unchecked
            )
            check.setData(QtCore.Qt.ItemDataRole.UserRole, info.path)
            self.table.setItem(row, 0, check)
            nameItem = QtWidgets.QTableWidgetItem(info.name)
            nameItem.setToolTip(info.path)
            self.table.setItem(row, 1, nameItem)
            self.table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(info.category or "(root)")
            )
        self.table.blockSignals(False)
        self._updateStatus()

    def _onItemChanged(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            self._checked.add(path)
        else:
            self._checked.discard(path)
        self._updateStatus()

    def _selectVisible(self, checked: bool) -> None:
        for info in self._visible():
            if checked:
                self._checked.add(info.path)
            else:
                self._checked.discard(info.path)
        self._populate()

    def _updateStatus(self) -> None:
        if not self._folder:
            text = "No folder chosen yet."
        else:
            text = "%d elements found · %d selected" % (
                len(self._infos),
                len(self._checked),
            )
        self.status.setText(text)

    # ------------------------------------------------------------------
    def _targetGroup(self) -> str | None:
        """Group name for this run, or None when the prompt was cancelled."""
        label = self.groupCombo.currentText()
        if label == _NEW_GROUP:
            name, ok = QtWidgets.QInputDialog.getText(
                self, "New group", "Group name:"
            )
            if not ok:
                return None
            name = name.strip()
            if not name or any(c in name for c in _INVALID_NAME_CHARS):
                QtWidgets.QMessageBox.warning(
                    self,
                    "New group",
                    "Invalid group name: %r" % name,
                )
                return None
            return name
        if label in self._labels:
            return self._groups[self._labels.index(label)]
        return ""

    def _import(self) -> None:
        paths = sorted(self._checked)
        if not paths:
            QtWidgets.QMessageBox.information(
                self,
                "Import QElectroTech elements",
                "Select at least one element to import.",
            )
            return
        group = self._targetGroup()
        if group is None:
            return
        dest = (
            os.path.join(self.catalog.root, group) if group else self.catalog.root
        )
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor
        )
        try:
            report = importQETFiles(paths, dest)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        handled = set(report.imported) | set(report.skipped)
        failed_paths = {path for path, _reason in report.failed}
        self._checked = {
            path
            for path in self._checked
            if path in failed_paths and path not in handled
        }
        self._populate()
        self._refreshGroups()
        if report.imported and self.onImported is not None:
            self.onImported()
        self._showReport(report, group)

    def _showReport(self, report: QETImportReport, group: str) -> None:
        lines = [
            "Imported %d symbol(s) into %s."
            % (len(report.imported), group or "(root)")
        ]
        if report.skipped:
            lines.append(
                "Skipped %d already present: %s"
                % (len(report.skipped), ", ".join(sorted(report.skipped)))
            )
        if report.failed:
            lines.append("Failed %d:" % len(report.failed))
            for path, reason in report.failed:
                lines.append(
                    "  - %s: %s" % (os.path.basename(path), reason)
                )
        if report.notes:
            lines.append("Notes: " + "; ".join(report.notes))
        boxes = (
            QtWidgets.QMessageBox.warning
            if report.failed
            else QtWidgets.QMessageBox.information
        )
        boxes(
            self,
            "Import QElectroTech elements",
            "\n".join(lines),
        )
