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
from Features.Items.SchemeObj import Item
from Features.Utils.MDI import *
from Features.Utils.SVGSymbolsCache import loadSVGSymbol
from Features.Utils.Snap import snap
import Features.Utils.CopyPaste

def Create(sheet, name, x=0, y=0):
    # Add transaction!
    obj = FreeCAD.ActiveDocument.addObject('App::FeaturePython', name)    
    BPSymbolFeature(obj, sheet, name, x, y)
    BPSymbolViewProvider(obj.ViewObject)
    sheet.Proxy.addItem(obj)
    return obj

class BPSymbolFeature():

    def __init__(self, obj, sheet, name, x, y):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} init object \n")
        self.Type = 'BPSymbolFeature'
        obj.addProperty('App::PropertyString', 'ElementType', 'Data', 'Element type: Lamp, Rely etc...').ElementType = name   
        obj.addProperty('App::PropertyString', 'Tooltip', 'Data', 'Tooltip of element').Tooltip = ''
        obj.addProperty('App::PropertyLength', 'X', 'Position', 'X position on sheet',8+16).X = x
        obj.addProperty('App::PropertyLength', 'Y', 'Position', 'Y position on sheet',8+16).Y = y
        obj.addProperty('App::PropertyAngle', 'Rotation', 'Position', 'Rotation angle of item',8+16).Rotation = 0
        # ------------------------
        #obj.addProperty('App::PropertyStringList', 'PinNameList', 'Pin data', 'List of pin names').PinNameList = []
        #obj.addProperty('App::PropertyFloatList', 'PinXList', 'Pin data', 'List of pin X positions').PinXList = []
        #obj.addProperty('App::PropertyFloatList', 'PinYList', 'Pin data', 'List of pin Y positions').PinYList = []
        obj.Proxy = self
        self.initItem(obj, sheet)
        #print(self.__dict__)

    def execute(self, obj):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} execute \n")

    def onChanged(self, obj, prop):
        '''Do something when a property has changed'''
        val = obj.getPropertyByName(prop)
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} Change property: " + str(prop) + "=" + str(val) + "\n")
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
            self.item.setX(round(val * mm, 3))
        if prop == "Y":
            self.item.setY(round(val * mm, 3))
        if prop == "Rotation":
            self.item.setRotation(val)
        if prop == "Tooltip":
            self.item.setToolTip(val)          

    def initItem(self, obj, sheet):
        if hasattr(self, 'item'):
            self.item.scene().removeItem(self.item)
            del self.item
        #svg.setFlags(svg.ItemClipsToShape)
        renderer = QtSvg.QSvgRenderer()
        renderer.setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        data, pins = loadSVGSymbol(obj.ElementType)
        data = sheet.Proxy.appearance.decode(data)
        renderer.load(data.encode())
        svg = SymbolItem(obj, sheet, pins)
        svg.setSharedRenderer(renderer)
        #svg.setCursor(QtCore.Qt.SizeAllCursor)
        svg.setToolTip(obj.Tooltip)
        svg.setFlags(svg.ItemIsMovable | svg.ItemIsSelectable | svg.ItemSendsGeometryChanges)
        svg.setElementId("")
        #svg.setBoundingRegionGranularity(0.5)
        self.item = svg
        sheet.Proxy.scene.addItem(self.item)
        obj.X = obj.X
        obj.Y = obj.Y
        obj.Rotation = obj.Rotation
        # Wire connections and wires must be at front 
        #svg.setZValue(1) # Qreal from -1 ... 1. 1 = go to front
        print(svg.boundingRect(), svg.renderer().viewBoxF(), svg.renderer().aspectRatioMode())
        br = svg.boundingRect()
        # Anchor to center
        c = br.center()
        svg.setTransform(QtGui.QTransform().translate(-c.x(), -c.y()), combine=True)
        svg.setTransformOriginPoint(c.x(), c.y())

    def onDelete(self):
        #self.obj.sheet.Proxy.getScene().removeItem(self.item)
        #print('hide')
        if hasattr(self, 'item'):
            self.item.hide()   # FreeCAD is not delete object, it hides it... Will do the same

    def onRestore(self):
        #self.obj.sheet.Proxy.getScene().removeItem(self.item)
        #print('show')
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

class BPSymbolViewProvider(Item):

    def __init__(self, obj):
        """ Set this object to the proxy object of the actual view provider """
        obj.Proxy = self

    # This controlled by document observer
    #def onDelete(self, feature, subelements):
    #    FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onDelete " + str(feature) + " subelements: " + str(subelements) + "\n")

    def onChanged(self, obj, prop):
        """ Print the name of the property that has changed """
        val = obj.getPropertyByName(prop)
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onChanged property: " + str(prop) + "=" + str(val) + "\n")

    def getIcon(self):
        return getTreeviewIconPath('Symbol.svg')

    #def doubleClicked(self, vpobj):
    #    activateItemTab(vpobj.Object.Proxy.item)
    #    return False

class SymbolItem(QtSvg.QGraphicsSvgItem):
    """ This item contains pins position """

    def __init__(self, obj, sheet, pins):
        super().__init__()
        self.obj = obj
        self.sheet = sheet
        self.pins = pins
        self.pinsXY = None
        self.recalculatePins(self.x(), self.y(), self.rotation())
        self.positionUpdated = False
        self.setCacheMode(self.NoCache)

    def itemChange(self, change, value):
        #print(change)
        # If snap on sheet mode is one
        if change == self.ItemPositionChange:
            ### self.scene().disableAllModes() # Item paste mode too?
            self.positionUpdated = True
            value = snap(value, self.sheet)
            ### print(value)
            self.recalculatePins(value.x(), value.y(), self.rotation())
            return value # Return value with snap to grid
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