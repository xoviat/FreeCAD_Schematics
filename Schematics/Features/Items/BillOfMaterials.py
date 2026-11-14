# -*- coding: utf-8 -*-
###############################################################################
#
#  BillOfMaterials.py - a live component-list table placed on the sheet.
#
###############################################################################
"""Placeable BOM table: renders the sheet's annotated symbols as a grid
directly on the drawing, like a KiCad/QET table object.

The content is read live from :func:`componentRows` on every paint, so
the table never goes stale - annotate, rename or delete a symbol and the
row list follows on the next repaint (the view runs in full-viewport
update mode). Only the position (X/Y) and the Title are persisted;
columns are fixed at Designator/Value/Symbol/Description.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from Schematics.Features.Items.SchemeObject import (
    SchemeObjectFeature,
    SchemeObjectViewProvider,
    makeObject,
)
from Schematics.Features.Items.SchemeObjectItem import SchemeObjectItem
from Schematics.Features.Utils.Reports import ComponentRow, componentRows
from Schematics.Features.Utils.Snap import snap

#: (heading, width in sheet units) per column, left to right.
BOM_COLUMNS: tuple[tuple[str, float], ...] = (
    ("Designator", 22.0),
    ("Value", 30.0),
    ("Symbol", 45.0),
    ("Description", 55.0),
)
ROW_H = 7.0
TITLE_H = 9.0
FONT_PX = 4
#: Stroke width for every table line (border, grid) - one width everywhere.
LINE_W = 0.4
#: Horizontal inset for cell text.
TEXT_PAD = 2.0


class BillOfMaterials:
    """Factory: ``BillOfMaterials(x, y, sheet)`` returns the App object."""

    # StartDraw() reads inst.typ; BOM is not an SVG symbol.
    typ: str | None = None

    def __new__(cls, x: float | None = None, y: float | None = None,
                sheet: Any = None) -> Any:
        obj: Any = makeObject(BOMFeature, BOMViewProvider, sheet, cls)
        if x is not None:
            obj.X = x
        if y is not None:
            obj.Y = y
        return obj


# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class BOMFeature(SchemeObjectFeature):

    def initDataPropertyies(self, obj: Any) -> None:
        obj.addProperty(
            'App::PropertyString', 'Title', 'Data',
            'Table heading', 8 + 16,
        ).Title = 'Bill of materials'
        # The item sizes itself from its rows; Width/Height stay derived.
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")

    def onDataPropertyChanged(self, obj: Any, prop: str) -> None:
        if prop == "Title" and hasattr(self, "item"):
            self.item.prepareGeometryChange()
            self.item.update()

    def getItem(self, obj: Any, sheet: Any) -> BOMItem:
        return BOMItem(obj, sheet)

    def initRootMethods(self, obj: Any) -> None:
        pass


# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class BOMViewProvider(SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj: Any) -> None:
        pass

    def onViewPropertyChanged(self, vobj: Any, prop: str) -> None:
        pass


class BOMItem(SchemeObjectItem, QtWidgets.QGraphicsItem):
    """The drawn table; content is live, position/title persist."""

    def __init__(self, obj: Any, sheet: Any) -> None:
        super().__init__(obj, sheet)
        self.setZValue(-0.4)   # above wires, below symbols
        self._rowCount = 0

    # ------------------------------------------------------------------
    def tableRows(self) -> list[ComponentRow]:
        """Live component rows for this sheet (shared with the dialog)."""
        try:
            return componentRows(self.sheet)
        except (ReferenceError, RuntimeError, AttributeError):
            return []

    def _title(self) -> str:
        try:
            return str(self.obj.Title or "")
        except (ReferenceError, RuntimeError, AttributeError):
            return ""

    def updateTransform(self) -> None:
        # Origin stays top-left: no centering transform (like Wire).
        self.setTransform(QtGui.QTransform(), combine=False)
        self.setTransformOriginPoint(QtCore.QPointF(0, 0))

    def boundingRect(self) -> QtCore.QRectF:
        if not self.isVisible():
            return QtCore.QRectF(0, 0, 0, 0)
        if self.drawMode:
            # Placement footprint: the whole sheet, like other primitives
            return QtCore.QRectF(-5e3, -5e3, 10e3, 10e3)
        rows = self.tableRows()
        width = sum(width for _name, width in BOM_COLUMNS) + 2.0
        height = ROW_H   # header row
        if self._title():
            height += TITLE_H
        height += len(rows) * ROW_H
        return QtCore.QRectF(-1.0, -1.0, width, height)

    def shape(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    # ------------------------------------------------------------------
    # Placement (same flow as Symbol primitives)
    # ------------------------------------------------------------------
    def _trackDrawPos(self, scenePos: QtCore.QPointF) -> None:
        if self.drawMode:
            self.curRelPos = snap(scenePos, self.sheet)
            self.setPos(self.curRelPos)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.drawMode and event.button() == QtCore.Qt.MouseButton.LeftButton:
            start = snap(event.scenePos(), self.sheet)
            self.obj.X = start.x()
            self.obj.Y = start.y()
            self.drawMode = False
            self.positionUpdated = False
        super().mousePressEvent(event)

    def hoverMoveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        self._trackDrawPos(event.scenePos())

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        self._trackDrawPos(event.scenePos())
        super().mouseMoveEvent(event)

    # ------------------------------------------------------------------
    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        g = painter   # base stubs name this parameter "painter"
        if not self.isVisible():
            return
        try:
            self.obj.Name   # liveness probe: object may be deleted
            appearance = self.sheet.Proxy.appearance
        except ReferenceError:
            return
        rows = self.tableRows()
        if len(rows) != self._rowCount:
            self._rowCount = len(rows)
            self.prepareGeometryChange()   # rows changed -> re-measure

        line_color = QtGui.QColor.fromRgbF(*appearance.linesColor())
        paper = QtGui.QColor.fromRgbF(*appearance.paperColor())
        title = self._title()

        total_w = sum(width for _name, width in BOM_COLUMNS)
        height = ROW_H
        if title:
            height += TITLE_H
        height += len(rows) * ROW_H

        g.save()
        g.beginNativePainting()
        g.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.TextAntialiasing
        )

        # One pen, one width, for every stroke AND the text color - never
        # call setPen() with a fresh pen in between (a default-width pen
        # used to make the grid lines 1.0 wide against a 0.4 border).
        pen = QtGui.QPen(line_color, LINE_W)
        g.setPen(pen)
        font = g.font()
        font.setPixelSize(FONT_PX)
        font.setBold(False)
        font.setItalic(False)
        g.setFont(font)

        # Background + outer border (one connected rectangle)
        g.setBrush(paper)
        g.drawRect(QtCore.QRectF(0.0, 0.0, total_w, height))
        g.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        text_flags = int(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        y = 0.0
        if title:
            g.drawText(
                QtCore.QRectF(0.0, y, total_w, TITLE_H),
                int(QtCore.Qt.AlignmentFlag.AlignCenter),
                title,
            )
            y += TITLE_H
            g.drawLine(QtCore.QPointF(0.0, y), QtCore.QPointF(total_w, y))

        # Header row (same font as everything else)
        x = 0.0
        for name, width in BOM_COLUMNS:
            g.drawText(
                QtCore.QRectF(x + TEXT_PAD, y, width - 2 * TEXT_PAD, ROW_H),
                text_flags,
                name,
            )
            x += width
        y += ROW_H
        g.drawLine(QtCore.QPointF(0.0, y), QtCore.QPointF(total_w, y))

        # Data rows: every horizontal spans the full width, every vertical
        # spans the full height, so all lines meet the border and each
        # other - a fully connected grid.
        for row in rows:
            cells = (row.designator, row.value, row.symbol, row.description)
            x = 0.0
            for (_name, width), cell in zip(BOM_COLUMNS, cells):
                g.drawText(
                    QtCore.QRectF(x + TEXT_PAD, y, width - 2 * TEXT_PAD, ROW_H),
                    text_flags,
                    cell,
                )
                x += width
            y += ROW_H
            if y < height:   # last row line is the bottom border itself
                g.drawLine(QtCore.QPointF(0.0, y), QtCore.QPointF(total_w, y))

        x = 0.0
        for _name, width in BOM_COLUMNS[:-1]:
            x += width
            g.drawLine(QtCore.QPointF(x, 0.0), QtCore.QPointF(x, height))

        g.endNativePainting()
        g.restore()
