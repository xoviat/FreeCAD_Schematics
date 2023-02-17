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

from SCUtils import getRootPath

def help():
    with open(getRootPath('README.md'), 'r') as file:
        str = file.read()
        print(str)

def gethelp():
    with open(getRootPath('README.md'), 'r') as file:
        str = file.read()
        print(str)
        return str
