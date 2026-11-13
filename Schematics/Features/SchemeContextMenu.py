# -*- coding: utf-8 -*-
###############################################################################
#
#  SchemeContextMenu.py
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

from PySide6 import QtGui, QtWidgets
from Schematics.Features.Utils.MDI import *
import Schematics.Features.Utils.CopyPaste

class ContextMenu(QtWidgets.QMenu):

    def __init__(self, parent):
        super().__init__(parent)
        self.scene = parent.scene()
        self.contextMenuScenePos = None

    def addActionExt(self, text, parent, func, enabled=True):
        # PySide6: QAction moved from QtWidgets to QtGui
        action = QtGui.QAction(text, parent, triggered=func)
        action.setEnabled(enabled)
        self.addAction(action)

    def addStandartActions(self):
        # print(Features.Utils.CopyPaste.sceneCopyPos, self.contextMenuScenePos)
        somethingSelected = False
        # if objects selected at scene...
        if len(FreeCAD.Gui.Selection.getSelection()) > 0:
            somethingSelected = True
        self.addActionExt('Copy', self, self.copy, somethingSelected)
        self.addAction(QtGui.QAction('Paste', self, triggered=self.paste))
        self.addSeparator()
        self.addAction(QtGui.QAction('Paste to the same place', self, triggered=self.pasteAtSamePlace))
        self.addActionExt('Duplicate this sheet', self, self.duplicateSheet, False)
        action = QtGui.QAction('Duplicate this sheet', self, triggered=self.duplicateSheet)
        if somethingSelected:
            self.addAction(QtGui.QAction('Turn Right +90°', self, triggered=self.turnRight))
            self.addAction(QtGui.QAction('Turn Left -90°', self, triggered=self.turnLeft))
        #contextMenu.hideEvent = self.contextMenuClosed
        # Remove item command?

    def invokeAt(self, pos):
        # Store scene position where user invoke contex menu
        self.contextMenuScenePos = self.scene.mouseCurPos
        self.exec(pos)

    #def contextMenuClosed(self, event):
        #print("contextMenuClosed")

    def copy(self):
        # Store scene pos where context menu is invoked, before copy objects
        Schematics.Features.Utils.CopyPaste.sceneCopyPos = self.contextMenuScenePos
        print("Copy at ", Schematics.Features.Utils.CopyPaste.sceneCopyPos)
        FreeCAD.Gui.runCommand('Std_Copy', 0)

    def paste(self):
        Schematics.Features.Utils.CopyPaste.scenePastePos = self.contextMenuScenePos
        Schematics.Features.Utils.CopyPaste.pasteAtPos = True
        FreeCAD.Gui.runCommand('Std_Paste', 0)
        Schematics.Features.Utils.CopyPaste.pasteAtPos = False
        # Shift objects after paste

    def pasteAtSamePlace(self):
        # print("Paste to the same place")
        FreeCAD.Gui.runCommand('Std_Paste', 0)

    def turnRight(self):
        for obj in FreeCAD.Gui.Selection.getSelection():
            if hasattr(obj, 'Rotation'):
                obj.Rotation = obj.Rotation.Value + (-360+90 if obj.Rotation.Value+90 > 360 else 90)

    def turnLeft(self):
        for obj in FreeCAD.Gui.Selection.getSelection():
            if hasattr(obj, 'Rotation'):
                obj.Rotation = obj.Rotation.Value - (-360+90 if obj.Rotation.Value-90 < -360 else 90)

    def duplicateSheet(self):
        return
