# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeViewAndScene.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import math
from typing import Any

from PySide6 import QtGui, QtCore, QtWidgets
from Schematics.Features.Utils.Snap import constrainAngle, snap
from Schematics.Features.Utils.Sheets import pageIndex
from Schematics.Features.Utils.QtEnums import *
from Schematics.Features.SchemeContextMenu import ContextMenu
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.CursorItemMixin import *

class SchemeGraphicsView(CursorItemMixin, QtWidgets.QGraphicsView):

    def __init__(self) -> None:
        super().__init__()
        #self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag) #ScrollHandDrag)
        self.setMouseTracking(True)
        self.setCacheMode(QtWidgets.QGraphicsView.CacheModeFlag.CacheBackground)
        self.panning = False
        self.instance = None
        self.currentObj = None

    def getScale(self) -> float:
        t = self.transform()
        scalex = math.sqrt(t.m11() * t.m11() + t.m12() * t.m12())
        scaley = math.sqrt(t.m21() * t.m21() + t.m22() * t.m22())
        scale = (scalex+scaley)/2
        return scale

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        # While drawing a wire the right button cancels instead of opening
        # the context menu (this view sees the event before the scene).
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            sc = self.scene()
            if isinstance(sc, SchemeGraphicsScene) and sc.drawingWire:
                sc.cancelWireDraw()
                event.accept()
                return
        # Update on left click (selection/deselection)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.instance is not None:
                if self.currentObj is not None and self.currentObj.Proxy.item.drawMode is True:
                    pass
                else:
                    self.currentObj = Draw(self.instance())
            self.scene().update()
        # ! call super().mousePressEvent only after object is create
        super().mousePressEvent(event)
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            # rubber mode of
            self.sceneCenter = self.mapToScene(self.viewport().rect().center())
            # Qt6: QMouseEvent.localPos() is deprecated in favor of position()
            self.startPos = event.position()
            self.panning = True
            self.viewport().setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            self.viewport().unsetCursor()
            if self.instance is not None and self.currentObj is not None:
                if self.currentObj.Proxy.item.doNotResetInstance:
                    self.currentObj.Proxy.item.doNotResetInstance = False
                else:
                    self.instance = None
                    self.underCursorItem = None
                    self.currentObj = None
            else:
                contextMenu = ContextMenu(self)
                contextMenu.addStandartActions()
                # Qt6: globalPos() is deprecated in favor of globalPosition()
                contextMenu.invokeAt(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            # rubber mode on
            self.panning = False
            self.viewport().unsetCursor() #QtCore.Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        #print(f"mmove event {event.position()}, {self.mapToScene(event.pos())}")
        if self.underCursorItem is not None:
            self.underCursorItem.mousePos(self.mapToScene(event.pos()))
        overItem: Any = self.itemAt(event.position().toPoint())
        #if hasattr(overItem, "drawMode") and overItem.drawMode:
        sc = self.scene()
        if self.instance is not None or (isinstance(sc, SchemeGraphicsScene) and sc.drawingWire):
            self.viewport().setCursor(QtCore.Qt.CursorShape.CrossCursor)
        else:
            if overItem is not None and (overItem.flags() & QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable):
                self.viewport().setCursor(overItem.getCursor())
            else:
                self.viewport().setCursor(QtCore.Qt.CursorShape.ArrowCursor)

        if self.panning:
            self.centerOn(self.sceneCenter + (self.startPos - event.position()) * (1.0 / self.getScale()))
        super().mouseMoveEvent(event)

    def zoom(self, factor: float) -> None:
        self.scale(factor, factor)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        # print("mwheel event", event)
        if event.angleDelta().y() > 0:
            self.zoom(1.25)
        else:
            self.zoom(0.8)

# ---------------------------------------------------------------------------------------

class SchemeGraphicsScene(QtWidgets.QGraphicsScene):
    
    def __init__(self, obj: Any) -> None:
        super().__init__()
        self.obj = obj
        self.vobj = obj.ViewObject
        self.mouseCurPos: QtCore.QPointF | None = None
        self.points: list[Any] = []
        # Interactive wire drawing state (startWireDraw / finishWireDraw)
        self.drawingWire: bool = False
        self.wirePoints: list[QtCore.QPointF] = []

    #def drawBackground(self, g, rect):
    #   print("drawBackground")

    def drawForeground(self, painter: QtGui.QPainter, rect: QtCore.QRectF | QtCore.QRect) -> None:
        g = painter   # base stubs name this parameter "painter"
        ### g.drawText(50, 50, str(len(self.items())))

        # ! Do not paint anything while the file is loading.
        # FreeCAD raises ReferenceError (not AttributeError) when a deleted
        # object is touched and hasattr() does not swallow it — without the
        # try below this spams one traceback per repaint after the document
        # holding the sheet was closed.
        try:
            if not hasattr(self.obj, "Proxy"):
                return
        except ReferenceError:
            self.retireStaleWindow()
            return

        #svg = self.obj.Proxy.svg_template
        #svg.paint(g, None, None)

        # Show grid
        if self.vobj.GridVisible:

            minorBrush = QtGui.QColor.fromRgbF(*self.vobj.MinorGridLineColor)
            minorPen = QtGui.QPen(minorBrush, self.vobj.MinorGridLineWidth.Value,
                QtLineStyles[self.vobj.MinorGridLineStyle], QtCore.Qt.PenCapStyle.FlatCap, QtCore.Qt.PenJoinStyle.RoundJoin)

            majorBrush = QtGui.QColor.fromRgbF(*self.vobj.MajorGridLineColor)
            majorPen = QtGui.QPen(majorBrush, self.vobj.MajorGridLineWidth.Value,
                QtLineStyles[self.vobj.MajorGridLineStyle], QtCore.Qt.PenCapStyle.SquareCap, QtCore.Qt.PenJoinStyle.RoundJoin)

            g.setPen(minorPen)

            minorGridStep = self.vobj.GridSpacing.Value
            majorGridStep = self.vobj.MajorGridLineEvery
            sheetWidth = self.vobj.Width
            sheetHeight = self.vobj.Height

            minorLinesIsVisible = self.obj.Proxy.view.getScale() > 3
            
            i = 0
            for x in range(0, int(sheetWidth/minorGridStep)):
                xd = x * minorGridStep
                if rect.left() < xd < rect.right():
                    if i % majorGridStep == 0:
                        g.setPen(majorPen)
                        g.drawLine(QtCore.QPointF(xd, 0), QtCore.QPointF(xd, sheetHeight))
                        g.setPen(minorPen)
                    elif minorLinesIsVisible:
                        g.drawLine(QtCore.QPointF(xd, 0), QtCore.QPointF(xd, sheetHeight))
                i += 1
            i = 0    
            for y in range(0, int(sheetHeight/minorGridStep)):
                yd = y * minorGridStep
                if rect.top() < yd < rect.bottom():
                    if i % majorGridStep == 0:
                        g.setPen(majorPen)
                        g.drawLine(QtCore.QPointF(0, yd), QtCore.QPointF(sheetWidth, yd))
                        g.setPen(minorPen)
                    elif minorLinesIsVisible:
                        g.drawLine(QtCore.QPointF(0, yd), QtCore.QPointF(sheetWidth, yd))
                i += 1

        # Wire drawing preview: committed vertices + rubber line to cursor
        if self.drawingWire and self.wirePoints:
            pen = QtGui.QPen(QtGui.QColor.fromRgbF(*self.obj.LinesColor), 1.0)
            pen.setCosmetic(True)
            g.setPen(pen)
            g.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            path = QtGui.QPainterPath(self.wirePoints[0])
            for p in self.wirePoints[1:]:
                path.lineTo(p)
            if self.mouseCurPos is not None:
                # Rubber segment with the same posture/pin resolution the
                # click will use, so the preview shows the exact landing.
                last = self.wirePoints[-1]
                path.lineTo(self._resolveWirePoint(self.mouseCurPos, last))
            g.drawPath(path)
            for p in self.wirePoints:
                g.drawEllipse(p, 2.0, 2.0)

        # Page number, bottom right (multi-page projects)
        try:
            page, total = pageIndex(self.obj)
            if page:
                g.setPen(QtGui.QPen(QtGui.QColor.fromRgbF(*self.obj.LinesColor)))
                font = g.font()
                font.setPixelSize(6)
                g.setFont(font)
                sheet_w = float(self.vobj.Width.Value)
                sheet_h = float(self.vobj.Height.Value)
                g.drawText(
                    QtCore.QRectF(sheet_w - 70.0, sheet_h - 9.0, 64.0, 8.0),
                    int(QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignBottom),
                    "Page %d of %d" % (page, total),
                )
        except (ReferenceError, RuntimeError, AttributeError, TypeError):
            pass   # sheet/document tearing down mid-paint

    def retireStaleWindow(self) -> None:
        """ Close the MDI window bound to a deleted document object.

        Deferred with a zero timer because this is called from inside a
        paint event, where destroying widgets is not allowed. """
        if getattr(self, "_retiring", False):
            return
        self._retiring = True

        def _close():
            for view in self.views():
                widget: QtWidgets.QWidget | None = view
                while widget is not None:
                    if widget.__class__.__name__ == 'SchemeMDIView':
                        try:
                            widget.close()
                        except RuntimeError:
                            pass   # already destroyed
                        return
                    widget = widget.parentWidget()

        QtCore.QTimer.singleShot(0, _close)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.drawingWire:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                pos = event.scenePos()
                if self.wirePoints and self._isConnectionPoint(pos):
                    # KiCad: clicking a pin or another wire completes the
                    # wire there - and the tool stays armed so the next
                    # click starts a new one.
                    if self.wireAppendPoint(pos):
                        self.finishWireDraw()
                else:
                    self.wireAppendPoint(pos)
                event.accept()
                return
            if event.button() == QtCore.Qt.MouseButton.RightButton:
                self.cancelWireDraw()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        # Double-click finishes the wire: the second press already appended
        # the final vertex in mousePressEvent.
        if self.drawingWire and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.finishWireDraw()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # Enter finishes the wire, Escape cancels it (KiCad: finish/cancel).
        if self.drawingWire:
            if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                self.finishWireDraw()
                event.accept()
                return
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.cancelWireDraw()
                event.accept()
                return
        if event.key() == QtCore.Qt.Key.Key_Escape:
            # KiCad: Esc cancels the current tool, else clears the selection.
            self._cancelPlacementTool()
            self.clearSelection()
            FreeCAD.Gui.Selection.clearSelection()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Home:
            # KiCad: Home zooms to fit the sheet.
            template = getattr(self, "svg_template", None)
            if template is not None:
                rect = template.sceneBoundingRect().adjusted(-20, -20, 20, 20)
                for view in self.views():
                    view.fitInView(rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            event.accept()
            return
        if event.key() in (QtCore.Qt.Key.Key_PageUp, QtCore.Qt.Key.Key_PageDown):
            # KiCad: Page Up / Page Down switch sheets.
            from Schematics.Features.Utils.MDI import cycleSheet
            delta = -1 if event.key() == QtCore.Qt.Key.Key_PageUp else 1
            cycleSheet(delta)
            event.accept()
            return
        super().keyPressEvent(event)

    def _cancelPlacementTool(self) -> None:
        """Reset an active symbol-placement tool (KiCad Esc behaviour)."""
        for view in self.views():
            if hasattr(view, "instance"):
                setattr(view, "instance", None)
                setattr(view, "currentObj", None)
                setattr(view, "underCursorItem", None)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        self.snapItemsToGrid()
        super().mouseReleaseEvent(event)

    # This method generate transaction
    def snapItemsToGrid(self) -> None:
        # Snap items to grid after it's position is updated
        items: list[Any] = []
        for item in self.selectedItems():
            if hasattr(item, "positionUpdated") and item.positionUpdated:
                items.append(item)
        if items:
            #itemsStr = " ".join(map(lambda i: i.obj.Name, items))  # List of items (Deprecated)
            name = items[0].obj.Name if len(items) == 1 else str(len(items)) + " Items"
            message = f"Position of {name} is changed"
            # It is necessary to clear the selected elements, 
            # otherwise elements from different sheets may be copied.
            #FreeCAD.Gui.Selection.clearSelection()
            doc = FreeCAD.ActiveDocument
            if doc is None:
                return
            doc.openTransaction(message)
            for item in items:
                item.positionUpdated = False
                item.obj.X = item.x()
                item.obj.Y = item.y()
                #FreeCAD.Gui.doCommand(f'FreeCAD.ActiveDocument.getObject("{item.obj.Name}").X = {item.x()}')
                #FreeCAD.Gui.doCommand(f'FreeCAD.ActiveDocument.getObject("{item.obj.Name}").Y = {item.y()}')
                FreeCAD.Gui.Selection.addSelection(item.obj)                
            doc.commitTransaction()
            doc.recompute()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        # print(f"{event.scenePos()}")
        self.mouseCurPos = event.scenePos()
        self.update()       # mandatory for draw lines
        super().mouseMoveEvent(event)

#    def wheelEvent(self, event):
#        super().wheelEvent(event)
 
    def clear(self) -> None:
        self.points.clear()
        self.drawingWire = False
        self.wirePoints.clear()
        self.update()

    # ------------------------------------------------------------------
    # Interactive wire drawing
    # ------------------------------------------------------------------
    def startWireDraw(self) -> None:
        """Enter wire drawing mode: click vertices, double-click or Enter to
        finish, Escape or right-click to cancel."""
        self.drawingWire = True
        self.wirePoints = []
        self._cancelPlacementTool()
        self.update()

    def cancelWireDraw(self) -> None:
        self.drawingWire = False
        self.wirePoints = []
        self.update()

    def finishWireDraw(self) -> None:
        """Complete the current wire; the tool stays armed so the next click
        starts a new one (KiCad behaviour). Escape or right-click exits."""
        points = list(self.wirePoints)
        self.wirePoints = []
        self.update()
        if len(points) < 2:
            return
        from Schematics.Features.Items.Wire import Wire
        Wire(points=points, sheet=self.obj)

    def wirePinTolerance(self) -> float:
        """Snap radius for wire ends: a fraction of the grid spacing."""
        try:
            return float(self.vobj.GridSpacing.Value) * 0.6
        except (ReferenceError, AttributeError, RuntimeError, TypeError):
            return 3.0

    def nearestWirePin(self, pos: QtCore.QPointF) -> QtCore.QPointF | None:
        """Scene position of the closest symbol pin within tolerance.

        Pins live on symbol items (``SymbolItem.pins``: (name, x, y) in item
        local coordinates); mapToScene applies the item transform so rotated
        symbols snap correctly.
        """
        tol = self.wirePinTolerance()
        best: QtCore.QPointF | None = None
        bestDist = tol
        for item in self.items():
            if getattr(item, "drawMode", False):
                continue   # preview/cursor item, not a placed symbol
            pins = getattr(item, "pins", None)
            if not pins:
                continue
            for pin in pins:
                try:
                    _name, px, py = pin
                    scenePos = item.mapToScene(QtCore.QPointF(px, py))
                except (ReferenceError, RuntimeError, TypeError, ValueError, AttributeError):
                    continue
                dist = math.hypot(scenePos.x() - pos.x(), scenePos.y() - pos.y())
                if dist <= bestDist:
                    bestDist = dist
                    best = scenePos
        return best

    def wireAppendPoint(self, pos: QtCore.QPointF) -> bool:
        """Append the next wire vertex through _resolveWirePoint; returns
        False when the point duplicates the previous one (ignored)."""
        last = self.wirePoints[-1] if self.wirePoints else None
        point = self._resolveWirePoint(pos, last)
        if last is not None and math.hypot(
            point.x() - last.x(), point.y() - last.y()
        ) < 0.25:
            return False
        self.wirePoints.append(point)
        self.update()
        return True

    def _resolveWirePoint(
        self,
        pos: QtCore.QPointF,
        last: QtCore.QPointF | None,
    ) -> QtCore.QPointF:
        """Where a wire click lands: pins win (connections beat posture),
        otherwise KiCad-style H/V/45-degree posture from the previous
        vertex, then grid snap."""
        pin = self.nearestWirePin(pos)
        if pin is not None:
            return pin
        if last is None:
            return snap(pos, self.obj)
        return snap(constrainAngle(last, pos), self.obj)

    def _isConnectionPoint(self, pos: QtCore.QPointF) -> bool:
        """True when pos sits on a symbol pin or on an existing wire - the
        places where a click should complete the wire being drawn."""
        if self.nearestWirePin(pos) is not None:
            return True
        from Schematics.Features.Utils.Connectivity import onWireBody
        return onWireBody(self.obj, pos)
