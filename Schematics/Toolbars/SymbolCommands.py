# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolCommands.py - Toolbar of symbol commands
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from SCUtils import *
from Schematics.Features.Functions.Effects import *
from Schematics.Features.Functions.Transforms import *
from Schematics.Features.Functions.TextStyle import *
from Schematics.Features.Items.Polyline import *
from Schematics.Features.Items.Ellipse import *
from Schematics.Features.Items.Line import *
from Schematics.Features.Items.Text import *
from Schematics.Features.Items.Symbol import *
from Schematics.Features.Utils.SVGSymbolsCache import loadSVGSymbol

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
#addCommand('Separator')

class PrimitiveCommand:
    """ Add primitive """

    def __init__(self, name, inst, group=None):
        self.name = name
        self.inst = inst
        self.group = group
        addCommand('SC' + self.name, self)

    def GetResources(self):
        iconPath = getToolbarIconPath(f"{self.name}.svg")
        if not os.path.exists(iconPath):
            iconPath = getSymbolIconPath(f"{self.name}.svg")
        if not os.path.exists(iconPath) and self.group is not None:
            iconPath = getSymbolPath(f"{os.path.join('GOST',os.path.join(self.group,self.name))}.svg")
        self.iconPath = iconPath
        return {
            'Pixmap': iconPath,
            'MenuText': "Add " + self.name,
            'ToolTip': "Add " + self.name
        }

    def Activated(self):
        self.inst.typ = None
        if self.group is not None:
            self.inst.typ = self.name   # ! Only for symbols
            self.inst.grp = self.group  # ! Only for symbols
            self.inst.std = 'GOST'
        StartDraw(self.inst)

    def IsActive(self):
        return activeWindowIsScheme()

PrimitiveCommand('Polyline', Polyline)
PrimitiveCommand('Rectangle', Rectangle)
PrimitiveCommand('Ellipse', Ellipse)
PrimitiveCommand('Line', Line)
PrimitiveCommand('Text', Text)

addCommand('Separator')

dir = pathToSymbolsFolder+"\\GOST"
for subdir, dirs, files in os.walk(dir):
    for file in files:
        if ".svg" in file.lower():
            #print(os.path.join(subdir, file))
            typ = file[:-4] #.replace(" ", "").replace(".", "")
            group = ''
            if subdir != dir:
                group = os.path.basename(subdir)
            print(group)
            loadSVGSymbol("GOST"+'\\'+group+'\\'+typ) #typ, os.path.join(subdir, file))
            PrimitiveCommand(typ, Symbol, group)

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

addCommand('Separator')

class DialogFunctionCommand:
    """ This command call a dialog function and apply result of it to all selected items """

    def __init__(self, name, dlgfunc=None, func=None, text=None):
        self.name = name
        self.func = func
        self.dlgfunc = dlgfunc
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
            res = self.dlgfunc()
            if res is not None:
                for item in scheme.Proxy.scene.selectedItems():
                    self.func(item.obj, res)
        # Update sheet after apply effects or actions to items
        scheme.Proxy.scene.update()

    def IsActive(self):
        return activeWindowIsScheme()

DialogFunctionCommand('SetFont', fontDialog, setFont, "Set font to text")
