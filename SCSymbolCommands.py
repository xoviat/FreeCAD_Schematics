# -*- coding: utf-8 -*-
###############################################################################
#
#  SCSymbolCommands.py - Toolbar of symbol commands
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
import random
from SCUtils import *
from Features.Utils.MDI import *
import Features.Items.Symbol as Symbol

# this list must be got from symbols folder
SymbolList = {
    # (key) type : short label
    "Node" : "N",
    "Lamp" : "HL",
    "Button" : "SB",
    "RelayCoil" : "KM",
    "RelayContact" : "K",
}

SymbolCommandList = []

def addCommand(name, function=None):
    SymbolCommandList.append(name)
    if function is not None:
        FreeCAD.Gui.addCommand(name, function)

class SCDrawWireMode:
    """ Switch editor to edit wire mode """

    def GetResources(self):
        return {
            'Pixmap': getToolbarIconPath('DrawWireMode.svg'),
            'MenuText': "Switch editor to draw wire mode",
            'ToolTip': "Switch editor to draw wire mode"
        }

    def Activated(self):
        #MessageBox("Warning", "FreeCAD Schematics", "Tool for adding wire connections is under development")
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            scheme.Proxy.scene.enableDrawWireMode()
        #FreeCAD.ActiveDocument.recompute()
        return

    def IsActive(self):
        return activeWindowIsScheme()

addCommand('SCDrawWireMode', SCDrawWireMode())

addCommand('Separator')

class SymbolCommand:
    """ Add Symbol command """

    def __init__(self, type, help):
        self.Type = type
        self.Code = help

    def GetResources(self):
        
        return {'Pixmap': getSymbolIconPath(f"{self.Type}.svg"),
                'MenuText': f"Add {self.Type} symbol",
                'ToolTip': f"Add {self.Code}"}

    def Activated(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            symbolObj = Symbol.Create(scheme, self.Type, random.randint(100, 300), random.randint(100, 200))
            #scheme.Proxy.addShadow(obj.Proxy.item)
            #scheme.Proxy.addColorize(obj.Proxy.item, QtGui.Qt.white, 0.7)
            scheme.Proxy.scene.disableAllModes()    # Set symbol place mode
            FreeCAD.ActiveDocument.recompute()
        return

    def IsActive(self):
        return activeWindowIsScheme()

def AddSymbolCommand(type):
    cmd = 'SC' + type
    FreeCAD.Gui.addCommand(cmd, SymbolCommand(type, SymbolList[type]))   # Add command to FreeCAD Envorinment
    SymbolCommandList.append(cmd)                       # Add command to list of Symbols toolbar

# generate all commands
for key in SymbolList:
    AddSymbolCommand(key)
