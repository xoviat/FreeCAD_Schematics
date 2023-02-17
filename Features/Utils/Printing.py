
import FreeCAD
from PySide2 import QtGui, QtCore, QtWidgets, QtPrintSupport

def PrintPreviewAction():

    # ! Mandatory. If move this code to def drawPage, then printing will not occur.
    asw = FreeCAD.Gui.getMainWindow().findChild(QtWidgets.QMdiArea).activeSubWindow()
    scene = asw.obj.Proxy.scene

    def drawPage(printer):
        printer.setFullPage(True)
        printer.setResolution(600)
        printer.setColorMode(printer.GrayScale)
        m = printer.margins()
        m.left = 0; m.top = 0; m.right = 0; m.bottom = 0
        printer.setMargins(m)

        painter = QtGui.QPainter()
        painter.begin(printer)
        targetRect = printer.pageLayout().fullRectPixels(printer.resolution())
        sourceRect = QtCore.QRect(0, 0, 210.0, 297.0) #420.0, 297.0)
        # Ideal adjust for my A4
        sourceRect.adjust(0, -0.5, +0.7, +4.0)
        scene.render(painter, targetRect, sourceRect)
        #asw.obj.Proxy.scene.render(painter)
        #, QtCore.QRect(0,0,printer.width(),printer.height()), QtCore.QRect(0,0,210.0,297.0))
        painter.end()
        print(f"Printer information")
        print(f"printer name :{printer.printerName()}")
        print(f"supported resolutions :{printer.supportedResolutions()}")
        print(f"page rect:{printer.pageRect(printer.Millimeter)}")
        print(f"paper rect:{printer.paperRect(printer.Millimeter)}")
        print(f"color mode:{printer.colorMode()}")
        print(f"paper source:{printer.paperSource()}")

    print('The Std_PrintPreview action should occur now, but this will not occurred because '
         'the original function has been replaced.')
    printer = QtPrintSupport.QPrinter()
    printer.setFullPage(True)
    # Get page size and orientation From template
    printer.setPageSize(QtGui.QPageSize(QtCore.QSizeF(210.0, 297.0), QtGui.QPageSize.Millimeter))
    printer.setPageOrientation(QtGui.QPageLayout.Orientation.Portrait)
    # ------------------------------------------
    dlg = QtPrintSupport.QPrintPreviewDialog() #printer, None)
    dlg.paintRequested.connect(drawPage)
    dlg.exec_()
