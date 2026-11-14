# -*- coding: utf-8 -*-
###############################################################################
#
#  Wire.py - Scheme wire (conductor) item.
#
###############################################################################
"""First-class wire document objects.

A wire is an ``App::FeaturePython`` object like every other sheet element:
its vertices (``Points``, stored relative to the item position ``X``/``Y``)
and its ``WireType`` live in the FreeCAD document, so wires survive save
and load, participate in undo, can be selected on the sheet or in the tree,
and are deleted through the standard element machinery.

Drawing is interactive (see ``SchemeGraphicsScene.startWireDraw``); the
item itself is the persistent representation of a finished wire.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

import FreeCAD

from Schematics.Features.Items.SchemeObject import (
    SchemeObjectFeature,
    SchemeObjectViewProvider,
    makeObject,
)
from Schematics.Features.Items.SchemeObjectItem import SchemeObjectItem
from Schematics.Features.Items.StrokeMixin import (
    StrokeDataProperties,
    StrokeViewProperties,
)

#: Conductor classes for machine schematics. Semantic only for now — the
#: visible line style follows the per-wire Stroke* view properties
#: (StrokeDash in particular), so a Control wire can be drawn dashed.
WIRE_TYPES: list[str] = ["Power", "Control", "Hydraulic", "Pneumatic", "Signal"]

#: Conductor classes drawn dashed by default (control/signal wiring);
#: Power/Hydraulic/Pneumatic stay solid. Users can still override the
#: style per wire through the StrokeDash view property.
DASHED_WIRE_TYPES: tuple[str, ...] = ("Control", "Signal")

PointInput = QtCore.QPointF | tuple[float, float]


def _toVector(p: PointInput) -> FreeCAD.Vector:
    """Normalize a point input to an absolute FreeCAD.Vector (z = 0)."""
    if isinstance(p, QtCore.QPointF):
        return FreeCAD.Vector(p.x(), p.y(), 0.0)
    return FreeCAD.Vector(p[0], p[1], 0.0)


class Wire:
    """Factory: ``Wire(points, sheet, wireType)`` returns the App object.

    ``points`` are absolute sheet coordinates; they are stored relative to
    the first vertex, which becomes the item position ``X``/``Y``.
    """

    def __new__(
        cls,
        points: Sequence[PointInput] | None = None,
        sheet: Any = None,
        wireType: str | None = None,
    ) -> Any:
        obj: Any = makeObject(WireFeature, WireViewProvider, sheet, cls)
        if points is not None and len(points) >= 2:
            origin: FreeCAD.Vector = _toVector(points[0])
            obj.Points = [
                FreeCAD.Vector(v.x - origin.x, v.y - origin.y, 0.0)
                for v in (_toVector(p) for p in points)
            ]
            obj.X = origin.x
            obj.Y = origin.y
        if wireType is not None:
            obj.WireType = wireType
        return obj


# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class WireFeature(StrokeDataProperties, SchemeObjectFeature):

    def initDataPropertyies(self, obj: Any) -> None:
        obj.addProperty(
            'App::PropertyVectorList', 'Points', 'Geometry',
            'Wire vertices relative to the item position', 8 + 16,
        ).Points = []
        obj.addProperty(
            'App::PropertyEnumeration', 'WireType', 'Data',
            'Conductor class of this wire', 8 + 16,
        ).WireType = list(WIRE_TYPES)
        obj.WireType = WIRE_TYPES[0]
        # Label (not "Label": that name is FreeCAD's built-in tree label).
        # A non-empty tag joins same-labelled wires into one net and marks
        # the wire's ends as intentionally terminated (KiCad net labels).
        obj.addProperty(
            'App::PropertyString', 'Tag', 'Data',
            'Wire label / conductor tag (e.g. X1)', 8 + 16,
        ).Tag = ''
        # Size is derived from Points; wires do not rotate about a center.
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")
        obj.setPropertyStatus("Rotation", "ReadOnly")

    def onDataPropertyChanged(self, obj: Any, prop: str) -> None:
        if prop == "Points":
            self._updateSize(obj)
        elif prop in ("WireType", "Tag") and hasattr(self, "item"):
            if prop == "Tag":
                # The label grows the bounding rect (room for the text).
                self.item.prepareGeometryChange()
            self.item.update()

    @staticmethod
    def _updateSize(obj: Any) -> None:
        """Width/Height mirror the bounding box of the vertices."""
        pts = obj.Points
        if not pts:
            obj.Width = 0
            obj.Height = 0
            return
        xs: list[float] = [v.x for v in pts]
        ys: list[float] = [v.y for v in pts]
        obj.Width = max(xs) - min(xs)
        obj.Height = max(ys) - min(ys)

    def getItem(self, obj: Any, sheet: Any) -> WireItem:
        return WireItem(obj, sheet)

    def initRootMethods(self, obj: Any) -> None:
        pass   # wires have no root-level rendering work (unlike symbols)


# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class WireViewProvider(StrokeViewProperties, SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj: Any) -> None:
        pass

    def onViewPropertyChanged(self, vobj: Any, prop: str) -> None:
        pass


class WireItem(SchemeObjectItem, QtWidgets.QGraphicsItem):
    """Persistent polyline: selectable, movable, saved with the document."""

    def __init__(self, obj: Any, sheet: Any) -> None:
        super().__init__(obj, sheet)
        # Wires sit under symbols so terminals stay visible on top.
        self.setZValue(-0.5)
        self._netHighlight = False
        self.setAcceptHoverEvents(True)

    # ------------------------------------------------------------------
    # Net highlight (KiCad hover)
    # ------------------------------------------------------------------
    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        self._setNetHighlight(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        self._setNetHighlight(False)
        super().hoverLeaveEvent(event)

    def _setNetHighlight(self, on: bool) -> None:
        """Toggle the accent colour on this wire's whole net."""
        try:
            name = str(self.obj.Name)
        except (ReferenceError, RuntimeError, AttributeError):
            return
        from Schematics.Features.Utils.Connectivity import netClosure, wireByName
        for wireName in netClosure(self.sheet, name):
            wire = wireByName(self.sheet, wireName)
            if wire is None:
                continue
            try:
                item = wire.Proxy.item
            except (ReferenceError, RuntimeError, AttributeError):
                continue
            item._netHighlight = on
            item.update()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    def _points(self) -> list[QtCore.QPointF]:
        """Vertices in item-local coordinates (relative to X/Y)."""
        try:
            return [QtCore.QPointF(v.x, v.y) for v in self.obj.Points]
        except (ReferenceError, AttributeError, RuntimeError):
            return []   # object deleted or Points not migrated yet

    def _strokeWidth(self) -> float:
        try:
            return float(self.obj.ViewObject.StrokeWidth.Value)
        except (ReferenceError, AttributeError, RuntimeError):
            return 1.0

    def updateTransform(self) -> None:
        # Override the base class centering: wires are drawn from their
        # first vertex, so the item position IS the first vertex.
        self.setTransform(QtGui.QTransform(), combine=False)
        self.setTransformOriginPoint(QtCore.QPointF(0, 0))

    def boundingRect(self) -> QtCore.QRectF:
        if not self.isVisible():
            return QtCore.QRectF(0, 0, 0, 0)
        pts = self._points()
        if len(pts) < 2:
            return QtCore.QRectF(0, 0, 0, 0)
        xs: list[float] = [p.x() for p in pts]
        ys: list[float] = [p.y() for p in pts]
        m: float = self._strokeWidth() / 2.0 + 3.0   # stroke + anchor markers
        top_pad: float = m + self._labelHeight()      # room for the label
        return QtCore.QRectF(
            min(xs) - m, min(ys) - top_pad,
            (max(xs) - min(xs)) + 2 * m,
            (max(ys) - min(ys)) + top_pad + m,
        )

    def _labelHeight(self) -> float:
        """Extra top space needed by the label (0 when there is none)."""
        try:
            return 8.0 if str(self.obj.Tag or "") else 0.0
        except (ReferenceError, RuntimeError, AttributeError):
            return 0.0

    def shape(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        pts = self._points()
        if len(pts) < 2:
            return path
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        stroker = QtGui.QPainterPathStroker()
        stroker.setWidth(self._strokeWidth() + 4.0)   # generous grab band
        return stroker.createStroke(path)

    # ------------------------------------------------------------------
    # Painting
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
        except ReferenceError:
            return
        pts = self._points()
        if len(pts) < 2:
            return
        g.save()
        g.beginNativePainting()
        g.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing)
        g.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        color: Any = QtGui.QColor.fromRgbF(*self.sheet.Proxy.appearance.linesColor())
        if self.isSelected():
            color = QtCore.Qt.GlobalColor.green
        pen: QtGui.QPen
        wire_type = "Power"
        try:
            wire_type = str(self.obj.WireType)
        except (ReferenceError, RuntimeError, AttributeError):
            pass
        highlighted = bool(getattr(self, "_netHighlight", False))
        if highlighted:
            # KiCad-style net highlight: accent colour, slightly heavier
            pen = QtGui.QPen(QtGui.QColor("#2563eb"), self._strokeWidth() + 1.0)
        else:
            pen = getattr(self.obj.ViewObject.Proxy, "pen", None) \
                or QtGui.QPen(color, 0.5)
            pen.setColor(color)
            if pen.capStyle() == QtCore.Qt.PenCapStyle.FlatCap:
                # Softer wire ends (KiCad-like); user-set caps are kept
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            if (
                wire_type in DASHED_WIRE_TYPES
                and pen.style() == QtCore.Qt.PenStyle.SolidLine
            ):
                pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        g.setPen(pen)

        path = QtGui.QPainterPath(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        g.drawPath(path)

        if self.isSelected():
            for p in pts:
                self.drawAnchor(g, p.x(), p.y())

        # Junction dots where this wire's ends land on another wire
        # (the drawing convention for connected crossings/T junctions)
        from Schematics.Features.Utils.Connectivity import junctionPoints
        g.setBrush(color if not highlighted else QtGui.QColor("#2563eb"))
        for scene_point in junctionPoints(self.sheet, self.obj):
            local = self.mapFromScene(scene_point)
            g.drawEllipse(local, 1.8, 1.8)
        g.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        # Label at the middle vertex, above the line (KiCad net-label style)
        try:
            tag = str(self.obj.Tag or "")
        except (ReferenceError, RuntimeError, AttributeError):
            tag = ""
        if tag:
            mid = pts[len(pts) // 2]
            font = g.font()
            font.setPixelSize(5)
            g.setFont(font)
            g.drawText(
                QtCore.QRectF(mid.x() - 40.0, mid.y() - 9.0, 80.0, 8.0),
                int(QtCore.Qt.AlignmentFlag.AlignHCenter
                    | QtCore.Qt.AlignmentFlag.AlignBottom),
                tag,
            )

        g.endNativePainting()
        g.restore()
