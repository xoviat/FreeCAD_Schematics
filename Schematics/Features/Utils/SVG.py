# -*- coding: utf-8 -*-
###############################################################################
#
#  SVG.py - svg parsing functions
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import re
from PySide6 import QtGui

def __setColors(res, strokeColor, fillColor):
    color = res.group(0).upper()
    if color == '#000000' or color == '#000':
        return strokeColor
    elif color == '#FFFFFF' or color == '#FFF':
        return fillColor
    # Other colors not changed        
    return color

def setColors(xml, strokeColor, fillColor):
    hexStrokeColor = QtGui.QColor.fromRgbF(*strokeColor).name()
    hexFillColor = QtGui.QColor.fromRgbF(*fillColor).name()
    return re.sub(r'#([0-9a-fA-F]{3}){1,2}', lambda _res: __setColors(_res, hexStrokeColor, hexFillColor), xml)

def exchangeBlackWhite(xml):
    return re.sub(r'#([0-9a-fA-F]{3}){1,2}', lambda _res: __setColors(_res, "#FFFFFF", "#000000"), xml)

class Default:
    def __init__(self, obj):
        self.obj = obj

    def linesColor(self): return 0.0, 0.0, 0.0, 1.0
    def paperColor(self): return 1.0, 1.0, 1.0, 1.0
    def decode(self, data): return data

class InvertBlackAndWhite(Default):
    def linesColor(self): return 1.0, 1.0, 1.0, 1.0
    def paperColor(self): return 0.0, 0.0, 0.0, 1.0
    def decode(self, data): return exchangeBlackWhite(data)

class CustomColors(Default):
    def linesColor(self): return self.obj.LinesColor[:-1] + (1.0,)
    def paperColor(self): return self.obj.PaperColor[:-1] + (1.0,)
    def decode(self, data): return setColors(data, self.linesColor(), self.paperColor())

class BluePrint(CustomColors):
    def linesColor(self): return 0.75, 0.85, 0.95, 1.0
    def paperColor(self): return 0.25, 0.40, 0.65, 1.0

class WhitePrint(CustomColors):
    def linesColor(self): return 0.30, 0.15, 0.20, 1.0
    def paperColor(self): return 1.00, 0.98, 0.98, 1.0

SheetAppearanceStyles = {
    "Default": Default,
    "Invert black and white": InvertBlackAndWhite,
    "BluePrint (Cyanotype)": BluePrint,
    "WhitePrint (Diazotype)": WhitePrint,
    "Custom colors": CustomColors
}
