# -*- coding: utf-8 -*-
###############################################################################
#
#  Rectangle.py - Scheme rectangle item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from typing import Any

from PySide6 import QtGui, QtCore, QtWidgets
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.Items.SchemeObjectItem import *
from Schematics.Features.Utils.Snap import snap
from Schematics.Features.Items.StrokeMixin import *

class Rectangle:
    def __new__(cls, x=None, y=None, width=None, height=None, sheet=None) -> Any:
        obj = makeObject(RectangleFeature, RectangleViewProvider, sheet, cls)
        # Honor the documented x/y/width/height parameters (they were accepted
        # but silently dropped). None keeps the interactive draw path unchanged.
        if x is not None:
            obj.X = x
        if y is not None:
            obj.Y = y
        if width is not None:
            obj.Width = width
        if height is not None:
            obj.Height = height
        return obj

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class RectangleFeature(StrokeDataProperties, SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        pass

    def onDataPropertyChanged(self, obj, prop):
        pass

    def getItem(self, obj, sheet):
        return RectangleItem(obj, sheet)

    def initRootMethods(self, obj):
        pass

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class RectangleViewProvider(StrokeViewProperties, SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj):
        pass

    def onViewPropertyChanged(self, vobj, prop):
        pass

class RectangleItem(SchemeObjectItem, QtWidgets.QGraphicsRectItem):

    def boundingRect(self):
        if not self.isVisible():
            return QtCore.QRectF(0, 0, 0, 0)
        # Draw mode. Extend rect to maximal size
        if self.drawMode:
            return QtCore.QRectF(-5e+3, -5e+3, 10e+3, 10e+3)
        # Draw completed
        else:
            try:
                w = self.obj.ViewObject.StrokeWidth.Value
                m = 1   # Margin
                rect = QtCore.QRectF(-w/2, -w/2, self.obj.Width.Value+w, self.obj.Height.Value+w).normalized()
            except ReferenceError:
                # Object deleted (document closed / element removed):
                # empty rect so Qt stops laying out and painting us.
                return QtCore.QRectF(0, 0, 0, 0)
            return rect.adjusted(-m, -m, m, m)

    def shape(self):
        path = QtGui.QPainterPath()
        if self.drawMode:
            path.addRect(self.boundingRect())
        else:
            try:
                rect = QtCore.QRectF(0, 0, self.obj.Width.Value, self.obj.Height.Value).normalized()
                margin = 1   # Margin
                m = self.obj.ViewObject.StrokeWidth.Value + margin
            except ReferenceError:
                return path   # no hit area for a deleted object
            path.addRect(rect.adjusted(-m, -m, m, m))
            rect = rect.adjusted(m, m, -m, -m)
            # Do not draw internal rect if shape is small
            if rect.width() > 0 and rect.height() > 0:
                path.addRect(rect)
        return path

    def paint(self, painter, option, widget=None):
        g = painter   # base stubs name this parameter "painter"
        if not self.isVisible():
            return
        try:
            self.obj.Name   # liveness probe: object may be deleted
        except ReferenceError:
            return
        g.save()
        g.beginNativePainting()

        g.setRenderHints(g.RenderHint.Antialiasing)
        g.setBrush(QtCore.Qt.NoBrush)

        if self.drawMode:
            w = self.curRelPos.x()
            h = self.curRelPos.y()
        else:
            w = self.obj.Width.Value
            h = self.obj.Height.Value

        if self.isSelected():
            self.drawAnchor(g, w/2, h/2)

        color = QtGui.QColor.fromRgbF(*self.sheet.Proxy.appearance.linesColor())
        if self.isSelected():
            color = QtCore.Qt.green
        # pen.setCosmetic(True)
        pen = self.obj.ViewObject.Proxy.pen
        pen.setColor(color)
        # pen.setDashPattern([0.0001, 1.9999])
        g.setPen(pen)
        self.drawShape(g, w, h)

        g.endNativePainting()
        g.restore()

    def drawShape(self, g, w, h):
        g.drawRect(QtCore.QRectF(0.0, 0.0, w, h))

    def mousePressEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                startPos = snap(event.scenePos(), self.sheet)
                self.obj.X = startPos.x()
                self.obj.Y = startPos.y()
                self.curRelPos = QtCore.QPointF(0, 0)
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
                #inst = self.obj.instance()()
                #inst.Proxy.item.drawMode = True
                self.positionUpdated = False
        super().mouseReleaseEvent(event)

    def _trackDrawPos(self, scenePos):
        """Follow the cursor while drawing (shared by hover and mouse move)."""
        if self.drawMode:
            self.curRelPos = snap(scenePos - self.pos(), self.sheet)
            self.update()   # ! Mandatory

    # if all mouse buttons released
    def hoverMoveEvent(self, event):
        self._trackDrawPos(event.scenePos())

    # if mouse buttons pressed
    def mouseMoveEvent(self, event):
        self._trackDrawPos(event.scenePos())
        super().mouseMoveEvent(event)   # ! Mandatory
        # In other case item is being not movable
