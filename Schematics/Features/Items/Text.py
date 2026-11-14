# -*- coding: utf-8 -*-
###############################################################################
#
#  Text.py - Scheme rectangle item.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from typing import Any

from PySide6 import QtGui, QtCore, QtWidgets
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.Items.SchemeObjectItem import *
from Schematics.Features.Utils.Snap import snap

class Text:
    def __new__(cls, x=None, y=None, sheet=None) -> Any:
        obj = makeObject(TextFeature, TextViewProvider, sheet, cls)
        # Honor documented params; None keeps the interactive path unchanged
        if x is not None:
            obj.X = x
        if y is not None:
            obj.Y = y
        return obj

# ! Do not change name and location of this class
# Module path and name of this class will be stored to *.FCStd file in Document.xml
class TextFeature(SchemeObjectFeature):

    def initDataPropertyies(self, obj):
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")
        obj.addProperty('App::PropertyString', 'Text', 'Content', 'Formatted text', 8+16).Text = ""

    def onDataPropertyChanged(self, obj, prop):
        if prop == "Text":
            if obj.Proxy.item.doNotUpdateText:
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

    # Named default_font: a class attribute named "font" would shadow
    # QGraphicsTextItem.font() and confuse type checkers.
    default_font = QtGui.QFont()
    default_font.setFamilies(["GOSTRUS"]) #"OSIFONT",
    #default_font.setBold(True)
    default_font.setItalic(True)
    default_font.setPointSizeF(8.0)
    default_font.setHintingPreference(QtGui.QFont.HintingPreference.PreferNoHinting) # Try other hitting on distance
    default_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 0.1)
    #f = obj.Proxy.item.default_font; f.setPixelSize(6) ; obj.Proxy.item.setFont(f)

    def __init__(self, obj, sheet):
        super().__init__(obj, sheet)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.document().contentsChanged.connect(self.contentsChanged)
        self.doNotUpdateText = False
        self.setFont(self.default_font)

    def boundingRect(self):
        # In draw mode extend rect to maximal size
        if self.drawMode:
            return QtCore.QRectF(-5e+3, -5e+3, 10e+3, 10e+3)
        else:
            try:
                self.obj.Name   # liveness probe: object may be deleted
            except ReferenceError:
                # Object deleted (document closed / element removed):
                # empty rect so Qt stops laying out and painting us.
                return QtCore.QRectF(0, 0, 0, 0)
            rect = super().boundingRect()
            self.obj.Width = rect.width()
            self.obj.Height = rect.height()
            return rect

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    # Override drawMode when this item is focusable
    def getmode(self):
        return self.__drawMode

    def setmode(self, mode):
        if mode:
            self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable)
        else:
            self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable | QtWidgets.QGraphicsItem.ItemIsSelectable | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
                          | QtWidgets.QGraphicsItem.ItemIsFocusable)
            self.updateTransform()
        self.__drawMode = mode

    drawMode = property(getmode, setmode)

    def paint(self, painter, option, widget=None):
        g = painter   # base stubs name this parameter "painter"
        g.setRenderHints(QtGui.QPainter.RenderHint.TextAntialiasing | QtGui.QPainter.RenderHint.Antialiasing)   # ...SmoothPixmapTransform
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

    # Text changed
    def contentsChanged(self):
        self.doNotUpdateText = True
        self.obj.Text = self.document().toHtml()

    # Clear selection if focus in (For text blocks)
    def focusInEvent(self, event):
        super().focusInEvent(event)
        FreeCAD.Gui.Selection.clearSelection()
        FreeCAD.Gui.Selection.addSelection(self.obj)
