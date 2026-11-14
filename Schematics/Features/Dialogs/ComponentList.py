# -*- coding: utf-8 -*-
###############################################################################
#
#  ComponentList.py - component list dialog (BOM-lite for machine schemes).
#
###############################################################################
"""Table view over :mod:`Schematics.Features.Utils.Reports` with CSV
export and clipboard copy - the machine-schematic equivalent of KiCad's
"Generate Bill of Materials" (device list only; no PCB fields).
"""

from __future__ import annotations

import csv
import io

from PySide6 import QtCore, QtWidgets

from Schematics.Features.Utils.Reports import (
    REPORT_HEADERS,
    ComponentRow,
    componentRows,
    writeCsv,
)


class ComponentListDialog(QtWidgets.QDialog):
    """Show a sheet's component list; export CSV or copy as TSV."""

    def __init__(
        self,
        rows: list[ComponentRow],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Component list")
        self.setModal(True)
        self.rows = rows

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(len(REPORT_HEADERS))
        self.table.setHorizontalHeaderLabels(list(REPORT_HEADERS))
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self._populate()

        summary = QtWidgets.QLabel("%d device(s)" % len(rows), self)

        exportBtn = QtWidgets.QPushButton("Export CSV…", self)
        exportBtn.clicked.connect(self._exportCsv)
        copyBtn = QtWidgets.QPushButton("Copy", self)
        copyBtn.clicked.connect(self._copy)
        closeBtn = QtWidgets.QPushButton("Close", self)
        closeBtn.clicked.connect(self.accept)

        actions = QtWidgets.QHBoxLayout()
        actions.addWidget(summary)
        actions.addStretch(1)
        actions.addWidget(exportBtn)
        actions.addWidget(copyBtn)
        actions.addWidget(closeBtn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)
        self.resize(640, 420)

    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            for column, text in enumerate(
                (row.designator, row.value, row.symbol, row.description)
            ):
                self.table.setItem(
                    row_index,
                    column,
                    QtWidgets.QTableWidgetItem(text),
                )

    def _exportCsv(self) -> None:
        fileName, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export component list", "components.csv", "CSV files (*.csv)"
        )
        if not fileName:
            return
        try:
            writeCsv(fileName, self.rows)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Component list", "Export failed: %s" % exc
            )

    def _copy(self) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter="\t")
        writer.writerow(REPORT_HEADERS)
        for row in self.rows:
            writer.writerow((row.designator, row.value, row.symbol, row.description))
        QtWidgets.QApplication.clipboard().setText(buffer.getvalue())


def openComponentList(sheet: object, parent: QtWidgets.QWidget | None = None) -> None:
    """Build the list for a sheet and show it (modal)."""
    rows = componentRows(sheet)
    if not rows:
        QtWidgets.QMessageBox.information(
            parent, "Component list",
            "No annotated symbols on this sheet - place symbols or run "
            "'Annotate sheet' first.",
        )
        return
    ComponentListDialog(rows, parent=parent).exec()
