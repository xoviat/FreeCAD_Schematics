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
import Schematics.Features.Utils.Snap as SN
from Schematics.Features.Utils.Reports import (
    ComponentRow,
    componentRows,
    symbolCount,
)

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
#: Corner magnet reach in sheet units: when an axis of the table's
#: bottom-right corner is this close to the title block's top-right
#: corner it snaps onto it, so the table settles flush above the block.
#: Independent per axis (right-edge and bottom-edge alignment are
#: useful on their own); exact value entry through the property editor
#: stays literal because the X/Y setters run with WithoutSnap.
TB_SNAP_TOL = 5.0


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

    def _tableSize(self, row_count: int | None = None) -> tuple[float, float]:
        """Drawn table size in sheet units as (width, height), top-left at
        the origin - the same numbers paint() and boundingRect() use.

        row_count defaults to symbolCount() rather than tableRows(): the
        count is all the geometry needs, and resolving catalog metadata
        for every row would walk the symbol store on each mouse-move.
        """
        if row_count is None:
            row_count = symbolCount(self.sheet)
        width = sum(width for _name, width in BOM_COLUMNS)
        height = ROW_H   # header row
        if self._title():
            height += TITLE_H
        height += row_count * ROW_H
        return width, height

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
        total_w, height = self._tableSize()
        # +/-1 slack around the drawn rect (its 0.4 stroke stays inside);
        # the height needs the same +2 the width has, otherwise the bottom
        # border falls outside the repaint/click bounds
        return QtCore.QRectF(-1.0, -1.0, total_w + 2.0, height + 2.0)

    def shape(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    # ------------------------------------------------------------------
    # Title-block corner magnet
    # ------------------------------------------------------------------
    def _alignToTitleBlock(self, raw: QtCore.QPointF) -> QtCore.QPointF | None:
        """Snap the table's bottom-right corner onto the title block's
        top-right corner.

        Tolerance is measured from the raw (pre-snap) point, so it reads
        as "how close did you drop it". Each axis is independent: the
        right edge aligns usefully on its own, the bottom edge likewise,
        and together they land the corner. The axis that does *not*
        magnetize still gets the normal grid snap - a half-aligned drop
        must not leave that axis off-grid.

        Returns None when nothing aligns, so the caller falls back to a
        plain grid snap.
        """
        try:
            if self.sheet.SnapEnabled is not True or SN.WithoutSnap:
                return None   # snapping off, or a literal property write
            title_block = self.sheet.Proxy.titleBlockRect()
        except (ReferenceError, RuntimeError, AttributeError):
            return None
        if title_block is None:
            return None   # no title block on the sheet (or hidden)
        total_w, height = self._tableSize()
        # Line up the *ink*, not the paths. Qt centres a stroked rect on
        # its path, so the table's border paints LINE_W/2 past it, while
        # the title block's SVG border is clipped to its bounding box and
        # stops dead at titleBlockRect(). Aiming at the raw corner left
        # the table overhanging the block (and the frame) by half a
        # stroke - about 1-2 px on screen.
        target_x = title_block.right() - total_w - LINE_W / 2.0
        target_y = title_block.top() - height - LINE_W / 2.0
        magnet_x = abs(raw.x() - target_x) <= TB_SNAP_TOL
        magnet_y = abs(raw.y() - target_y) <= TB_SNAP_TOL
        if not magnet_x and not magnet_y:
            return None
        snapped = SN.snap(raw, self.sheet)
        return QtCore.QPointF(
            target_x if magnet_x else snapped.x(),
            target_y if magnet_y else snapped.y(),
        )

    def _placePoint(self, raw: QtCore.QPointF) -> QtCore.QPointF:
        """Title-block magnet first (exact corner), else grid snap."""
        aligned = self._alignToTitleBlock(raw)
        if aligned is not None:
            return aligned
        return SN.snap(raw, self.sheet)

    def itemChange(self, change: Any, value: Any) -> Any:
        # Drags land here (drawMode off sets ItemSendsGeometryChanges);
        # hover placement during drawMode does not, hence _placePoint too.
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            aligned = self._alignToTitleBlock(value)
            if aligned is not None:
                self.positionUpdated = True
                return aligned
            return super().itemChange(change, value)
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Placement (same flow as Symbol primitives)
    # ------------------------------------------------------------------
    def _trackDrawPos(self, scenePos: QtCore.QPointF) -> None:
        if self.drawMode:
            self.curRelPos = self._placePoint(scenePos)
            self.setPos(self.curRelPos)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.drawMode and event.button() == QtCore.Qt.MouseButton.LeftButton:
            start = self._placePoint(event.scenePos())
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

        total_w, height = self._tableSize(len(rows))

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
            # Explicit full-width box for the title row: its own border
            # on all four sides (top/sides shared with the table border)
            g.drawRect(QtCore.QRectF(0.0, 0.0, total_w, y))
        grid_top = y   # column separators start below the title row

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

        # Column separators run from the first header row down. They must
        # not start at 0: doing so cut the title row into cells, so the
        # heading never sat in one box spanning the full row width.
        x = 0.0
        for _name, width in BOM_COLUMNS[:-1]:
            x += width
            g.drawLine(QtCore.QPointF(x, grid_top), QtCore.QPointF(x, height))

        g.endNativePainting()
        g.restore()
