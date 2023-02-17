# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeObjectItem.py - contains item that apply to all scheme items.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.Utils.Snap import snap
import FreeCAD

class SchemeObjectItem():

    def __init__(self, obj, sheet):
        super().__init__()
        self.obj = obj
        self.sheet = sheet
        self.setToolTip(obj.Tooltip)
        self.curRelPos = None
        self.doNotResetInstance = False
        # onRestore document or created by command
        self.drawMode = False
        #self.setZValue(-0.8) # Qreal from -1 ... 1. 1 = go to front
        self.positionUpdated = False
        self.setCacheMode(self.NoCache)
        self._shape = self.shape()
        self.markerPen = QtGui.QPen(QtGui.QColor(0, 64, 255, 128), 1.5)
        self.markerPen.setCosmetic(True)

    def drawAnchor(self, g, x, y):
        g.setPen(self.markerPen)
        s = 1.0
        g.drawLine(QtCore.QPointF(x - s, y - s), QtCore.QPointF(x + s, y + s))
        g.drawLine(QtCore.QPointF(x - s, y + s), QtCore.QPointF(x + s, y - s))

    def updateTransform(self):
        # !!! Not correct if item is rotated
        # set rotation Anchor to center
        w = self.obj.Width.Value
        h = self.obj.Height.Value
        self.setTransform(QtGui.QTransform().translate(-w/2, -h/2), combine=False)
        self.setTransformOriginPoint(w/2, h/2)

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

    # Clear selection if focus in (For text blocks)
    def focusInEvent(self, event):
        super().focusInEvent(event)
        FreeCAD.Gui.Selection.clearSelection()
        FreeCAD.Gui.Selection.addSelection(self.obj)