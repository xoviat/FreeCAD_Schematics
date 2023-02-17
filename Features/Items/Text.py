# -*- coding: utf-8 -*-
###############################################################################
#
#  Text.py - Scheme rectangle item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.Items.SchemeObject import *
from Features.Items.SchemeObjectItem import *
from Features.Utils.Snap import snap
from Features.Utils.MDI import *

class Text:
    def __new__(cls, x=None, y=None, sheet=None):
        return makeObject(TextFeature, TextViewProvider, sheet, cls)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class TextFeature(SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")
        obj.addProperty('App::PropertyString', 'Text', 'Content', 'Formatted text', 8+16).Text = ""

    def onDataPropertyChanged(self, obj, prop):
        if prop == "Text":
            if obj.Proxy.item.doNotUpdateText == True:
                obj.Proxy.item.doNotUpdateText = False
            else:
                val = obj.getPropertyByName(prop)
                obj.Proxy.item.setHtml(val)

    def getItem(self, obj, sheet):
        return TextItem(obj, sheet)

    def initRootMethods(self, obj):
        # obj.Text = obj.Text is not worked, force update text
        obj.Proxy.item.setHtml(obj.Text)

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in GuiDocument.xml
class TextViewProvider(SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj):
        pass

    def onViewPropertyChanged(self, vobj, prop):
        pass

class TextItem(SchemeObjectItem, QtWidgets.QGraphicsTextItem):

    font = QtGui.QFont()
    font.setFamilies(["GOSTRUS"]) #"OSIFONT",
    #font.setBold(True)
    font.setItalic(True)
    font.setPointSizeF(8.0)
    font.setHintingPreference(font.PreferNoHinting) # Try other hitting on distance
    font.setLetterSpacing(font.AbsoluteSpacing, 0.1)
    #f = obj.Proxy.item.font; f.setPixelSize(6) ; obj.Proxy.item.setFont(f)

    def __init__(self, obj, sheet):
        super().__init__(obj, sheet)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.document().contentsChanged.connect(self.contentsChanged)
        self.doNotUpdateText = False
        self.setFont(self.font)

    def boundingRect(self):
        # In draw mode extend rect to maximal size
        if self.drawMode:
            return QtCore.QRectF(-5e+3, -5e+3, 10e+3, 10e+3)
        else:
            rect = super().boundingRect()
            self.obj.Width = rect.width()
            self.obj.Height = rect.height()
            return rect

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        self._shape = path
        return path

    def getmode(self):
        return self.__drawMode

    def setmode(self, mode):
        if mode:
            self.setFlags(self.ItemIsSelectable)
        else:
            self.setFlags(self.ItemIsMovable | self.ItemIsSelectable | self.ItemSendsGeometryChanges
                          | self.ItemIsFocusable)
            self.updateTransform()
        self.__drawMode = mode

    drawMode = property(getmode, setmode)

    def paint(self, g, option, widget):
        g.setRenderHints(#g.RenderHint.SmoothPixmapTransform |
                         g.RenderHint.TextAntialiasing |
                         g.RenderHint.Antialiasing
                        )
        super().paint(g, option, widget)

    def mousePressEvent(self, event):
        if self.drawMode:
            if event.button() == QtCore.Qt.LeftButton:
                startPos = snap(event.scenePos(), self.sheet)
                self.obj.X = startPos.x()
                self.obj.Y = startPos.y()
                self.drawMode = False
                self.setFocus()
                self.sheet.Proxy.view.instance = None   # Stop continuous insert
        super().mousePressEvent(event)   # ! Mandatory
        # In other case selection invoked only after RMB released

    def contentsChanged(self):
        self.doNotUpdateText = True
        self.obj.Text = self.document().toHtml()
