# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolManager.py - symbol library browser and pin/property editor.
#
###############################################################################
"""Symbol manager in the spirit of KiCad's Symbol Library Table + Editor.

* :class:`SymbolManager` - browse the store with search, preview and pin
  list; duplicate, import, delete, open the folder, refresh.
* :class:`PinEditor` - edit a symbol's connection pins (name, x, y; click
  the preview to place the selected pin) and its root-tag metadata
  (``schematics:description``, ``schematics:ref``).

Graphics editing stays in external SVG tools (Inkscape etc.): this editor
owns the data that matters for schematics - connectivity pins and fields.
Saving rewrites only the ``<rect schematics:pin=.../>`` lines and the
root ``<svg>`` tag attributes; every drawing element is left untouched.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from Schematics.Features.Dialogs.SymbolChooser import SymbolPreview
from Schematics.Features.Utils.SymbolCatalog import (
    SymbolCatalog,
    SymbolEntry,
    SymbolPin,
)
from Schematics.Features.Utils.SVGSymbolsCache import extractPins, invalidate

# Same line-bound patterns the loader uses (extractPins' regex cannot
# span newlines, so pin rects must live one per line).
_PIN_RECT_RE = re.compile(r'< *rect .*pin="[^"]*".*(?:/>|</rect>)')
_ROOT_TAG_RE = re.compile(r"<svg[^>]*>")
# extractPins only understands this charset for pin names.
_PIN_NAME_RE = re.compile(r"^[A-Za-z0-9.]+$")


def _fmt(value: float) -> str:
    return "%g" % value


def _setRootAttr(tag: str, name: str, value: str) -> str:
    """Set (or add) an attribute on an <svg ...> tag string."""
    escaped = value.replace('"', "'")
    pattern = re.compile(re.escape(name) + r'="[^"]*"')
    if pattern.search(tag):
        return pattern.sub(lambda _m: '%s="%s"' % (name, escaped), tag)
    return tag[:-1] + ' %s="%s"' % (name, escaped) + ">"


def writeSymbol(
    path: str,
    pins: list[SymbolPin],
    description: str | None = None,
    ref: str | None = None,
) -> None:
    """Rewrite a symbol file: replace all pin rects and (optionally) the
    root-tag metadata, leaving the drawing content byte-identical."""
    with open(path, "r", encoding="utf-8") as handle:
        data = handle.read()
    if not _ROOT_TAG_RE.search(data) or "</svg>" not in data:
        raise ValueError("not a symbol file (no <svg>/</svg>): " + path)
    data = _PIN_RECT_RE.sub("", data)
    pin_xml = "".join(
        '<rect schematics:pin="%s" x="%s" y="%s"/>\n'
        % (pin.name, _fmt(pin.x), _fmt(pin.y))
        for pin in pins
    )
    idx = data.rfind("</svg>")
    head = data[:idx]
    if pin_xml and head and not head.endswith("\n"):
        head += "\n"
    data = head + pin_xml + data[idx:]
    if description is not None or ref is not None:
        match = _ROOT_TAG_RE.search(data)
        if match is not None:
            tag = match.group(0)
            new_tag = tag
            if description is not None:
                new_tag = _setRootAttr(new_tag, "schematics:description", description)
            if ref is not None:
                new_tag = _setRootAttr(new_tag, "schematics:ref", ref)
            data = data.replace(tag, new_tag, 1)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(data)


def readSymbol(path: str) -> tuple[str, str, list[SymbolPin]]:
    """Read (description, ref, pins) straight from a file (no cache)."""
    with open(path, "r", encoding="utf-8") as handle:
        data = handle.read()
    _stripped, raw = extractPins(data)
    pins = [SymbolPin(str(n), float(x), float(y)) for n, x, y in raw]
    root = _ROOT_TAG_RE.search(data)
    desc = ""
    ref = ""
    if root is not None:
        m = re.search(r'schematics:description="([^"]*)"', root.group(0))
        if m:
            desc = m.group(1)
        m = re.search(r'schematics:ref="([^"]*)"', root.group(0))
        if m:
            ref = m.group(1)
    return desc, ref, pins


def validatePins(pins: list[SymbolPin]) -> str | None:
    """Return an error message if the pins cannot be written, else None."""
    for pin in pins:
        if not _PIN_NAME_RE.match(pin.name):
            return (
                "Invalid pin name %r - allowed: letters, digits and dot "
                "(the loader's charset)" % pin.name
            )
        if pin.x < 0 or pin.y < 0:
            return "Pin %s has negative coordinates (%g, %g)" % (pin.name, pin.x, pin.y)
    return None


class PinEditor(QtWidgets.QDialog):
    """Edit one symbol file's pins and metadata.

    Works on a plain file path so it can target copies (tests, imports);
    the caller refreshes its catalog after a successful save.
    """

    def __init__(
        self,
        path: str,
        pins: list[SymbolPin],
        description: str = "",
        ref: str = "",
        cacheKey: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.cacheKey = cacheKey
        self.setWindowTitle("Edit pins - %s" % os.path.basename(path))
        self.setModal(True)

        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        self.preview = SymbolPreview(self)
        self.preview.setData(raw, [(p.name, p.x, p.y) for p in pins])
        self.preview.pinPicked.connect(self._onPinPicked)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Pin", "X", "Y"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.itemSelectionChanged.connect(self._onSelectionChanged)
        self.table.itemChanged.connect(lambda _item: self._refreshPreview())

        addBtn = QtWidgets.QPushButton("Add pin", self)
        addBtn.clicked.connect(self._addPin)
        removeBtn = QtWidgets.QPushButton("Remove pin", self)
        removeBtn.clicked.connect(self._removePin)
        hint = QtWidgets.QLabel(
            "Click the preview to set the selected pin's coordinates.", self
        )
        hint.setWordWrap(True)

        self.descriptionEdit = QtWidgets.QLineEdit(description, self)
        self.descriptionEdit.setPlaceholderText("Description")
        self.refEdit = QtWidgets.QLineEdit(ref, self)
        self.refEdit.setPlaceholderText("Reference prefix (e.g. K, R, Y)")
        nameValidator = QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression("[A-Za-z0-9.]*"), self.refEdit
        )
        self.refEdit.setValidator(nameValidator)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(addBtn)
        row.addWidget(removeBtn)
        right.addLayout(row)
        right.addWidget(hint)
        right.addWidget(QtWidgets.QLabel("Description", self))
        right.addWidget(self.descriptionEdit)
        right.addWidget(QtWidgets.QLabel("Reference prefix", self))
        right.addWidget(self.refEdit)
        rightWidget = QtWidgets.QWidget(self)
        rightWidget.setLayout(right)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        body = QtWidgets.QHBoxLayout()
        body.addWidget(self.preview, 1)
        body.addWidget(rightWidget, 1)
        body.setContentsMargins(8, 8, 8, 8)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addLayout(body, 1)
        outer.addWidget(buttons)

        self._loadRows(pins)
        self.resize(720, 480)

    # ------------------------------------------------------------------
    def _loadRows(self, pins: list[SymbolPin]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(pins))
        for row, pin in enumerate(pins):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(pin.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(_fmt(pin.x)))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(_fmt(pin.y)))
        self.table.blockSignals(False)
        self._refreshPreview()

    def _pinsFromTable(self) -> list[SymbolPin]:
        pins: list[SymbolPin] = []
        for row in range(self.table.rowCount()):
            nameItem = self.table.item(row, 0)
            xItem = self.table.item(row, 1)
            yItem = self.table.item(row, 2)
            name = nameItem.text().strip() if nameItem is not None else ""
            try:
                x = float(xItem.text()) if xItem is not None else 0.0
                y = float(yItem.text()) if yItem is not None else 0.0
            except ValueError:
                x, y = -1.0, -1.0   # rejected by validatePins
            pins.append(SymbolPin(name=name, x=x, y=y))
        return pins

    def _refreshPreview(self) -> None:
        self.preview.setPins(self._pinsFromTable())

    def _onSelectionChanged(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            pin = self._pinsFromTable()[rows[0].row()]
            self.preview.setHighlight(pin.name)

    def _onPinPicked(self, x: float, y: float) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        self.table.blockSignals(True)
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(_fmt(x)))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(_fmt(y)))
        self.table.blockSignals(False)
        self._refreshPreview()

    def _addPin(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem("0"))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem("0"))
        self.table.selectRow(row)
        self._refreshPreview()

    def _removePin(self) -> None:
        rows = sorted(
            (i.row() for i in self.table.selectionModel().selectedRows()),
            reverse=True,
        )
        for row in rows:
            self.table.removeRow(row)
        self._refreshPreview()

    # ------------------------------------------------------------------
    def save(self) -> str | None:
        """Write the file. Returns None on success or an error message
        (no dialogs - the caller shows them, tests can assert on them)."""
        pins = self._pinsFromTable()
        error = validatePins(pins)
        if error is not None:
            return error
        try:
            writeSymbol(
                self.path,
                pins,
                description=self.descriptionEdit.text(),
                ref=self.refEdit.text(),
            )
        except (OSError, ValueError) as exc:
            return "Could not save %s: %s" % (self.path, exc)
        if self.cacheKey is not None:
            invalidate(self.cacheKey)
        return None

    def accept(self) -> None:
        error = self.save()
        if error is not None:
            QtWidgets.QMessageBox.warning(self, "Pin editor", error)
            return
        super().accept()


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

        self.editBtn = QtWidgets.QPushButton("Edit pins…", self)
        self.editBtn.clicked.connect(self._editSelected)
        dupBtn = QtWidgets.QPushButton("Duplicate", self)
        dupBtn.clicked.connect(self._duplicate)
        importBtn = QtWidgets.QPushButton("Import…", self)
        importBtn.clicked.connect(self._importSvg)
        deleteBtn = QtWidgets.QPushButton("Delete…", self)
        deleteBtn.clicked.connect(self._delete)
        folderBtn = QtWidgets.QPushButton("Open folder", self)
        folderBtn.clicked.connect(self._openFolder)
        refreshBtn = QtWidgets.QPushButton("Refresh", self)
        refreshBtn.clicked.connect(self._refresh)
        closeBtn = QtWidgets.QPushButton("Close", self)
        closeBtn.clicked.connect(self.accept)

        for button in (self.editBtn, dupBtn, importBtn, deleteBtn):
            button.setEnabled(False)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.filter, 1)
        left = QtWidgets.QVBoxLayout()
        left.addLayout(top)
        left.addWidget(self.table, 1)
        actions = QtWidgets.QHBoxLayout()
        for button in (self.editBtn, dupBtn, importBtn, deleteBtn):
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
        editor = PinEditor(
            path=entry.path,
            pins=pins,
            description=desc,
            ref=ref,
            cacheKey=entry.key,
            parent=self,
        )
        if editor.exec():
            self._refresh(keepSelection=entry.key)

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

    def _importSvg(self) -> None:
        fileName, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import symbol SVG", "", "SVG files (*.svg)"
        )
        if not fileName:
            return
        groups = list(self.catalog.groups())
        labels = [g if g else "(root)" for g in groups]
        label, ok = QtWidgets.QInputDialog.getItem(
            self, "Import symbol", "Target group:", labels, 0, False
        )
        if not ok:
            return
        group = groups[labels.index(label)] if label in labels else ""
        dest_dir = (
            os.path.join(self.catalog.root, group) if group else self.catalog.root
        )
        os.makedirs(dest_dir, exist_ok=True)
        base = os.path.basename(fileName)
        stem, ext = os.path.splitext(base)
        target = os.path.join(dest_dir, base)
        suffix = 2
        while os.path.exists(target):
            target = os.path.join(dest_dir, "%s%d%s" % (stem, suffix, ext))
            suffix += 1
        try:
            shutil.copy2(fileName, target)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Symbol manager", "Import failed: %s" % exc
            )
            return
        self._refresh()
        self._selectByName(os.path.splitext(os.path.basename(target))[0])

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
