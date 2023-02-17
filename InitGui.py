# -*- coding: utf-8 -*-
###############################################################################
#
#  InitGui.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD

class SchematicsWorkbench(FreeCAD.Gui.Workbench):

    from SCUtils import getIconPath

    MenuText = "Schematics"
    ToolTip = "Workbench for Electric circuit creation"
    Icon = getIconPath("Schematics.svg")

    def Initialize(self):
        """ This function is executed when FreeCAD starts """

        import PySide2
        import SCCommands, SCSymbolCommands
    
        print(f"QtCore Version: {PySide2.QtCore.qVersion()}")

        cmdList = SCCommands.CommandList
        self.appendToolbar("Scheme sheet managing", cmdList)
        symbolCmdList = SCSymbolCommands.SymbolCommandList
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

FreeCAD.Gui.addWorkbench(SchematicsWorkbench())

# Activate all observers at FreeCAD started
import Features.Observers
Features.Observers.setup()

# Move to features folder separate class
class GuiDocumentObserver:

    # onDocumentClose
    # Close all connected tabs!!!

    def slotDeletedObject(self, viewProviderObject):
        if viewProviderObject.TypeId == 'Gui::ViewProviderPythonFeature':
            print('slotDeletedObject')
            print('Object delete: ', viewProviderObject.Object.Name)
            # If method exist invoke it
            if hasattr(viewProviderObject.Object.Proxy, 'onDelete'):
                viewProviderObject.Object.Proxy.onDelete()

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
