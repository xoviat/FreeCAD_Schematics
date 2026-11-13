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
    """Flip horizontally"""
    item = obj.Proxy.item
    item.setTransform(QtGui.QTransform().scale(-1, 1), combine=False)
    if hasattr(item, "setAnchor"):
        item.setAnchor(True) # !!! Update all transformations with  combine=False

def vFlip(obj):
    """Flip vertically"""
    item = obj.Proxy.item
    item.setTransform(QtGui.QTransform().scale(1, -1), combine=False)
    if hasattr(item, "setAnchor"):
        item.setAnchor(True) # !!! Update all transformations with  combine=False

def turnLeft(obj):
    """Turn left to 90 degrees"""
    if hasattr(obj, 'Rotation'):
        obj.Rotation = obj.Rotation.Value - (-360+90 if obj.Rotation.Value-90 < -360 else 90)

def turnRight(obj):
    """Turn right to 90 degrees"""
    if hasattr(obj, 'Rotation'):
        obj.Rotation = obj.Rotation.Value + (-360+90 if obj.Rotation.Value+90 > 360 else 90)
