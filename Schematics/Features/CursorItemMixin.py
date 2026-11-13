# -*- coding: utf-8 -*-
###############################################################################
#
#  CursorItemMixin.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtCore, QtSvg, QtSvgWidgets, QtWidgets
from Schematics.Features.Utils.Snap import snap
from Schematics.Features.Utils.SVGSymbolsCache import loadSVGSymbol

class CursorItemMixin:

    __UnderCursorItem = None

    def getUnderCursorItem(self):
        return self.__UnderCursorItem

    def setUnderCursorItem(self, item):
        if self.__UnderCursorItem is not None:
            self.__UnderCursorItem.scene().removeItem(self.__UnderCursorItem)
            self.__UnderCursorItem = None
        if item is not None:
            item.sheet.Proxy.scene.addItem(item)
            item.hide()  # Hide when mouse not moved to QGraphicsView area
            self.__UnderCursorItem = item
        print("set", self.__UnderCursorItem)

    underCursorItem = property(getUnderCursorItem, setUnderCursorItem)

    def enterEvent(self, event):
        if self.underCursorItem is not None:
            # Qt6: QEnterEvent carries a QPointF position
            self.underCursorItem.mousePos(self.mapToScene(event.position().toPoint()))
            self.underCursorItem.show()

    def leaveEvent(self, event):
        if self.underCursorItem is not None:
            self.underCursorItem.hide()

class CursorSymbolItem(QtSvgWidgets.QGraphicsSvgItem):

    def __init__(self, typ, grp, std, sheet):
        super().__init__()
        self.fulltyp = std+"\\"+grp+"\\"+typ
        self.sheet = sheet
        self.setFlags(QtWidgets.QGraphicsItem.GraphicsItemFlags(0))
        # ! Store renderer to self. in other case Access memory violation will occur
        self.rerender()
        self.setAnchor()
        self.setAcceptHoverEvents(True)

    def rerender(self):
        self.renderer = QtSvg.QSvgRenderer()
        self.renderer.setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        data, pins = loadSVGSymbol(self.fulltyp)
        data = self.sheet.Proxy.appearance.decode(data)
        self.renderer.load(data.encode())
        self.setSharedRenderer(self.renderer)

    def setAnchor(self):
        center = super().boundingRect().center()
        self.setTransform(QtGui.QTransform().translate(-center.x(), -center.y()), combine=False)
        self.setTransformOriginPoint(center)

    def mousePos(self, pos):
        self.setPos(snap(pos, self.sheet))
