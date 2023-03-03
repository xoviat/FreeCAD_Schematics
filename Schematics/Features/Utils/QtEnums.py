# -*- coding: utf-8 -*-
###############################################################################
#
#  QtEnums.py - Contain Qt enums with names for item list property's
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide2 import QtCore

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
    "Not displayed": QtCore.Qt.NoPen,
    "Solid line": QtCore.Qt.SolidLine,
    "Dash line": QtCore.Qt.DashLine,
    "Dot line": QtCore.Qt.DotLine,
    "Dash dot line": QtCore.Qt.DashDotLine,
    "Dash dot dot line": QtCore.Qt.DashDotDotLine,
    #"Custom dash line": QtCore.Qt.CustomDashLine,
}

QtJoinStyles = {
    "Miter join": QtCore.Qt.MiterJoin,
    "Bevel join": QtCore.Qt.BevelJoin,
    "Round join": QtCore.Qt.RoundJoin,
    "SVG miter join": QtCore.Qt.SvgMiterJoin,
}

QtCapStyles = {
    "Flat cap": QtCore.Qt.FlatCap,
    "Square cap": QtCore.Qt.SquareCap,
    "Round cap": QtCore.Qt.RoundCap,
}
