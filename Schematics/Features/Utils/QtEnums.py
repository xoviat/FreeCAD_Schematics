# -*- coding: utf-8 -*-
###############################################################################
#
#  QtEnums.py - Contain Qt enums with names for item list property's
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtCore

# To get list
# list = list(QtLineStyles)

# To get Qt value
# value = QtLineStyles['Solid line']

# To get value by index
# value list(QtLineStyles)[3]

# To get index by value
# index = list(QtLineStyles).index("Not displayed")

def nextEnum(enum, value):
    vlist = list(enum)
    index = vlist.index(value)
    index = (index + 1) % len(vlist)
    return vlist[index]

Standards = [
    'GOST'
]

QtLineStyles = {
    "Not displayed": QtCore.Qt.PenStyle.NoPen,
    "Solid line": QtCore.Qt.PenStyle.SolidLine,
    "Dash line": QtCore.Qt.PenStyle.DashLine,
    "Dot line": QtCore.Qt.PenStyle.DotLine,
    "Dash dot line": QtCore.Qt.PenStyle.DashDotLine,
    "Dash dot dot line": QtCore.Qt.PenStyle.DashDotDotLine,
    #"Custom dash line": QtCore.Qt.PenStyle.CustomDashLine,
}

QtJoinStyles = {
    "Miter join": QtCore.Qt.PenJoinStyle.MiterJoin,
    "Bevel join": QtCore.Qt.PenJoinStyle.BevelJoin,
    "Round join": QtCore.Qt.PenJoinStyle.RoundJoin,
    "SVG miter join": QtCore.Qt.PenJoinStyle.SvgMiterJoin,
}

QtCapStyles = {
    "Flat cap": QtCore.Qt.PenCapStyle.FlatCap,
    "Square cap": QtCore.Qt.PenCapStyle.SquareCap,
    "Round cap": QtCore.Qt.PenCapStyle.RoundCap,
}
