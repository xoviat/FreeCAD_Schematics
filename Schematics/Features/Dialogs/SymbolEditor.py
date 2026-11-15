# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolEditor.py - built-in symbol drawing/pin editor.
#
###############################################################################
"""KiCad-style symbol editor: draw primitives, place pins, edit metadata.

* :class:`SymbolCanvas` - the drawing surface: select/move/resize shapes,
  draw line/rect/circle/polyline/text, place pins, snap to a 0.5 grid,
  wheel zoom, pan, undo/redo.  Unmodelled artwork (``<path>``/``<g>`` from
  external editors) renders as a static backdrop.
* :class:`SymbolEditor` - dialog wrapping the canvas with the tool bar,
  pin table, metadata and style controls; ``save()`` returns an error
  string instead of showing dialogs (tests assert on it).
"""

from __future__ import annotations

import math
import os
from enum import Enum

from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

from Schematics.Features.Utils.SymbolCatalog import SymbolPin
from Schematics.Features.Utils.SymbolDrawing import (
    DrawingElement,
    RawElement,
    Shape,
    parseDrawing,
    rawSnapTargets,
    saveSymbolFile,
    viewBoxOf,
    validatePins,
    writeSymbol,
)
from Schematics.Features.Utils.SVGSymbolsCache import invalidate

# Hit tolerance / handle size in screen pixels.
_TOL_PX = 7.0
# Placement snap radius - deliberately larger than hit-testing so the
# magnet feels generous before the grid fallback takes over.
_SNAP_PX = 14.0
_HANDLE_PX = 7.0
_SNAP_STEP = 0.5
_UNDO_LIMIT = 100


class Tool(Enum):
    """Canvas interaction mode."""

    SELECT = "select"
    LINE = "line"
    RECT = "rect"
    CIRCLE = "circle"
    POLYLINE = "polyline"
    TEXT = "text"
    PIN = "pin"


class _Drag(Enum):
    """Active mouse gesture."""

    NONE = "none"
    PAN = "pan"
    MOVE = "move"
    RESIZE = "resize"
    DRAW = "draw"
    PIN_MOVE = "pin_move"


def _cloneShape(shape: Shape) -> Shape:
    return Shape(
        kind=shape.kind,
        coords=list(shape.coords),
        points=list(shape.points),
        text=shape.text,
        stroke=shape.stroke,
        fill=shape.fill,
        stroke_width=shape.stroke_width,
        font_size=shape.font_size,
    )


def _segDistance(px: float, py: float, ax: float, ay: float,
                 bx: float, by: float) -> float:
    """Distance from point P to segment AB."""
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class SymbolCanvas(QtWidgets.QWidget):
    """Interactive drawing surface for one symbol file."""

    changed = QtCore.Signal()           # document mutated (undo buttons...)
    selectionChanged = QtCore.Signal()  # shape/pin selection changed
    pinsChanged = QtCore.Signal()       # pin list mutated (table reload)
    toolChanged = QtCore.Signal()       # tool switched (toolbar sync)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 280)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self._elements: list[DrawingElement] = []
        self._pins: list[SymbolPin] = []
        self._viewBox = QtCore.QRectF(0.0, 0.0, 20.0, 20.0)
        self._backdrop = QtSvg.QSvgRenderer()

        self._tool = Tool.SELECT
        self._snap = True
        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)

        self._selShape: int | None = None
        self._selPin: int | None = None

        self._drag = _Drag.NONE
        self._dragStart = QtCore.QPointF(0.0, 0.0)
        self._placedStart = QtCore.QPointF(0.0, 0.0)
        self._widgetStart = QtCore.QPointF(0.0, 0.0)
        self._handle = -1
        self._dragShape: Shape | None = None
        self._dragPin: SymbolPin | None = None
        self._dragPushed = False
        self._pending: Shape | None = None
        self._polyPoints: list[QtCore.QPointF] = []
        self._lastCursor = QtCore.QPointF(0.0, 0.0)
        self._hover: QtCore.QPointF | None = None   # pin-tool ghost
        self._rawTargets: list[tuple[float, float]] = []

        self._style = ("#000000", 0.5, "#ffffff")

        self._undo: list[tuple[list[DrawingElement], list[SymbolPin]]] = []
        self._redo: list[tuple[list[DrawingElement], list[SymbolPin]]] = []
        self._drawingDirty = False
        self._clip: Shape | SymbolPin | None = None

        self._setFont()

    # ------------------------------------------------------------------
    # document
    # ------------------------------------------------------------------
    def setDocument(self, svg: str, pins: list[SymbolPin]) -> None:
        """Parse the SVG; pins come from the caller (they win over the
        file's, so tests/imports can pass copies)."""
        x, y, w, h = viewBoxOf(svg)
        self._viewBox = QtCore.QRectF(x, y, w, h)
        self._elements = parseDrawing(svg)
        self._rawTargets = [
            pt
            for element in self._elements
            if isinstance(element, RawElement)
            for pt in rawSnapTargets(element.text)
        ]
        self._pins = list(pins)
        self._rebuildBackdrop()
        self._selShape = None
        self._selPin = None
        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)
        self._undo.clear()
        self._redo.clear()
        self._drawingDirty = False
        self._lastCursor = self._viewBox.center()
        self._hover = None
        self._cancelPending()
        self.changed.emit()
        self.selectionChanged.emit()
        self.pinsChanged.emit()

    @property
    def elements(self) -> list[DrawingElement]:
        return self._elements

    @property
    def pins(self) -> list[SymbolPin]:
        return list(self._pins)

    @property
    def drawingDirty(self) -> bool:
        """True when shapes were added/edited since load."""
        return self._drawingDirty

    @property
    def canUndo(self) -> bool:
        return bool(self._undo)

    @property
    def canRedo(self) -> bool:
        return bool(self._redo)

    def _rebuildBackdrop(self) -> None:
        """Renderer for unmodelled artwork (paths/groups), drawn under
        the editable shapes.  Raw elements never change while open."""
        self._backdrop = QtSvg.QSvgRenderer()
        raws = [e.text for e in self._elements if isinstance(e, RawElement)]
        if not raws:
            return
        vb = self._viewBox
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g">'
            "\n%s\n</svg>"
            % (vb.x(), vb.y(), vb.width(), vb.height(), "\n".join(raws))
        )
        self._backdrop.load(svg.encode())

    # ------------------------------------------------------------------
    # tool / style / snap
    # ------------------------------------------------------------------
    def tool(self) -> Tool:
        return self._tool

    def setTool(self, tool: Tool) -> None:
        if tool is self._tool:
            return
        self._cancelPending()
        self._tool = tool
        self._hover = None
        cursor = (
            QtCore.Qt.CursorShape.CrossCursor
            if tool is not Tool.SELECT
            else QtCore.Qt.CursorShape.ArrowCursor
        )
        self.setCursor(cursor)
        self.toolChanged.emit()
        self.update()

    def setSnap(self, enabled: bool) -> None:
        self._snap = enabled

    def snapEnabled(self) -> bool:
        return self._snap

    def drawingStyle(self) -> tuple[str, float, str]:
        """(stroke, stroke_width, fill) defaults for new shapes."""
        return self._style

    def applyStyle(
        self,
        stroke: str | None = None,
        width: float | None = None,
        fill: str | None = None,
    ) -> None:
        stroke_v, width_v, fill_v = self._style
        if stroke is not None:
            stroke_v = stroke
        if width is not None:
            width_v = width
        if fill is not None:
            fill_v = fill
        self._style = (stroke_v, width_v, fill_v)
        shape = self.selectedShape()
        if shape is not None:
            self._pushUndo()
            shape.stroke = stroke_v
            shape.stroke_width = width_v
            if shape.kind != "text":
                shape.fill = fill_v
            self._drawingDirty = True
            self.changed.emit()
            self.selectionChanged.emit()
        self.update()

    # ------------------------------------------------------------------
    # selection / mutations
    # ------------------------------------------------------------------
    def selectedShape(self) -> Shape | None:
        if self._selShape is not None and 0 <= self._selShape < len(self._elements):
            element = self._elements[self._selShape]
            if isinstance(element, Shape):
                return element
        return None

    def selectedPinIndex(self) -> int | None:
        if self._selPin is not None and 0 <= self._selPin < len(self._pins):
            return self._selPin
        return None

    def selectShape(self, index: int | None) -> None:
        if index == self._selShape:
            return
        self._selShape = index
        self._selPin = None
        self.selectionChanged.emit()
        self.update()

    def selectPin(self, index: int | None) -> None:
        if index == self._selPin:
            return
        self._selPin = index
        self._selShape = None
        self.selectionChanged.emit()
        self.update()

    def addShape(self, shape: Shape) -> None:
        """Append a shape (used by the draw tools and tests)."""
        self._pushUndo()
        self._elements.append(shape)
        self._selShape = len(self._elements) - 1
        self._selPin = None
        self._drawingDirty = True
        self.changed.emit()
        self.selectionChanged.emit()
        self.update()

    def setPins(self, pins: list[SymbolPin], record: bool = True) -> None:
        if record:
            self._pushUndo()
        self._pins = list(pins)
        if self._selPin is not None and self._selPin >= len(self._pins):
            self._selPin = None
        self.pinsChanged.emit()
        self.selectionChanged.emit()
        self.update()

    def addPinAt(self, x: float, y: float) -> None:
        used = {p.name for p in self._pins}
        number = 1
        while str(number) in used:
            number += 1
        self._pushUndo()
        self._pins.append(SymbolPin(str(number), x, y))
        self._selPin = len(self._pins) - 1
        self._selShape = None
        self.pinsChanged.emit()
        self.selectionChanged.emit()
        self.update()

    def addPinCentered(self) -> None:
        """Add a pin at the viewBox center (table 'Add pin' button)."""
        center = self._viewBox.center()
        self.addPinAt(self._snapVal(center.x()), self._snapVal(center.y()))

    def deleteSelection(self) -> None:
        if self._selShape is not None:
            self._pushUndo()
            del self._elements[self._selShape]
            self._selShape = None
            self._drawingDirty = True
            self.changed.emit()
            self.selectionChanged.emit()
            self.update()
            return
        if self._selPin is not None:
            self._pushUndo()
            del self._pins[self._selPin]
            self._selPin = None
            self.pinsChanged.emit()
            self.selectionChanged.emit()
            self.update()

    # ------------------------------------------------------------------
    # clipboard (canvas-local: shapes and pins)
    # ------------------------------------------------------------------
    def copySelection(self) -> bool:
        """Copy the selected shape or pin; False when nothing is selected."""
        shape = self.selectedShape()
        if shape is not None:
            self._clip = _cloneShape(shape)
            return True
        idx = self.selectedPinIndex()
        if idx is not None:
            pin = self._pins[idx]
            self._clip = SymbolPin(pin.name, pin.x, pin.y)
            return True
        return False

    def cutSelection(self) -> bool:
        """Copy then delete the selection."""
        if not self.copySelection():
            return False
        self.deleteSelection()
        return True

    def pasteClipboard(self) -> bool:
        """Paste the clipboard copy at the cursor.  Endpoint/grid snap
        apply (Ctrl is held for the shortcut itself, so no bypass);
        pasting onto the original spot nudges by two grid steps."""
        if isinstance(self._clip, Shape):
            shape = _cloneShape(self._clip)
            anchor = _shapeAnchor(shape)
            target = self._placePoint(self._lastCursor, False)
            if math.hypot(target.x() - anchor[0], target.y() - anchor[1]) < 1e-6:
                target = QtCore.QPointF(
                    target.x() + _SNAP_STEP * 2, target.y() + _SNAP_STEP * 2
                )
            self.addShape(
                _moveShape(shape, target.x() - anchor[0], target.y() - anchor[1])
            )
            return True
        if isinstance(self._clip, SymbolPin):
            target = self._placePoint(self._lastCursor, False)
            if (
                abs(target.x() - self._clip.x) < 1e-6
                and abs(target.y() - self._clip.y) < 1e-6
            ):
                target = QtCore.QPointF(
                    target.x() + _SNAP_STEP * 2, target.y() + _SNAP_STEP * 2
                )
            self.addPinAt(target.x(), target.y())
            return True
        return False

    def _snapshot(self) -> tuple[list[DrawingElement], list[SymbolPin]]:
        elements: list[DrawingElement] = [
            _cloneShape(e) if isinstance(e, Shape) else e
            for e in self._elements
        ]
        pins = [SymbolPin(p.name, p.x, p.y) for p in self._pins]
        return elements, pins

    def _pushUndo(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > _UNDO_LIMIT:
            del self._undo[0]
        self._redo.clear()

    def _restore(
        self, snapshot: tuple[list[DrawingElement], list[SymbolPin]]
    ) -> None:
        elements, pins = snapshot
        self._elements = [
            _cloneShape(e) if isinstance(e, Shape) else e for e in elements
        ]
        self._pins = list(pins)
        self._selShape = None
        self._selPin = None
        self._drawingDirty = True
        self.changed.emit()
        self.selectionChanged.emit()
        self.pinsChanged.emit()
        self.update()

    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())

    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())

    def viewBoxRect(self) -> QtCore.QRectF:
        """The symbol's coordinate frame (viewBox), for tools and tests."""
        return QtCore.QRectF(self._viewBox)

    def fitView(self) -> None:
        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)
        self.update()

    # ------------------------------------------------------------------
    # view transform
    # ------------------------------------------------------------------
    def _fitScale(self) -> float:
        vw = max(self._viewBox.width(), 1e-6)
        vh = max(self._viewBox.height(), 1e-6)
        return max(min((self.width() - 24) / vw, (self.height() - 24) / vh), 0.01)

    def _scale(self) -> float:
        return self._fitScale() * self._zoom

    def _origin(self) -> QtCore.QPointF:
        scale = self._scale()
        return QtCore.QPointF(
            (self.width() - self._viewBox.width() * scale) / 2.0 + self._pan.x(),
            (self.height() - self._viewBox.height() * scale) / 2.0 + self._pan.y(),
        )

    def toWidget(self, point: QtCore.QPointF) -> QtCore.QPointF:
        scale = self._scale()
        origin = self._origin()
        return QtCore.QPointF(
            origin.x() + (point.x() - self._viewBox.x()) * scale,
            origin.y() + (point.y() - self._viewBox.y()) * scale,
        )

    def toSvg(self, pos: QtCore.QPointF) -> QtCore.QPointF:
        scale = self._scale()
        origin = self._origin()
        return QtCore.QPointF(
            self._viewBox.x() + (pos.x() - origin.x()) / scale,
            self._viewBox.y() + (pos.y() - origin.y()) / scale,
        )

    def _snapVal(self, value: float) -> float:
        if not self._snap:
            return value
        return round(value / _SNAP_STEP) * _SNAP_STEP

    def _snapPoint(self, point: QtCore.QPointF) -> QtCore.QPointF:
        return QtCore.QPointF(self._snapVal(point.x()), self._snapVal(point.y()))

    def _placePoint(
        self, point: QtCore.QPointF, bypass: bool
    ) -> QtCore.QPointF:
        """Endpoint snap first (line ends, polyline vertices, rect
        corners), then the grid.  Holding Ctrl (bypass) - or the Snap
        toggle being off - places freely."""
        if bypass or not self._snap:
            return point
        tol = _SNAP_PX / max(self._scale(), 1e-6)
        best: QtCore.QPointF | None = None
        best_d = tol
        # backdrop artwork first (existing symbols are mostly raw
        # paths - editable Shapes alone would offer no targets), then
        # the shapes drawn in this session
        for ex, ey in self._rawTargets:
            d = math.hypot(point.x() - ex, point.y() - ey)
            if d <= best_d:
                best_d = d
                best = QtCore.QPointF(ex, ey)
        for element in self._elements:
            if not isinstance(element, Shape):
                continue
            for ex, ey in _snapTargets(element):
                d = math.hypot(point.x() - ex, point.y() - ey)
                if d <= best_d:
                    best_d = d
                    best = QtCore.QPointF(ex, ey)
        if best is not None:
            return best
        return self._snapPoint(point)

    def _tolUnits(self) -> float:
        return _TOL_PX / max(self._scale(), 1e-6)

    # ------------------------------------------------------------------
    # hit testing
    # ------------------------------------------------------------------
    def _hitPin(self, svg: QtCore.QPointF) -> int | None:
        tol = _TOL_PX / max(self._scale(), 1e-6)
        for idx in range(len(self._pins) - 1, -1, -1):
            pin = self._pins[idx]
            if math.hypot(svg.x() - pin.x, svg.y() - pin.y) <= tol:
                return idx
        return None

    def _hitShape(self, svg: QtCore.QPointF) -> int | None:
        tol = self._tolUnits()
        for idx in range(len(self._elements) - 1, -1, -1):
            element = self._elements[idx]
            if isinstance(element, Shape) and _shapeHit(element, svg, tol):
                return idx
        return None

    def _handleAt(self, pos: QtCore.QPointF) -> int:
        shape = self.selectedShape()
        if shape is None:
            return -1
        for idx, handle in enumerate(_shapeHandles(shape)):
            if (self.toWidget(handle) - pos).manhattanLength() <= _HANDLE_PX:
                return idx
        return -1

    # ------------------------------------------------------------------
    # mouse
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        try:
            self._press(event)
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass

    def _press(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._drag = _Drag.PAN
            self._widgetStart = event.position()
            return
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        svg = self.toSvg(event.position())
        self._dragStart = svg
        self._widgetStart = event.position()
        self._dragPushed = False
        self._lastCursor = svg
        bypass = bool(
            event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        )

        if self._tool is Tool.SELECT:
            pin_idx = self._hitPin(svg)
            if pin_idx is not None:
                self._selPin = pin_idx
                self._selShape = None
                self._drag = _Drag.PIN_MOVE
                self._dragPin = self._pins[pin_idx]
                self.selectionChanged.emit()
                self.update()
                return
            shape_idx = self._hitShape(svg)
            if shape_idx is not None:
                self._selShape = shape_idx
                self._selPin = None
                self.selectionChanged.emit()
                handle = self._handleAt(event.position())
                if handle >= 0:
                    self._drag = _Drag.RESIZE
                    self._handle = handle
                    self._dragShape = _cloneShape(self.selectedShape())  # type: ignore[arg-type]
                else:
                    self._drag = _Drag.MOVE
                    self._dragShape = _cloneShape(self.selectedShape())  # type: ignore[arg-type]
                self.update()
                return
            # empty space: deselect + start panning
            self._selShape = None
            self._selPin = None
            self.selectionChanged.emit()
            self._drag = _Drag.PAN
            self.update()
            return

        if self._tool is Tool.LINE or self._tool is Tool.RECT:
            start = self._placePoint(svg, bypass)
            self._placedStart = start
            self._drag = _Drag.DRAW
            if self._tool is Tool.LINE:
                self._pending = Shape(
                    kind="line",
                    coords=[start.x(), start.y(), start.x(), start.y()],
                    stroke=self._style[0],
                    stroke_width=self._style[1],
                )
            else:
                self._pending = Shape(
                    kind="rect",
                    coords=[start.x(), start.y(), 0.0, 0.0],
                    stroke=self._style[0],
                    fill=self._style[2],
                    stroke_width=self._style[1],
                )
            self.update()
            return

        if self._tool is Tool.CIRCLE:
            start = self._placePoint(svg, bypass)
            self._placedStart = start
            self._drag = _Drag.DRAW
            self._pending = Shape(
                kind="circle",
                coords=[start.x(), start.y(), 0.0],
                stroke=self._style[0],
                fill=self._style[2],
                stroke_width=self._style[1],
            )
            self.update()
            return

        if self._tool is Tool.POLYLINE:
            point = self._placePoint(svg, bypass)
            if not self._polyPoints or (
                self._polyPoints[-1] - point
            ).manhattanLength() > 1e-6:
                self._polyPoints.append(point)
            self.update()
            return

        if self._tool is Tool.TEXT:
            text, ok = QtWidgets.QInputDialog.getText(
                self, "Symbol text", "Text:", text="M"
            )
            if ok and text:
                point = self._placePoint(svg, bypass)
                self.addShape(
                    Shape(
                        kind="text",
                        coords=[point.x(), point.y()],
                        text=text,
                        stroke=self._style[0],
                        fill="none",
                    )
                )
            return

        if self._tool is Tool.PIN:
            point = self._placePoint(svg, bypass)
            self._hover = point
            self.addPinAt(point.x(), point.y())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        try:
            self._move(event)
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass

    def _move(self, event: QtGui.QMouseEvent) -> None:
        svg = self.toSvg(event.position())
        self._lastCursor = svg
        bypass = bool(
            event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        )
        if self._drag is _Drag.NONE:
            if self._tool is Tool.PIN:
                # live ghost at the position a click would commit to
                self._hover = self._placePoint(svg, bypass)
                self.update()
            return
        if self._drag is _Drag.PAN:
            delta = event.position() - self._widgetStart
            self._pan = self._pan + delta
            self._widgetStart = event.position()
            self.update()
            return
        if self._drag is _Drag.DRAW and self._pending is not None:
            end = self._placePoint(svg, bypass)
            x0 = self._placedStart.x()
            y0 = self._placedStart.y()
            if self._pending.kind == "line":
                self._pending.coords = [x0, y0, end.x(), end.y()]
            elif self._pending.kind == "rect":
                self._pending.coords = [
                    min(x0, end.x()), min(y0, end.y()),
                    abs(end.x() - x0), abs(end.y() - y0),
                ]
            else:  # circle
                radius = math.hypot(end.x() - x0, end.y() - y0)
                self._pending.coords = [x0, y0, radius]
            self.update()
            return
        if self._drag is _Drag.MOVE and self._dragShape is not None:
            if not self._dragPushed:
                self._pushUndo()
                self._dragPushed = True
            delta = svg - self._dragStart
            dx = delta.x() if bypass else self._snapVal(delta.x())
            dy = delta.y() if bypass else self._snapVal(delta.y())
            moved = _moveShape(self._dragShape, dx, dy)
            if self._selShape is not None:
                self._elements[self._selShape] = moved
            self._drawingDirty = True
            self.changed.emit()
            self.update()
            return
        if self._drag is _Drag.RESIZE and self._dragShape is not None:
            if not self._dragPushed:
                self._pushUndo()
                self._dragPushed = True
            resized = _resizeShape(
                self._dragShape, self._handle, self._placePoint(svg, bypass)
            )
            if self._selShape is not None:
                self._elements[self._selShape] = resized
            self._drawingDirty = True
            self.changed.emit()
            self.update()
            return
        if self._drag is _Drag.PIN_MOVE and self._dragPin is not None:
            if not self._dragPushed:
                self._pushUndo()
                self._dragPushed = True
            delta = svg - self._dragStart
            candidate = QtCore.QPointF(
                self._dragPin.x + delta.x(), self._dragPin.y + delta.y()
            )
            placed = self._placePoint(candidate, bypass)
            moved_pin = SymbolPin(self._dragPin.name, placed.x(), placed.y())
            if self._selPin is not None:
                self._pins[self._selPin] = moved_pin
            self.pinsChanged.emit()
            self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        try:
            self._release(event)
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass

    def _release(self, event: QtGui.QMouseEvent) -> None:
        if event.button() not in (
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.MiddleButton,
        ):
            return
        if self._drag is _Drag.DRAW and self._pending is not None:
            shape = self._pending
            self._pending = None
            if _shapeIsBigEnough(shape):
                self.addShape(shape)
            else:
                self.update()
        self._drag = _Drag.NONE
        self._handle = -1
        self._dragShape = None
        self._dragPin = None

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        try:
            self._doubleClick(event)
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass

    def _doubleClick(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        svg = self.toSvg(event.position())
        if self._tool is Tool.POLYLINE:
            # The second press of the double click added a duplicate
            # point - drop it, then finish with what is left.
            if len(self._polyPoints) >= 2:
                last = self._polyPoints[-1]
                if (last - self._polyPoints[-2]).manhattanLength() < 1e-6:
                    self._polyPoints.pop()
            self._finishPolyline()
            return
        if self._tool is Tool.SELECT:
            idx = self._hitShape(svg)
            if idx is None:
                return
            element = self._elements[idx]
            if isinstance(element, Shape) and element.kind == "text":
                text, ok = QtWidgets.QInputDialog.getText(
                    self, "Symbol text", "Text:", text=element.text
                )
                if ok and text and text != element.text:
                    self._pushUndo()
                    element.text = text
                    self._drawingDirty = True
                    self.changed.emit()
                    self.update()

    def _finishPolyline(self) -> None:
        points = [QtCore.QPointF(p) for p in self._polyPoints]
        self._polyPoints = []
        if len(points) < 2:
            self.update()
            return
        self.addShape(
            Shape(
                kind="polyline",
                points=[(p.x(), p.y()) for p in points],
                stroke=self._style[0],
                stroke_width=self._style[1],
            )
        )

    def _cancelPending(self) -> None:
        self._pending = None
        self._polyPoints = []
        self._drag = _Drag.NONE
        self._handle = -1
        self._dragShape = None
        self._dragPin = None
        self.update()

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        try:
            steps = event.angleDelta().y() / 120.0
            if not steps:
                return
            before = self.toSvg(event.position())
            self._zoom = max(0.15, min(60.0, self._zoom * (1.25 ** steps)))
            after = self.toSvg(event.position())
            scale = self._scale()
            self._pan = self._pan + (after - before) * scale
            self.update()
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        try:
            key = event.key()
            modifiers = event.modifiers()
            ctrl = bool(modifiers & QtCore.Qt.KeyboardModifier.ControlModifier)
            if key in (
                QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace
            ):
                self.deleteSelection()
                return
            if key == QtCore.Qt.Key.Key_Escape:
                if self._pending is not None or self._polyPoints:
                    self._cancelPending()
                    return
                if self._tool is not Tool.SELECT:
                    self.setTool(Tool.SELECT)
                    return
                super().keyPressEvent(event)
                return
            if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                if self._polyPoints:
                    self._finishPolyline()
                    return
                super().keyPressEvent(event)
                return
            if ctrl and key == QtCore.Qt.Key.Key_C:
                self.copySelection()
                return
            if ctrl and key == QtCore.Qt.Key.Key_X:
                self.cutSelection()
                return
            if ctrl and key == QtCore.Qt.Key.Key_V:
                self.pasteClipboard()
                return
            if ctrl and key == QtCore.Qt.Key.Key_Z:
                if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                    self.redo()
                else:
                    self.undo()
                return
            if ctrl and key == QtCore.Qt.Key.Key_Y:
                self.redo()
                return
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    def _setFont(self) -> None:
        font = QtGui.QFont(self.font())
        font.setPixelSize(11)
        self.setFont(font)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        try:
            self._paint(painter)
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            pass
        finally:
            if painter.isActive():
                painter.end()

    def _paint(self, painter: QtGui.QPainter) -> None:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#ffffff"))

        scale = self._scale()
        origin = self._origin()
        vb = self._viewBox
        vb_widget = QtCore.QRectF(
            origin.x(),
            origin.y(),
            vb.width() * scale,
            vb.height() * scale,
        )

        # grid (bounded by construction to the viewBox rect)
        minor = scale >= 8.0
        if minor:
            painter.setPen(QtGui.QPen(QtGui.QColor("#f2f2f2"), 1.0))
            self._drawGrid(painter, vb, 1.0)
        painter.setPen(QtGui.QPen(QtGui.QColor("#e0e0e0"), 1.0))
        self._drawGrid(painter, vb, 5.0)

        # backdrop artwork (paths/groups from external editors)
        if self._backdrop.isValid():
            self._backdrop.render(painter, vb_widget)

        # editable shapes
        for idx, element in enumerate(self._elements):
            if not isinstance(element, Shape):
                continue
            selected = idx == self._selShape
            self._drawShape(painter, element, selected)

        # in-progress polyline
        if self._polyPoints:
            painter.setPen(QtGui.QPen(QtGui.QColor("#000000"), 1.0))
            path = QtGui.QPainterPath(self.toWidget(self._polyPoints[0]))
            for point in self._polyPoints[1:]:
                path.lineTo(self.toWidget(point))
            if self._drag is not _Drag.NONE:
                path.lineTo(self.toWidget(self._lastCursor))
            painter.drawPath(path)
            painter.setBrush(QtGui.QColor("#d97706"))
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.0))
            for point in self._polyPoints:
                painter.drawEllipse(self.toWidget(point), 3.0, 3.0)

        # pending shape preview
        if self._pending is not None:
            self._drawShape(painter, self._pending, False)

        # resize handles for the selection
        shape = self.selectedShape()
        if shape is not None and self._drag in (_Drag.NONE, _Drag.RESIZE):
            painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 1.0))
            painter.setBrush(QtGui.QColor("#ffffff"))
            half = _HANDLE_PX / 2.0
            for handle in _shapeHandles(shape):
                center = self.toWidget(handle)
                painter.drawRect(
                    QtCore.QRectF(
                        center.x() - half, center.y() - half,
                        _HANDLE_PX, _HANDLE_PX,
                    )
                )

        # pins
        for idx, pin in enumerate(self._pins):
            center = self.toWidget(QtCore.QPointF(pin.x, pin.y))
            selected = idx == self._selPin
            radius = 5.5 if selected else 4.0
            color = "#d97706" if selected else "#dc2626"
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.0))
            painter.setBrush(QtGui.QColor(color))
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QtGui.QColor("#404040"))
            painter.drawText(
                QtCore.QPointF(center.x() + 6.0, center.y() - 4.0), pin.name
            )

        # pin-tool ghost: the exact point a click would commit to, so
        # the endpoint magnet is visible before you press the button
        if self._tool is Tool.PIN and self._hover is not None:
            center = self.toWidget(self._hover)
            painter.setPen(QtGui.QPen(QtGui.QColor("#d97706"), 1.5))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, 6.0, 6.0)
            painter.setBrush(QtGui.QColor("#d97706"))
            painter.drawEllipse(center, 1.5, 1.5)

        # widget frame
        painter.setPen(QtGui.QPen(QtGui.QColor("#b0b0b0"), 1.0))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _drawGrid(
        self, painter: QtGui.QPainter, vb: QtCore.QRectF, step: float
    ) -> None:
        scale = self._scale()
        x = math.ceil(vb.left() / step) * step
        while x <= vb.right() + 1e-9:
            widget = self.toWidget(QtCore.QPointF(x, vb.top()))
            painter.drawLine(
                QtCore.QPointF(widget.x(), widget.y()),
                QtCore.QPointF(
                    widget.x(),
                    widget.y() + vb.height() * scale,
                ),
            )
            x += step
        y = math.ceil(vb.top() / step) * step
        while y <= vb.bottom() + 1e-9:
            widget = self.toWidget(QtCore.QPointF(vb.left(), y))
            painter.drawLine(
                QtCore.QPointF(widget.x(), widget.y()),
                QtCore.QPointF(
                    widget.x() + vb.width() * scale, widget.y(),
                ),
            )
            y += step

    def _drawShape(
        self, painter: QtGui.QPainter, shape: Shape, selected: bool
    ) -> None:
        scale = self._scale()
        if shape.kind == "text":
            font = QtGui.QFont(self.font())
            font.setPixelSize(max(int(round(shape.font_size * scale)), 1))
            painter.setFont(font)
            metrics = QtGui.QFontMetricsF(font)
            advance = metrics.horizontalAdvance(shape.text)
            point = self.toWidget(QtCore.QPointF(*shape.coords[:2]))
            rect = QtCore.QRectF(
                point.x() - advance / 2.0,
                point.y() - shape.font_size * scale,
                advance + 2.0,
                shape.font_size * scale * 1.45,
            )
            painter.setPen(QtGui.QColor(shape.stroke))
            painter.drawText(rect, int(QtCore.Qt.AlignmentFlag.AlignLeft), shape.text)
            if selected:
                painter.setPen(
                    QtGui.QPen(QtGui.QColor("#d97706"), 1.0,
                               QtCore.Qt.PenStyle.DashLine)
                )
                painter.drawRect(rect)
            return

        width = max(shape.stroke_width * scale, 1.0)
        pen = QtGui.QPen(QtGui.QColor(shape.stroke), width)
        if selected:
            pen.setColor(QtGui.QColor("#d97706"))
            width = max(width, 1.5)
            pen.setWidthF(width)
        painter.setPen(pen)
        if shape.fill not in ("none", ""):
            painter.setBrush(QtGui.QColor(shape.fill))
        else:
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        if shape.kind == "line":
            x1, y1, x2, y2 = shape.coords
            painter.drawLine(
                self.toWidget(QtCore.QPointF(x1, y1)),
                self.toWidget(QtCore.QPointF(x2, y2)),
            )
        elif shape.kind == "rect":
            x, y, w, h = shape.coords
            top_left = self.toWidget(QtCore.QPointF(x, y))
            painter.drawRect(
                QtCore.QRectF(
                    top_left.x(), top_left.y(), w * scale, h * scale
                )
            )
        elif shape.kind == "circle":
            cx, cy, r = shape.coords
            center = self.toWidget(QtCore.QPointF(cx, cy))
            painter.drawEllipse(center, r * scale, r * scale)
        elif shape.kind == "ellipse":
            cx, cy, rx, ry = shape.coords
            center = self.toWidget(QtCore.QPointF(cx, cy))
            painter.drawEllipse(center, rx * scale, ry * scale)
        elif shape.kind == "polyline" and shape.points:
            path = QtGui.QPainterPath(
                self.toWidget(QtCore.QPointF(*shape.points[0]))
            )
            for vertex in shape.points[1:]:
                path.lineTo(self.toWidget(QtCore.QPointF(*vertex)))
            painter.drawPath(path)


# ----------------------------------------------------------------------
# shape geometry helpers (module level: pure functions, easy to test)
# ----------------------------------------------------------------------
def _shapeIsBigEnough(shape: Shape) -> bool:
    if shape.kind == "line":
        x1, y1, x2, y2 = shape.coords
        return math.hypot(x2 - x1, y2 - y1) >= 0.25
    if shape.kind == "rect":
        return shape.coords[2] >= 0.25 and shape.coords[3] >= 0.25
    if shape.kind == "circle":
        return shape.coords[2] >= 0.25
    if shape.kind == "ellipse":
        return shape.coords[2] >= 0.25 and shape.coords[3] >= 0.25
    if shape.kind == "polyline":
        return len(shape.points) >= 2
    return bool(shape.text)


def _shapeAnchor(shape: Shape) -> tuple[float, float]:
    """The point a paste positions: first vertex / top-left / center."""
    if shape.kind == "polyline" and shape.points:
        return shape.points[0]
    if len(shape.coords) >= 2:
        return (shape.coords[0], shape.coords[1])
    return (0.0, 0.0)


def _snapTargets(shape: Shape) -> list[tuple[float, float]]:
    """Points geometry snaps onto: line ends, polyline vertices and rect
    corners - the "ends of lines" of a symbol outline."""
    if shape.kind == "line":
        x1, y1, x2, y2 = shape.coords
        return [(x1, y1), (x2, y2)]
    if shape.kind == "polyline":
        return list(shape.points)
    if shape.kind == "rect":
        x, y, w, h = shape.coords
        return [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    return []


def _moveShape(shape: Shape, dx: float, dy: float) -> Shape:
    moved = _cloneShape(shape)
    if moved.kind == "polyline":
        moved.points = [(x + dx, y + dy) for x, y in moved.points]
    elif moved.kind == "text":
        moved.coords = [moved.coords[0] + dx, moved.coords[1] + dy]
    else:
        moved.coords = [c + (dx if i % 2 == 0 else dy)
                        for i, c in enumerate(moved.coords)]
    return moved


def _shapeHandles(shape: Shape) -> list[QtCore.QPointF]:
    if shape.kind == "line":
        x1, y1, x2, y2 = shape.coords
        return [QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2)]
    if shape.kind == "rect":
        x, y, w, h = shape.coords
        return [
            QtCore.QPointF(x, y),
            QtCore.QPointF(x + w, y),
            QtCore.QPointF(x, y + h),
            QtCore.QPointF(x + w, y + h),
        ]
    if shape.kind == "circle":
        cx, cy, r = shape.coords
        return [QtCore.QPointF(cx + r, cy)]
    if shape.kind == "ellipse":
        cx, cy, rx, ry = shape.coords
        return [QtCore.QPointF(cx + rx, cy), QtCore.QPointF(cx, cy + ry)]
    if shape.kind == "polyline":
        return [QtCore.QPointF(x, y) for x, y in shape.points]
    return []


def _resizeShape(shape: Shape, handle: int, point: QtCore.QPointF) -> Shape:
    resized = _cloneShape(shape)
    cx = point.x()
    cy = point.y()
    if shape.kind == "line" and handle in (0, 1):
        resized.coords[handle * 2] = cx
        resized.coords[handle * 2 + 1] = cy
    elif shape.kind == "rect" and handle in (0, 1, 2, 3):
        x, y, w, h = shape.coords
        fixed = [
            QtCore.QPointF(x + w, y + h),
            QtCore.QPointF(x, y + h),
            QtCore.QPointF(x + w, y),
            QtCore.QPointF(x, y),
        ][handle]
        new_x = min(fixed.x(), cx)
        new_y = min(fixed.y(), cy)
        resized.coords = [
            new_x, new_y,
            max(abs(cx - fixed.x()), 0.25),
            max(abs(cy - fixed.y()), 0.25),
        ]
    elif shape.kind == "circle" and handle == 0:
        sx, sy, _r = shape.coords
        resized.coords[2] = max(math.hypot(cx - sx, cy - sy), 0.25)
    elif shape.kind == "ellipse" and handle in (0, 1):
        sx, sy, _rx, _ry = shape.coords
        if handle == 0:
            resized.coords[2] = max(abs(cx - sx), 0.25)
        else:
            resized.coords[3] = max(abs(cy - sy), 0.25)
    elif shape.kind == "polyline" and 0 <= handle < len(resized.points):
        resized.points[handle] = (cx, cy)
    return resized


def _shapeHit(shape: Shape, point: QtCore.QPointF, tol: float) -> bool:
    px = point.x()
    py = point.y()
    if shape.kind == "line":
        x1, y1, x2, y2 = shape.coords
        return _segDistance(px, py, x1, y1, x2, y2) <= tol
    if shape.kind == "polyline":
        points = shape.points
        for idx in range(len(points) - 1):
            ax, ay = points[idx]
            bx, by = points[idx + 1]
            if _segDistance(px, py, ax, ay, bx, by) <= tol:
                return True
        return False
    if shape.kind == "rect":
        x, y, w, h = shape.coords
        if shape.fill not in ("none", "") and x <= px <= x + w and y <= py <= y + h:
            return True
        return (
            _segDistance(px, py, x, y, x + w, y) <= tol
            or _segDistance(px, py, x + w, y, x + w, y + h) <= tol
            or _segDistance(px, py, x + w, y + h, x, y + h) <= tol
            or _segDistance(px, py, x, y + h, x, y) <= tol
        )
    if shape.kind == "circle":
        cx, cy, r = shape.coords
        if r <= 0:
            return False
        distance = math.hypot(px - cx, py - cy)
        if shape.fill not in ("none", "") and distance <= r:
            return True
        return abs(distance - r) <= tol
    if shape.kind == "ellipse":
        cx, cy, rx, ry = shape.coords
        if rx <= 0 or ry <= 0:
            return False
        q = math.hypot((px - cx) / rx, (py - cy) / ry)
        if shape.fill not in ("none", "") and q <= 1.0:
            return True
        return abs(q - 1.0) * min(rx, ry) <= tol
    if shape.kind == "text":
        x, y = shape.coords
        width = max(len(shape.text), 1) * shape.font_size * 0.62
        return (
            x - width / 2.0 - tol <= px <= x + width / 2.0 + tol
            and y - shape.font_size - tol <= py <= y + shape.font_size * 0.45 + tol
        )
    return False


class SymbolEditor(QtWidgets.QDialog):
    """Full symbol editor: drawing canvas + pins + metadata + style."""

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
        self.setWindowTitle("Symbol editor - %s" % os.path.basename(path))
        self.setModal(True)

        with open(path, "r", encoding="utf-8") as handle:
            svg = handle.read()

        self.canvas = SymbolCanvas(self)
        self.canvas.setDocument(svg, pins)
        self.canvas.changed.connect(self._onCanvasChanged)
        self.canvas.selectionChanged.connect(self._onSelection)
        self.canvas.pinsChanged.connect(self._reloadTable)

        # --- tool bar ------------------------------------------------
        self._toolActions: dict[Tool, QtGui.QAction] = {}
        toolbar = QtWidgets.QToolBar(self)
        toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        group = QtGui.QActionGroup(self)
        group.setExclusive(True)
        for tool, label in (
            (Tool.SELECT, "Select"),
            (Tool.LINE, "Line"),
            (Tool.RECT, "Rect"),
            (Tool.CIRCLE, "Circle"),
            (Tool.POLYLINE, "Polyline"),
            (Tool.TEXT, "Text"),
            (Tool.PIN, "Pin"),
        ):
            action = QtGui.QAction(label, self)
            action.setCheckable(True)
            group.addAction(action)
            toolbar.addAction(action)
            action.triggered.connect(
                lambda _checked=False, t=tool: self.canvas.setTool(t)
            )
            self._toolActions[tool] = action
        self._toolActions[Tool.SELECT].setChecked(True)
        self.canvas.toolChanged.connect(self._syncToolActions)

        toolbar.addSeparator()
        snapAction = QtGui.QAction("Snap", self)
        snapAction.setCheckable(True)
        snapAction.setChecked(True)
        snapAction.toggled.connect(self.canvas.setSnap)
        toolbar.addAction(snapAction)

        fitAction = QtGui.QAction("Fit", self)
        fitAction.triggered.connect(lambda _c=False: self.canvas.fitView())
        toolbar.addAction(fitAction)

        toolbar.addSeparator()
        self.undoAction = QtGui.QAction("Undo", self)
        self.undoAction.setShortcut("Ctrl+Z")
        self.undoAction.setEnabled(False)
        self.undoAction.triggered.connect(lambda _c=False: self.canvas.undo())
        toolbar.addAction(self.undoAction)

        self.redoAction = QtGui.QAction("Redo", self)
        self.redoAction.setShortcut("Ctrl+Shift+Z")
        self.redoAction.setEnabled(False)
        self.redoAction.triggered.connect(lambda _c=False: self.canvas.redo())
        toolbar.addAction(self.redoAction)

        # --- pin table ----------------------------------------------
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Pin", "X", "Y"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.itemSelectionChanged.connect(self._onTableSelection)
        self.table.itemChanged.connect(self._onTableChanged)

        addBtn = QtWidgets.QPushButton("Add pin", self)
        addBtn.clicked.connect(self._addPinRow)
        removeBtn = QtWidgets.QPushButton("Remove pin", self)
        removeBtn.clicked.connect(self._removePinRow)
        hint = QtWidgets.QLabel(
            "Pin tool: click the canvas to add a pin; drag dots to move "
            "them. Ends snap to line ends and corners - including the "
            "imported artwork of existing symbols (the orange ring shows "
            "where a click lands); hold Ctrl for free placement. "
            "Ctrl+C/X/V copy, cut and paste shapes and pins.",
            self,
        )
        hint.setWordWrap(True)

        self.descriptionEdit = QtWidgets.QLineEdit(description, self)
        self.descriptionEdit.setPlaceholderText("Description")
        self.refEdit = QtWidgets.QLineEdit(ref, self)
        self.refEdit.setPlaceholderText("Reference prefix (e.g. K, R, Y)")
        self.refEdit.setValidator(
            QtGui.QRegularExpressionValidator(
                QtCore.QRegularExpression("[A-Za-z0-9.]*"), self.refEdit
            )
        )

        # --- style controls ------------------------------------------
        self.strokeBtn = QtWidgets.QPushButton("Stroke", self)
        self.strokeBtn.clicked.connect(self._pickStroke)
        self.widthSpin = QtWidgets.QDoubleSpinBox(self)
        self.widthSpin.setRange(0.1, 5.0)
        self.widthSpin.setSingleStep(0.1)
        self.widthSpin.setDecimals(2)
        self.widthSpin.setValue(self.canvas.drawingStyle()[1])
        self.widthSpin.valueChanged.connect(self._widthChanged)
        self.fillCombo = QtWidgets.QComboBox(self)
        self.fillCombo.addItem("Fill: none", "none")
        self.fillCombo.addItem("Fill: white", "#ffffff")
        self.fillCombo.addItem("Fill: black", "#000000")
        self.fillCombo.currentIndexChanged.connect(self._fillChanged)
        self._syncStyleControls()

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
        styleRow = QtWidgets.QHBoxLayout()
        styleRow.addWidget(self.strokeBtn)
        styleRow.addWidget(self.widthSpin)
        right.addLayout(styleRow)
        right.addWidget(self.fillCombo)
        rightWidget = QtWidgets.QWidget(self)
        rightWidget.setLayout(right)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addWidget(toolbar)
        splitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal, self
        )
        splitter.addWidget(self.canvas)
        splitter.addWidget(rightWidget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, 1)
        outer.addWidget(buttons)

        self._reloadTable()
        self.resize(900, 560)

    # ------------------------------------------------------------------
    def _syncToolActions(self) -> None:
        action = self._toolActions.get(self.canvas.tool())
        if action is not None and not action.isChecked():
            action.setChecked(True)

    def _onCanvasChanged(self) -> None:
        self.undoAction.setEnabled(self.canvas.canUndo)
        self.redoAction.setEnabled(self.canvas.canRedo)
        self._syncStyleControls()

    def _onSelection(self) -> None:
        self._syncStyleControls()
        pin_idx = self.canvas.selectedPinIndex()
        if pin_idx is not None and pin_idx != self.table.currentRow():
            self.table.selectRow(pin_idx)

    def _syncStyleControls(self) -> None:
        shape = self.canvas.selectedShape()
        stroke, width, fill = (
            (shape.stroke, shape.stroke_width, shape.fill)
            if shape is not None
            else self.canvas.drawingStyle()
        )
        self.widthSpin.blockSignals(True)
        self.fillCombo.blockSignals(True)
        self.widthSpin.setValue(width)
        fill_idx = self.fillCombo.findData(fill)
        self.fillCombo.setCurrentIndex(fill_idx if fill_idx >= 0 else 0)
        self.widthSpin.blockSignals(False)
        self.fillCombo.blockSignals(False)
        self.strokeBtn.setStyleSheet(
            "QPushButton { background-color: %s; color: %s; }"
            % (stroke, "#ffffff" if stroke != "#ffffff" else "#000000")
        )

    def _pickStroke(self, _checked: bool = False) -> None:
        shape = self.canvas.selectedShape()
        current = shape.stroke if shape is not None else self.canvas.drawingStyle()[0]
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Stroke color"
        )
        if color.isValid():
            self.canvas.applyStyle(stroke=color.name())

    def _widthChanged(self, value: float) -> None:
        self.canvas.applyStyle(width=float(value))

    def _fillChanged(self, index: int) -> None:
        data = self.fillCombo.itemData(index)
        if isinstance(data, str):
            self.canvas.applyStyle(fill=data)

    # ------------------------------------------------------------------
    def _reloadTable(self) -> None:
        pins = self.canvas.pins
        self.table.blockSignals(True)
        self.table.setRowCount(len(pins))
        for row, pin in enumerate(pins):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(pin.name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem("%g" % pin.x))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem("%g" % pin.y))
        self.table.blockSignals(False)
        pin_idx = self.canvas.selectedPinIndex()
        if pin_idx is not None and pin_idx < self.table.rowCount():
            self.table.selectRow(pin_idx)

    def _onTableSelection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.canvas.selectPin(rows[0].row())

    def _onTableChanged(self, _item: QtWidgets.QTableWidgetItem) -> None:
        pins: list[SymbolPin] = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            x_item = self.table.item(row, 1)
            y_item = self.table.item(row, 2)
            name = name_item.text().strip() if name_item is not None else ""
            try:
                x = float(x_item.text()) if x_item is not None else 0.0
                y = float(y_item.text()) if y_item is not None else 0.0
            except ValueError:
                x, y = -1.0, -1.0   # rejected by validatePins
            pins.append(SymbolPin(name=name, x=x, y=y))
        self.canvas.setPins(pins)

    def _addPinRow(self) -> None:
        self.canvas.addPinCentered()

    def _removePinRow(self) -> None:
        # only ever removes the selected PIN (the button's promise) -
        # a selected shape must not vanish behind "Remove pin".
        if self.canvas.selectedPinIndex() is not None:
            self.canvas.deleteSelection()

    # ------------------------------------------------------------------
    def save(self) -> str | None:
        """Write the file. Returns None on success or an error message
        (no dialogs - the caller shows them, tests can assert on them)."""
        pins = self.canvas.pins
        error = validatePins(pins)
        if error is not None:
            return error
        description = self.descriptionEdit.text()
        ref = self.refEdit.text()
        try:
            if self.canvas.drawingDirty:
                saveSymbolFile(
                    self.path,
                    self.canvas.elements,
                    pins,
                    description=description,
                    ref=ref,
                )
            else:
                writeSymbol(
                    self.path,
                    pins,
                    description=description,
                    ref=ref,
                )
        except (OSError, ValueError) as exc:
            return "Could not save %s: %s" % (self.path, exc)
        if self.cacheKey is not None:
            invalidate(self.cacheKey)
        return None

    def accept(self) -> None:
        error = self.save()
        if error is not None:
            QtWidgets.QMessageBox.warning(self, "Symbol editor", error)
            return
        super().accept()
