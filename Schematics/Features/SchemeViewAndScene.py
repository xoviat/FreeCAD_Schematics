# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeViewAndScene.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import math
from PySide2 import QtGui, QtCore, QtWidgets
from Schematics.Features.Utils.QtEnums import *
from Schematics.Features.SchemeContextMenu import ContextMenu
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.CursorItemMixin import *

class SchemeGraphicsView(CursorItemMixin, QtWidgets.QGraphicsView):

    def __init__(self):
        super().__init__()
        #self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.setViewportUpdateMode(self.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(self.RubberBandDrag) #ScrollHandDrag)
        self.setMouseTracking(True)
        self.setCacheMode(self.CacheBackground)
        self.dragMode = False
        self.instance = None
        self.currentObj = None

    def getScale(self):
        t = self.transform()
        scalex = math.sqrt(t.m11() * t.m11() + t.m12() * t.m12())
        scaley = math.sqrt(t.m21() * t.m21() + t.m22() * t.m22())
        scale = (scalex+scaley)/2
        return scale

    def mousePressEvent(self, event):
        # Update on left click (selection/deselection)
        if event.button() == QtCore.Qt.LeftButton:
            if self.instance is not None:
                if self.currentObj is not None and self.currentObj.Proxy.item.drawMode is True:
                    pass
                else:
                    self.currentObj = Draw(self.instance())
            self.scene().update()
        # ! call super().mousePressEvent only after object is create
        super().mousePressEvent(event)
        if event.button() == QtCore.Qt.MiddleButton:
            # rubber mode of
            self.sceneCenter = self.mapToScene(self.viewport().rect().center())
            self.startPos = event.localPos()
            self.dragMode = True
            self.viewport().setCursor(QtCore.Qt.ClosedHandCursor)
        if event.button() == QtCore.Qt.RightButton:
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
                contextMenu.invokeAt(event.globalPos())

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            # rubber mode on
            self.dragMode = False
            self.viewport().unsetCursor() #QtCore.Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        #print(f"mmove event {event.localPos()}, {self.mapToScene(event.pos())}")
        if self.underCursorItem is not None:
            self.underCursorItem.mousePos(self.mapToScene(event.pos()))
        overItem = self.itemAt(event.localPos().toPoint())
        #if hasattr(overItem, "drawMode") and overItem.drawMode:
        if self.instance is not None:
            self.viewport().setCursor(QtCore.Qt.CrossCursor)
        else:
            if overItem is not None and (overItem.flags() & overItem.ItemIsMovable):
                self.viewport().setCursor(overItem.getCursor())
            else:
                self.viewport().setCursor(QtCore.Qt.ArrowCursor)

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

class SchemeGraphicsScene(QtWidgets.QGraphicsScene):
    
    def __init__(self, obj):
        super().__init__()
        self.obj = obj
        self.vobj = obj.ViewObject
        self.mouseCurPos = None
        self.points = []

    #def drawBackground(self, g, rect):
    #   print("drawBackground")

    def drawForeground(self, g, rect):
        ### g.drawText(50, 50, str(len(self.items())))

        # ! Do not paint anything while the file is loading
        if not hasattr(self.obj, "Proxy"):
            return

        #svg = self.obj.Proxy.svg_template
        #svg.paint(g, None, None)

        # Show grid
        if self.vobj.GridVisible:

            minorBrush = QtGui.QColor.fromRgbF(*self.vobj.MinorGridLineColor)
            minorPen = QtGui.QPen(minorBrush, self.vobj.MinorGridLineWidth.Value,
                QtLineStyles[self.vobj.MinorGridLineStyle], QtCore.Qt.FlatCap, QtCore.Qt.RoundJoin)

            majorBrush = QtGui.QColor.fromRgbF(*self.vobj.MajorGridLineColor)
            majorPen = QtGui.QPen(majorBrush, self.vobj.MajorGridLineWidth.Value,
                QtLineStyles[self.vobj.MajorGridLineStyle], QtCore.Qt.SquareCap, QtCore.Qt.RoundJoin)

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
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.snapItemsToGrid()
        super().mouseReleaseEvent(event)

    # This method generate transaction
    def snapItemsToGrid(self):
        # Snap items to grid after it's position is updated
        items = []
        for item in self.selectedItems():
            if hasattr(item, "positionUpdated") and item.positionUpdated == True:
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
