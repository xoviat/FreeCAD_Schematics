# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeObj.py - Scheme Obj class. Contains actions that apply to all items.
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

class Item:

    def attach(self, obj):      
        """ Setup the scene sub-graph of the view provider, this method is mandatory """
        from pivy import coin    # Without that icon is be gray  
        # App.Console.PrintMessage("Not3DViewProviderr attach \n")
        drawingDisplayMode = coin.SoGroup()
        obj.addDisplayMode(drawingDisplayMode, "Drawing");
        
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