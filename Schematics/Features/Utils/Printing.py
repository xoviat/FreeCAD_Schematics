# -*- coding: utf-8 -*-
###############################################################################
#
#  Printing.py - print preview and PDF export for scheme sheets.
#
###############################################################################
"""Render a sheet (template + items) to a printer or a PDF file.

Page size and orientation come from the sheet's dimensions (set from the
SVG template) and are mapped to standard paper sizes where possible; the
scene is fitted into the page keeping its aspect ratio. The previous
implementation hardcoded A4 portrait with a magic source-rect fudge,
which mangled the 420x297 landscape sheets and is why the README used to
call printing unsupported.
"""

from __future__ import annotations

from typing import Any

import FreeCAD
from PySide6 import QtGui, QtCore, QtWidgets, QtPrintSupport

from Schematics.Features.Utils.MDI import tryToGetSchemeFromActiveWindow


def sheetSizeMm(sheet: Any) -> tuple[float, float]:
    """Sheet page size in millimetres (from the view properties)."""
    try:
        width = float(sheet.ViewObject.Width.Value)
        height = float(sheet.ViewObject.Height.Value)
    except (ReferenceError, RuntimeError, AttributeError, TypeError):
        width, height = 0.0, 0.0
    if width <= 0 or height <= 0:
        width, height = 297.0, 210.0
    return width, height


def pageSizeFor(width: float, height: float) -> QtGui.QPageSize:
    """Standard paper (A4/A3/A2) matching the sheet, else a custom size."""
    long_side = max(width, height)
    short_side = min(width, height)
    for size_id in (
        QtGui.QPageSize.PageSizeId.A4,
        QtGui.QPageSize.PageSizeId.A3,
        QtGui.QPageSize.PageSizeId.A2,
    ):
        size = QtGui.QPageSize(size_id)
        paper = size.size(QtGui.QPageSize.Unit.Millimeter)
        if (
            abs(paper.width() - long_side) < 4.0
            and abs(paper.height() - short_side) < 4.0
        ):
            return size
    return QtGui.QPageSize(
        QtCore.QSizeF(width, height), QtGui.QPageSize.Unit.Millimeter
    )


def pageOrientationFor(width: float, height: float) -> QtGui.QPageLayout.Orientation:
    if width > height:
        return QtGui.QPageLayout.Orientation.Landscape
    return QtGui.QPageLayout.Orientation.Portrait


def renderSheet(sheet: Any, painter: QtGui.QPainter, target: QtCore.QRectF) -> None:
    """Draw the sheet into target, aspect preserved and centred."""
    scene = sheet.Proxy.scene
    width, height = sheetSizeMm(sheet)
    source = QtCore.QRectF(0.0, 0.0, width, height)
    scale = min(target.width() / width, target.height() / height)
    fitted = QtCore.QRectF(
        target.center().x() - width * scale / 2.0,
        target.center().y() - height * scale / 2.0,
        width * scale,
        height * scale,
    )
    scene.render(painter, fitted, source)


def _configuredPrinter(sheet: Any) -> QtPrintSupport.QPrinter:
    width, height = sheetSizeMm(sheet)
    printer = QtPrintSupport.QPrinter(
        QtPrintSupport.QPrinter.PrinterMode.HighResolution
    )
    printer.setPageSize(pageSizeFor(width, height))
    printer.setPageOrientation(pageOrientationFor(width, height))
    printer.setPageMargins(QtCore.QMarginsF(0.0, 0.0, 0.0, 0.0))
    printer.setFullPage(True)
    return printer


def PrintPreviewAction() -> None:
    """Replacement for FreeCAD's Std_Print / Std_PrintPreview on sheets."""
    sheet = tryToGetSchemeFromActiveWindow()
    if sheet is None:
        return
    printer = _configuredPrinter(sheet)

    def drawPage(previewPrinter: QtPrintSupport.QPrinter) -> None:
        previewPrinter.setFullPage(True)
        painter = QtGui.QPainter()
        if not painter.begin(previewPrinter):
            return
        try:
            target = QtCore.QRectF(
                previewPrinter.pageLayout().fullRectPixels(previewPrinter.resolution())
            )
            renderSheet(sheet, painter, target)
        finally:
            painter.end()

    mainWin = FreeCAD.Gui.getMainWindow()
    dialog = QtPrintSupport.QPrintPreviewDialog(printer, mainWin)
    dialog.paintRequested.connect(drawPage)
    dialog.exec()


def exportPdf(sheet: Any, path: str) -> None:
    """Write the sheet to a PDF file (raises OSError on failure)."""
    width, height = sheetSizeMm(sheet)
    writer = QtGui.QPdfWriter(path)
    writer.setResolution(300)
    writer.setPageSize(pageSizeFor(width, height))
    writer.setPageOrientation(pageOrientationFor(width, height))
    writer.setPageMargins(QtCore.QMarginsF(0.0, 0.0, 0.0, 0.0))
    painter = QtGui.QPainter()
    if not painter.begin(writer):
        raise OSError("could not open PDF for writing: " + path)
    try:
        target = QtCore.QRectF(writer.pageLayout().fullRectPixels(writer.resolution()))
        renderSheet(sheet, painter, target)
    finally:
        painter.end()


def exportPdfInteractive(parent: QtWidgets.QWidget | None = None) -> None:
    """File dialog + export for the active sheet; reports success/errors."""
    sheet = tryToGetSchemeFromActiveWindow()
    if sheet is None:
        return
    defaultName = (str(getattr(sheet, "Label", "")) or "schematic") + ".pdf"
    path, _filter = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Export PDF", defaultName, "PDF files (*.pdf)"
    )
    if not path:
        return
    try:
        exportPdf(sheet, path)
    except OSError as exc:
        QtWidgets.QMessageBox.warning(parent, "Export PDF", str(exc))
        return
    FreeCAD.Console.PrintMessage("Schematics: exported %s\n" % path)
