# -*- coding: utf-8 -*-
###############################################################################
#
#  Observers.py - Setup observers
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
from PySide2 import QtWidgets
from Features.Utils.ActionsReplacer import *
from Features.Utils.MDI import *
from Features.Utils.Printing import PrintPreviewAction


def setup():
    # Connect function to subWindowActivated event
    getMdiArea().subWindowActivated.connect(subWindowChanged)
    # Register actions to ActionsReplacer
    registerAction("Std_PrintPreview", PrintPreviewAction)
    registerAction("Std_ViewZoomIn", SchemeZoomIn)
    registerAction("Std_ViewZoomOut", SchemeZoomOut)

# This code invoked if user has changed the active tab.
def subWindowChanged():
    FreeCAD.Gui.Selection.clearSelection()
    print('subWindowChanged + clearSelection')
    # If current active window is schematics replace original actions
    actionsSetActivate(activeWindowIsScheme())
    FreeCAD.ActiveDocument.recompute()

def SchemeZoomIn():
    scheme = tryToGetSchemeFromActiveWindow()
    if scheme is not None:
        scheme.Proxy.view.zoom(1.25)

def SchemeZoomOut():
    scheme = tryToGetSchemeFromActiveWindow()
    if scheme is not None:
        scheme.Proxy.view.zoom(0.8)