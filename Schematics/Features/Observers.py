# -*- coding: utf-8 -*-
###############################################################################
#
#  Observers.py - Setup observers
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from Schematics.Features.Utils.ActionsReplacer import *
from Schematics.Features.Utils.MDI import *
from Schematics.Features.Utils.Printing import PrintPreviewAction
from SCUtils import *
from Schematics.Utils import MessageBox


def setup():
    # Connect function to subWindowActivated event
    getMdiArea().subWindowActivated.connect(subWindowChanged)
    # Register actions to ActionsReplacer
    registerAction("Std_PrintPreview", PrintPreviewAction)
    registerAction("Std_Print", PrintPreviewAction)
    registerAction("Std_Export", Plug)
    registerAction("Std_Import", Plug)
    registerAction("Std_PrintPdf", Plug)
    registerAction("Std_ViewZoomIn", SchemeZoomIn)
    registerAction("Std_ViewZoomOut", SchemeZoomOut)

# This code invoked if user has changed the active tab.
def subWindowChanged():
    # If current active window is schematics replace original actions
    if activeWindowIsScheme():
        actionsSetActivate(True)
        FreeCAD.Gui.Selection.clearSelection()
        #print('schemeSelected + clearSelection')
    else:
        actionsSetActivate(False)
    # No document may exist yet (the signal also fires during startup)
    if FreeCAD.ActiveDocument is not None:
        FreeCAD.ActiveDocument.recompute() # ! Update toolbars buttons state

def Plug():
    MessageBox("Information", "Schematics", "This function unsupported for schematics")

def SchemeZoomIn():
    scheme = tryToGetSchemeFromActiveWindow()
    if scheme is not None:
        scheme.Proxy.view.zoom(1.25)

def SchemeZoomOut():
    scheme = tryToGetSchemeFromActiveWindow()
    if scheme is not None:
        scheme.Proxy.view.zoom(0.8)