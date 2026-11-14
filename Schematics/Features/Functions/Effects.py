# -*- coding: utf-8 -*-
###############################################################################
#
#  Effects.py - Items effects
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
from PySide6 import QtGui, QtCore, QtWidgets


def addShadow(obj, radius=10, xOffset=5, yOffset=5):
    """ Add shadow effect to schematics object """
    FreeCAD.Console.PrintWarning("\n! Effects not saves to file, and looks pixelated on print preview !\n\n")
    item = obj.Proxy.item
    item.setGraphicsEffect(None)   # ! Mandatory
    shadow = QtWidgets.QGraphicsDropShadowEffect()
    shadow.setBlurRadius(radius)
    shadow.setXOffset(xOffset)
    shadow.setYOffset(yOffset)
    item.setGraphicsEffect(shadow)

def addColorize(obj, color=QtGui.Qt.GlobalColor.gray, strength=0.5):
    """ Add colorization effect to schematics object """
    FreeCAD.Console.PrintWarning("\n! Effects not saves to file, and looks pixelated on print preview !\n\n")
    item = obj.Proxy.item
    item.setGraphicsEffect(None)   # ! Mandatory
    colorize = QtWidgets.QGraphicsColorizeEffect()
    colorize.setColor(color)
    colorize.setStrength(strength)
    item.setGraphicsEffect(colorize)

def addBlur(obj, radius=5, hint=QtWidgets.QGraphicsBlurEffect.BlurHint.QualityHint):
    """ Add blur effect to schematics object """
    FreeCAD.Console.PrintWarning("\n! Effects not saves to file, and looks pixelated on print preview !\n\n")
    item = obj.Proxy.item
    item.setGraphicsEffect(None)   # ! Mandatory
    blur = QtWidgets.QGraphicsBlurEffect()
    blur.setBlurHints(hint)
    blur.setBlurRadius(radius)
    item.setGraphicsEffect(blur)

def removeEffect(obj):
    """ Remove effect from schematics object """
    item = obj.Proxy.item
    item.setGraphicsEffect(None)
