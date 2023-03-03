# -*- coding: utf-8 -*-
###############################################################################
#
#  Ellipse.py - Scheme ellipse item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore
from Schematics.Features.Items.Rectangle import *

class Ellipse:
    def __new__(cls, x=None, y=None, width=None, height=None, sheet=None):
        return makeObject(EllipseFeature, EllipseViewProvider, sheet, cls)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class EllipseFeature(RectangleFeature):

    def getItem(self, obj, sheet):
        return EllipseItem(obj, sheet)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class EllipseViewProvider(RectangleViewProvider):
    pass

class EllipseItem(RectangleItem):

    def shape(self):
        path = QtGui.QPainterPath()
        if self.drawMode:
            path.addRect(self.boundingRect())
        else:
            rect = QtCore.QRectF(0, 0, self.obj.Width.Value, self.obj.Height.Value).normalized()
            margin = 1   # Margin
            m = self.obj.ViewObject.StrokeWidth.Value + margin
            path.addEllipse(rect.adjusted(-m, -m, m, m))
            rect = rect.adjusted(m, m, -m, -m)
            # Do not draw internal rect if shape is small
            if rect.width() > 0 and rect.height() > 0:
                path.addEllipse(rect)
        self._shape = path
        return path

    def drawShape(self, g, w, h):
        g.drawEllipse(QtCore.QRectF(0.0, 0.0, w, h))
