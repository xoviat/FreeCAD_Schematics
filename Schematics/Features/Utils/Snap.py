# -*- coding: utf-8 -*-
###############################################################################
#
#  Snap.py - Contains the snap to grid function that used in all workbench
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtCore

WithoutSnap = False

def snapAxis(step, value):
    return (value + step / 2) // step * step

def snap(value, sheet):
    """ value type is QtCore.QPointF. step is integer"""
    if sheet.SnapEnabled is not True or WithoutSnap:
        return value
    step = sheet.ViewObject.GridSpacing.Value
    if sheet.SnapToMajorGrid:
        step *= sheet.ViewObject.MajorGridLineEvery
    return QtCore.QPointF(snapAxis(step, value.x()), snapAxis(step, value.y()))
