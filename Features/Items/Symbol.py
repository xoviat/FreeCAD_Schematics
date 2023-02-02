# -*- coding: utf-8 -*-
###############################################################################
#
#  Symbol.py - Scheme Symbol Item. Based on SchemeItem class
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets

from SCUtils import getTreeviewIconPath
from Features.Utils.MDI import *
from Features.Utils.SVGSymbolsCache import loadSVGSymbol
from Features.Utils.Snap import snap
import Features.Utils.CopyPaste

class Item:

    def attach(self, obj):
        """ Setup the scene sub-graph of the view provider, this method is mandatory """
        from pivy import coin  # Without this, the icon will be displayed in grayscale
        # App.Console.PrintMessage("Not3DViewProviderr attach \n")
        drawingDisplayMode = coin.SoGroup()
        obj.addDisplayMode(drawingDisplayMode, "Drawing")

        # Moved from __init__ to get rid of super().__init__(obj)
        # These settings are used for the 3D view, but this object is part of the 2D sheet.
        # Therefore, these properties are not needed and should be hidden.
        # BluePrint sheet can ONLY be selected via the treeview
        obj.setPropertyStatus("DisplayMode", "Hidden")
        obj.setPropertyStatus("OnTopWhenSelected", "Hidden")
        obj.setPropertyStatus("SelectionStyle", "Hidden")
        return

    def getDisplayModes(self, obj):
        """ Return a list of display modes. """
        # App.Console.PrintMessage("Not3DViewProvider getDisplayModes \n")
        return ["Drawing"]

    def getDefaultDisplayMode(self):
        """ Return the name of the default display mode. It must be defined in getDisplayModes. """
        # App.Console.PrintMessage("Not3DViewProvider getDefaultDisplayMode \n")
        return "Drawing"

def Create(sheet, name, x=0, y=0):
    # Add transaction!
    obj = FreeCAD.ActiveDocument.addObject('App::FeaturePython', name)    
    SymbolFeature(obj, sheet, name, x, y)
    SymbolViewProvider(obj.ViewObject)
    sheet.addItem(obj)
    return obj

class SymbolFeature:

    def __init__(self, obj, sheet, name, x, y):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} init object \n")
        self.Type = 'Symbol'
        obj.addProperty('App::PropertyString', 'ElementType', 'Data', 'Element type: Lamp, Rely etc...').ElementType = name
        obj.setPropertyStatus("ElementType", "ReadOnly")
        obj.addProperty('App::PropertyString', 'Tooltip', 'Data', 'Tooltip of element', 8+16).Tooltip = ''
        obj.addProperty('App::PropertyDistance', 'X', 'Position', 'X position on sheet', 8+16).X = x
        obj.addProperty('App::PropertyDistance', 'Y', 'Position', 'Y position on sheet', 8+16).Y = y
        obj.addProperty('App::PropertyAngle', 'Rotation', 'Position', 'Rotation angle of item', 8+16).Rotation = 0
        obj.Proxy = self
        self.initItem(obj, sheet)

    def execute(self, obj):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} execute \n")

    def onChanged(self, obj, prop):
        '''Do something when a property has changed'''
        val = obj.getPropertyByName(prop)
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} Change property: {str(prop)}={str(val)} \n")
        # --- Workaround ---
        # The ExpressionEngine property is called after changing all other properties, 
        # i.e. at the end. This feature can be used to create an object in cases when 
        # the standard api does not provide such an opportunity (Copy/Paste for example). 
        # !!! If the sheet is copied completely with attached elements. This code will turn an error.
        if prop == "ExpressionEngine":
            # If item not exist init not invoked, but undo/redo
            if not hasattr(self, 'Type'):
                print('Create item and connect it to active scheme sheet')
                activeSubWindow = FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea).activeSubWindow()
                if hasattr(activeSubWindow, 'obj') and hasattr(activeSubWindow.obj, 'Elements'):
                    sheet = activeSubWindow.obj
                    self.initItem(obj, sheet)
                    sheet.Elements += [obj]
                    if Features.Utils.CopyPaste.pasteAtPos and Features.Utils.CopyPaste.sceneCopyPos is not None:
                        obj.X = obj.X.Value - (
                                Features.Utils.CopyPaste.sceneCopyPos.x() - Features.Utils.CopyPaste.scenePastePos.x())
                        obj.Y = obj.Y.Value - (
                                Features.Utils.CopyPaste.sceneCopyPos.y() - Features.Utils.CopyPaste.scenePastePos.y())
                        FreeCAD.Gui.Selection.addSelection(obj.Document.Name, obj.Name)
                    else:
                        obj.X = obj.X.Value
                        obj.Y = obj.Y.Value
                #else:
                #    #print("This object restored or paste to not scheme window")
                #    #obj.ViewObject.Visibility = False
                #    # Canceling the paste operation
                #    # ... that can intercepted by MDIView
        # If item in scene not exist do nothing...
        if not hasattr(self, "item"):
            return
        mm = 1 # 3.5424723 # One millimeter in scene units (deprecated)
        if prop == "X":
            self.item.setX(round(val * mm, 5))
        if prop == "Y":
            self.item.setY(round(val * mm, 5))
        if prop == "Rotation":
            self.item.setRotation(val)
        if prop == "Tooltip":
            self.item.setToolTip(val)

    def initItem(self, obj, sheet):
        if hasattr(self, 'item'):
            self.item.scene().removeItem(self.item)
            del self.item
        self.item = SymbolItem(obj, sheet)
        sheet.Proxy.scene.addItem(self.item)
        obj.X = obj.X
        obj.Y = obj.Y
        obj.Rotation = obj.Rotation

    def onDelete(self):
        if hasattr(self, 'item'):
            self.item.hide()   # FreeCAD is not delete object, it hides it... Will do the same

    def onRestore(self):
        if hasattr(self, 'item'):
            self.item.show()   # Restore hided object...

    def setSelected(self, state):
        if hasattr(self, 'item'):
            # At first switch tab, at second add selection
            activateItemTab(self.item)
            self.item.setSelected(state)

    # Mandatory! Return None so serializer doesn't try to save self.item and other self. objects
    def __getstate__(self):
        return None    

class SymbolViewProvider(Item):

    def __init__(self, obj):
        """ Set this object to the proxy object of the actual view provider """
        obj.Proxy = self

    # This controlled by document observer
    #def onDelete(self, feature, subelements):
    #    FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onDelete " + str(feature) + " subelements: " + str(subelements) + "\n")

    def onChanged(self, obj, prop):
        """ Print the name of the property that has changed """
        val = obj.getPropertyByName(prop)
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onChanged property: {str(prop)}={str(val)} \n")

    def getIcon(self):
        return getTreeviewIconPath('Symbol.svg')

    #def doubleClicked(self, vpobj):
    #    activateItemTab(vpobj.Object.Proxy.item)
    #    return False

class SymbolItem(QtSvg.QGraphicsSvgItem):
    """ This item contains pins position """

    def __init__(self, obj, sheet):
        super().__init__()
        self.obj = obj
        self.sheet = sheet
        renderer = QtSvg.QSvgRenderer()
        renderer.setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        data, pins = loadSVGSymbol(obj.ElementType)
        data = sheet.Proxy.appearance.decode(data)
        renderer.load(data.encode())
        #svg.setCursor(QtCore.Qt.SizeAllCursor)
        self.setToolTip(obj.Tooltip)
        self.setFlags(self.ItemIsMovable | self.ItemIsSelectable | self.ItemSendsGeometryChanges)
        #self.setElementId("")
        self.setSharedRenderer(renderer)
        # Wire connections and wires must be at front
        #svg.setZValue(1) # Qreal from -1 ... 1. 1 = go to front
        #print(svg.boundingRect(), svg.renderer().viewBoxF(), svg.renderer().aspectRatioMode())
        # Anchor to center
        self.setAnchor(False)
        self.pins = pins
        self.pinsXY = None
        self._shape = self.getShape(renderer, 0.75, 5, True)
        self.recalculatePins(self.x(), self.y(), self.rotation())
        self.positionUpdated = False
        self.setCacheMode(self.NoCache)

    def setAnchor(self, combine):
        center = self.boundingRect().center()
        self.setTransform(QtGui.QTransform().translate(-center.x(), -center.y()), combine=combine)
        self.setTransformOriginPoint(center)

    def shape(self):
        return self._shape

    def getShape(self, renderer, borderSize=0.75, scaleFactor=5, rounded=True):
        # Create an image based on the item boundingRect size (QRectF->QSizeF->QSize)
        img = QtGui.QImage(self.boundingRect().size().toSize()*scaleFactor, QtGui.QImage.Format_ARGB32)
        # Fill buffer by transparent color
        img.fill(QtCore.Qt.transparent)
        # Create a QPainter and ask the renderer to render it
        painter = QtGui.QPainter(img)
        renderer.render(painter)
        painter.end()

        #ba = QtCore.QByteArray()
        #buffer = QtCore.QBuffer(ba)
        #img.save(buffer, "XPM")
        #print(ba)

        # Create the mask by adding a QRegion based on it
        mask = img.createAlphaMask()
        shape = QtGui.QPainterPath()
        shape.addRegion(QtGui.QRegion(QtGui.QBitmap.fromImage(mask)))
        # Get region as list of QPolygonF
        polygons = shape.toFillPolygons()

        # Create the shape (sharp or rounded) with border margin and scale correction
        shape = QtGui.QPainterPath()
        shape.setFillRule(QtCore.Qt.WindingFill)
        border = QtCore.QPointF(borderSize, borderSize)

        # Transform all QPolygonF to Rects and add it to shape
        for point in polygons:
            rect = QtCore.QRectF(point[0] / scaleFactor - border, point[2] / scaleFactor + border)
            shape.addRoundedRect(rect, borderSize, borderSize) if rounded else shape.addRect(rect)

        # Simplify shape
        shape = shape.simplified()

        # Substract pins
        for pin in self.pins:
            name, px, py = pin
            pinPath = QtGui.QPainterPath()
            pinPath.addEllipse(px-1.5, py-1.5, 3, 3)
            shape = shape - pinPath

        return shape

    def paint(self, g, option, widget):
        selected = option.state & QtWidgets.QStyle.State_Selected
        option.state &= ~QtWidgets.QStyle.State_Selected
        super().paint(g, option, widget)
        '''if selected:
            g.setBrush(QtCore.Qt.NoBrush)
            g.setPen(QtGui.QPen(QtCore.Qt.red, 0, QtCore.Qt.SolidLine))
            g.drawPath(self._shape)
            #g.setPen(QtGui.QPen(QtCore.Qt.black, 0, QtCore.Qt.DashLine))
            #g.drawPath(self._shape)'''
        g.setPen(QtGui.QPen(QtCore.Qt.black, 0, QtCore.Qt.SolidLine))
        for i in range(self._shape.elementCount()):
            p = self._shape.elementAt(i)
            #g.drawRect(QtCore.QRectF(p.x-0.1, p.y-0.1, 0.2, 0.2))

    def itemChange(self, change, value):
        #print(change)
        if change == self.ItemPositionChange:
            self.positionUpdated = True
            value = snap(value, self.sheet)
            self.recalculatePins(value.x(), value.y(), self.rotation())
            return value   # Return value with snap to grid
        if change == self.ItemRotationChange:
            self.recalculatePins(self.x(), self.y(), value)
        # Applicable to all Items    
        if change == self.ItemSelectedChange:
            if value == True:
                FreeCAD.Gui.Selection.addSelection(self.obj)
            else:
                FreeCAD.Gui.Selection.removeSelection(self.obj)
        return super().itemChange(change, value)

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