# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeObjectItem.py - contains item that apply to all scheme items.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore
from Schematics.Features.Utils.Snap import snap
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
        self.markerPen = QtGui.QPen(QtGui.QColor(0, 64, 255, 128), 1.5)
        self.markerPen.setCosmetic(True)

    # Used only for rectangle, ellipse, line etc...
    def drawAnchor(self, g, x, y):
        g.setPen(self.markerPen)
        s = 1.0
        g.drawLine(QtCore.QPointF(x - s, y - s), QtCore.QPointF(x + s, y + s))
        g.drawLine(QtCore.QPointF(x - s, y + s), QtCore.QPointF(x + s, y - s))

    def getCursor(self):
        return QtCore.Qt.SizeAllCursor

    def updateTransform(self):
        # !!! Not correct if item is rotated
        # set rotation Anchor to center
        w = self.obj.Width.Value
        h = self.obj.Height.Value
        self.setTransform(QtGui.QTransform().translate(-w/2, -h/2), combine=False)
        self.setTransformOriginPoint(w/2, h/2)

    def getmode(self):
        return self.__drawMode

    def setmode(self, mode):
        if mode == True:
            #self.curRelPos = None # ! mandatory
            self.setFlags(self.ItemIsSelectable)
            self.setAcceptHoverEvents(True)
        else:
            self.setFlags(self.ItemIsMovable | self.ItemIsSelectable | self.ItemSendsGeometryChanges)
            self.setAcceptHoverEvents(False)  # ! Turn off hoverMoveEvent
            self.updateTransform()
        self.__drawMode = mode

    drawMode = property(getmode, setmode)

    # Applicable to all Items
    def itemChange(self, change, value):
        if change == self.ItemPositionChange:
            self.positionUpdated = True
            value = snap(value, self.sheet)
            return value   # Return value with snap to grid
        if change == self.ItemSelectedChange:
            if value == True:
                #self.setFlag(self.ItemIsFocusable, True)   # For text
                if not FreeCAD.Gui.Selection.isSelected(self.obj):
                    FreeCAD.Gui.Selection.addSelection(self.obj)
                #self.showMarkers() #self.marker.show()
            else:
                #self.setFlag(self.ItemIsFocusable, False)  # For text
                if FreeCAD.Gui.Selection.isSelected(self.obj):
                    FreeCAD.Gui.Selection.removeSelection(self.obj)
                #self.hideMarkers() #self.marker.hide()
        return super().itemChange(change, value)