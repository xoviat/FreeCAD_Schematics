# -*- coding: utf-8 -*-
###############################################################################
#
#  Polyline.py - Scheme polyline Item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtWidgets
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.Items.SchemeObjectItem import *
from Schematics.Features.Utils.Snap import snap
from Schematics.Features.Items.StrokeMixin import *
from Schematics.Features.Items.MarkersMixin import *

class Polyline:
    def __new__(cls, x=None, y=None, sheet=None):
        return makeObject(PolylineFeature, PolylineViewProvider, sheet, cls)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class PolylineFeature(MarkersDataProperties, StrokeDataProperties, SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")
        obj.addProperty('App::PropertyVectorList', 'Points', 'Data', 'Points of polyline', 8+16).Points = []

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
class PolylineViewProvider(MarkersViewProperties, StrokeViewProperties, SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj):
        pass

    def onViewPropertyChanged(self, vobj, prop):
        pass

class PolylineItem(MarkersItem, SchemeObjectItem, QtWidgets.QGraphicsRectItem):

    def __init__(self, obj, sheet):
        self.path = None
        super().__init__(obj, sheet)

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
            g.save()
            g.beginNativePainting()

            g.setRenderHints(g.RenderHint.Antialiasing)
            color = QtGui.QColor.fromRgbF(*self.sheet.Proxy.appearance.linesColor())
            #color = QtCore.Qt.black
            if self.isSelected():
                color = QtCore.Qt.green
            g.setBrush(QtCore.Qt.NoBrush)
            width = self.obj.ViewObject.StrokeWidth.Value
            g.setPen(QtGui.QPen(color, width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            # drawPath can't draw one point, use drawPoint instead
            cnt = self.path.elementCount()
            if cnt == 1:
                g.drawPoint(0, 0)
                sp1 = sp2 = ep1 = ep2 = QtCore.QPointF(0, 0)
            else:
                g.drawPath(self.path)
                sp1 = QtCore.QPointF(self.path.elementAt(0).x, self.path.elementAt(0).y)
                sp2 = QtCore.QPointF(self.path.elementAt(1).x, self.path.elementAt(1).y)
                ep1 = QtCore.QPointF(self.path.elementAt(cnt - 2).x, self.path.elementAt(cnt - 2).y)
                ep2 = QtCore.QPointF(self.path.elementAt(cnt - 1).x, self.path.elementAt(cnt - 1).y)
            if self.drawMode is True and self.path.elementCount() > 0:
                g.drawLine(ep2, self.curRelPos)
                if ep2 != self.curRelPos:
                    ep1 = ep2
                    ep2 = self.curRelPos
                if cnt == 1:
                    sp1 = ep1
                    sp2 = ep2
            self.drawMarkers(g, sp2, sp1, ep1, ep2)

            g.endNativePainting()
            g.restore()

    def mousePressEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                if self.obj.Points == []:
                    startPos = snap(event.scenePos(), self.sheet)
                    self.obj.X = startPos.x()
                    self.obj.Y = startPos.y()
                    # Recalc relPos after move object
                    self.curRelPos = QtCore.QPointF(0.0, 0.0)
                    self.obj.addPoint(0, 0)
                else:
                    self.obj.addPoint(self.curRelPos.x(), self.curRelPos.y())
                # Turn back draw mode after add point
                self.drawMode = True
            if event.button() == QtCore.Qt.RightButton:
                if self.drawMode:
                    self.setSelected(False)
                    self.drawMode = False
                    self.positionUpdated = False
                    self.doNotResetInstance = True
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