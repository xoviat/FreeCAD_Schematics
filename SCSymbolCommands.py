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
from Features.Items.Effects import *
from Features.Items.Actions import *
from Features.Items.Polyline import *
from Features.Items.Rectangle import *
from Features.Items.Ellipse import *
from Features.Items.Line import *

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

#addCommand('SCDrawWireMode', SCDrawWireMode())

addCommand('Separator')

class PrimitiveCommand:
    """ Add primitive """

    def __init__(self, name, inst):
        self.name = name
        self.inst = inst
        addCommand('SC' + self.name, self)

    def GetResources(self):
        return {
            'Pixmap': getToolbarIconPath(self.name + '.svg'),
            'MenuText': "Add " + self.name,
            'ToolTip': "Add " + self.name
        }

    def Activated(self):
        obj = Draw(self.inst())

    def IsActive(self):
        return activeWindowIsScheme()

PrimitiveCommand('Polyline', Polyline)
PrimitiveCommand('Rectangle', Rectangle)
PrimitiveCommand('Ellipse', Ellipse)
PrimitiveCommand('Line', Line)

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
            obj = Symbol.Create(scheme, self.Type, random.randint(100, 300), random.randint(100, 200))
            FreeCAD.ActiveDocument.recompute()
        return

    def IsActive(self):
        return activeWindowIsScheme()

def AddSymbolCommand(type):
    cmd = 'SC' + type
    FreeCAD.Gui.addCommand(cmd, SymbolCommand(type, SymbolList[type]))   # Add command to FreeCAD Environment
    SymbolCommandList.append(cmd)                       # Add command to list of Symbols toolbar

# generate all commands
for key in SymbolList:
    AddSymbolCommand(key)

addCommand('Separator')

class FunctionCommand:
    """ Item(s) change command class """

    def __init__(self, name, func=None, text=None):
        self.name = name
        self.func = func
        self.text = text
        addCommand('SC' + self.name, self)

    def GetDescription(self):
        return self.text

    def GetResources(self):
        return {
            'Pixmap': getToolbarIconPath(self.name + '.svg'),
            'MenuText': self.GetDescription(),
            'ToolTip': self.GetDescription()
        }

    def Activated(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            for item in scheme.Proxy.scene.selectedItems():
                self.func(item.obj)
        # Update sheet after apply effects or actions to items
        scheme.Proxy.scene.update()

    def IsActive(self):
        return activeWindowIsScheme()

FunctionCommand('ToFront', toFront, "Bring to front")
FunctionCommand('ToBottom', toBack, "Bring to back")
#FunctionCommand('HFlip', hFlip, "Flip horizontally")
#FunctionCommand('VFlip', vFlip, "Flip vertically")
FunctionCommand('TurnLeft', turnLeft, "Turn left to 90 degrees")
FunctionCommand('TurnRight', turnRight, "Turn right to 90 degrees")
#lockTransformations
#unlockTransformations

addCommand('Separator')

FunctionCommand('Shadow', addShadow, "Add shadow effect to item")
FunctionCommand('Colorize', addColorize, "Add colorize effect to item")
FunctionCommand('Blur', addBlur, "Add blur effect to item")
FunctionCommand('RemoveEffect', removeEffect, "Remove effect from item")

