# -*- coding: utf-8 -*-
###############################################################################
#
#  Polyline.py - Scheme polyline Item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.Items.SchemeObject import *
from Features.Utils.Snap import snap
from SCUtils import getTreeviewIconPath
from Features.Utils.MDI import *

class Polyline:
    def __new__(cls, sheet=None):
        return makeObject(PolylineFeature, PolylineViewProvider, sheet, cls)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class PolylineFeature(SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        obj.addProperty('App::PropertyVectorList', 'Points', 'Data', 'Points of polyline', 8 + 16).Points = []

    def onDataPropertyChanged(self, obj, prop):
        if prop == "Points":
            obj.Proxy.item.updatePoints()

    def getItem(self, obj, sheet):
        return PolylineItem(obj, sheet)

    def initRootMethods(self, obj):
        obj.Points = obj.Points

        # Connect special functions
        def addPoint(self, x, y):
            """ Add first or new point at end of path """
            obj.Points += [FreeCAD.Vector(x, y, 0)]
            obj.Proxy.item.drawMode = False
        obj.addPoint = addPoint

        def setPointPosition(self, index, x, y):
            """ Set new position of existed point """
            points = self.Points
            points[index].x += x
            points[index].y += y
            obj.Points = points
            obj.Proxy.item.drawMode = False
        obj.setPointPosition = setPointPosition

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class PolylineViewProvider(SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj):
        vobj.addProperty('App::PropertyLength', 'StrokeWidth', 'Style', 'Stroke width', 8+16).StrokeWidth = "0.5 mm"

    def onViewPropertyChanged(self, vobj, prop):
        pass

    def getIcon(self):
        return getTreeviewIconPath('Polyline.svg')

class PolylineItem(QtWidgets.QGraphicsRectItem):

    def __init__(self, obj, sheet):
        super().__init__()
        self.obj = obj
        self.sheet = sheet
        self.setToolTip(obj.Tooltip)
        self.path = None
        self.curRelPos = None
        if self.obj.Points == []:
            self.drawMode = True
            self.setFlags(self.ItemIsSelectable)
        else:
            # onRestore document
            # self.updatePoints()
            self.endDraw()
        #self.setZValue(-0.8) # Qreal from -1 ... 1. 1 = go to front
        self.setAcceptHoverEvents(True)
        self.positionUpdated = False
        self.setCacheMode(self.NoCache)

    def endDraw(self):
        self.setFlags(self.ItemIsMovable | self.ItemIsSelectable | self.ItemSendsGeometryChanges)
        self.drawMode = False
        self.setAcceptHoverEvents(False)    # ! Turn off hoverMoveEvent
        self.updateAnchor()

    def updateAnchor(self):
        # !!! Not correct if item is rotated
        # set rotation Anchor to center
        center = self.boundingRect().center()
        #self.setTransform(QtGui.QTransform().translate(-center.x(), -center.y()), combine=True)
        self.setTransformOriginPoint(center)

    def boundingRect(self):
        # Draw mode. Extend rect to maximal size
        if self.drawMode:
            return QtCore.QRectF(-5e+3, -5e+3, 10e+3, 10e+3)
        # Item drag or modify mode
        if self.path is not None:
            return self.path.boundingRect().adjusted(-1, -1, 1, 1) # 1 - line width
        else:
            return QtCore.QRectF(-0.5, -0.5, 1, 1)

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def updatePoints(self):
        points = self.obj.Points
        path = QtGui.QPainterPath()
        for p in points:
            path.lineTo(p.x, p.y)
        self.path = path
        super().update()

    def paint(self, g, option, widget):
        if not self.isVisible():
            return
        # Don't display the selection rect to improve performance
        if self.drawMode == False:
            self.prepareGeometryChange()
            #self.setPen(QtGui.QPen(QtCore.Qt.black, 0, QtCore.Qt.SolidLine))
            super().paint(g, option, widget)
        if self.path is not None:
            g.setRenderHints(g.RenderHint.Antialiasing)
            color = QtGui.QColor.fromRgbF(*self.sheet.Proxy.appearance.linesColor())
            #color = QtCore.Qt.black
            if self.isSelected():
                color = QtCore.Qt.green
            g.setBrush(QtCore.Qt.NoBrush)
            width = self.obj.ViewObject.StrokeWidth.Value
            g.setPen(QtGui.QPen(color, width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            # drawPath can't draw one point, use drawPoint instead
            if self.path.elementCount() == 1:
                g.drawPoint(0, 0)
            else:
                g.drawPath(self.path)
            if self.drawMode and self.path.elementCount() > 0:
                g.drawLine(self.path.elementAt(self.path.elementCount()-1), self.curRelPos)

    def itemChange(self, change, value):
        if change == self.ItemPositionChange:
            self.positionUpdated = True
            value = snap(value, self.sheet)
            return value   # Return value with snap to grid
        # Applicable to all Items
        if change == self.ItemSelectedChange:
            if value == True:
                FreeCAD.Gui.Selection.addSelection(self.obj)
            else:
                FreeCAD.Gui.Selection.removeSelection(self.obj)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                if self.obj.Points == []:
                    startPos = snap(event.scenePos(), self.sheet)
                    self.obj.X = startPos.x()
                    self.obj.Y = startPos.y()
                    # Recalc relPos after move object
                    self.curRelPos = QtCore.QPointF(0, 0)
                    self.obj.addPoint(0, 0)
                else:
                    self.obj.addPoint(self.curRelPos.x(), self.curRelPos.y())
                # Turn back draw mode after add point
                self.drawMode = True
            if event.button() == QtCore.Qt.RightButton:
                if self.obj.Points == []:
                    # ! Block context menu at first, before item delete from scene
                    self.scene().blockContextMenu = True
                    self.scene().removeItem(self)
                    FreeCAD.ActiveDocument.removeObject(self.obj.Name)
                else:
                    self.scene().blockContextMenu = True
                    self.setSelected(False)
                    self.endDraw()
                    self.obj.instance()()
        super().mousePressEvent(event)   # ! Mandatory
        # In other case selection invoked only after RMB released

    # if all mouse buttons released
    def hoverMoveEvent(self, event):
        if self.drawMode:
            self.curRelPos = snap(event.scenePos() - self.pos(), self.sheet)
            self.update()   # ! Mandatory

    # if mouse buttons pressed
    def mouseMoveEvent(self, event):
        self.hoverMoveEvent(event)
        super().mouseMoveEvent(event)   # ! Mandatory
        # In other case item is being not movable