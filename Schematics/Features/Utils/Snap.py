# -*- coding: utf-8 -*-
###############################################################################
#
#  Snap.py - Contains the snap to grid function that used in all workbench
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from typing import Any

from PySide6 import QtCore

WithoutSnap = False

def snapAxis(step: float, value: float) -> float:
    return (value + step / 2) // step * step

def snap(value: QtCore.QPointF, sheet: Any) -> QtCore.QPointF:
    """ value type is QtCore.QPointF. step is integer"""
    if sheet.SnapEnabled is not True or WithoutSnap:
        return value
    step = sheet.ViewObject.GridSpacing.Value
    if sheet.SnapToMajorGrid:
        step *= sheet.ViewObject.MajorGridLineEvery
    return QtCore.QPointF(snapAxis(step, value.x()), snapAxis(step, value.y()))

def constrainAngle(last: QtCore.QPointF, cursor: QtCore.QPointF) -> QtCore.QPointF:
    """KiCad wire posture: constrain the segment last->cursor to the nearest
    horizontal, vertical or 45-degree direction, returning the point on
    that ray closest to the cursor."""
    dx = cursor.x() - last.x()
    dy = cursor.y() - last.y()
    if dx == 0.0 and dy == 0.0:
        return QtCore.QPointF(last)
    candidates = [
        QtCore.QPointF(cursor.x(), last.y()),   # horizontal
        QtCore.QPointF(last.x(), cursor.y()),   # vertical
    ]
    if dx != 0.0 and dy != 0.0:
        m = min(abs(dx), abs(dy))
        candidates.append(QtCore.QPointF(
            last.x() + (m if dx > 0 else -m),
            last.y() + (m if dy > 0 else -m),
        ))
    best = candidates[0]
    best_d = (best.x() - cursor.x()) ** 2 + (best.y() - cursor.y()) ** 2
    for candidate in candidates[1:]:
        d = (candidate.x() - cursor.x()) ** 2 + (candidate.y() - cursor.y()) ** 2
        if d < best_d:
            best, best_d = candidate, d
    return best
