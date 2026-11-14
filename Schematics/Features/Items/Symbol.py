# -*- coding: utf-8 -*-
###############################################################################
#
#  Symbol.py - Scheme Symbol Item. Based on SchemeItem class
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from typing import Any

from PySide6 import QtGui, QtCore, QtSvg, QtSvgWidgets
from Schematics.Features.Items.SchemeObject import *
from Schematics.Features.Items.SchemeObjectItem import *
from Schematics.Features.Utils.Snap import snap
from Schematics.Features.Utils.SVGSymbolsCache import loadSVGSymbol
from Schematics.Features.Utils.QtEnums import *

class Symbol:
    # Set by PrimitiveCommand before StartDraw(); declared class-level so
    # assignments like inst.typ = name type-check (the factory runs on the
    # class, not an instance).
    typ: str | None = None
    grp: str | None = None
    std: str | None = None

    def __new__(cls, x=None, y=None, sheet=None) -> Any:
        obj = makeObject(SymbolFeature, SymbolViewProvider, sheet, cls, typ=cls.typ, grp=cls.grp, std=cls.std)
        # Honor documented params; None keeps the interactive path unchanged
        if x is not None:
            obj.X = x
        if y is not None:
            obj.Y = y
        # KiCad-style auto-annotation on placement (prefix from the
        # symbol's schematics:ref metadata; no-op without a prefix).
        from Schematics.Features.Utils.Annotate import autoDesignate
        autoDesignate(obj, sheet)
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
        # KiCad-style fields: Designator is auto-assigned on placement from
        # the library's schematics:ref prefix; Value defaults to the
        # library name and is hidden while it equals it.
        obj.addProperty('App::PropertyString', 'Designator', 'Data',
                        'Reference designator (e.g. K1)', 8+16).Designator = ''
        obj.addProperty('App::PropertyString', 'Value', 'Data',
                        'Component value shown under the symbol', 8+16).Value = ''
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")

    def onDataPropertyChanged(self, obj, prop):
        if prop in ("Designator", "Value") and hasattr(obj.Proxy, "item"):
            obj.Proxy.item.update()   # repaint the field labels

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
        self.irenderer.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        try:
            data, pins = loadSVGSymbol(self.obj.Standard+"\\"+self.obj.Group+"\\"+self.typ)
        except OSError as exc:
            # Symbol file deleted/renamed outside FreeCAD (symbol manager
            # delete, manual edits): render a placeholder instead of letting
            # the error escape into Qt's paint/restore machinery.
            FreeCAD.Console.PrintError(
                "Schematics: missing symbol %s (%s)\n" % (self.typ, exc))
            data = ('<svg xmlns="http://www.w3.org/2000/svg" width="10" '
                    'height="10" viewBox="0 0 10 10"></svg>')
            pins = []
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
            base = super().boundingRect()
            # Room for the designator (above) and value (below) labels so
            # they are not clipped and are clickable like in KiCad.
            return base.adjusted(0.0, -self._labelMargin(), 0.0, self._labelMargin())

    def _labelMargin(self) -> float:
        """Vertical space the field labels need (0 when nothing is shown)."""
        try:
            designator = str(self.obj.Designator or "")
            value = str(self.obj.Value or "")
            if value == str(self.obj.Type):
                value = ""   # default value = library name: hidden
        except (ReferenceError, RuntimeError, AttributeError):
            return 0.0
        if not designator and not value:
            return 0.0
        return super().boundingRect().height() * 0.4

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        try:
            designator = str(self.obj.Designator or "")
            value = str(self.obj.Value or "")
            if value == str(self.obj.Type):
                value = ""   # hide the default value (library name)
        except (ReferenceError, RuntimeError, AttributeError):
            return
        if not designator and not value:
            return
        rect = super().boundingRect()
        painter.save()
        color = QtGui.QColor.fromRgbF(*self.sheet.Proxy.appearance.linesColor())
        painter.setPen(QtGui.QPen(color))
        font = painter.font()
        font.setPixelSize(max(3, int(rect.height() * 0.3)))
        painter.setFont(font)
        height = float(painter.fontMetrics().height())
        if designator:
            above = QtCore.QRectF(rect.left(), rect.top() - height, rect.width(), height)
            painter.drawText(
                above,
                int(QtCore.Qt.AlignmentFlag.AlignHCenter
                    | QtCore.Qt.AlignmentFlag.AlignBottom),
                designator,
            )
        if value:
            below = QtCore.QRectF(rect.left(), rect.bottom(), rect.width(), height)
            painter.drawText(
                below,
                int(QtCore.Qt.AlignmentFlag.AlignHCenter
                    | QtCore.Qt.AlignmentFlag.AlignTop),
                value,
            )
        painter.restore()

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

    def _trackDrawPos(self, scenePos):
        """Follow the cursor while drawing (shared by hover and mouse move)."""
        if self.drawMode:
            self.curRelPos = snap(scenePos, self.sheet)
            self.setPos(self.curRelPos)
            #self.obj.X = self.curRelPos.x()
            #self.obj.Y = self.curRelPos.y()
            #self.update()   # ! Mandatory

    # if all mouse buttons released
    def hoverMoveEvent(self, event):
        self._trackDrawPos(event.scenePos())

    # if mouse buttons pressed
    def mouseMoveEvent(self, event):
        self._trackDrawPos(event.scenePos())
        super().mouseMoveEvent(event)   # ! Mandatory
        # In other case item is being not movable

    def recalculatePins(self, x, y, r):
        """ Calculate pins position in scene coordinates. Invoked after move or rotate item. """
        # !!! Update only if pins show mode active
        center = self.renderer().viewBoxF().center()
        tr = QtGui.QTransform().rotate(r).translate(-center.x(), -center.y())
        self.pinsXY = []
        if not self.pins:
            return
        for pin in self.pins:
            name, px, py = pin
            rp = tr.map(QtCore.QPointF(px, py))
            px = x - rp.x()
            py = y - rp.y()
            self.pinsXY.append((name, px, py))
            #print(f'{px} {py}')
