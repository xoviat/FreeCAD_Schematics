# -*- coding: utf-8 -*-
###############################################################################
#
#  ActionsReplacer.py - Tool for replace original menu item actions to user defined
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from typing import Any

import FreeCAD
from PySide6 import QtGui, QtCore, QtWidgets

ActionsList: list["MenuActionContainer"] = []

def registerAction(cmdName: str, functionName: Any) -> None:
    """ Add new action to list. Example: registerAction("Std_Copy", myCopy) """
    global ActionsList
    ActionsList += [MenuActionContainer(cmdName, functionName)]

def actionsSetActivate(state: bool) -> None:
    """ Activate/Deactivate replaced functions """
    global ActionsList
    if state:
        # Better to do two actions
        for x in ActionsList:
            x.deActivate()
        for x in ActionsList:
            x.activate()
    else:
        # Better to do two actions
        for x in ActionsList:
            x.activate()
        for x in ActionsList:
            x.deActivate()

class MenuActionContainer:
    """ Container class for store and switch original and user defined actions """
    def __init__(self, cmdName: str, newMethod: Any) -> None:
        #print(f'Init {cmdName} MenuActionContainer')
        self.cmdName = cmdName
        self.newMethod = newMethod
        self.newAction: QtGui.QAction | None = None
        self.origAction: QtGui.QAction | None = None
        self.menu: QtWidgets.QMenu | None = None
        self.active: bool | None = None

    def tryToFindAction(self) -> None:
        """ This function iterate all menu items and try to find action which invoke cmdName command """
        mw: Any = FreeCAD.Gui.getMainWindow()
        if mw is None:
            return
        # PySide6: QAction moved from QtWidgets to QtGui
        actions = mw.menuBar().findChildren(QtGui.QAction)
        for a in actions:
           # print(a.data())
           if a.menu() is not None:
              for origAction in a.menu().actions():
                 # print(origAction.data())
                 if origAction.data() == self.cmdName:
                    self.menu = a.menu()
                    self.origAction = origAction
                    if self.newAction is None:
                        # PySide6 has no (icon, text, parent, triggered=...)
                        # constructor overload: connect explicitly.
                        self.newAction = QtGui.QAction(
                            self.origAction.icon(), self.origAction.text(), None)
                        self.newAction.triggered.connect(self.newMethod)
                        self.newAction.setShortcut(self.origAction.shortcut())
                    self.active = False
                    #print(f"{self.cmdName} is finded!")
                    return
        #print(f"{self.cmdName} Not finded!" )

    def activate(self) -> None:
        """ Replace original action to user defined Python function """
        self.tryToFindAction()
        if self.active is False and self.menu is not None \
                and self.origAction is not None and self.newAction is not None:
            # print(f'activate {self.cmdName}')
            self.menu.insertAction(self.origAction, self.newAction)
            self.menu.removeAction(self.origAction)
            self.active = True

    def deActivate(self) -> None:
        """ Turn back original action and remove user defined Python function """
        self.tryToFindAction()
        if self.active is True and self.menu is not None \
                and self.origAction is not None and self.newAction is not None:
            # print(f'deActivate {self.cmdName}')
            self.menu.insertAction(self.newAction, self.origAction)
            self.menu.removeAction(self.newAction)
            self.active = False
