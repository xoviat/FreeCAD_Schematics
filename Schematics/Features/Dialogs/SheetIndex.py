# -*- coding: utf-8 -*-
###############################################################################
#
#  SheetIndex.py - project sheet index (KiCad hierarchy navigator stand-in).
#
###############################################################################
"""Table of every sheet in the document: page number, name, symbol and
wire counts - the overview a multi-page machine schematic needs until
real hierarchical sheets exist.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from Schematics.Features.Utils.Sheets import SheetRow, sheetIndexRows


class SheetIndexDialog(QtWidgets.QDialog):
    """Read-only index of the document's sheets."""

    def __init__(
        self,
        rows: list[SheetRow],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sheet index")
        self.setModal(True)
        self.rows = rows

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Page", "Sheet", "Symbols", "Wires"]
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, text in enumerate(
                (str(row.page), row.name, str(row.symbols), str(row.wires))
            ):
                self.table.setItem(
                    row_index, column, QtWidgets.QTableWidgetItem(text)
                )

        closeBtn = QtWidgets.QPushButton("Close", self)
        closeBtn.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        layout.addWidget(closeBtn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.resize(480, 320)


def openSheetIndex(parent: QtWidgets.QWidget | None = None) -> None:
    """Build and show the index for the active document (modal)."""
    rows = sheetIndexRows()
    if not rows:
        QtWidgets.QMessageBox.information(
            parent, "Sheet index", "No sheets in the active document."
        )
        return
    SheetIndexDialog(rows, parent=parent).exec()
