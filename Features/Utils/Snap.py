# -*- coding: utf-8 -*-
###############################################################################
#
#  Snap.py - Contains the snap to grid function that used in all workbench
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtCore

def snap(value, sheet):
    """ value type is QtCore.QPointF. step is integer"""
    if sheet.SnapEnabled is not True:
        return value
    step = sheet.GridSpacing.Value
    if sheet.SnapToMajorGrid:
        step *= sheet.MajorGridLineEvery
    # !!! Formula incorrectly converts negative values
    return QtCore.QPointF((value.x() + step / 2) // step * step, (value.y() + step / 2) // step * step)