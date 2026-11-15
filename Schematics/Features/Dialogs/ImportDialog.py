# -*- coding: utf-8 -*-
###############################################################################
#
#  ImportDialog.py - pick a folder, tick symbols, import them.
#
###############################################################################
"""Import symbols from a folder: store-format ``.svg`` files and
QElectroTech ``.elmt`` files alike.

The symbol manager's ``Import…`` opens a folder picker; this dialog
lists everything that folder contains (both kinds), lets the user
filter, tick and choose a target group, then writes the selection.

Two things keep it fast on a full QET checkout (~9k files):

* **a worker thread** - scanning and writing run off the UI thread,
  reporting progress over Qt signals, so the wait is a progress bar
  with a Cancel button instead of a frozen cursor.  The work itself is
  the Qt-free :mod:`Schematics.Features.Utils.BatchImport` functions;
  with the GIL the win is responsiveness and overlapped file I/O, not
  parallel parsing - one worker, not many.
* **a model/view selection list** - a ``QTableWidget`` would
  materialise three items per row (27k widgets over that tree), while
  this view only ever builds the rows actually on screen, and the
  proxy filter matches without touching the widgets at all.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable
from typing import Any, ClassVar

from PySide6 import QtCore, QtWidgets

from Schematics.Features.Utils.BatchImport import (
    ImportItem,
    ImportReport,
    importSymbolItems,
    scanImportFolder,
)
from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog

_NEW_GROUP = "(new group…)"
_BY_CATEGORY = "(by category)"
_INVALID_NAME_CHARS = set('\\/:*?"<>|')
# The completion report stays bounded: a 9k-file run must not print a
# 9k-line dialog.  Fixed entry counts and a fixed line width.
_SUMMARY_NAMES = 3
_SUMMARY_FAILURES = 8
_SUMMARY_NOTES = 3
_SUMMARY_WIDTH = 110


def _clip(text: str, width: int = _SUMMARY_WIDTH) -> str:
    """One report line, cut to *width* with an ellipsis."""
    return text if len(text) <= width else text[: width - 1] + "…"


def _bounded(entries: list[str], limit: int) -> list[str]:
    """At most *limit* entries, then a line counting the rest."""
    shown = entries[:limit]
    if len(entries) > limit:
        shown.append("… and %d more" % (len(entries) - limit))
    return shown


def _checkValue(value: object) -> object:
    """A CheckState-role payload as an int, whichever side sent it."""
    return getattr(value, "value", value)


class _ImportModel(QtCore.QAbstractTableModel):
    """The discovered items plus their check state."""

    CHECK, NAME, KIND, CATEGORY = range(4)
    _HEADERS: ClassVar[list[str]] = ["", "Symbol", "Type", "Category"]

    checkedChanged = QtCore.Signal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[ImportItem] = []
        self._checked: set[str] = set()

    # -- data ----------------------------------------------------------
    def setItems(self, items: list[ImportItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        # A re-scan keeps ticks for files still present, drops the rest.
        self._checked.intersection_update({item.path for item in items})
        self.endResetModel()
        self.checkedChanged.emit()

    def itemAt(self, row: int) -> ImportItem:
        return self._items[row]

    def rowCount(
        self,
        parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = (
            QtCore.QModelIndex()
        ),
    ) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(
        self,
        parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = (
            QtCore.QModelIndex()
        ),
    ) -> int:
        return len(self._HEADERS)

    def data(
        self,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
        role: int = 0,  # Qt.ItemDataRole.DisplayRole
    ) -> object | None:
        if not index.isValid():
            return None
        item = self._items[index.row()]
        column = index.column()
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if column == self.NAME:
                return item.name
            if column == self.KIND:
                return "QET" if item.kind == "qet" else "SVG"
            if column == self.CATEGORY:
                return item.category or "(root)"
            return None
        if (
            role == QtCore.Qt.ItemDataRole.ToolTipRole
            and column == self.NAME
        ):
            return item.path
        if (
            role == QtCore.Qt.ItemDataRole.CheckStateRole
            and column == self.CHECK
        ):
            # Qt wants an int here; CheckState is not an IntEnum.
            return (
                QtCore.Qt.CheckState.Checked.value
                if item.path in self._checked
                else QtCore.Qt.CheckState.Unchecked.value
            )
        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = 0,  # Qt.ItemDataRole.DisplayRole
    ) -> object | None:
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._HEADERS)
        ):
            return self._HEADERS[section]
        return None

    def flags(
        self, index: QtCore.QModelIndex | QtCore.QPersistentModelIndex
    ) -> QtCore.Qt.ItemFlag:
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.isValid() and index.column() == self.CHECK:
            flags |= QtCore.Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(
        self,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
        value: Any,
        role: int = 0,  # Qt.ItemDataRole.CheckStateRole
    ) -> bool:
        if (
            role == QtCore.Qt.ItemDataRole.CheckStateRole
            and index.isValid()
            and index.column() == self.CHECK
        ):
            path = self._items[index.row()].path
            if _checkValue(value) == QtCore.Qt.CheckState.Checked.value:
                self._checked.add(path)
            else:
                self._checked.discard(path)
            self.dataChanged.emit(index, index, [role])
            self.checkedChanged.emit()
            return True
        return False

    # -- check state ---------------------------------------------------
    def checkedPaths(self) -> list[str]:
        return sorted(self._checked)

    def checkedCount(self) -> int:
        return len(self._checked)

    def setChecked(self, paths: Iterable[str], checked: bool) -> None:
        if checked:
            self._checked.update(paths)
        else:
            self._checked.difference_update(paths)
        if self._items:
            self.dataChanged.emit(
                self.index(0, self.CHECK),
                self.index(len(self._items) - 1, self.CHECK),
                [],  # empty == every role changed
            )
        self.checkedChanged.emit()


class _FilterProxy(QtCore.QSortFilterProxyModel):
    """Substring match over name, category and kind, without widgets."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._needle = ""

    def setNeedle(self, text: str) -> None:
        self._needle = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ) -> bool:
        if not self._needle:
            return True
        model = self.sourceModel()
        if not isinstance(model, _ImportModel):
            return True
        item = model.itemAt(source_row)
        return (
            self._needle in item.name.lower()
            or self._needle in item.category.lower()
            or self._needle in item.kind
        )


class _WorkerSignals(QtCore.QObject):
    """Cross-thread delivery: emitted by workers, handled on the UI thread."""

    scanDone = QtCore.Signal(object)      # list[ImportItem]
    scanFailed = QtCore.Signal(str)
    importProgress = QtCore.Signal(int, int)
    importDone = QtCore.Signal(object)    # ImportReport


class ImportDialog(QtWidgets.QDialog):
    """Selection list over a scanned folder of SVG and QET symbols."""

    lastFolder: ClassVar[str] = ""

    def __init__(
        self,
        folder: str,
        catalog: SymbolCatalog,
        parent: QtWidgets.QWidget | None = None,
        onImported: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import symbols")
        self.setModal(True)
        self.catalog = catalog
        self.onImported = onImported
        self._folder = folder
        self._items: list[ImportItem] = []
        self._scanned = False
        self._result_label = ""
        self._busy = False
        self._cancel = threading.Event()
        self._signals = _WorkerSignals(self)
        self._signals.scanDone.connect(self._onScanDone)
        self._signals.scanFailed.connect(self._onScanFailed)
        self._signals.importProgress.connect(self._onProgress)
        self._signals.importDone.connect(self._onImportDone)

        self.folderEdit = QtWidgets.QLineEdit(folder, self)
        self.folderEdit.setReadOnly(True)
        self.browseBtn = QtWidgets.QPushButton("Browse…", self)
        self.browseBtn.clicked.connect(self._browse)

        self.filter = QtWidgets.QLineEdit(self)
        self.filter.setPlaceholderText("Filter by name or category…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._onFilter)

        self.groupCombo = QtWidgets.QComboBox(self)
        self._groups: list[str] = []
        self._labels: list[str] = []
        self._refreshGroups()

        self._model = _ImportModel(self)
        self._proxy = _FilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self.table = QtWidgets.QTableView(self)
        self.table.setModel(self._proxy)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(_ImportModel.CHECK, 28)
        self.table.setColumnWidth(_ImportModel.KIND, 52)

        self.status = QtWidgets.QLabel(self)
        self.progress = QtWidgets.QProgressBar(self)
        self.progress.setVisible(False)
        self._model.checkedChanged.connect(self._updateStatus)

        self.allBtn = QtWidgets.QPushButton("Select all visible", self)
        self.allBtn.clicked.connect(lambda: self._selectVisible(True))
        self.noneBtn = QtWidgets.QPushButton("Select none", self)
        self.noneBtn.clicked.connect(lambda: self._selectVisible(False))
        self.cancelBtn = QtWidgets.QPushButton("Cancel", self)
        self.cancelBtn.setVisible(False)
        self.cancelBtn.clicked.connect(self._cancelImport)
        self.importBtn = QtWidgets.QPushButton("Import…", self)
        self.importBtn.clicked.connect(self._import)
        self.closeBtn = QtWidgets.QPushButton("Close", self)
        self.closeBtn.clicked.connect(self.reject)

        folderRow = QtWidgets.QHBoxLayout()
        folderRow.addWidget(QtWidgets.QLabel("Folder:", self))
        folderRow.addWidget(self.folderEdit, 1)
        folderRow.addWidget(self.browseBtn)
        filterRow = QtWidgets.QHBoxLayout()
        filterRow.addWidget(self.filter, 1)
        filterRow.addWidget(QtWidgets.QLabel("Target group:", self))
        filterRow.addWidget(self.groupCombo)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.allBtn)
        buttons.addWidget(self.noneBtn)
        buttons.addStretch(1)
        buttons.addWidget(self.cancelBtn)
        buttons.addWidget(self.importBtn)
        buttons.addWidget(self.closeBtn)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addLayout(folderRow)
        outer.addLayout(filterRow)
        outer.addWidget(self.table, 1)
        statusRow = QtWidgets.QHBoxLayout()
        statusRow.addWidget(self.status, 1)
        statusRow.addWidget(self.progress)
        outer.addLayout(statusRow)
        outer.addLayout(buttons)
        self.resize(820, 540)

        ImportDialog.lastFolder = folder
        self._startScan()

    # -- scanning ------------------------------------------------------
    def _browse(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Folder with symbols to import", self._folder
        )
        if folder:
            self._setFolder(folder)

    def _setFolder(self, folder: str) -> None:
        self._folder = folder
        self.folderEdit.setText(folder)
        ImportDialog.lastFolder = folder
        self._startScan()

    def _startScan(self) -> None:
        self._scanned = False
        self._items = []
        self._model.setItems([])
        self._setBusy("Scanning %s…" % self._folder, indeterminate=True)
        folder = self._folder

        def work() -> None:
            try:
                items = scanImportFolder(folder)
            except Exception as exc:  # keep the UI alive on any failure
                self._signals.scanFailed.emit(
                    "%s: %s" % (type(exc).__name__, exc)
                )
                return
            self._signals.scanDone.emit(items)

        threading.Thread(target=work, daemon=True).start()

    def _onScanDone(self, items: object) -> None:
        self._items = list(items) if isinstance(items, list) else []
        self._model.setItems(self._items)
        self._scanned = True
        self._setIdle()
        if not self._items:
            QtWidgets.QMessageBox.information(
                self,
                "Import symbols",
                "No .svg or .elmt symbols found under:\n%s" % self._folder,
            )

    def _onScanFailed(self, message: str) -> None:
        self._setIdle()
        QtWidgets.QMessageBox.warning(
            self, "Import symbols", "Scan failed:\n%s" % message
        )

    # -- selection -----------------------------------------------------
    def _onFilter(self, text: str) -> None:
        self._proxy.setNeedle(text)
        self._updateStatus()

    def _visiblePaths(self) -> list[str]:
        paths: list[str] = []
        for row in range(self._proxy.rowCount()):
            source = self._proxy.mapToSource(self._proxy.index(row, 0))
            paths.append(self._model.itemAt(source.row()).path)
        return paths

    def _selectVisible(self, checked: bool) -> None:
        self._model.setChecked(self._visiblePaths(), checked)

    def _updateStatus(self) -> None:
        if self._busy:
            return
        if not self._scanned:
            self.status.setText("Scanning…")
            return
        svg = sum(1 for item in self._items if item.kind == "svg")
        self.status.setText(
            "%d symbols found (%d SVG, %d QET) · %d selected"
            % (len(self._items), svg, len(self._items) - svg,
               self._model.checkedCount())
        )

    # -- group choice --------------------------------------------------
    def _refreshGroups(self) -> None:
        self._groups = list(self.catalog.groups())
        self._labels = [g if g else "(root)" for g in self._groups]
        current = self.groupCombo.currentText()
        self.groupCombo.clear()
        self.groupCombo.addItems(self._labels)
        self.groupCombo.addItem(_BY_CATEGORY)
        self.groupCombo.addItem(_NEW_GROUP)
        index = self.groupCombo.findText(current)
        if index >= 0:
            self.groupCombo.setCurrentIndex(index)

    def _targetGroup(self) -> str | None:
        """Group for this run, or None when the prompt was cancelled."""
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
                    self, "New group", "Invalid group name: %r" % name
                )
                return None
            return name
        if label in self._labels:
            return self._groups[self._labels.index(label)]
        return ""

    # -- busy state ----------------------------------------------------
    def _setBusy(self, label: str, indeterminate: bool = False) -> None:
        self._busy = True
        self.status.setText(label)
        if indeterminate:
            self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        for widget in (
            self.browseBtn, self.filter, self.groupCombo, self.allBtn,
            self.noneBtn, self.importBtn, self.closeBtn,
        ):
            widget.setEnabled(False)
        self.cancelBtn.setVisible(True)
        self.cancelBtn.setEnabled(True)

    def _setIdle(self) -> None:
        self._busy = False
        self.progress.setVisible(False)
        self.cancelBtn.setVisible(False)
        for widget in (
            self.browseBtn, self.filter, self.groupCombo, self.allBtn,
            self.noneBtn, self.importBtn, self.closeBtn,
        ):
            widget.setEnabled(True)
        self._updateStatus()

    def reject(self) -> None:
        if self._busy:
            return  # close is the Cancel button's job while busy
        super().reject()

    # -- import --------------------------------------------------------
    def _cancelImport(self) -> None:
        self._cancel.set()
        self.cancelBtn.setEnabled(False)
        self.status.setText("Cancelling…")

    def _import(self) -> None:
        checked = set(self._model.checkedPaths())
        items = [item for item in self._items if item.path in checked]
        if not items:
            QtWidgets.QMessageBox.information(
                self, "Import symbols", "Select at least one symbol."
            )
            return
        label = self.groupCombo.currentText()
        by_category = label == _BY_CATEGORY
        if by_category:
            # Each item lands in a group mirroring its source category
            # path, so the store keeps the source's structure.
            group_label = _BY_CATEGORY
            dest = self.catalog.root
        else:
            group = self._targetGroup()
            if group is None:
                return
            group_label = group or "(root)"
            dest = (
                os.path.join(self.catalog.root, group)
                if group
                else self.catalog.root
            )
        self._result_label = group_label
        self._cancel.clear()
        self._setBusy("Importing %d symbol(s)…" % len(items))
        self.progress.setRange(0, len(items))
        self.progress.setValue(0)

        # Qt delivers one queued slot per emit: throttle to ~100 updates
        # so a 9k-file run cannot flood the event loop.
        last = 0
        step = max(1, len(items) // 100)

        def onProgress(done: int, total: int) -> None:
            nonlocal last
            if done >= total or done - last >= step:
                last = done
                self._signals.importProgress.emit(done, total)

        def work() -> None:
            report = importSymbolItems(
                items,
                dest,
                progress=onProgress,
                cancelled=self._cancel.is_set,
                groupByCategory=by_category,
            )
            self._signals.importDone.emit(report)

        threading.Thread(target=work, daemon=True).start()

    def _onProgress(self, done: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _onImportDone(self, report: object) -> None:
        self._setIdle()
        if not isinstance(report, ImportReport):
            return
        failed_paths = {path for path, _reason in report.failed}
        # Anything not failing is done: uncheck it so the next run only
        # repeats work that actually needs repeating.
        self._model.setChecked(
            [path for path in self._model.checkedPaths()
             if path not in failed_paths],
            False,
        )
        self._refreshGroups()
        if report.imported and self.onImported is not None:
            self.onImported()
        self._showReport(report)

    def _showReport(self, report: ImportReport) -> None:
        """Bounded summary: fixed entry counts, fixed line width."""
        lines = [
            "Imported %d · skipped %d · failed %d into %s."
            % (
                len(report.imported),
                len(report.skipped),
                len(report.failed),
                _clip(self._result_label or "(root)", 40),
            )
        ]
        if report.cancelled:
            lines.append(
                "Cancelled - stopped after %d symbol(s)."
                % len(report.imported)
            )
        if report.skipped:
            names = [_clip(name, 40) for name in sorted(report.skipped)]
            lines.append(
                _clip(
                    "Skipped %d already present: %s"
                    % (len(report.skipped), ", ".join(names[:_SUMMARY_NAMES]))
                )
            )
            if len(names) > _SUMMARY_NAMES:
                lines.append(
                    "… and %d more not shown"
                    % (len(names) - _SUMMARY_NAMES)
                )
        if report.failed:
            lines.append("Failed %d:" % len(report.failed))
            failures = [
                "%s: %s" % (os.path.basename(path), _clip(reason))
                for path, reason in report.failed
            ]
            lines.extend(
                "  - " + line
                for line in _bounded(failures, _SUMMARY_FAILURES)
            )
        if report.notes:
            lines.append(
                "Notes: "
                + "; ".join(
                    _bounded([_clip(note) for note in report.notes],
                             _SUMMARY_NOTES)
                )
            )
        boxes = (
            QtWidgets.QMessageBox.warning
            if report.failed
            else QtWidgets.QMessageBox.information
        )
        boxes(self, "Import symbols", "\n".join(lines))
