# -*- coding: utf-8 -*-
###############################################################################
#
#  ActionsReplacer.py - Tool for replace original menu item actions to user defined
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
from PySide2 import QtGui, QtCore, QtWidgets

ActionsList = []

def registerAction(cmdName, functionName):
    """ Add new action to list. Example: registerAction("Std_Copy", myCopy) """
    global ActionsList
    ActionsList += [MenuActionContainer(cmdName, functionName)]

def actionsSetActivate(state):
    """ Activate/Deactivate replaced functions """
    global ActionsList
    if state:
        # Better to do two actions
        for x in ActionsList: x.deActivate()
        for x in ActionsList: x.activate()
    else:
        # Better to do two actions
        for x in ActionsList: x.activate()
        for x in ActionsList: x.deActivate()

class MenuActionContainer:
    """ Container class for store and switch original and user defined actions """
    def __init__(self, cmdName, newMethod):
        #print(f'Init {cmdName} MenuActionContainer')
        self.cmdName = cmdName
        self.newMethod = newMethod
        self.newAction = None
        self.origAction = None
        self.menu = None
        self.active = None

    def tryToFindAction(self):
        """ This function iterate all menu items and try to find action which invoke cmdName command """
        mw = FreeCAD.Gui.getMainWindow()
        actions = mw.menuBar().findChildren(QtWidgets.QAction)
        for a in actions:
           # print(a.data())
           if a.menu() is not None:
              for origAction in a.menu().actions():
                 # print(origAction.data())
                 if origAction.data() == self.cmdName:
                    self.menu = a.menu()
                    self.origAction = origAction
                    if self.newAction is None:
                        self.newAction = QtWidgets.QAction(
                            self.origAction.icon(), self.origAction.text(), None, triggered=self.newMethod)
                        self.newAction.setShortcut(self.origAction.shortcut())
                    self.active = False
                    #print(f"{self.cmdName} is finded!")
                    return
        #print(f"{self.cmdName} Not finded!" )

    def activate(self):
        """ Replace original action to user defined Python function """
        self.tryToFindAction()
        if self.active == False:
            # print(f'activate {self.cmdName}')
            self.menu.insertAction(self.origAction, self.newAction)
            self.menu.removeAction(self.origAction)
            self.active = True

    def deActivate(self):
        """ Turn back original action and remove user defined Python function """
        self.tryToFindAction()
        if self.active == True:
            # print(f'deActivate {self.cmdName}')
            self.menu.insertAction(self.newAction, self.origAction)
            self.menu.removeAction(self.newAction)
            self.active = False
