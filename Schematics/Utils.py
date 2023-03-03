# -*- coding: utf-8 -*-
###############################################################################
#
#  Utils.py - Global utils: messaging, FreeCAD version, etc...
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets
import FreeCAD

# ------------------------- StatusBar -------------------------

def StatusBarMessage(text, time_ms=0):
    FreeCAD.Gui.getMainWindow().statusBar().showMessage(text, time_ms)

# ------------------------- Dialogs -------------------------

def MessageBox(typeString, title, text):
    dlg = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.values[typeString], title, text)
    dlg.exec_()

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
        version = minor + "." + revision
    else:
        version = minor
    return float(version)

def FreeCADVersionIsHigherThan(major, minor, revision):
    FCmajor = FreeCAD.Version()[0]
    FCminor = FreeCAD.Version()[1]
    FCrevision = FreeCAD.Version()[2]
    if not FCrevision.isnumeric():
        FCrevision = 0
    if FCmajor > major and FCminor > minor and FCrevision > revision:
        return True
    return False

# def FreeCADGitVersionIsHigherOrEqualThan(number):
#    return True