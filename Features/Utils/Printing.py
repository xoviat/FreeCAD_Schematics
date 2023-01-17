
import FreeCAD
from PySide2 import QtGui, QtCore, QtWidgets, QtPrintSupport

def PrintPreviewAction():
   def drawPage(printer):
        painter = QtGui.QPainter(printer)
        asw = FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea).activeSubWindow()
        scene = asw.obj.Proxy.scene
        targetRect = printer.pageLayout().fullRectPixels(printer.resolution())
        sourceRect = QtCore.QRect(0, 0, 420.0, 297.0)
        scene.render(painter, targetRect, sourceRect)
        #asw.obj.Proxy.scene.render(painter)
        #, QtCore.QRect(0,0,printer.width(),printer.height()), QtCore.QRect(0,0,210.0,297.0))
   print('The Std_PrintPreview action should occur now, but this will not occured because '
         'the original function has been replaced.')
   printer = QtPrintSupport.QPrinter()
   printer.setFullPage(True)
   # Get page size and orentation From template
   printer.setPageSize(QtGui.QPageSize(QtCore.QSizeF(210.0, 297.0), QtGui.QPageSize.Millimeter))
   printer.setPageOrientation(QtGui.QPageLayout.Orientation.Landscape)
   # ------------------------------------------
   dlg = QtPrintSupport.QPrintPreviewDialog(printer, None)
   dlg.paintRequested.connect(drawPage)
   dlg.exec_()
