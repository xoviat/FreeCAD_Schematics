# -*- coding: utf-8 -*-
###############################################################################
#
#  SCCommands.py - Main toolbar commands
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from Features.Utils.MDI import *
from Features.SchemeFeature import CreateScheme
from SCUtils import *
from Features.Utils.QtEnums import *
from Features.Utils.SVG import *

CommandList = []   

def addCommand(name, function = None):
    CommandList.append(name)
    if function is not None:
        FreeCAD.Gui.addCommand(name, function)

class SCNewScheme:
    """ Add a new sheet for scheme drawing """

    def GetResources(self):
        return {
            'Pixmap': getToolbarIconPath('NewScheme.svg'),
            'MenuText': "Add a new sheet for scheme drawing",
            'ToolTip': "Add a new sheet for scheme drawing"
        }

    def Activated(self):
        if FreeCAD.ActiveDocument == None:
            FreeCAD.newDocument()
        bp = CreateScheme()
        bp.Template = getTemplatePath('Default.svg')
        FreeCAD.ActiveDocument.recompute()
        return

    def IsActive(self):
        return True

addCommand('SCNewScheme', SCNewScheme())

class SCGrid:
    """ Show or hide the grid on the sheet """

    def GetResources(self):
        self.action = None
        return {
            'Pixmap': getToolbarIconPath('Grid.svg'),
            'MenuText': "Show or hide the grid on the sheet",
            'ToolTip': "Show or hide the grid on the sheet"
        }

    def Activated(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            scheme.GridVisible = not scheme.GridVisible
        self.action.setChecked(scheme.GridVisible) # ! Duplicated to avoid blinking when pressed
        return

    def IsActive(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is None:
            return False
        if self.action is None:
            self.action = GetToolBarButtonAction("SCGrid")
        self.action.setChecked(scheme.GridVisible)
        return True

addCommand('SCGrid', SCGrid())

class SCSnap:
    """ Enable / Disable Snap sheet items to grid """

    def GetResources(self):
        self.action = None
        return {
            'Pixmap': getToolbarIconPath('Snap.svg'),
            'MenuText': "Enable / Disable Snap sheet items to grid",
            'ToolTip': "Enable / Disable Snap sheet items to grid"
        }

    def Activated(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            scheme.SnapEnabled = not scheme.SnapEnabled
        self.action.setChecked(scheme.SnapEnabled)  # ! Duplicated to avoid blinking when pressed
        return

    def IsActive(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is None:
            return False
        if self.action is None:
            self.action = GetToolBarButtonAction("SCSnap")
        self.action.setChecked(scheme.SnapEnabled)
        return True

addCommand('SCSnap', SCSnap())

class SCSheetAppearance:
    """ Change sheet appearance """

    def GetResources(self):
        return {
            'Pixmap': getToolbarIconPath('SheetAppearance.svg'),
            'MenuText': "Change sheet appearance",
            'ToolTip': "Change sheet appearance"
        }

    def Activated(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            scheme.Appearance = nextEnum(SheetAppearanceStyles, scheme.Appearance)
        return

    def IsActive(self):
        return activeWindowIsScheme()

addCommand('SCSheetAppearance', SCSheetAppearance())

# Duplicate sheet command
