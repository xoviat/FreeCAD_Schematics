# -*- coding: utf-8 -*-
###############################################################################
#
#  StrokeMixin.py - contains typical stroke style properties
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtCore
from Schematics.Features.Utils.QtEnums import *

class StrokeDataProperties:

    def __init__(self, obj, type="Unknown"):
        super().__init__(obj, type)
        pass

    def onChanged(self, obj, prop):
        super().onChanged(obj, prop)
        pass

    def initItem(self, obj, sheet):
        super().initItem(obj, sheet)
        obj.ViewObject.StrokeWidth = obj.ViewObject.StrokeWidth
        obj.ViewObject.StrokeDash = obj.ViewObject.StrokeDash
        obj.ViewObject.StrokeCap = obj.ViewObject.StrokeCap
        obj.ViewObject.StrokeJoin = obj.ViewObject.StrokeJoin

class StrokeViewProperties:

    def __init__(self, vobj):
        vobj.addProperty('App::PropertyLength', 'StrokeWidth', 'Style', 'Stroke width', 8+16).StrokeWidth = "0.5 mm"
        vobj.addProperty('App::PropertyEnumeration', 'StrokeDash', 'Style', 'Stroke dash', 8+16).StrokeDash = list(QtLineStyles)
        vobj.StrokeDash = list(QtLineStyles)[1]   # Default solid style  # Add custom
        vobj.addProperty('App::PropertyEnumeration', 'StrokeCap', 'Style', 'Stroke cap', 8+16).StrokeCap = list(QtCapStyles)
        vobj.StrokeCap = list(QtCapStyles)[0]   # Default flat cap
        vobj.addProperty('App::PropertyEnumeration', 'StrokeJoin', 'Style', 'Stroke join', 8+16).StrokeJoin = list(QtJoinStyles)
        vobj.StrokeJoin = list(QtJoinStyles)[0]   # Default miter cap
        #vobj.addProperty('App::PropertyFloatList', 'StrokeDashPattern', 'Style', 'Stroke dash pattern', 8+16).StrokeDashPattern = [1, 2]
        super().__init__(vobj)

    def onChanged(self, vobj, prop):
        super().onChanged(vobj, prop)
        #val = vobj.getPropertyByName(prop)
        # Pen recreated only if property's changed
        if prop == "StrokeWidth" or prop == "StrokeDash" or prop == "StrokeCap" or prop == "StrokeJoin":
            if hasattr(vobj, "StrokeWidth"):
                self.pen = QtGui.QPen(QtCore.Qt.green,
                    vobj.StrokeWidth.Value,
                    QtLineStyles[vobj.StrokeDash],
                    QtCapStyles[vobj.StrokeCap],
                    QtJoinStyles[vobj.StrokeJoin])
            # Add check on item when this is mixin
            if hasattr(self, "item"):
                if prop == "StrokeWidth":
                    vobj.Object.Proxy.item.shape()
                vobj.Object.Proxy.item.scene().update()
