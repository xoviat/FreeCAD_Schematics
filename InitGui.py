# -*- coding: utf-8 -*-
###############################################################################
#
#  InitGui.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
from SCUtils import getIconPath

class SchematicsWorkbench(FreeCAD.Gui.Workbench):

    # NOTE: FreeCAD exec()s InitGui.py with separate globals()/locals() dicts,
    # so names bound at module level (like getIconPath imported above) are NOT
    # visible inside class/function bodies here. The icon is therefore
    # assigned after the class body — see below.
    MenuText = "Schematics"
    ToolTip = "Workbench for Electric circuit creation"

    def Initialize(self):
        """ This function is executed when FreeCAD starts """

        # PySide6 does not expose submodules lazily: `import PySide6` then
        # `PySide6.QtCore...` raises AttributeError. Import QtCore explicitly.
        from PySide6 import QtCore
        from Schematics.Toolbars import SymbolCommands
        from Schematics.Toolbars import Commands

        print(f"QtCore Version: {QtCore.qVersion()}")

        cmdList = Commands.CommandList
        self.appendToolbar("Scheme sheet managing", cmdList)
        symbolCmdList = SymbolCommands.SymbolCommandList
        self.appendToolbar("Scheme sheet items", symbolCmdList)

    def Activated(self):
        """ This function is executed when the workbench is activated """
        return

    def Deactivated(self):
        """ This function is executed when the workbench is deactivated """
        return

    def ContextMenu(self, recipient):
        """ This is executed whenever the user right-clicks on screen """

    def GetClassName(self):
        """ this function is mandatory if this is a full python workbench """
        return "Gui::PythonWorkbench"

# See the note in the class body: assigned at module level on purpose.
SchematicsWorkbench.Icon = getIconPath("Schematics.svg")

# FreeCAD may execute this file twice (workbench installed in the user Mod
# directory AND passed with -M for development): a second registration
# raises "'SchematicsWorkbench' already exists" and aborts FreeCAD.
if "SchematicsWorkbench" not in FreeCAD.Gui.listWorkbenches():
    FreeCAD.Gui.addWorkbench(SchematicsWorkbench())

# Embedding the Schematics API in FreeCAD
from Schematics.API import API
# Activate all observers at FreeCAD started.
# Use an aliased import: a plain `import Schematics.Features.Observers` would
# rebind the name "Schematics" to the package and clobber the API instance below.
import Schematics.Features.Observers as SCObserversModule
SCObserversModule.setup()
# The `global` is required: without it `Schematics = API()` binds only in the
# throwaway exec() locals dict and would never reach FreeCAD's Python console
# (__main__), where the README examples (Schematics.Rectangle() ...) run.
global Schematics
Schematics = API()

# Move to features folder separate class
class GuiDocumentObserver:

    # onDocumentClose
    # Close all connected tabs!!!

    def slotDeletedObject(self, viewProviderObject):
        # During teardown the view provider can already be dead: attribute
        # access raises ReferenceError, which must not escape into FreeCAD.
        try:
            if viewProviderObject.TypeId == 'Gui::ViewProviderPythonFeature':
                print('slotDeletedObject')
                print('Object delete: ', viewProviderObject.Object.Name)
                # If method exist invoke it
                if hasattr(viewProviderObject.Object.Proxy, 'onDelete'):
                    viewProviderObject.Object.Proxy.onDelete()
        except (ReferenceError, RuntimeError, AttributeError):
            pass

    def slotDeletedDocument(self, document):
        # Scheme MDI windows are Qt widgets owned by the main window, not
        # by the document: when the document closes nothing else destroys
        # them, and a stale window keeps repainting the deleted object
        # (one traceback per repaint, symbol commands failing on the dead
        # sheet). Close them synchronously — a deferred close could still
        # lose the race against a pending paint of the deleted items.
        try:
            from Schematics.Features.Utils.MDI import closeSchemeWindowsOfDocument
            n = closeSchemeWindowsOfDocument(document)
            print(f"slotDeletedDocument: closed {n} scheme window(s)")
        except Exception as e:
            print(f"closeSchemeWindowsOfDocument failed: {e}")

    def slotCreatedObject(self, viewProviderObject):
        if viewProviderObject.TypeId == 'Gui::ViewProviderPythonFeature':
            print('Object create: ', viewProviderObject.Object.Name)
            # Ignore object that not have Proxy
            if hasattr(viewProviderObject.Object, "Proxy"):
                if viewProviderObject.Object.Proxy is None:
                    print("This object is absolutely new or created after paste")
                    return
                else:
                    print("This object is restored after Undo/Redo/Delete commands")
                    # invoke special method for restore object after delete if object have it
                    if hasattr(viewProviderObject.Object.Proxy, 'onRestore'):
                        viewProviderObject.Object.Proxy.onRestore()

DocumentObserver = GuiDocumentObserver()
FreeCAD.Gui.addDocumentObserver(DocumentObserver)

class SelObserver:
    # def onSelectionChanged(self, doc, obj, sub, pnt):
    #    FreeCAD.Console.PrintMessage("onSelectionChanged "+str(doc)+","+str(obj)+","+str(sub)+","+str(pnt)+" \n")

    def addSelection(self, doc, obj, sub, pnt):
        obj = FreeCAD.getDocument(doc).getObject(obj)
        if hasattr(obj, 'Elements'):
            FreeCAD.Console.PrintMessage(f"addSelection {str(doc)}, {str(obj)}, {str(sub)}, {str(pnt)} \n")
            obj.Proxy.onSelect()
            # Select all sub elements (for copy all sheet)
            # Activate tab
        if hasattr(obj, 'Proxy') and hasattr(obj.Proxy, 'setSelected'):
            FreeCAD.Console.PrintMessage(f"addSelection {str(doc)}, {str(obj)}, {str(sub)}, {str(pnt)} \n")
            obj.Proxy.setSelected(True)
            # Activate tab

    def removeSelection(self, doc, obj, sub):
        obj = FreeCAD.getDocument(doc).getObject(obj)
        if hasattr(obj, 'Proxy') and hasattr(obj.Proxy, 'setSelected'):
            FreeCAD.Console.PrintMessage(f"removeSelection {str(doc)}, {str(obj)}, {str(sub)} \n")
            obj.Proxy.setSelected(False)

    def clearSelection(self, doc):
        # ActiveDocument is None while no document is open (e.g. right
        # after the last one was closed).
        if FreeCAD.ActiveDocument is None:
            return
        for x in FreeCAD.ActiveDocument.RootObjects:
            if hasattr(x, 'Elements'):  # obj.Proxy.__class__.__name__=='SchemeFeature'
                x.Proxy.clearSelection()
        print("clearSelection")

    # def setPreselection(self, doc, obj, sub):
    #    FreeCAD.Console.PrintMessage("setPreselection "+str(doc)+","+str(obj)+","+str(sub)+" \n")

    # def removePreselection(self, doc, obj, sub):
    #    FreeCAD.Console.PrintMessage("removePreselection "+str(doc)+","+str(obj)+","+str(sub)+" \n")

    # def pickedListChanged():
    #    FreeCAD.Console.PrintMessage("pickedListChanged \n")

# Init Selection Observer
s = SelObserver()
FreeCAD.Gui.Selection.addObserver(s)
