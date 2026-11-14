# -*- coding: utf-8 -*-
###############################################################################
#
#  ConnectionCheck.py - ERC-lite dialog (unconnected pins, floating ends).
#
###############################################################################
"""Show the geometric connectivity check for a sheet: pins with no wire
and wire ends resting on nothing - KiCad's ERC reduced to what the
current data model can honestly know (no electrical types yet).
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from Schematics.Features.Utils.Connectivity import connectionReport


class ConnectionCheckDialog(QtWidgets.QDialog):
    """Read-only report viewer."""

    def __init__(
        self,
        report: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connection check")
        self.setModal(True)

        self.text = QtWidgets.QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setPlainText(report)
        self.text.setMinimumSize(460, 260)

        closeBtn = QtWidgets.QPushButton("Close", self)
        closeBtn.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.text, 1)
        layout.addWidget(closeBtn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.resize(560, 400)


def openConnectionCheck(sheet: object, parent: QtWidgets.QWidget | None = None) -> None:
    """Run the check for a sheet and show the report (modal)."""
    ConnectionCheckDialog(connectionReport(sheet), parent=parent).exec()
