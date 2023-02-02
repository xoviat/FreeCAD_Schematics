# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeFeature.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
from Features.SchemeViewAndScene import SchemeGraphicsView, SchemeGraphicsScene
from Features.Utils.SVGSymbolsCache import transformUnits
from SCUtils import *
from Features.SchemeProviderSetup import SchemeViewProviderSetup
from Features.Utils.SVG import *
from Features.Utils.MDI import *
from Features.Utils.QtEnums import *
import Features.Utils.CopyPaste

def CreateScheme():
    # Add transaction!
    obj = FreeCAD.ActiveDocument.addObject('App::FeaturePython', 'Schematic')
    SchemeFeature(obj)
    BluePrintViewProvider(obj.ViewObject)
    return obj

class SchemeMDIView(QtWidgets.QMdiSubWindow):

    def __init__(self, obj):
        super().__init__()
        self.obj = obj
        self.setMouseTracking(True)
        self.contextMenuScenePos = None

    def ZcontextMenuEvent(self, event):
        # If scene in special mode state not show context menu
        if self.obj.Proxy.scene.mode is not None:
            return
        # Store scene position where user invoke contex menu
        self.contextMenuScenePos = self.obj.Proxy.scene.mouseCurPos
        # print(Features.Utils.CopyPaste.sceneCopyPos, self.contextMenuScenePos)
        contextMenu = QtWidgets.QMenu(parent=self)
        somethingSelected = False
        # if objects selected at scene...
        if len(FreeCAD.Gui.Selection.getSelection()) > 0 :
            somethingSelected = True
        action = QtWidgets.QAction('Copy', self, triggered=self.contextMenuCopy)
        action.setEnabled(somethingSelected)
        contextMenu.addAction(action)
        contextMenu.addAction(QtWidgets.QAction('Paste', self, triggered=self.contextMenuPaste))
        contextMenu.addSeparator()
        contextMenu.addAction(QtWidgets.QAction('Paste to the same place', self, triggered=self.contextMenuPasteSamePlace))
        action = QtWidgets.QAction('Duplicate this sheet', self, triggered=self.contextMenuDuplicateSheet)
        action.setEnabled(False)
        contextMenu.addAction(action)
        contextMenu.addSeparator()
        if somethingSelected:
            contextMenu.addAction(QtWidgets.QAction('Turn Right +90°', self, triggered=self.contextMenuTurnRight))
            contextMenu.addAction(QtWidgets.QAction('Turn Left -90°', self, triggered=self.contextMenuTurnLeft))
        #contextMenu.hideEvent = self.contextMenuClosed
        # Remove item command?
        contextMenu.exec_(event.globalPos())

    #def contextMenuClosed(self, event):
        #print("contextMenuClosed")

    def contextMenuCopy(self):
        # Store scene pos where context menu is invoked, before copy objects
        Features.Utils.CopyPaste.sceneCopyPos = self.contextMenuScenePos
        print("Copy at ", Features.Utils.CopyPaste.sceneCopyPos)
        FreeCAD.Gui.runCommand('Std_Copy', 0)

    def contextMenuPaste(self):
        Features.Utils.CopyPaste.scenePastePos = self.contextMenuScenePos
        Features.Utils.CopyPaste.pasteAtPos = True
        FreeCAD.Gui.runCommand('Std_Paste', 0)
        Features.Utils.CopyPaste.pasteAtPos = False
        # Shift objects after paste

    def contextMenuPasteSamePlace(self):
        # print("Paste to the same place")
        FreeCAD.Gui.runCommand('Std_Paste', 0)

    def contextMenuTurnRight(self):
        for obj in FreeCAD.Gui.Selection.getSelection():
            if hasattr(obj, 'Rotation'):
                obj.Rotation = obj.Rotation.Value + (-360+90 if obj.Rotation.Value+90 > 360 else 90)

    def contextMenuDuplicateSheet(self):
        return

    def contextMenuTurnLeft(self):
        for obj in FreeCAD.Gui.Selection.getSelection():
            if hasattr(obj, 'Rotation'):
                obj.Rotation = obj.Rotation.Value - (-360+90 if obj.Rotation.Value-90 < -360 else 90)

    #def leaveEvent(self, event):
    #    Features.CopyPaste.mouseCopyPos = None
    #    print("leaveEvent", event)

    #def enterEvent(self, event):
    #    print("enterEvent", event)

    def closeEvent(self, event):
        #print("Tab is closed")
        setattr(self.obj, "Visibility", False)
        # removeSelection is mandatory for invoke setSelection event if user select sheet again
        FreeCAD.Gui.Selection.removeSelection(self.obj)
        super().closeEvent(event)

class SchemeFeature:

    labelfont = QtGui.QFont("Arial", 16, 2, False)

    def __init__(self, obj):
        """ Default constructor """
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} init object \n")
        self.Type = 'SchemeFeature'
        obj.addProperty('App::PropertyFileIncluded', 'Template', 'Base', 'A slot for SVG Template file')
        # https://github.com/FreeCAD/FreeCAD/blob/302d3f5b95030b81d1a4b45f40fc8d18f1ecbe49/src/App/PropertyFile.cpp#L613-L629
        if FreeCADVersion() >= 20.3:
            obj.Template = {"filter" : "Svg files (*.svg *.SVG);;All files (*.*)"}
        obj.Proxy = self
        # Using the PropertyLinkListHidden property type instead of just PropertyLinkList 
        # allows to avoid the intrusive dialog that popup when user try to remove any element from the sheet.
        obj.addProperty('App::PropertyEnumeration', 'Appearance', 'Appearance', 'Sheet appearance style', 8+16).Appearance = list(SheetAppearanceStyles)
        obj.Appearance = list(SheetAppearanceStyles)[0]   # Default appearance
        obj.addProperty('App::PropertyColor', 'LinesColor', 'Appearance', 'Color of scheme lines', 8+16).LinesColor = (0.0, 0.0, 0.0, 1.0)
        obj.addProperty('App::PropertyColor', 'PaperColor', 'Appearance', 'Color of paper', 8+16).PaperColor = (1.0, 1.0, 0.98, 1.0)
        # -----------------------------------------------------------------------------------------
        obj.addProperty('App::PropertyLinkListHidden', 'Elements', 'Base', 'Elements list of sheet', 8+16).Elements = []
        obj.setPropertyStatus("Elements", "Hidden")
        obj.addProperty('App::PropertyBool', 'GridVisible', 'Grid',
           'If this parameter is true, the grid is displayed on the sheet, otherwise it is not', 8+16).GridVisible = False
        obj.addProperty('App::PropertyLength', 'GridSpacing', 'Grid', 'Distance between grid lines', 8+16).GridSpacing = "5 mm"
        obj.addProperty('App::PropertyIntegerConstraint', 'MajorGridLineEvery', 'Grid', 'Major grid line every', 8+16).MajorGridLineEvery = (2, 1, 2147483647, 1)
        obj.addProperty('App::PropertyColor', 'MinorGridLineColor', 'Grid', 'Color of minor grid lines', 8+16).MinorGridLineColor = (0.5, 0.5, 0.5, 1.0)
        obj.addProperty('App::PropertyLength', 'MinorGridLineWidth', 'Grid', 'Width of minor grid lines', 8+16).MinorGridLineWidth = "0.05 mm"
        obj.addProperty('App::PropertyEnumeration', 'MinorGridLineStyle', 'Grid', 'Draw style of minor grid lines', 8+16).MinorGridLineStyle = list(QtLineStyles)
        obj.MinorGridLineStyle = list(QtLineStyles)[3]   # Default dot style
        obj.addProperty('App::PropertyColor', 'MajorGridLineColor', 'Grid', 'Color of major grid lines', 8+16).MajorGridLineColor = (0.5, 0.5, 0.5, 1.0)
        obj.addProperty('App::PropertyLength', 'MajorGridLineWidth', 'Grid', 'Width of major grid lines', 8+16).MajorGridLineWidth = "0.15 mm"
        obj.addProperty('App::PropertyEnumeration', 'MajorGridLineStyle', 'Grid', 'Draw style of major grid lines', 8+16).MajorGridLineStyle = list(QtLineStyles)
        obj.MajorGridLineStyle = list(QtLineStyles)[3]   # Default dot style
        obj.addProperty('App::PropertyBool', 'SnapEnabled', 'Grid', 'Snap enabled or not', 8+16).SnapEnabled = True
        obj.addProperty('App::PropertyBool', 'SnapToMajorGrid', 'Grid', 'Snap step major grid otherwise to minor grid', 8+16).SnapToMajorGrid = False
        self.obj = obj
        self.initWindow(obj)

    def onDocumentRestored(self, obj):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onDocumentRestored " + str(obj) + " \n")
        self.initWindow(obj)

    # This function is called in two cases:
    # after __init__() when the user creates an new object,
    # after onDocumentRestored() when the document is loaded after saving.
    def initWindow(self, obj):
        # Iterate existed windows
        subWindowsList = FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea).subWindowList()
        for sw in subWindowsList:
            if sw.__class__.__name__ == 'SchemeMDIView':
                if sw.obj == self.obj:
                    print('Tab is exist')
                    return
        self.scene = SchemeGraphicsScene(self.obj)
        view = SchemeGraphicsView()
        #print(str(view.cacheMode()), str(view.viewportUpdateMode()))
        view.setBackgroundBrush(QtGui.Qt.gray) # Add background color property
        view.setScene(self.scene)
        self.view = view

        # Find QMdiArea at MainWindow
        mainWindow = FreeCAD.Gui.getMainWindow()
        mdiArea = mainWindow.findChild(QtWidgets.QMdiArea)

        # Create MDIView
        self.frame = SchemeMDIView(obj)
        self.frame.setWindowTitle(obj.Name)
        self.frame.setWidget(self.view)
        self.frame.setAttribute(QtCore.Qt.WA_DeleteOnClose)  # Destroy on close  
        subWindow = mdiArea.addSubWindow(self.frame)         # Add QGraphicsView to this area and get QMdiSubWindow
        subWindow.show()                                     # Show getted QMdiSubWindow
        mdiArea.setActiveSubWindow(subWindow)                # Activate sub window

        self.appearance = SheetAppearanceStyles[obj.Appearance](obj)

        self.updateTemplate(obj)

        # Add methods to FeaturePython object https://forum.freecadweb.org/viewtopic.php?t=3691
        def addItem(self, item):
            obj.Elements += [item]
            return

        obj.addItem = addItem

        # Restoring all elements of sheet
        for x in obj.Elements:
            x.Proxy.initItem(x, obj)

    def onChanged(self, obj, prop):
        self.obj = obj   # Used when document is restored
        val = obj.getPropertyByName(prop)
        #FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} Change property: " + str(prop) + "=" + str(val) + "\n")
        if not hasattr(self, "scene"):
            return

        if prop == "Visibility":
            if val == True:
                self.initWindow(obj)    # Needs to show closed mdi window again
                FreeCAD.Gui.Selection.removeSelection(obj)  # Remove selection from sheet for comfortabilly work
            else:
                self.onDelete()
        elif prop == "Template":
            self.updateTemplate(obj)        # Set new template or update existed
        elif "Grid" in prop or "Snap" in prop:
            # !!! Grid parameters move to ViewProvider?
            self.scene.update()             # Force redraw sheet after visible changed
        elif prop == "LinesColor" or prop == "PaperColor":
            self.obj.Appearance = list(SheetAppearanceStyles)[-1]  # Activate last style
            return
        elif prop == "Appearance":
            self.appearance = SheetAppearanceStyles[val](obj)
            # Save viewport state
            transform = self.view.transform()
            center = self.view.mapToScene(self.view.viewport().rect()).boundingRect().center()
            #print(self.view.transform())
            # Set background color
            #    self.view.setBackgroundBrush(QtGui.Qt.black)
            # Update all elements of sheet
            self.updateTemplate(obj)
            for x in obj.Elements:
                x.Proxy.initItem(x, obj)
            # Restore viewport state
            self.view.setTransform(transform)
            self.view.centerOn(center)
            #print(self.view.transform())
        elif prop == "Label":
            self.frame.setWindowTitle(val)  # Change window title and tab text updated automatically too

    def updateTemplate(self, obj):
        if obj.Template != "":
            if hasattr(self, "svg_template"):
                self.scene.removeItem(self.svg_template)
                del self.svg_template
            svg = QtSvg.QGraphicsSvgItem()
            renderer = QtSvg.QSvgRenderer()
            renderer.setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
            with open(obj.Template, "r", encoding='utf-8') as f:
                data = f.read()
                data = transformUnits(data)
                data = self.appearance.decode(data)
                renderer.load(data.encode())
            svg.setSharedRenderer(renderer)
            svg.setElementId("")
            self.scene.svg_template = self.scene.addItem(svg)
            svg.setPos(0,0)
            svg.setZValue(-1) # QReal from -1 ... 1. -1 = go to back
            self.svg_template = svg

            # Set sheet size from template
            templateRect = svg.renderer().viewBoxF()
            obj.ViewObject.Width = templateRect.width()
            obj.ViewObject.Height = templateRect.height()
            if templateRect.width() >= templateRect.height():
                obj.ViewObject.Orientation = "Landscape"
            else:
                obj.ViewObject.Orientation = "Portrait"

            #print(svg.boundingRect(), svg.renderer().viewBoxF(), svg.renderer().aspectRatioMode())
            # Make margins around sheet for comfortable scrolling
            w = svg.boundingRect().width() * 0.25
            h = svg.boundingRect().height() * 0.25
            self.scene.setSceneRect(svg.boundingRect().adjusted(-w, -h, w, h))
            # Fit sheet to view
            self.view.fitInView(svg.boundingRect().adjusted(-20, -20, 20, 20), QtCore.Qt.KeepAspectRatio)

    def onSelect(self):
        # if Visibility == False this means that the window was closed by the user 
        # and is not in the list of tabs. When the window is highlighted, the tab should be restored.
        if self.obj.Visibility == False:
            self.obj.Visibility = True
        # Set current active window
        activateSceneTab(self.scene)
        # --- Workaround ---
        # If select a sheet and make a copy, then each element will be attached
        # to both the copy and the original. In order for the copy to occur without errors, 
        # the sheet must be copied along with all the sub-elements.
        # To avoid errors in the process of copying a sheet, when selecting a sheet, 
        # all its sub-elements are automatically allocated.
        # Copying the entire sheet (or sheets) works correctly only if the copy is inserted into the 3D viewing window.
        # But this does not allow to customize the sheet

        # If select an element, and then the sheet in which the element is located, 
        # then the selection of all sub elements will not occur. For this works, 
        # need to call recompute before select sub-elements.
        #FreeCAD.ActiveDocument.recompute()
        #for x in self.obj.Elements:
        #    print('add selection')
        #    FreeCAD.Gui.Selection.addSelection(x)  

    def onDelete(self):
        # If window exist delete all items and close it
        if isWindowExist(self.obj) is not None:
            delattr(self, "svg_template")
            for x in self.obj.Elements:
               delattr(x.Proxy, "item")
            self.frame.close()

    def execute(self, obj):
        """ Called on document recompute """
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} execute \n")

    #def shapeSetPosAndmakeMovable(self, item, x=0, y=0):
    #    item.setPos(x, y)
    #    item.setFlag(QtGui.QGraphicsItem.ItemIsMovable)
    #    item.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
    #    item.setFlag(QtGui.QGraphicsItem.ItemSendsGeometryChanges)
    #    #item.setElementId("")

    #def addLabel(self, text, x=0, y=0, font=labelfont):
    #    textitem = self.scene.addText(text, font)
    #    self.shapeSetPosAndmakeMovable(textitem, x, y)
    #    textitem.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
    #    # self.addShadow(textitem)
    #    return textitem

    #def addItem(self, item):
    #    self.obj.Elements += [item]
    #    return

    def clearSelection(self):
        self.scene.clearSelection()

    # Return None so serializer doesn't try to save self.item and other self. objects
    def __getstate__(self):
        return None

class BluePrintViewProvider(SchemeViewProviderSetup):

    def __init__(self, obj):
        """ Set this object to the proxy object of the actual view provider """
        # FreeCAD.Console.PrintMessage(f"{__class__.__name__} init")
        obj.addProperty('App::PropertyEnumeration', 'Orientation', 'Base', "Sheet orientation horizontal or vertical").Orientation = \
              ['Landscape', 'Portrait']
        obj.addProperty('App::PropertyLength', 'Width', 'Size', 'Sheet width getted from svg template (read only)').Width = '0 mm'
        obj.addProperty('App::PropertyLength', 'Height', 'Size', 'Sheet height getted from svg template (read only)').Height = '0 mm'
        obj.setPropertyStatus("Width", "ReadOnly")
        obj.setPropertyStatus("Height", "ReadOnly")
        obj.setPropertyStatus("Orientation", "ReadOnly")
        # !!! Save view port rect
        self.elements = []
        obj.Proxy = self

    def onDelete(self, obj, subelements):
        FreeCAD.Console.PrintMessage(f"{__class__.__name__} onDelete {str(obj)} subelements: {str(subelements)}\n")
        #onDelete find tab and destroy it

        # Remove sub-objects
        for x in obj.Object.Elements:
            FreeCAD.ActiveDocument.removeObject(x.Name)
        return True

    def updateData(self, obj, prop):
        self.elements = obj.Elements
        return

    def claimChildren(self):
        return self.elements

    #def getDetailPath(self, subname, path, append):
    #    FreeCAD.Console.PrintMessage(f"{__class__.__name__} getDetailPath: {str(subname)} {str(path)} {str(append)}\n")

    #def getElementPicked(self, pp):
    #    FreeCAD.Console.PrintMessage(f"{__class__.__name__} getElementPicked: {str(pp)}\n")

    #def onChanged(self, vp, prop):
    #    FreeCAD.Console.PrintMessage(f"{__class__.__name__} onChanged property: {str(prop)}\n")

    def getIcon(self):
        return getTreeviewIconPath('Scheme.svg')

    # Return None so serializer doesn't try to save self. objects
    def __getstate__(self):
        return None
