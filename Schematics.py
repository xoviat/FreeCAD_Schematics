# -*- coding: utf-8 -*-
###############################################################################
#
#  Schematics.py - Wrapper for workbench
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

"""

# For use input to Python console:

from Schematics import *
polyline = Polyline()

or other case of import and using,
more convenient but less conflicted:

import Schematics
polyline = Schematics.Polyline()

"""

from Features.Items.SchemeObject import Draw
from Features.Items.Polyline import Polyline
from Features.Items.Rectangle import Rectangle
from Features.Items.Ellipse import Ellipse
from Features.Items.Line import Line

from Features.Items.Effects import *

from SCUtils import getRootPath

def help():
    with open(getRootPath('README.md'), 'r') as file:
        str = file.read()
        print(str)
