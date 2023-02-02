# -*- coding: utf-8 -*-
###############################################################################
#
#  SCUtils.py - Folder locations, messaging, FreeCAD version...
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

# -------------------- Paths to folders --------------------

import os

dir = os.path.dirname(__file__)
pathToIconsFolder = os.path.join(dir, 'Icons')
pathToTreeviewIconsFolder = os.path.join(pathToIconsFolder, 'Treeview')
pathToToolbarsIconsFolder = os.path.join(pathToIconsFolder, 'Toolbars')
pathToSymbolIconsFolder = os.path.join(pathToToolbarsIconsFolder, 'Symbols')
pathToTemplatesFolder = os.path.join(dir, 'Templates')
pathToSymbolsFolder = os.path.join(dir, 'Symbols')
pathToTranslationsFolder = os.path.join(dir, 'translations')

def getRootPath(file):
    return os.path.join(dir, file)

def getIconPath(file):
   return os.path.join(pathToIconsFolder, file)

def getTreeviewIconPath(file):
   return os.path.join(pathToTreeviewIconsFolder, file)

def getToolbarIconPath(file):
   return os.path.join(pathToToolbarsIconsFolder, file)

def getSymbolIconPath(file):
   return os.path.join(pathToSymbolIconsFolder, file)

def getSymbolPath(file):
   return os.path.join(pathToSymbolsFolder, file)

def getTemplatePath(file):
   return os.path.join(pathToTemplatesFolder, file)

# ------------------------- StatusBar -------------------------

import FreeCAD

def StatusBarMessage(text, time_ms=0):
    FreeCAD.Gui.getMainWindow().statusBar().showMessage(text, time_ms)

# ------------------------- Dialogs -------------------------

from PySide2 import QtGui, QtCore, QtSvg, QtWidgets

def MessageBox(typeString, title, text):
    dlg = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.values[typeString], title, text)
    dlg.exec_()

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

def FreeCADVersionIsHigherThan(major,minor,revision):
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

