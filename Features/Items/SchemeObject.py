# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeObject.py - contains actions that apply to all scheme items.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.Utils.MDI import *
import Features.Utils.CopyPaste as Clipbuffer
import Features.Utils.Snap as SN
from SCUtils import getTreeviewIconPath
import FreeCAD

class Draw:
    def __new__(cls, obj):
        obj.Proxy.item.drawMode = True
        return obj

def makeObject(objectProxy, viewObjectProxy, sheet, cls):
    if sheet is None:
        sheet = tryToGetSchemeFromActiveWindow()
        if sheet is None:
            error = f"An attempt to create an {cls.__name__}() object " \
                    f"in the current active window was rejected. " \
                    f"Since the current active window is not contain a schematic. " \
                    f"To create new {cls.__name__} in the specify schematic use: {cls.__name__}(targetSchematic) "
            raise RuntimeError(error)

    # !!! Need clear selection at start
    print("added")
    FreeCAD.ActiveDocument.openTransaction(f"{cls.__name__} added")
    obj = FreeCAD.ActiveDocument.addObject('App::FeaturePython', cls.__name__)
    objectProxy(obj, sheet, cls.__name__)
    viewObjectProxy(obj.ViewObject)
    obj.Proxy.initItem(obj, sheet)
    sheet.addItem(obj)
    FreeCAD.ActiveDocument.commitTransaction()

    def instance(self):
        return cls

    obj.instance = instance
    FreeCAD.ActiveDocument.recompute()
    return obj

class SchemeObjectFeature:

    def __init__(self, obj, sheet, type="Unknown", ):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} init object \n")
        self.Type = type
        obj.addProperty('App::PropertyString', 'Tooltip', 'Data', 'Tooltip of element', 8+16).Tooltip = ''
        obj.addProperty('App::PropertyDistance', 'X', 'Position', 'X position on sheet', 8+16).X = 0
        obj.addProperty('App::PropertyDistance', 'Y', 'Position', 'Y position on sheet', 8+16).Y = 0
        obj.addProperty('App::PropertyAngle', 'Rotation', 'Position', 'Rotation angle of item', 8+16).Rotation = 0
        self.initDataPropertyies(obj)
        obj.Proxy = self
        #self.initItem(obj, sheet)

    def execute(self, obj):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} execute \n")

    def onChanged(self, obj, prop):
        """ Do something when a property has changed """
        val = obj.getPropertyByName(prop)
        #FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} Change property: {str(prop)}={str(val)} \n")
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
                    if Clipbuffer.pasteAtPos and Clipbuffer.sceneCopyPos is not None:
                        obj.X = obj.X.Value - (Clipbuffer.sceneCopyPos.x() - Clipbuffer.scenePastePos.x())
                        obj.Y = obj.Y.Value - (Clipbuffer.sceneCopyPos.y() - Clipbuffer.scenePastePos.y())
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
        elif prop == "X":
            SN.WithoutSnap = True
            self.item.setX(round(val, 5))
            SN.WithoutSnap = False
        elif prop == "Y":
            SN.WithoutSnap = True
            self.item.setY(round(val, 5))
            SN.WithoutSnap = False
        elif prop == "Rotation":
            self.item.setRotation(val)
            self.item.scene().update()
        elif prop == "Tooltip":
            self.item.setToolTip(val)
        elif prop == "Visibility":
            if val == True:
                self.item.show()
            else:
                self.item.hide()
            obj.Proxy.item.scene().update()
        self.onDataPropertyChanged(obj, prop)

    # This must be called from to ViewObject (after ViewObject created) or from makeObject
    def initItem(self, obj, sheet):
        if not hasattr(self, 'item'):
            self.item = self.getItem(obj, sheet)
            sheet.Proxy.scene.addItem(self.item)
        obj.X = obj.X
        obj.Y = obj.Y
        obj.Rotation = obj.Rotation
        self.initRootMethods(obj)

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

class SchemeObjectViewProvider:

    def __init__(self, vobj):
        """ Set this object to the proxy object of the actual view provider """
        vobj.setPropertyStatus("DisplayMode", "Hidden")
        vobj.setPropertyStatus("OnTopWhenSelected", "Hidden")
        vobj.setPropertyStatus("SelectionStyle", "Hidden")
        self.initViewPropertyies(vobj)
        vobj.Proxy = self

    def onChanged(self, vobj, prop):
        """ Print the name of the property that has changed """
        val = vobj.getPropertyByName(prop)
        #FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onChanged property: {str(prop)}={str(val)} \n")
        self.onViewPropertyChanged(vobj, prop)

    def attach(self, vobj):
        """ Setup the scene sub-graph of the view provider, this method is mandatory """
        from pivy import coin     # Without this, the icon will be displayed in grayscale
        #FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} attach \n")
        drawingDisplayMode = coin.SoGroup()
        vobj.addDisplayMode(drawingDisplayMode, "Drawing")
        return

    def getDisplayModes(self, vobj):
        """ Return a list of display modes. """
        #FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} getDisplayModes \n")
        return ["Drawing"]

    def getDefaultDisplayMode(self):
        """ Return the name of the default display mode. It must be defined in getDisplayModes. """
        #FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} getDefaultDisplayMode \n")
        return "Drawing"

    def getIcon(self):
        # ! subtract 12 last charters (ViewProvider) from class name
        return getTreeviewIconPath(self.__class__.__name__[:-12]+'.svg')

    # Mandatory! Return None so serializer doesn't try to save self.item and other self. objects
    def __getstate__(self):
        return None
