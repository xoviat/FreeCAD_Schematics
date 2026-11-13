# -*- coding: utf-8 -*-
###############################################################################
#
#  Symbol.py - Scheme Symbol Item. Based on SchemeItem class
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtCore, QtSvg, QtSvgWidgets
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.Items.SchemeObjectItem import *
from Schematics.Features.Utils.Snap import snap
from Schematics.Features.Utils.SVGSymbolsCache import loadSVGSymbol
from Schematics.Features.Utils.QtEnums import *

class Symbol:
    def __new__(cls, x=None, y=None, sheet=None):
        obj = makeObject(SymbolFeature, SymbolViewProvider, sheet, cls, typ=cls.typ, grp=cls.grp, std=cls.std)
        # Honor documented params; None keeps the interactive path unchanged
        if x is not None: obj.X = x
        if y is not None: obj.Y = y
        return obj

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class SymbolFeature(SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        obj.addProperty('App::PropertyString', 'Group', 'Data', 'Group of type', 8+16).Group = ''
        obj.setPropertyStatus("Group", "ReadOnly")
        obj.addProperty('App::PropertyEnumeration', 'Standard', 'Data',
            'Defines the appearance of the symbol', 8+16).Standard = Standards
        obj.Standard = Standards
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")

    def onDataPropertyChanged(self, obj, prop):
        pass

    def getItem(self, obj, sheet):
        return SymbolItem(obj, sheet)

    def initRootMethods(self, obj):
        self.item.rerender()
        pass

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class SymbolViewProvider(SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj):
        pass

    def onViewPropertyChanged(self, vobj, prop):
        pass

class SymbolItem(SchemeObjectItem, QtSvgWidgets.QGraphicsSvgItem):

    def __init__(self, obj, sheet):
        super().__init__(obj, sheet)
        self.obj = obj
        self.typ = obj.Type
        self.sheet = sheet
        self.pins = None
        self.rerender()
        self.setAnchor()
        self.pinsXY = None
        self.recalculatePins(self.x(), self.y(), self.rotation())

    def rerender(self):
        self.irenderer = QtSvg.QSvgRenderer()
        self.irenderer.setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        data, pins = loadSVGSymbol(self.obj.Standard+"\\"+self.obj.Group+"\\"+self.typ)
        data = self.sheet.Proxy.appearance.decode(data)
        self.irenderer.load(data.encode())
        self.setSharedRenderer(self.irenderer)
        self.pins = pins
        rect = super().boundingRect()
        self.obj.Width = rect.width()
        self.obj.Height = rect.height()

    def setAnchor(self):
        center = super().boundingRect().center()  # !
        self.setTransform(QtGui.QTransform().translate(-center.x(), -center.y()), combine=False)
        self.setTransformOriginPoint(center)

    def boundingRect(self):
        # In draw mode extend rect to maximal size
        if self.drawMode:
            # ! extendet boundingRect size must be proportional with original
            return super().boundingRect().adjusted(-5e+3, -5e+3, 10e+3, 10e+3)
        else:
            return super().boundingRect()

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def mousePressEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                startPos = snap(event.scenePos(), self.sheet)
                self.obj.X = startPos.x()
                self.obj.Y = startPos.y()
                self.drawMode = False
                #self.sheet.Proxy.view.instance = None   # Stop continuous insert
        super().mousePressEvent(event)   # ! Mandatory
        # In other case selection invoked only after RMB released

    # if all mouse buttons released
    def hoverMoveEvent(self, event):
        if self.drawMode:
            self.curRelPos = snap(event.scenePos(), self.sheet)
            self.setPos(self.curRelPos)
            #self.obj.X = self.curRelPos.x()
            #self.obj.Y = self.curRelPos.y()
            #self.update()   # ! Mandatory

    # if mouse buttons pressed
    def mouseMoveEvent(self, event):
        self.hoverMoveEvent(event)
        super().mouseMoveEvent(event)   # ! Mandatory
        # In other case item is being not movable

    def recalculatePins(self, x, y, r):
        """ Calculate pins position in scene coordinates. Invoked after move or rotate item. """
        # !!! Update only if pins show mode active
        center = self.renderer().viewBoxF().center()
        tr = QtGui.QTransform().rotate(r).translate(-center.x(), -center.y())
        self.pinsXY = []
        for pin in self.pins:
            name, px, py = pin
            rp = tr.map(QtCore.QPointF(px, py))
            px = x - rp.x()
            py = y - rp.y()
            self.pinsXY.append((name, px, py))
            #print(f'{px} {py}')
