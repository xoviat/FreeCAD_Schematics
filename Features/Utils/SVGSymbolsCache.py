# -*- coding: utf-8 -*-
###############################################################################
#
#  SVGSymbolsCache.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from SCUtils import getSymbolPath
from Features.Utils.SVG import *

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
            return (data, pins)
    return cacheData

import sys

def getCacheSize():
    return sys.getsizeof(cache)
