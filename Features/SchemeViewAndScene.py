# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeViewAndScene.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
import math
from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.Utils.Snap import snap
from Features.Utils.QtEnums import *

class SchemeGraphicsView(QtWidgets.QGraphicsView):

    def __init__(self):
        super().__init__()
        #self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        #self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        #self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.setViewportUpdateMode(self.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(self.RubberBandDrag) #ScrollHandDrag)
        self.setMouseTracking(True)
        self.setCacheMode(self.CacheNone)
        self.dragMode = False

    def getScale(self):
        t = self.transform()
        scalex = math.sqrt(t.m11() * t.m11() + t.m12() * t.m12())
        scaley = math.sqrt(t.m21() * t.m21() + t.m22() * t.m22())
        scale = (scalex+scaley)/2
        return scale

    def mousePressEvent(self, event):
        # print("mpress event", event)
        if event.button() == QtCore.Qt.MiddleButton:
            # rubber mode of
            self.sceneCenter = self.mapToScene(self.viewport().rect().center())
            self.startPos = event.localPos()
            self.dragMode = True
            self.viewport().setCursor(QtCore.Qt.ClosedHandCursor) 
        super().mousePressEvent(event)
   
    def mouseReleaseEvent(self, event):
        # print("mrelease event", event)
        if event.button() == QtCore.Qt.MiddleButton:
            # rubber mode on
            self.dragMode = False
            self.viewport().setCursor(QtCore.Qt.ArrowCursor) 
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        #print(f"mmove event {event.localPos()}")
        overItem = self.itemAt(event.localPos().toPoint())
        if overItem is not None and (overItem.flags() & overItem.ItemIsSelectable):
            self.setCursor(QtCore.Qt.SizeAllCursor)
        else:
            self.setCursor(QtCore.Qt.ArrowCursor)

        if self.dragMode:
            self.centerOn(self.sceneCenter + (self.startPos - event.localPos()) / self.getScale())
        super().mouseMoveEvent(event)

    def zoom(self, factor):
        self.scale(factor, factor)

    def wheelEvent(self, event):
        # print("mwheel event", event)
        if event.angleDelta().y() > 0:
            self.zoom(1.25)
        else:
            self.zoom(0.8)

# ---------------------------------------------------------------------------------------

class drawWireMode:

    def __init__(self, obj, scene, points):
        self.obj = obj
        self.scene = scene
        self.points = points
        self.drawingMode(True)

    def __del__(self):
        # If user start draw wire, terminate that
        if len(self.points) > 0:
            if self.points[-1] is not None:
                self.points.append(None)
        self.drawingMode(False)
        #print(f'drawWireMode class destructed')

    def drawingMode(self, status):
        print(f'!!! setInteractive({not status})')
        ### self.obj.Proxy.view.setInteractive(not status)
        for item in self.scene.items():
            if hasattr(item, "pinsXY"):
                item.setFlag(item.ItemIsMovable, not status)
                item.setFlag(item.ItemIsSelectable, not status)

    def drawForeground(self, g, rect):
        # Highlight pins
        pinsPen = QtGui.QPen(QtCore.Qt.red, 0.5, QtCore.Qt.SolidLine)
        g.setPen(pinsPen)
        s = 1.5
        for item in self.scene.items():
            if hasattr(item, "pinsXY"):
                for pin in item.pinsXY:
                    name, x, y = pin
                    g.drawLine(QtCore.QPointF(x - s, y - s), QtCore.QPointF(x + s, y + s))
                    g.drawLine(QtCore.QPointF(x - s, y + s), QtCore.QPointF(x + s, y - s))

    def mousePressEvent(self, event):
        cursorScenePos = event.scenePos()
        self.curpos = snap(cursorScenePos, self.obj)
        if event.button() == QtCore.Qt.LeftButton:
            if len(self.points) == 0:
                self.points.append(self.curpos)
            else:
                prev = self.points[-1]   # last element
                if prev is None:
                    self.points.append(self.curpos)
                else:
                    if self.curpos.x() == prev.x() or self.curpos.y() == prev.y():
                        self.points.append(self.curpos)
                    else:
                        # !!! if the length is >3 grid steps, remember the course of the wire and do not change it.
                        if abs(self.curpos.x()-prev.x()) < abs(self.curpos.y()-prev.y()):
                            self.points.append(QtCore.QPointF(prev.x(), self.curpos.y()))
                            self.points.append(self.curpos)
                        else:
                            self.points.append(QtCore.QPointF(self.curpos.x(), prev.y()))
                            self.points.append(self.curpos)
        if event.button() == QtCore.Qt.RightButton:
            if len(self.points) > 0  and self.points[-1] is not None:
                self.points.append(None)
            else:
                self.scene.disableAllModes()
        #self.update()

# ---------------------------------------------------------------------------------------

class SchemeGraphicsScene(QtWidgets.QGraphicsScene):
    
    def __init__(self, obj):
        super().__init__()
        self.obj = obj
        self.mode = None
        self.mouseCurPos = None
        self.points = []

    def disableAllModes(self):
        self.mode = None
        self.update()

    def enableDrawWireMode(self):
        self.mode = drawWireMode(self.obj, self, self.points)
        self.update()

    def drawWires(self, g, curpos):
        g.setRenderHints(g.RenderHint.Antialiasing | g.RenderHint.TextAntialiasing)

        # Draw wires
        prev = None
        brush = QtGui.QColor.fromRgbF(*self.obj.Proxy.appearance.linesColor())
        wirePen = QtGui.QPen(brush, 0.5, QtCore.Qt.SolidLine)
        g.setPen(wirePen)
        for p in self.points:
            if prev is not None and p is not None:
                g.drawLine(prev, p)
            prev = p

        if curpos is not None:
            curpos = snap(curpos, self.obj)
            if prev is not None:
                if curpos.x() == prev.x() or curpos.y() == prev.y():
                    g.drawLine(prev, curpos)
                else:
                    if abs(curpos.x() - prev.x()) < abs(curpos.y() - prev.y()):
                        g.drawLine(prev, QtCore.QPointF(prev.x(), curpos.y()))
                        g.drawLine(QtCore.QPointF(prev.x(), curpos.y()), curpos)
                    else:
                        g.drawLine(prev, QtCore.QPointF(curpos.x(), prev.y()))
                        g.drawLine(QtCore.QPointF(curpos.x(), prev.y()), curpos)

    def drawForeground(self, g, rect):
        # Draw wires
        self.drawWires(g, self.mouseCurPos)

        if self.mode is not None:
            self.mode.drawForeground(g, rect)

        # Show grid
        if self.obj.GridVisible:

            minorBrush = QtGui.QColor.fromRgbF(*self.obj.MinorGridLineColor)
            minorPen = QtGui.QPen(minorBrush, self.obj.MinorGridLineWidth.Value, QtLineStyles[self.obj.MinorGridLineStyle])

            majorBrush = QtGui.QColor.fromRgbF(*self.obj.MajorGridLineColor)
            majorPen = QtGui.QPen(majorBrush, self.obj.MajorGridLineWidth.Value, QtLineStyles[self.obj.MajorGridLineStyle])

            g.setPen(minorPen)

            minorGridStep = self.obj.GridSpacing.Value
            majorGridStep = self.obj.MajorGridLineEvery
            sheetWidth = self.obj.ViewObject.Width
            sheetHeight = self.obj.ViewObject.Height

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
    
    def mousePressEvent(self, event):
        if self.mode is not None:
            self.mode.mousePressEvent(event)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.snapItemsToGrid()
        super().mouseReleaseEvent(event)

    # This method generate transaction
    def snapItemsToGrid(self):
        # Snap items to grid after it's position is updated
        items = []
        for item in self.selectedItems():
            if item.positionUpdated == True:
                items.append(item)
        if items != []:
            #itemsStr = " ".join(map(lambda i: i.obj.Name, items))  # List of items (Deprecated)
            name = items[0].obj.Name if len(items) == 1 else str(len(items)) + " Items"
            message = f"Position of {name} is changed"
            # It is necessary to clear the selected elements, 
            # otherwise elements from different sheets may be copied.
            #FreeCAD.Gui.Selection.clearSelection()
            FreeCAD.ActiveDocument.openTransaction(message)
            for item in items:
                item.positionUpdated = False
                item.obj.X = item.x()
                item.obj.Y = item.y()
                #FreeCAD.Gui.doCommand(f'FreeCAD.ActiveDocument.getObject("{item.obj.Name}").X = {item.x()}')
                #FreeCAD.Gui.doCommand(f'FreeCAD.ActiveDocument.getObject("{item.obj.Name}").Y = {item.y()}')
                FreeCAD.Gui.Selection.addSelection(item.obj)                
            FreeCAD.ActiveDocument.commitTransaction()
            FreeCAD.ActiveDocument.recompute()

    def mouseMoveEvent(self, event):
        # print(f"{event.scenePos()}")
        self.mouseCurPos = event.scenePos()
        self.update()       # mandatory for draw lines
        super().mouseMoveEvent(event)

#    def wheelEvent(self, event):
#        super().wheelEvent(event)
 
    def clear(self):
        self.points.clear()
        self.update()
