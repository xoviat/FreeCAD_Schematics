# -*- coding: utf-8 -*-
###############################################################################
#
#  Transforms.py - Items actions like rotate, flip, lock etc...
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui


def toFront(obj):
    """Move item to front (Top)"""
    item = obj.Proxy.item
    item.setZValue(0.8)

def toBack(obj):
    """Move item to back (Bottom)"""
    item = obj.Proxy.item
    item.setZValue(-0.8)

def hFlip(obj):
    """Flip horizontally (KiCad X: mirror about the item's centre)."""
    item = obj.Proxy.item
    # combine=True keeps the anchor translate set by setAnchor()/setMode:
    # scale(-1,1) applied after it mirrors about the item's centre.
    # (The old setAnchor(True) call raised TypeError: setAnchor takes no
    # arguments, and re-running it would erase the flip anyway.)
    item.setTransform(QtGui.QTransform().scale(-1, 1), combine=True)

def vFlip(obj):
    """Flip vertically (KiCad Y: mirror about the item's centre)."""
    item = obj.Proxy.item
    item.setTransform(QtGui.QTransform().scale(1, -1), combine=True)

def turnLeft(obj):
    """Turn left to 90 degrees"""
    if hasattr(obj, 'Rotation'):
        obj.Rotation = obj.Rotation.Value - (-360+90 if obj.Rotation.Value-90 < -360 else 90)

def turnRight(obj):
    """Turn right to 90 degrees"""
    if hasattr(obj, 'Rotation'):
        obj.Rotation = obj.Rotation.Value + (-360+90 if obj.Rotation.Value+90 > 360 else 90)
