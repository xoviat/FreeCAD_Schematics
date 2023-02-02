
# View provider for not 3D view FeaturePython classes which involve: 
# QGraphicsView, QGraphicsScene, QGraphicsItem Qt classes like Blueprint or Blueprint elements...
# This code is repeated in many classes and placed in a separate file to not clogging up the code.

class SchemeViewProviderSetup:

    def attach(self, obj):
        """ Setup the scene sub-graph of the view provider, this method is mandatory """
        from pivy import coin     # Without this, the icon will be displayed in grayscale
        # App.Console.PrintMessage("Not3DViewProvider attach \n")
        drawingDisplayMode = coin.SoGroup()
        obj.addDisplayMode(drawingDisplayMode, "Drawing")
        
        # Moved from __init__ to get rid of super().__init__(obj)
        # These settings are used for the 3D view, but this object is part of the 2D sheet. 
        # Therefore, these properties are not needed and should be hidden.
        # BluePrint sheet can ONLY be selected via the treeview
        obj.setPropertyStatus("DisplayMode", "Hidden")
        obj.setPropertyStatus("OnTopWhenSelected", "Hidden")
        obj.setPropertyStatus("SelectionStyle", "Hidden") # Theoretical can be not hidden for elments to change the selection area of the object
        return

    def getDisplayModes(self, obj):
        """ Return a list of display modes. """
        # App.Console.PrintMessage("Not3DViewProvider getDisplayModes \n")
        return ["Drawing"]

    def getDefaultDisplayMode(self):
        """ Return the name of the default display mode. It must be defined in getDisplayModes. """
        # App.Console.PrintMessage("Not3DViewProvider getDefaultDisplayMode \n")
        return "Drawing"