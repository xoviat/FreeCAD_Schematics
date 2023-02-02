# -*- coding: utf-8 -*-
###############################################################################
#
#  Rectangle.py - Scheme rectangle item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.Items.SchemeObject import *
from Features.Items.SchemeObjectItem import *
from Features.Items.StrokeMixin import *
from Features.Utils.Snap import snap
from Features.Utils.MDI import *

class Rectangle:
    def __new__(cls, sheet=None):
        return makeObject(RectangleFeature, RectangleViewProvider, sheet, cls)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class RectangleFeature(StrokeDataProperties, SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        obj.addProperty('App::PropertyDistance', 'Width', 'Size', 'Width of shape', 8+16).Width = 0
        obj.addProperty('App::PropertyDistance', 'Height', 'Size', 'Height of shape', 8+16).Height = 0

    def onDataPropertyChanged(self, obj, prop):
        val = obj.getPropertyByName(prop)
        if prop == "Width" or prop == "Height":
            obj.Proxy.item.scene().update()
            if val != 0:
                obj.Proxy.item.drawMode = False

    def getItem(self, obj, sheet):
        return RectangleItem(obj, sheet)

    def initRootMethods(self, obj):
        obj.Width = obj.Width
        obj.Height = obj.Height

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class RectangleViewProvider(StrokeViewProperties, SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj):
        pass

    def onViewPropertyChanged(self, vobj, prop):
        pass

class RectangleItem(SchemeObjectItem):

    def getmode(self):
        return self.__drawMode

    def setmode(self, mode):
        if mode == True:
            self.curRelPos = None
            self.positionIsSet = False
            self.setFlags(self.ItemIsSelectable)
            self.setAcceptHoverEvents(True)
        else:
            self.positionIsSet = True
            self.setFlags(self.ItemIsMovable | self.ItemIsSelectable | self.ItemSendsGeometryChanges)
            self.setAcceptHoverEvents(False)  # ! Turn off hoverMoveEvent
            self.updateTransform()
        self.__drawMode = mode

    drawMode = property(getmode, setmode)

    def updateTransform(self):
        # !!! Not correct if item is rotated
        # set rotation Anchor to center
        w = self.obj.Width.Value
        h = self.obj.Height.Value
        self.setTransform(QtGui.QTransform().translate(-w/2, -h/2), combine=False)
        self.setTransformOriginPoint(w/2, h/2)

    def boundingRect(self):
        if not self.isVisible():
            return QtCore.QRectF(0, 0, 0, 0)
        # Draw mode. Extend rect to maximal size
        if self.drawMode:
            return QtCore.QRectF(-5e+3, -5e+3, 10e+3, 10e+3)
        # Draw completed
        else:
            w = self.obj.ViewObject.StrokeWidth.Value
            m = 1   # Margin
            rect = QtCore.QRectF(-w/2, -w/2, self.obj.Width.Value+w, self.obj.Height.Value+w).normalized()
            return rect.adjusted(-m, -m, m, m)

    def shape(self):
        path = QtGui.QPainterPath()
        if self.drawMode:
            path.addRect(self.boundingRect())
        else:
            rect = QtCore.QRectF(0, 0, self.obj.Width.Value, self.obj.Height.Value).normalized()
            margin = 1   # Margin
            m = self.obj.ViewObject.StrokeWidth.Value + margin
            path.addRect(rect.adjusted(-m, -m, m, m))
            rect = rect.adjusted(m, m, -m, -m)
            # Do not draw internal rect if shape is small
            if rect.width() > 0 and rect.height() > 0:
                path.addRect(rect)
        self._shape = path
        return path

    def drawShape(self, g, w, h):
        g.drawRect(QtCore.QRectF(0.0, 0.0, w, h))

    # Applicable to all Items
    def itemChange(self, change, value):
        if change == self.ItemPositionChange:
            self.positionUpdated = True
            value = snap(value, self.sheet)
            return value   # Return value with snap to grid
        if change == self.ItemSelectedChange:
            if value == True:
                FreeCAD.Gui.Selection.addSelection(self.obj)
            else:
                FreeCAD.Gui.Selection.removeSelection(self.obj)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                if not self.positionIsSet:
                    startPos = snap(event.scenePos(), self.sheet)
                    self.obj.X = startPos.x()
                    self.obj.Y = startPos.y()
                    self.curRelPos = QtCore.QPointF(0, 0)
                    self.positionIsSet = True
            if event.button() == QtCore.Qt.RightButton:
                if not self.positionIsSet:
                    # ! Block context menu at first, before item delete from scene
                    self.scene().blockContextMenu = True
                    self.scene().removeItem(self)
                    FreeCAD.ActiveDocument.removeObject(self.obj.Name)
        super().mousePressEvent(event)   # ! Mandatory
        # In other case selection invoked only after RMB released

    def mouseReleaseEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                # Add width height
                endPos = snap(event.scenePos(), self.sheet)
                self.obj.Width = endPos.x() - self.obj.X.Value
                self.obj.Height = endPos.y() - self.obj.Y.Value
                self.obj.X = self.obj.X.Value + self.obj.Width.Value/2
                self.obj.Y = self.obj.Y.Value + self.obj.Height.Value/2
                self.setSelected(False)
                self.drawMode = False
                inst = self.obj.instance()()
                inst.Proxy.item.drawMode = True
                self.positionUpdated = False
        super().mouseReleaseEvent(event)

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
