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

from SCUtils import getRootPath

class API:

    # !!! Not work yet
    #def Polyline(self, x=None, y=None, sheet=None):
    #    from Features.Items.Polyline import Polyline
    #    return Polyline(x, y, sheet)

    def Rectangle(self, x=0, y=0, sheet=None):
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
        return Rectangle(x, y, sheet)

    def Line(self, x=0, y=0, sheet=None):
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
        return Line(x, y, sheet)

    def help(self):
        with open(getRootPath('README.md'), 'r') as file:
            str = file.read()
            print(str)

def gethelp():
    with open(getRootPath('README.md'), 'r') as file:
        str = file.read()
        print(str)
        return str