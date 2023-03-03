# -*- coding: utf-8 -*-
###############################################################################
#
#  GridMixin.py - contains typical grid properties
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from Schematics.Features.Utils.QtEnums import *

class GridViewProperties:

    def __init__(self, vobj):
        print('grid mixin init')
        vobj.addProperty('App::PropertyBool', 'GridVisible', 'Grid', 'If this parameter is true, '
            'the grid is displayed on the sheet, otherwise it is not', 8+16).GridVisible = True
        vobj.addProperty('App::PropertyLength', 'GridSpacing', 'Grid',
            'Distance between grid lines', 8+16).GridSpacing = "2.5 mm"
        vobj.addProperty('App::PropertyIntegerConstraint', 'MajorGridLineEvery', 'Grid',
            'Major grid line every', 8+16).MajorGridLineEvery = (4, 1, 2147483647, 1)
        vobj.addProperty('App::PropertyColor', 'MinorGridLineColor', 'Grid',
            'Color of minor grid lines', 8+16).MinorGridLineColor = (0.5, 0.5, 0.5, 1.0)
        vobj.addProperty('App::PropertyLength', 'MinorGridLineWidth', 'Grid',
            'Width of minor grid lines', 8+16).MinorGridLineWidth = "0.05 mm"
        vobj.addProperty('App::PropertyEnumeration', 'MinorGridLineStyle', 'Grid',
            'Draw style of minor grid lines', 8+16).MinorGridLineStyle = list(QtLineStyles)
        vobj.MinorGridLineStyle = list(QtLineStyles)[3]   # Default dot style
        vobj.addProperty('App::PropertyColor', 'MajorGridLineColor', 'Grid',
            'Color of major grid lines', 8+16).MajorGridLineColor = (0.5, 0.5, 0.5, 1.0)
        vobj.addProperty('App::PropertyLength', 'MajorGridLineWidth', 'Grid',
            'Width of major grid lines', 8+16).MajorGridLineWidth = "0.15 mm"
        vobj.addProperty('App::PropertyEnumeration', 'MajorGridLineStyle', 'Grid',
            'Draw style of major grid lines', 8+16).MajorGridLineStyle = list(QtLineStyles)
        vobj.MajorGridLineStyle = list(QtLineStyles)[3]   # Default dot style

    def onChanged(self, vobj, prop):
        val = vobj.getPropertyByName(prop)
        if prop == "MinorGridLineColor":
            if val[3] == 0.0:
                vobj.MinorGridLineColor = val[:-1] + (1.0,)
        elif prop == "MajorGridLineColor":
            if val[3] == 0.0:
                vobj.MajorGridLineColor = val[:-1] + (1.0,)
        if "Grid" in prop or "Snap" in prop:
            # !!! Grid parameters move to ViewProvider?
            vobj.Object.Proxy.scene.update()
