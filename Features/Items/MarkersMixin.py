# -*- coding: utf-8 -*-
###############################################################################
#
#  MarkersMixin.py - contains line markers style properties and draw methods
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtGui, QtCore
from Features.Utils.QtEnums import *
import math

class MarkersDataProperties:

    def __init__(self, obj, sheet, type="Unknown"):
        super().__init__(obj, sheet, type)
        pass

    def onChanged(self, obj, prop):
        super().onChanged(obj, prop)
        pass

    def initItem(self, obj, sheet):
        super().initItem(obj, sheet)
        obj.ViewObject.StartMarkerType = obj.ViewObject.StartMarkerType
        obj.ViewObject.StartMarkerAngle = obj.ViewObject.StartMarkerAngle
        obj.ViewObject.StartMarkerLength = obj.ViewObject.StartMarkerLength
        obj.ViewObject.EndMarkerType = obj.ViewObject.EndMarkerType
        obj.ViewObject.EndMarkerAngle = obj.ViewObject.EndMarkerAngle
        obj.ViewObject.EndMarkerLength = obj.ViewObject.EndMarkerLength

class MarkersViewProperties:

    MarkerStyles = [
        "None",
        "Triangle",
        "To",
        "Stealth",
        "Open triangle"
    ]

    def __init__(self, vobj):
        vobj.addProperty('App::PropertyEnumeration', 'StartMarkerType', 'Markers', 'Type of line start marker', 8+16).StartMarkerType = self.MarkerStyles
        vobj.StartMarkerType = self.MarkerStyles[0]   # Default none
        vobj.addProperty('App::PropertyAngle', 'StartMarkerAngle', 'Markers', 'Angle of line start marker', 8+16).StartMarkerAngle = 20
        vobj.addProperty('App::PropertyLength', 'StartMarkerLength', 'Markers', 'Length of line start marker', 8+16).StartMarkerLength = "5.0 mm"
        vobj.addProperty('App::PropertyEnumeration', 'EndMarkerType', 'Markers', 'Type of line end marker', 8+16).EndMarkerType = self.MarkerStyles
        vobj.EndMarkerType = self.MarkerStyles[1]   # Default solid triangle
        vobj.addProperty('App::PropertyAngle', 'EndMarkerAngle', 'Markers', 'Angle of line end marker', 8+16).EndMarkerAngle = 20
        vobj.addProperty('App::PropertyLength', 'EndMarkerLength', 'Markers', 'Length of line end marker', 8+16).EndMarkerLength = "5.0 mm"
        # Middle markers?
        super().__init__(vobj)

    def onChanged(self, vobj, prop):
        super().onChanged(vobj, prop)

'''        
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
'''

class MarkersItem:

    def drawMarkers(self, g, sp2, sp1, ep1, ep2):
        t = g.transform()
        self.drawMarker(g, sp2, sp1, True)
        g.setTransform(t)
        self.drawMarker(g, ep1, ep2, False)

    def drawMarker(self, g, p1, p2, isStart):
        if isStart:
            typ = self.obj.ViewObject.StartMarkerType
            l = self.obj.ViewObject.StartMarkerLength
            ang = self.obj.ViewObject.StartMarkerAngle
        else:
            typ = self.obj.ViewObject.EndMarkerType
            l = self.obj.ViewObject.EndMarkerLength
            ang = self.obj.ViewObject.EndMarkerAngle
        MarkerStyles = self.obj.ViewObject.Proxy.MarkerStyles
        if typ == MarkerStyles[0]:
            return
        w = math.tan(math.radians(ang/2)) * l
        g.translate(p2.x(), p2.y())
        g.rotate(-QtCore.QLineF(p1, p2).angle()+90)

        fill = QtCore.Qt.black
        if typ == MarkerStyles[4]:
            fill = QtCore.Qt.white
        g.setBrush(QtGui.QBrush(fill))
        #g.setPen(QtCore.Qt.NoPen)

        if typ == MarkerStyles[1] or typ == MarkerStyles[4]:
            points = [QtCore.QPointF(w, l), QtCore.QPointF(0.0, 0.0),  QtCore.QPointF(-w, l)]
            marker = QtGui.QPolygonF(points)
            g.drawPolygon(marker)
        elif typ == MarkerStyles[3]:
            points = [QtCore.QPointF(w, l), QtCore.QPointF(),  QtCore.QPointF(-w, l), QtCore.QPointF(0.0, l * 0.8)]
            marker = QtGui.QPolygonF(points)
            g.drawPolygon(marker)
        elif typ == MarkerStyles[2]:
            points = [QtCore.QPointF(w, l), QtCore.QPointF(0.0, 0.0),  QtCore.QPointF(-w, l)]
            marker = QtGui.QPolygonF(points)
            g.drawPolyline(marker)

