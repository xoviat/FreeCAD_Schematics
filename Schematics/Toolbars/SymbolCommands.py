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

SymbolCommandList: list[str] = []

def addCommand(name, function=None):
    SymbolCommandList.append(name)
    if function is not None:
        FreeCAD.Gui.addCommand(name, function)

class SCDrawWire:
    """ Draw a wire (conductor) on the active sheet """

    def GetResources(self) -> dict[str, str]:
        return {
            'Pixmap': getToolbarIconPath('DrawWireMode.svg'),
            'MenuText': "Draw wire",
            'ToolTip': "Click to place vertices, double-click or Enter to finish, Escape or right-click to cancel",
            'Accel': 'W',
        }

    def Activated(self) -> None:
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None:
            scheme.Proxy.scene.startWireDraw()

    def IsActive(self) -> bool:
        return activeWindowIsScheme()

addCommand('SCDrawWire', SCDrawWire())


class SCChooseSymbol:
    """ Choose a symbol from the store and place it (KiCad-style) """

    def GetResources(self) -> dict[str, str]:
        return {
            'Pixmap': getToolbarIconPath('ChooseSymbol.svg'),
            'MenuText': "Place symbol…",
            'ToolTip': "Search, preview and place a symbol from the symbol store",
            'Accel': 'A',
        }

    def Activated(self) -> None:
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is None:
            return
        from Schematics.Features.Dialogs.SymbolChooser import SymbolChooser
        dialog = SymbolChooser(parent=FreeCAD.Gui.getMainWindow())
        if not dialog.exec():   # QDialog.Accepted == 1, Rejected == 0
            return
        entry = dialog.selectedEntry()
        if entry is None:
            return
        # Same placement path as the per-symbol toolbar buttons.
        Symbol.typ = entry.name
        Symbol.grp = entry.group
        Symbol.std = entry.standard
        StartDraw(Symbol)

    def IsActive(self) -> bool:
        return activeWindowIsScheme()


addCommand('SCChooseSymbol', SCChooseSymbol())
addCommand('Separator')


class SCSymbolManager:
    """ Browse/edit the symbol store (KiCad's Symbol Editor equivalent) """

    def GetResources(self) -> dict[str, str]:
        return {
            'Pixmap': getToolbarIconPath('SymbolManager.svg'),
            'MenuText': "Symbol manager…",
            'ToolTip': "Browse, duplicate, import and edit symbol pins/metadata "
                       "(opens the pin editor directly for the selected symbol)",
            'Accel': 'Ctrl+E',
        }

    def Activated(self) -> None:
        from Schematics.Features.Dialogs.SymbolManager import (
            PinEditor,
            SymbolManager,
            readSymbol,
        )
        from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog
        catalog = SymbolCatalog()
        parent = FreeCAD.Gui.getMainWindow()
        # KiCad Ctrl+E: with a symbol selected, edit that symbol directly.
        entry = None
        for obj in FreeCAD.Gui.Selection.getSelection():
            entry = catalog.find_by_instance(obj)
            if entry is not None:
                break
        if entry is not None:
            desc, ref, pins = readSymbol(entry.path)
            editor = PinEditor(
                path=entry.path, pins=pins, description=desc, ref=ref,
                cacheKey=entry.key, parent=parent,
            )
            editor.exec()
            return
        SymbolManager(catalog=catalog, parent=parent).exec()

    def IsActive(self) -> bool:
        return activeWindowIsScheme()


addCommand('SCSymbolManager', SCSymbolManager())


class SCAnnotate:
    """ Assign designators to unannotated symbols (KiCad Annotate) """

    def GetResources(self) -> dict[str, str]:
        return {
            'Pixmap': getToolbarIconPath('Annotate.svg'),
            'MenuText': "Annotate sheet",
            'ToolTip': "Assign designators to symbols that have none, using "
                       "each symbol's reference prefix",
        }

    def Activated(self) -> None:
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is None:
            return
        from Schematics.Features.Utils.Annotate import annotateSheet
        assigned, skipped = annotateSheet(scheme)
        FreeCAD.Console.PrintMessage(
            "Schematics: annotated %d symbol(s), %d without a reference prefix\n"
            % (assigned, skipped))
        if FreeCAD.ActiveDocument is not None:
            FreeCAD.ActiveDocument.recompute()

    def IsActive(self) -> bool:
        return activeWindowIsScheme()


addCommand('SCAnnotate', SCAnnotate())


class SCComponentList:
    """ Component list / BOM-lite for the active sheet """

    def GetResources(self) -> dict[str, str]:
        return {
            'Pixmap': getToolbarIconPath('ComponentList.svg'),
            'MenuText': "Component list…",
            'ToolTip': "List annotated symbols (designator, value, symbol, "
                       "description) with CSV export",
        }

    def Activated(self) -> None:
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is None:
            return
        from Schematics.Features.Dialogs.ComponentList import openComponentList
        openComponentList(scheme, parent=FreeCAD.Gui.getMainWindow())

    def IsActive(self) -> bool:
        return activeWindowIsScheme()


addCommand('SCComponentList', SCComponentList())


class SCCheckConnections:
    """ Check pins and wire ends (geometric ERC-lite) """

    def GetResources(self) -> dict[str, str]:
        return {
            'Pixmap': getToolbarIconPath('CheckConnections.svg'),
            'MenuText': "Check connections",
            'ToolTip': "List pins without wires and wire ends floating in "
                       "space (geometric connection check)",
        }

    def Activated(self) -> None:
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is None:
            return
        from Schematics.Features.Dialogs.ConnectionCheck import openConnectionCheck
        openConnectionCheck(scheme, parent=FreeCAD.Gui.getMainWindow())

    def IsActive(self) -> bool:
        return activeWindowIsScheme()


addCommand('SCCheckConnections', SCCheckConnections())

class PrimitiveCommand:
    """ Add primitive """

    def __init__(self, name, inst, group=None, accel: str | None = None):
        self.name = name
        self.inst = inst
        self.group = group
        self.accel = accel
        addCommand('SC' + self.name, self)

    def GetResources(self) -> dict[str, str]:
        iconPath = getToolbarIconPath(f"{self.name}.svg")
        if not os.path.exists(iconPath):
            iconPath = getSymbolIconPath(f"{self.name}.svg")
        if not os.path.exists(iconPath) and self.group is not None:
            iconPath = getSymbolPath(f"{os.path.join('GOST',os.path.join(self.group,self.name))}.svg")
        self.iconPath = iconPath
        resources: dict[str, str] = {
            'Pixmap': iconPath,
            'MenuText': "Add " + self.name,
            'ToolTip': "Add " + self.name,
        }
        if self.accel:
            resources['Accel'] = self.accel   # KiCad-compatible hotkey
        return resources

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
PrimitiveCommand('Line', Line, accel='I')
PrimitiveCommand('Text', Text, accel='T')

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

    def __init__(self, name, func=None, text=None, accel: str | None = None):
        self.name = name
        self.func = func
        self.text = text
        self.accel = accel
        addCommand('SC' + self.name, self)

    def GetDescription(self):
        return self.text or ""

    def GetResources(self) -> dict[str, str]:
        resources: dict[str, str] = {
            'Pixmap': getToolbarIconPath(self.name + '.svg'),
            'MenuText': self.GetDescription(),
            'ToolTip': self.GetDescription(),
        }
        if self.accel:
            resources['Accel'] = self.accel   # KiCad-compatible hotkey
        return resources

    def Activated(self):
        scheme = tryToGetSchemeFromActiveWindow()
        if scheme is not None and self.func is not None:
            for item in scheme.Proxy.scene.selectedItems():
                self.func(item.obj)
        # Update sheet after apply effects or actions to items
        if scheme is not None:
            scheme.Proxy.scene.update()

    def IsActive(self):
        return activeWindowIsScheme()

FunctionCommand('ToFront', toFront, "Bring to front")
FunctionCommand('ToBottom', toBack, "Bring to back")
# KiCad-compatible mirrors (X / Y)
FunctionCommand('HFlip', hFlip, "Mirror horizontally", accel='X')
FunctionCommand('VFlip', vFlip, "Mirror vertically", accel='Y')
# KiCad-compatible rotations (R = CCW, Shift+R = CW)
FunctionCommand('TurnLeft', turnLeft, "Turn left to 90 degrees", accel='R')
FunctionCommand('TurnRight', turnRight, "Turn right to 90 degrees", accel='Shift+R')


def setWireLabel(obj):
    """L hotkey: edit the label (Tag) of the selected wire - KiCad's
    Add Label, scoped to wires until labels exist for other items."""
    if getattr(obj, "Type", "") != "Wire":
        return
    from PySide6 import QtWidgets as _QtW
    current = str(getattr(obj, "Tag", "") or "")
    text, ok = _QtW.QInputDialog.getText(
        FreeCAD.Gui.getMainWindow(),
        "Wire label",
        "Label (conductor tag, joins same-labelled wires):",
        _QtW.QLineEdit.EchoMode.Normal,
        current,
    )
    if ok:
        obj.Tag = text.strip()


FunctionCommand('LabelWire', setWireLabel, "Add label to wire", accel='L')
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
        if scheme is not None and self.dlgfunc is not None and self.func is not None:
            res = self.dlgfunc()
            if res is not None:
                for item in scheme.Proxy.scene.selectedItems():
                    self.func(item.obj, res)
        # Update sheet after apply effects or actions to items
        if scheme is not None:
            scheme.Proxy.scene.update()

    def IsActive(self):
        return activeWindowIsScheme()

DialogFunctionCommand('SetFont', fontDialog, setFont, "Set font to text")
