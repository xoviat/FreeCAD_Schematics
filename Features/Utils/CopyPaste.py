# -*- coding: utf-8 -*-
###############################################################################
#
#  CopyPaste.py - Contains global variables
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

# QGraphicsScene coordinates where objects is copied
sceneCopyPos = None
# QGraphicsScene coordinates where objects is paste
scenePastePos = None
# If equal True during the insertion process, the objects will be inserted at the cursor position.
# Otherwise, the objects will be pasted at the same coordinates they were copied from.
pasteAtPos = False