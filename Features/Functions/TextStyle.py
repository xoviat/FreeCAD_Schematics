# -*- coding: utf-8 -*-
###############################################################################
#
#  TextStyle.py - Text actions like change font, color, style etc...
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore, QtWidgets


def replenishFontDatabase():
    """Add specific fonts to Qt font database"""
    pass


def fontDialog():
    """Open font dialog"""
    # !!! Set default font by global standard
    ok, font = QtWidgets.QFontDialog.getFont(QtGui.QFont("GOSTRUS", 10))
    # the user select OK then return font in other case return None
    if ok:
        return font
    return None


def setFont(obj, font):
    """Set font to object"""
    if hasattr(obj.Proxy.item, 'setFont'):
        print(font.toString())
        obj.Proxy.item.setFont(font)
        obj.Proxy.item.setHtml(obj.Proxy.item.toPlainText())
