# -*- coding: utf-8 -*-
###############################################################################
#
#  SVG.py - svg parsing functions
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import re
from PySide2 import QtGui

# ---------------------------------------------------------------------

# 1 mm = 1 scene units
# 1 inch = 25.4 mm = 25.4 scene units
# 1 scene unit = 1 mm = 0.039370078 (1/25.4) inch

def __transformUnits(res):
    strval = res.group(0)
    if "mm" in strval:
        val = float(strval.replace("mm",""))
        return str(val*1)
    if "cm" in strval:
        val = float(strval.replace("cm",""))
        return str(val*10)    
    if "in" in strval:
        val = float(strval.replace("in",""))
        return str(val*2.54*1)         
    return strval
    
def transformUnits(xml):
    return re.sub(r'([0-9]|\.[0-9]|[0-9]\.[0-9])+ *(mm|cm|in)', __transformUnits, xml)

# ---------------------------------------------------------------------

def extractPins(xml):
    pins = []
    # For findall grouping need to use syntax (?: | )
    expression = r'< *circle .*pin="[^"]*".*(?:\/>|<\/circle>)'
    tags = re.findall(expression, xml)
    # Save pins
    for tag in tags:
        # group(0) - return all string, group(1) - return value only
        pinName = re.search(r'pin="([a-zA-Z\.0-9]+)"', tag).group(1)
        pinX = float(re.search(r'cx="([\.0-9]+)"', tag).group(1))
        pinY = float(re.search(r'cy="([\.0-9]+)"', tag).group(1))
        print(f"Pin Name={pinName} X={pinX} Y={pinY}")
        pins.append((pinName,pinX,pinY))
    # Remove pin tags from svg
    xml = re.sub(expression, '', xml)
    return xml, pins

# ---------------------------------------------------------------------

def __exchangeBlackWhite(res):
    color = res.group(0).upper()
    if color == '#FFFFFF' or color == '#FFF':
        return '#000000'
    elif color == '#000000' or color == '#000':
        return '#FFFFFF'
    # Other colors not changed
    return color

def exchangeBlackWhite(xml):
    return re.sub(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})', __exchangeBlackWhite, xml)

# ---------------------------------------------------------------------

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
    return re.sub(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})', lambda _res: __setColors(_res, hexStrokeColor, hexFillColor), xml)

# ---------------------------------------------------------------------

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

class BluePrint(Default):
    def linesColor(self): return 0.75, 0.85, 0.95, 1.0
    def paperColor(self): return 0.25, 0.40, 0.65, 1.0
    def decode(self, data): return setColors(data, self.linesColor(), self.paperColor())

class WhitePrint(Default):
    def linesColor(self): return 0.30, 0.15, 0.20, 1.0
    def paperColor(self): return 1.00, 0.98, 0.98, 1.0
    def decode(self, data): return setColors(data, self.linesColor(), self.paperColor())

class CustomColors(Default):
    def linesColor(self): return self.obj.LinesColor
    def paperColor(self): return self.obj.PaperColor
    def decode(self, data): return setColors(data, self.linesColor(), self.paperColor())

SheetAppearanceStyles = {
    "Default": Default,
    "Invert black and white": InvertBlackAndWhite,
    "BluePrint (Cyanotype)": BluePrint,
    "WhitePrint (Diazotype)": WhitePrint,
    "Custom colors": CustomColors
}
