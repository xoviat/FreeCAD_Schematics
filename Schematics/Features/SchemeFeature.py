# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeFeature.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtCore, QtSvg, QtSvgWidgets, QtWidgets
from Schematics.Features.SchemeViewAndScene import SchemeGraphicsView, SchemeGraphicsScene
from Schematics.Features.Utils.SVGSymbolsCache import transformUnits
from SCUtils import *
from Schematics.Features.Utils.SVG import *
from Schematics.Features.Utils.MDI import *
from Schematics.Features.GridMixin import *
import Schematics.Features.Utils.SoftMigration as SoftMigration
from Schematics.Utils import *


def CreateScheme():
    # ! Open transaction for sheet is not supported.
    # If the sheet has been deleted all the hidden items then deleted too, and they are no longer recoverable
    #FreeCAD.ActiveDocument.openTransaction(f"Sheet added")
    obj = FreeCAD.ActiveDocument.addObject('App::FeaturePython', 'Schematic')
    SchemeFeature(obj)
    SchemeViewProvider(obj.ViewObject)
    obj.Proxy.initWindow(obj)
    #FreeCAD.ActiveDocument.commitTransaction()
    return obj

class SchemeMDIView(QtWidgets.QMdiSubWindow):

    def __init__(self, obj):
        super().__init__()
        self.obj = obj
        self.setMouseTracking(True)

    def closeEvent(self, event):
        #print("Tab is closed")
        setattr(self.obj, "Visibility", False)
        # removeSelection is mandatory for invoke setSelection event if user select sheet again
        FreeCAD.Gui.Selection.removeSelection(self.obj)
        super().closeEvent(event)

class SchemeFeature:

    def __init__(self, obj):
        """ Default constructor """
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} init object \n")
        self.Type = 'SchemeFeature'
        obj.addProperty('App::PropertyFileIncluded', 'Template', 'Base', 'A slot for SVG Template file')
        # https://github.com/FreeCAD/FreeCAD/blob/302d3f5b95030b81d1a4b45f40fc8d18f1ecbe49/src/App/PropertyFile.cpp#L613-L629
        if FreeCADGitVersion() >= 31900:
            obj.Template = {"filter": "Svg files (*.svg *.SVG);;All files (*.*)"}
        # Using the PropertyLinkListHidden property type instead of just PropertyLinkList 
        # allows to avoid the intrusive dialog that popup when user try to remove any element from the sheet.
        obj.addProperty('App::PropertyEnumeration', 'Appearance', 'Appearance', 'Sheet appearance style', 8+16).Appearance = list(SheetAppearanceStyles)
        obj.Appearance = list(SheetAppearanceStyles)[0]   # Default appearance
        obj.addProperty('App::PropertyColor', 'LinesColor', 'Appearance', 'Color of scheme lines', 8+16).LinesColor = (0.0, 0.0, 0.0, 1.0)
        obj.addProperty('App::PropertyColor', 'PaperColor', 'Appearance', 'Color of paper', 8+16).PaperColor = (1.0, 1.0, 0.98, 1.0)
        # -----------------------------------------------------------------------------------------
        obj.addProperty('App::PropertyLinkListHidden', 'Elements', 'Base', 'Elements list of sheet', 8+16).Elements = []
        obj.setPropertyStatus("Elements", "Hidden")
        obj.addProperty('App::PropertyBool', 'SnapEnabled', 'Grid', 'Snap enabled or not', 8+16).SnapEnabled = True
        obj.addProperty('App::PropertyBool', 'SnapToMajorGrid', 'Grid', 'Snap step major grid otherwise to minor grid', 8+16).SnapToMajorGrid = False
        obj.Proxy = self

    def onDocumentRestored(self, obj):
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} onDocumentRestored " + str(obj) + " \n")
        SMobj = SoftMigration.Start(obj)
        self.__init__(SMobj)
        self.smobj = SMobj
        #SMobj.cleanUp()
        obj.ViewObject.Proxy.onDocumentRestored(obj.ViewObject)
        self.initWindow(obj)

    # This function is called in two cases:
    # after __init__() when the user creates an new object,
    # after onDocumentRestored() when the document is loaded after saving.
    def initWindow(self, obj):
        # Iterate existed windows
        subWindowsList = FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea).subWindowList()
        for sw in subWindowsList:
            if sw.__class__.__name__ == 'SchemeMDIView':
                if sw.obj == obj:
                    print('Tab is exist')
                    return
        self.scene = SchemeGraphicsScene(obj)
        view = SchemeGraphicsView()
        #print(str(view.cacheMode()), str(view.viewportUpdateMode()))
        view.setBackgroundBrush(QtCore.Qt.gray) # Add background color property
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
        elif prop == "LinesColor" or prop == "PaperColor":
            obj.Appearance = list(SheetAppearanceStyles)[-1]  # Activate last style
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
        elif prop == "Text":
            self.frame.setWindowTitle(val)  # Change window title and tab text updated automatically too
        if "Grid" in prop or "Snap" in prop:
            # !!! Grid parameters move to ViewProvider?
            self.scene.update()             # Force redraw sheet after visible changed

    def updateTemplate(self, obj):
        if obj.Template != "":
            if hasattr(self, "svg_template"):
                self.scene.removeItem(self.svg_template)
                del self.svg_template
            svg = QtSvgWidgets.QGraphicsSvgItem()
            renderer = QtSvg.QSvgRenderer()
            renderer.setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
            with open(obj.Template, "r", encoding='utf-8') as f:
                data = f.read()
                data = transformUnits(data)
                data = self.appearance.decode(data)
                renderer.load(data.encode())
            # To the drawing of the template not going slowly, do not create large (the size of a sheet)
            # groups of elements, and it is also better to replace the text with contours.
            #svg.setCacheMode(svg.NoCache)
            svg.setMaximumCacheSize(QtCore.QSize(15000, 15000))
            # PySide6: enum values must be read from the class, not the instance
            svg.setFlags(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemClipsToShape)
            svg.setSharedRenderer(renderer)
            svg.setElementId("")
            self.scene.svg_template = self.scene.addItem(svg)
            svg.setPos(0, 0)
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

    def clearSelection(self):
        self.scene.clearSelection()

    # Return None so serializer doesn't try to save self.item and other self. objects
    def __getstate__(self):
        return None

    # Mandatory method!
    def __setstate__(self, data):
        return None

class SchemeViewProvider(GridViewProperties):

    def __init__(self, vobj):
        """ Set this object to the proxy object of the actual view provider """
        # FreeCAD.Console.PrintMessage(f"{__class__.__name__} init")
        # Move that to data
        vobj.addProperty('App::PropertyEnumeration', 'Orientation', 'Base', "Sheet orientation horizontal or vertical").Orientation = \
              ['Landscape', 'Portrait']
        vobj.addProperty('App::PropertyLength', 'Width', 'Size', 'Sheet width getted from svg template (read only)').Width = '0 mm'
        vobj.addProperty('App::PropertyLength', 'Height', 'Size', 'Sheet height getted from svg template (read only)').Height = '0 mm'
        vobj.setPropertyStatus("Width", "ReadOnly")
        vobj.setPropertyStatus("Height", "ReadOnly")
        vobj.setPropertyStatus("Orientation", "ReadOnly")
        # !!! Save view port rect
        super().__init__(vobj)
        vobj.Proxy = self

    # This method called from obj.onDocumentRestored
    def onDocumentRestored(self, vobj):
        SMobj = SoftMigration.Start(vobj)
        self.__init__(SMobj)
        #SMobj.cleanUp()

    def onChanged(self, vobj, prop):
        val = vobj.getPropertyByName(prop)
        FreeCAD.Console.PrintMessage(f"{self.__class__.__name__} property changed: " + str(prop) + "=" + str(val) + "\n")
        if not hasattr(vobj.Object.Proxy, "scene"):
            return
        super().onChanged(vobj, prop)
        return

    def onDelete(self, vobj, subelements):
        FreeCAD.Console.PrintMessage(f"{__class__.__name__} onDelete {str(vobj)} subelements: {str(subelements)}\n")
        #onDelete find tab and destroy it

        # Remove sub-objects
        for x in vobj.Object.Elements:
            FreeCAD.ActiveDocument.removeObject(x.Name)
        return True

    def updateData(self, vobj, prop):
        self.elements = vobj.Elements
        return

    def claimChildren(self):
        return self.elements

    def getIcon(self):
        return getTreeviewIconPath('Scheme.svg')

    # Return None so serializer doesn't try to save self. objects
    def __getstate__(self):
        return None

    # Mandatory method!
    def __setstate__(self, data):
        return None

    # View provider for not 3D view FeaturePython classes which involve:
    # QGraphicsView, QGraphicsScene, QGraphicsItem Qt classes like Blueprint or Blueprint elements...
    # This code is repeated in many classes and placed in a separate file to not clogging up the code.

    def attach(self, obj):
        """ Setup the scene sub-graph of the view provider, this method is mandatory """
        from pivy import coin  # Without this, the icon will be displayed in grayscale
        # App.Console.PrintMessage("Not3DViewProvider attach \n")
        drawingDisplayMode = coin.SoGroup()
        obj.addDisplayMode(drawingDisplayMode, "Drawing")

        # Moved from __init__ to get rid of super().__init__(vobj)
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