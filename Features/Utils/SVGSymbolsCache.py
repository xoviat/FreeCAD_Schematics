# -*- coding: utf-8 -*-
###############################################################################
#
#  SVGSymbolsCache.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import re
from SCUtils import getSymbolPath

cache = dict()

def loadSVGSymbol(type):
    global cache
    #print(f"Cache size: {getCacheSize()} bytes. Cache data:{cache}")
    cacheData = cache.get(type)
    if cacheData is None:
        with open(getSymbolPath(type + ".svg"), "r", encoding='utf-8') as f:
            data = f.read()
            data = transformUnits(data)
            data, pins = extractPins(data)
            cache[type] = (data, pins)
            return data, pins
    return cacheData

import sys

def getCacheSize():
    return sys.getsizeof(cache)

# 1 mm = 1 scene units
# 1 inch = 25.4 mm = 25.4 scene units
# 1 scene unit = 1 mm = 0.039370078 (1/25.4) inch

def __transformUnits(res):
    strval = res.group(0)
    if "mm" in strval:
        val = float(strval.replace("mm", ""))
        return str(val*1)
    if "cm" in strval:
        val = float(strval.replace("cm", ""))
        return str(val*10)
    if "in" in strval:
        val = float(strval.replace("in", ""))
        return str(val*2.54*1)
    return strval

def transformUnits(xml):
    # * zero or more, + one or more
    return re.sub(r'[0-9]*\.*[0-9]+ *(mm|cm|in)', __transformUnits, xml)

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
        pins.append((pinName, pinX, pinY))
    # Remove pin tags from svg
    xml = re.sub(expression, '', xml)
    return xml, pins
