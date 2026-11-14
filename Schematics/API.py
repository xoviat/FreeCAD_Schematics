# -*- coding: utf-8 -*-
###############################################################################
#
#  API.py - Provides convenient access to WB API via Python console or macroses
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

"""

# Examples of using:

# Create random rectangles
import random
lst = []
for i in range(0,100):
   rect = Schematics.Rectangle()
   rect.X = random.randint(0,300)
   rect.Y = random.randint(0,200)
   rect.Width = random.randint(0,100)
   rect.Height = random.randint(0,100)
   lst.append(rect)
   FreeCAD.Gui.updateGui()

# Print workbench help to console
Schematics.help()

"""

from typing import Any

from SCUtils import getRootPath

class API:

    # !!! Not work yet
    #def Polyline(self, x=None, y=None, sheet=None):
    #    from Features.Items.Polyline import Polyline
    #    return Polyline(x, y, sheet)

    def Rectangle(self, x: float = 0, y: float = 0, sheet: Any = None) -> Any:
        """
        Add Rectangle to sheet:

        obj = Rectangle(x, y, sheet) -> obj

        x(int) - x position of shape (optional, default value is 0)
        y(int) - y position of shape (optional, default value is 0)
        sheet(obj) - the sheet object, where the shape should be placed (optional)
        If the sheet parameter is not specified, the shape will be placed in the current active window.
        If the currently active window is not a Schematics sheet, an error message will get.

        Example:
        rect = Schematics.Rectangle()
        rect.X = 50
        rect.Y = 80
        rect.Width = 70
        rect.Height = 30
        """
        from Schematics.Features.Items.Rectangle import Rectangle
        # keyword arg: Rectangle.__new__ has width/height before sheet,
        # so a positional third argument would bind sheet -> width
        return Rectangle(x, y, sheet=sheet)

    def Line(self, x: float = 0, y: float = 0, sheet: Any = None) -> Any:
        """
        Add Line to sheet:

        obj = Line(x, y, sheet) -> obj

        x(int) - x position of shape (optional, default value is 0)
        y(int) - y position of shape (optional, default value is 0)
        sheet(obj) - the sheet object, where the shape should be placed (optional)
        If the sheet parameter is not specified, the shape will be placed in the current active window.
        If the currently active window is not a Schematics sheet, an error message will get.

        Example:
        line = Schematics.Line()
        line.X = 50
        line.Y = 80
        line.Width = 70
        line.Height = 30
        """
        from Schematics.Features.Items.Line import Line
        # keyword arg: see note in Rectangle()
        return Line(x, y, sheet=sheet)

    def Wire(self, points=None, sheet: Any = None, wireType: str | None = None) -> Any:
        """
        Add a first-class wire (conductor) to a sheet:

        obj = Wire(points, sheet) -> obj

        points(list) - vertex coordinates as (x, y) tuples or QPointF,
            absolute sheet coordinates, at least two entries
        sheet(obj) - the sheet object where the wire should be placed (optional)
        wireType(str) - one of Power, Control, Hydraulic, Pneumatic, Signal
            (optional, default Power)

        Wires are document objects: they are saved with the file, can be
        selected, moved and deleted like any other sheet element.

        Example:
        wire = Schematics.Wire([(0, 0), (50, 0), (50, 30)])
        wire.WireType = "Hydraulic"
        """
        from Schematics.Features.Items.Wire import Wire as WireFactory
        return WireFactory(points, sheet=sheet, wireType=wireType)

    def BillOfMaterials(self, x: float = 0, y: float = 0, sheet: Any = None) -> Any:
        """
        Add a live bill-of-materials table to a sheet:

        obj = BillOfMaterials(x, y, sheet) -> obj

        x(float) - table position on the sheet (optional)
        y(float) - table position on the sheet (optional)
        sheet(obj) - target sheet (optional; defaults to the active window)

        The table renders the sheet's annotated symbols (designator,
        value, symbol, description) and refreshes as they change; only
        the position and the Title are stored on the object.

        Example:
        bom = Schematics.BillOfMaterials(20, 180)
        bom.Title = "Device list"
        """
        from Schematics.Features.Items.BillOfMaterials import (
            BillOfMaterials as BOMFactory,
        )
        return BOMFactory(x, y, sheet=sheet)

    def help(self) -> None:
        with open(getRootPath('README.md'), 'r') as file:
            str = file.read()
            print(str)

def gethelp() -> str:
    with open(getRootPath('README.md'), 'r') as file:
        str = file.read()
        print(str)
        return str