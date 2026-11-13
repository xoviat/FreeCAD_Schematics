# -*- coding: utf-8 -*-
###############################################################################
#
#  Line.py - Scheme line item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtCore
from Schematics.Features.Items.Rectangle import *

class Line:
    def __new__(cls, x=None, y=None, width=None, height=None, sheet=None):
        obj = makeObject(LineFeature, LineViewProvider, sheet, cls)
        # Honor documented params; None keeps the interactive path unchanged
        if x is not None: obj.X = x
        if y is not None: obj.Y = y
        if width is not None: obj.Width = width
        if height is not None: obj.Height = height
        return obj

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class LineFeature(RectangleFeature):

    def getItem(self, obj, sheet):
        return LineItem(obj, sheet)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class LineViewProvider(RectangleViewProvider):
    pass

class LineItem(RectangleItem):

    def shape(self):
        path = QtGui.QPainterPath()
        if self.drawMode:
            path.addRect(self.boundingRect())
        else:
            m = 1.0
            start_p = QtCore.QPointF(0.0, 0.0)
            end_p = QtCore.QPointF(self.obj.Width.Value, self.obj.Height.Value)
            vec = end_p-start_p
            inv = QtGui.QVector2D(QtCore.QPointF(-vec.y(), vec.x())).normalized().toPointF()*m
            path = QtGui.QPainterPath(inv)
            path.lineTo(end_p + inv)
            path.lineTo(end_p - inv)
            path.lineTo(- inv)
            path.closeSubpath()
        self._shape = path
        return path

    def drawShape(self, g, w, h):
        g.drawLine(QtCore.QPointF(0.0, 0.0), QtCore.QPointF(w, h))
