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
