# -*- coding: utf-8 -*-
###############################################################################
#
#  MDI.py - Functions for control SubWindows in FreeCAD main window QMDIArea
#
#  Copyright Evgeniy 2022 <https://github.com/FreeCAD-Tools>
#
###############################################################################

import FreeCAD
from PySide6 import QtGui, QtCore, QtSvg, QtWidgets

def getMdiArea():
    return FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea)

def isWindowExist(obj):
    """ Try to find window which contain scheme object """
    subWindowsList = getMdiArea().subWindowList()
    for subWindow in subWindowsList:
        if subWindow.__class__.__name__ == 'SchemeMDIView':
            if subWindow.obj == obj:
                return subWindow
    return None

def tryToGetSchemeFromActiveWindow():
    """ Try to get Scheme object from current active window """
    activeSubWindow = getMdiArea().activeSubWindow()
    #if hasattr(activeSubWindow, 'obj') and hasattr(activeSubWindow.obj, 'Elements'):  # < --- Altrenative
    if activeSubWindow.__class__.__name__ == 'SchemeMDIView':
        obj = activeSubWindow.obj
        # The window can outlive its document object (document closed
        # while the tab stayed open): any attribute access on a deleted
        # object raises ReferenceError, so treat the sheet as absent.
        try:
            obj.Name
        except ReferenceError:
            return None
        return obj
    return None

def activeWindowIsScheme():
    """ Return True if current active window is Scheme """
    return True if tryToGetSchemeFromActiveWindow() is not None else False

def activateItemTab(item):
    activateSceneTab(item.scene())

def activateSceneTab(scene):
    mdi = getMdiArea()
    activeSubWindow = mdi.activeSubWindow()
    if hasattr(activeSubWindow, 'obj') and hasattr(activeSubWindow.obj, 'Elements') and activeSubWindow.obj.Proxy.scene == scene:
        print("Tab is activated yet")
    else:
        print("Activate tab")
        subWindowsList = mdi.subWindowList()
        for sw in subWindowsList:
            if hasattr(sw, 'obj'):
                if sw.obj.Proxy.scene == scene:
                    # When switching to the other sub window, the treeview will lose focus, so it needs to be returned.
                    w = QtWidgets.QApplication.focusWidget()
                    print(w.__class__.__name__)
                    mdi.setActiveSubWindow(sw)
                    w.setFocus()
                    break

def closeSchemeWindowsOfDocument(document):
    """ Close scheme windows that belong to the given document.

    The MDI windows are Qt widgets owned by the main window, not by the
    document, so nothing else destroys them on document close; kept alive
    they keep repainting deleted objects and answer commands with them.
    Called synchronously while the document is closing — before the event
    loop can deliver a paint to the stale view. Returns the number of
    windows closed. """
    # Gui observers receive Gui.Document, App observers App.Document.
    appDoc = getattr(document, "Document", None) or document
    try:
        appDocName = appDoc.Name
    except Exception:
        appDocName = None
    mdi = getMdiArea()
    if mdi is None:
        return 0
    closed = 0
    for sw in list(mdi.subWindowList()):
        if sw.__class__.__name__ != 'SchemeMDIView':
            continue
        try:
            docName = getattr(sw, "docName", None)
            if docName is not None and appDocName is not None:
                belongs = docName == appDocName
            else:
                # Fallback when the window does not remember its document:
                # only an already deleted object identifies the closing
                # document's window (other documents stay untouched).
                try:
                    sw.obj.Name
                    belongs = False
                except ReferenceError:
                    belongs = True
            if belongs:
                # Detach the view from the scene first: the window is
                # destroyed via deleteLater() while the document's scene may
                # be garbage-collected as soon as the objects die — a view
                # destructor touching an already freed scene crashes the
                # whole process at teardown (exit 127, intermittent).
                view = sw.widget()
                setScene = getattr(view, "setScene", None)
                if callable(setScene):
                    setScene(None)
                print(f"Closing scheme window '{sw.windowTitle()}' "
                      f"of deleted document '{appDocName}'")
                sw.close()
                closed += 1
        except Exception:
            # Never let window teardown break document closing; the
            # paint-time retire in SchemeGraphicsScene is the fallback.
            pass
    return closed
