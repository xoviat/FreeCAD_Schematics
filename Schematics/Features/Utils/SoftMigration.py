# -*- coding: utf-8 -*-
###############################################################################
#
#  SoftMigration.py - Tool for support opening of older schematics files
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

def Start(realobj):
    class plugObj:
        def __init__(self, _realobj):
            self.realobj = _realobj
            self.ActiveProp = [
                'Proxy',   # Proxy exist in Data and View objects
                'ExpressionEngine', 'Label', 'Label2',    # Default Data properties
                'DisplayMode', 'OnTopWhenSelected', 'SelectionStyle', 'ShowInTree', 'Visibility'   # Default View prop
            ]

        def setPropertyStatus(self, name, par):
            if not hasattr(self.realobj, name):
                self.realobj.setPropertyStatus(name, par)
            # In other case nothing do

        def cleanUp(self):
            Prop = self.realobj.PropertiesList
            for prop in Prop:
                if prop not in self.ActiveProp:
                    self.realobj.removeProperty(prop)
                    #print(f"Property '{prop}' removed")

        def addProperty(self, typ, name, group="", docstr="", proptype=0):
            self.ActiveProp.append(name)
            if not hasattr(self.realobj, name):
                res = self.realobj.addProperty(typ, name, group, docstr, proptype)
                #print(f"addProperty {name} ok")
                return res
            else:
                class Plug:
                    pass
                #print(f"Property {name} is already exist")
                return Plug()

    return plugObj(realobj)
