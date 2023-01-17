# -*- coding: utf-8 -*-
###############################################################################
#
#  Effects.py - Items effects
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui

def removeEffect(item):
    """ Remove effect if it connected. Mandatory """
    item.setGraphicsEffect(None)

def addShadow(item, radius=10, xOffset=5, yOffset=5):
    """Add shadow effect to scene item"""
    removeEffect(item)
    shadow = QtGui.QGraphicsDropShadowEffect()
    shadow.setBlurRadius(radius)
    shadow.setXOffset(xOffset)
    shadow.setYOffset(yOffset)
    item.setGraphicsEffect(shadow)

def addColorize(item, color=QtGui.Qt.gray, strength=0.5):
    """Add colorization effect to scene item"""
    removeEffect(item)
    shadow = QtGui.QGraphicsColorizeEffect()
    shadow.setColor(color)
    shadow.setStrength(strength)
    item.setGraphicsEffect(shadow)