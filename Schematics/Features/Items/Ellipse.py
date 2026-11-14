# -*- coding: utf-8 -*-
###############################################################################
#
#  Ellipse.py - Scheme ellipse item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from typing import Any

from PySide6 import QtGui, QtCore
from Schematics.Features.Items.Rectangle import *

class Ellipse:
    def __new__(cls, x=None, y=None, width=None, height=None, sheet=None) -> Any:
        obj = makeObject(EllipseFeature, EllipseViewProvider, sheet, cls)
        # Honor documented params; None keeps the interactive path unchanged
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
