# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolManager.py - symbol library browser and pin/property editor.
#
###############################################################################
"""Symbol manager in the spirit of KiCad's Symbol Library Table + Editor.

* :class:`SymbolManager` - browse the store with search, preview and pin
  list; create, duplicate, import, delete, open the folder, refresh.
* Drawing/pin/metadata editing lives in
  :mod:`Schematics.Features.Dialogs.SymbolEditor` - a built-in canvas
  with line/rect/circle/polyline/text tools, pin placement, snap grid
  and undo/redo.

Artwork from external SVG tools (Inkscape etc.) is preserved: the editor
renders unmodelled content (``<path>``/``<g>``) as a backdrop and saving
re-serialises only what it owns - drawing shapes, the
``<rect schematics:pin=.../>`` lines and the root ``<svg>`` tag
attributes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from PySide6 import QtCore, QtWidgets

from Schematics.Features.Dialogs.SymbolChooser import SymbolPreview
from Schematics.Features.Utils.SymbolCatalog import (
    SymbolCatalog,
    SymbolEntry,
    SymbolPin,
)
from Schematics.Features.Dialogs.SymbolEditor import SymbolEditor
from Schematics.Features.Dialogs.ImportDialog import ImportDialog
from Schematics.Features.Utils.SVGSymbolsCache import invalidate
from Schematics.Features.Utils.SymbolDrawing import (
    createNewSymbol,
    readSymbol,
    validatePins,
    writeSymbol,
)

class SymbolManager(QtWidgets.QDialog):
    """Browse the symbol store; duplicate, import, delete, edit pins."""

    def __init__(
        self,
        catalog: SymbolCatalog | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Symbol manager")
        self.setModal(True)
        self.catalog = catalog if catalog is not None else SymbolCatalog()
        self._rows: list[SymbolEntry] = []

        self.filter = QtWidgets.QLineEdit(self)
        self.filter.setPlaceholderText("Filter symbols…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._applyFilter)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Symbol", "Group", "Pins"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.itemSelectionChanged.connect(self._showSelection)
        self.table.itemDoubleClicked.connect(
            lambda _item: self._editSelected()
        )

        self.preview = SymbolPreview(self)
        self.description = QtWidgets.QLabel(self)
        self.description.setWordWrap(True)
        self.description.setTextFormat(QtCore.Qt.TextFormat.PlainText)

        self.editBtn = QtWidgets.QPushButton("Edit…", self)
        self.editBtn.clicked.connect(self._editSelected)
        self.newBtn = QtWidgets.QPushButton("New symbol…", self)
        self.newBtn.clicked.connect(self._newSymbol)
        self.dupBtn = QtWidgets.QPushButton("Duplicate", self)
        self.dupBtn.clicked.connect(self._duplicate)
        self.importBtn = QtWidgets.QPushButton("Import…", self)
        self.importBtn.clicked.connect(self._importFolder)
        self.deleteBtn = QtWidgets.QPushButton("Delete…", self)
        self.deleteBtn.clicked.connect(self._delete)
        folderBtn = QtWidgets.QPushButton("Open folder", self)
        folderBtn.clicked.connect(self._openFolder)
        refreshBtn = QtWidgets.QPushButton("Refresh", self)
        refreshBtn.clicked.connect(self._refresh)

        # Import never depends on a selection; the rest follow it.
        for button in (self.editBtn, self.dupBtn, self.deleteBtn):
            button.setEnabled(False)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.filter, 1)
        left = QtWidgets.QVBoxLayout()
        left.addLayout(top)
        left.addWidget(self.table, 1)
        actions = QtWidgets.QHBoxLayout()
        for button in (self.newBtn, self.editBtn, self.dupBtn,
                       self.importBtn, self.deleteBtn):
            actions.addWidget(button)
        left.addLayout(actions)
        leftWidget = QtWidgets.QWidget(self)
        leftWidget.setLayout(left)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self.preview, 1)
        right.addWidget(self.description)
        right.addWidget(folderBtn)
        right.addWidget(refreshBtn)
        rightWidget = QtWidgets.QWidget(self)
        rightWidget.setLayout(right)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close, self
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        outer = QtWidgets.QVBoxLayout(self)
        splitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal, self
        )
        splitter.addWidget(leftWidget)
        splitter.addWidget(rightWidget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)
        outer.addWidget(buttons)

        self._populate()
        self.resize(820, 540)

    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self.catalog.refresh()
        entries = self.catalog.all()
        self._rows = list(entries)
        self.table.blockSignals(True)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            pins = self.catalog.pins(entry)
            nameItem = QtWidgets.QTableWidgetItem(entry.name)
            nameItem.setData(QtCore.Qt.ItemDataRole.UserRole, entry.key)
            self.table.setItem(row, 0, nameItem)
            self.table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(entry.group or "(root)")
            )
            self.table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(str(len(pins)))
            )
        self.table.blockSignals(False)
        self._applyFilter(self.filter.text())
        if self._rows:
            self.table.selectRow(0)

    def _selected(self) -> SymbolEntry | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _applyFilter(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.table.rowCount()):
            entry = self._rows[row]
            hay = "%s %s" % (entry.name, entry.group)
            self.table.setRowHidden(row, bool(needle) and needle not in hay.lower())

    def _showSelection(self) -> None:
        entry = self._selected()
        has = entry is not None
        self.editBtn.setEnabled(has)
        self.dupBtn.setEnabled(has)
        self.deleteBtn.setEnabled(has)
        if entry is None:
            self.preview.setSymbol(self.catalog, None)
            self.description.setText("")
            return
        self.preview.setSymbol(self.catalog, entry)
        meta = self.catalog.meta(entry)
        parts: list[str] = []
        if meta.ref:
            parts.append("ref %s" % meta.ref)
        if meta.description:
            parts.append(meta.description)
        parts.append("%s%s" % (entry.group + "/" if entry.group else "", entry.name))
        parts.append("%d pins" % len(self.catalog.pins(entry)))
        self.description.setText("  ·  ".join(parts))

    # ------------------------------------------------------------------
    def _editSelected(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        desc, ref, pins = readSymbol(entry.path)
        editor = SymbolEditor(
            path=entry.path,
            pins=pins,
            description=desc,
            ref=ref,
            cacheKey=entry.key,
            parent=self,
        )
        if editor.exec():
            self._refresh(keepSelection=entry.key)

    def _newSymbol(self) -> None:
        """Create a blank symbol in a chosen group, then open the editor."""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "New symbol", "Name (file stem):"
        )
        if not ok or not name.strip():
            return
        groups = list(self.catalog.groups())
        labels = [g if g else "(root)" for g in groups]
        label, ok = QtWidgets.QInputDialog.getItem(
            self, "New symbol", "Group:", labels, 0, False
        )
        if not ok:
            return
        group = groups[labels.index(label)] if label in labels else ""
        try:
            path = createNewSymbol(self.catalog.root, group, name.strip())
        except (OSError, ValueError, FileExistsError) as exc:
            QtWidgets.QMessageBox.warning(
                self, "New symbol", "Could not create symbol: %s" % exc
            )
            return
        self._refresh()
        self._selectByName(os.path.splitext(os.path.basename(path))[0])
        self._editSelected()

    def _duplicate(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        stem = os.path.splitext(entry.path)[0]
        target = stem + "Copy"
        suffix = 2
        while os.path.exists(target + ".svg"):
            target = "%sCopy%d" % (stem, suffix)
            suffix += 1
        try:
            shutil.copy2(entry.path, target + ".svg")
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Symbol manager", "Duplicate failed: %s" % exc
            )
            return
        self._refresh(keepSelection=None)
        self._selectByName(os.path.basename(target))

    def _importFolder(self) -> None:
        """Pick a folder; the dialog finds .svg and .elmt symbols in it."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Folder with symbols to import", ImportDialog.lastFolder
        )
        if not folder:
            return
        dialog = ImportDialog(
            folder,
            self.catalog,
            parent=self,
            onImported=lambda: self._refresh(),
        )
        dialog.exec()
        self._refresh()

    def _delete(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete symbol",
            "Delete '%s'?\n\nExisting documents that use this symbol will "
            "render it as missing until it is restored." % entry.name,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(entry.path)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Symbol manager", "Delete failed: %s" % exc
            )
            return
        invalidate(entry.key)
        self._refresh()

    def _openFolder(self) -> None:
        entry = self._selected()
        folder = os.path.dirname(entry.path) if entry else self.catalog.root
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Symbol manager", "Could not open %s: %s" % (folder, exc)
            )

    def _refresh(self, keepSelection: str | None = None) -> None:
        self._populate()
        if keepSelection is not None:
            self._selectByKey(keepSelection)

    def _selectByName(self, name: str) -> None:
        for row, entry in enumerate(self._rows):
            if entry.name == name:
                self.table.selectRow(row)
                return

    def _selectByKey(self, key: str) -> None:
        for row, entry in enumerate(self._rows):
            if entry.key == key:
                self.table.selectRow(row)
                return
