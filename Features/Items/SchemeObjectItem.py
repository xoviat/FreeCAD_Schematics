# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeObjectItem.py - contains item that apply to all scheme items.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets

class SchemeObjectItem(QtWidgets.QGraphicsRectItem):

    def __init__(self, obj, sheet):
        super().__init__()
        self.obj = obj
        self.sheet = sheet
        self.setToolTip(obj.Tooltip)
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

    def paint(self, g, option, widget):
        if not self.isVisible():
            return
        if self.positionIsSet:
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

            # Selection rect is not displayed during the drawing of shape, to increase performance
            #if not self.drawMode and self._shape is not None:
            #    g.setPen(QtGui.QPen(QtCore.Qt.red, 0, QtCore.Qt.SolidLine))
            #    g.drawPath(self._shape)

            g.endNativePainting()
            g.restore()
