# -*- coding: utf-8 -*-
###############################################################################
#
#  Utils.py - Global utils: messaging, FreeCAD version, etc...
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtCore, QtSvg, QtWidgets
import FreeCAD

# ------------------------- StatusBar -------------------------

def StatusBarMessage(text, time_ms=0):
    FreeCAD.Gui.getMainWindow().statusBar().showMessage(text, time_ms)

# ------------------------- Dialogs -------------------------

def MessageBox(typeString, title, text):
    # PySide6: enums no longer expose .values; look the icon up by name instead
    dlg = QtWidgets.QMessageBox(getattr(QtWidgets.QMessageBox.Icon, typeString), title, text)
    dlg.exec()

# ---------------------- Toolbars actions ----------------------

def GetToolBarButtonAction(commandname):
    mw = FreeCAD.Gui.getMainWindow()
    toolbars = mw.findChildren(QtWidgets.QToolBar)
    for toolbar in toolbars:
        actions = toolbar.actions()
        for action in actions:
            if action.data() == commandname:
                action.setCheckable(True)
                return action
    return None

# ------------------------- Versioning -------------------------

def FreeCADVersion():
    major = FreeCAD.Version()[0]
    minor = FreeCAD.Version()[1]
    revision = FreeCAD.Version()[2]
    if revision.isnumeric():
        gitbuild = FreeCAD.Version()[3]
    else:
        revision = 0   # or None
        gitbuild = FreeCAD.Version()[2]
    gitbuild = int(''.join(filter(str.isdigit, gitbuild)))   # int(gitbuild.replace(" (Git)", ""))
    return (major, minor, revision), gitbuild

def FreeCADBuildVersion():
    return FreeCADVersion()[0]

def FreeCADGitVersion():
    return FreeCADVersion()[1]
