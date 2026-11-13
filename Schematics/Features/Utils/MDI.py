# -*- coding: utf-8 -*-
###############################################################################
#
#  MDI.py - Functions for control SubWindows in FreeCAD main window QMDIArea
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
from PySide6 import QtGui, QtCore, QtSvg, QtWidgets

def getMdiArea():
    return FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea)

def isWindowExist(obj):
    """ Try to find window which contain scheme object """
    subWindowsList = getMdiArea().subWindowList()
    for subWindow in subWindowsList:
        if subWindow.__class__.__name__ == 'SchemeMDIView':
            if subWindow.obj == obj:
                return subWindow
    return None

def tryToGetSchemeFromActiveWindow():
    """ Try to get Scheme object from current active window """
    activeSubWindow = getMdiArea().activeSubWindow()
    #if hasattr(activeSubWindow, 'obj') and hasattr(activeSubWindow.obj, 'Elements'):  # < --- Altrenative
    if activeSubWindow.__class__.__name__ == 'SchemeMDIView':
        return activeSubWindow.obj
    return None

def activeWindowIsScheme():
    """ Return True if current active window is Scheme """
    return True if tryToGetSchemeFromActiveWindow() is not None else False

def activateItemTab(item):
    activateSceneTab(item.scene())

def activateSceneTab(scene):
    mdi = getMdiArea()
    activeSubWindow = mdi.activeSubWindow()
    if hasattr(activeSubWindow, 'obj') and hasattr(activeSubWindow.obj, 'Elements') and activeSubWindow.obj.Proxy.scene == scene:
        print("Tab is activated yet")
    else:
        print("Activate tab")
        subWindowsList = mdi.subWindowList()
        for sw in subWindowsList:
            if hasattr(sw, 'obj'):
                if sw.obj.Proxy.scene == scene:
                    # When switching to the other sub window, the treeview will lose focus, so it needs to be returned.
                    w = QtWidgets.QApplication.focusWidget()
                    print(w.__class__.__name__)
                    mdi.setActiveSubWindow(sw)
                    w.setFocus()
                    break
