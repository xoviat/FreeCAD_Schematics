# -*- coding: utf-8 -*-
###############################################################################
#
#  TitleBlock.py - the drawing cartouche as a sheet element.
#
###############################################################################
"""Title block element: the GOST-style cartouche that sits in the
frame's bottom-right corner.

Like the BOM table it is a real document object in the sheet's Elements
list (visible in the model tree, selectable, deletable), and it is
inserted by default when a sheet is created (CreateScheme).

Differences from other elements:

- It is not placeable: X/Y are ignored, the item anchors itself to the
  frame's bottom-right corner on every template/page change, at the
  fixed physical size given by the sheet's TitleBlockWidth/
  TitleBlockHeight View properties (0 hides the element).

- Its text comes from Templates/TitleBlock.svg placeholders filled
  with the configured language's translation at creation (see
  Schematics.Features.Utils.TitleBlock for the i18n pipeline); live
  values (sheet title, page, page count) are drawn at paint time.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtSvg, QtSvgWidgets, QtWidgets

from Schematics.Features.Items.SchemeObject import (
    SchemeObjectFeature,
    SchemeObjectViewProvider,
    makeObject,
)
from Schematics.Features.Items.SchemeObjectItem import SchemeObjectItem
from Schematics.Features.Utils.TitleBlock import (
    TB_FONT_PX,
    TB_HEIGHT,
    TB_WIDTH,
    patchTitleBlockSvg,
    titleBlockTexts,
)


class TitleBlock:
    """Factory: ``TitleBlock(sheet)`` returns the App object."""

    # Not placeable through StartDraw; inserted by default at sheet
    # creation (kept for factory uniformity with the other elements).
    typ: str | None = None

    def __new__(
        cls, x: float | None = None, y: float | None = None,
        sheet: Any = None,
    ) -> Any:
        # x/y are accepted but ignored: the block is anchored to the
        # frame's bottom-right corner.
        return makeObject(TitleBlockFeature, TitleBlockViewProvider, sheet, cls)


class TitleBlockFeature(SchemeObjectFeature):

    def initDataPropertyies(self, obj: Any) -> None:
        # Anchored furniture: no own properties (size lives on the
        # sheet's View tab, text in the SVG placeholders).
        pass

    def onDataPropertyChanged(self, obj: Any, prop: str) -> None:
        pass

    def getItem(self, obj: Any, sheet: Any) -> TitleBlockItem:
        return TitleBlockItem(obj, sheet)

    def initRootMethods(self, obj: Any) -> None:
        pass


class TitleBlockViewProvider(SchemeObjectViewProvider):

    def initViewPropertyies(self, vobj: Any) -> None:
        pass

    def onViewPropertyChanged(self, vobj: Any, prop: str) -> None:
        pass


class TitleBlockItem(SchemeObjectItem, QtWidgets.QGraphicsItem):
    """Anchored cartouche: fixed size, translated labels, live values."""

    # Class-level defaults: the base SchemeObjectItem.__init__ triggers
    # updateTransform() (via the drawMode property) before __init__ body
    # assignments exist.
    width: float = TB_WIDTH
    height: float = TB_HEIGHT
    _renderer: QtSvg.QSvgRenderer | None = None
    _svg: QtSvgWidgets.QGraphicsSvgItem | None = None

    def __init__(self, obj: Any, sheet: Any) -> None:
        super().__init__(obj, sheet)
        self.setZValue(-0.9)   # above the frame (-1), below wires (-0.5)
        self.width = TB_WIDTH
        self.height = TB_HEIGHT
        self.valuePositions: dict[str, tuple[float, float, bool]] = {}
        # Labels are inserted at creation time from the configured
        # language; live values (title, page numbers) update on paint.
        self.texts: dict[str, str] = titleBlockTexts()
        self._renderer = None
        self._svg = None
        try:
            data, self.valuePositions = patchTitleBlockSvg(self.texts)
            renderer = QtSvg.QSvgRenderer()
            renderer.load(data)
            if renderer.isValid():
                svg = QtSvgWidgets.QGraphicsSvgItem(self)
                svg.setSharedRenderer(renderer)
                # Keep the renderer alive: setSharedRenderer does not
                # take ownership (README Testing gotcha) - a GC'd
                # wrapper deletes the C++ renderer the item points at.
                self._renderer = renderer
                svg.setFlags(
                    QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemClipsToShape
                )
                svg.setMaximumCacheSize(QtCore.QSize(2000, 2000))
                self._svg = svg
        except Exception:
            # Missing/broken cartouche template: live values alone still
            # render (containment: never raise into the scene path).
            pass
        self.updateTransform()

    # ------------------------------------------------------------------
    def updateTransform(self) -> None:
        """Anchor to the frame's bottom-right corner at the fixed size
        from the sheet's TitleBlock* View properties (0 hides)."""
        try:
            view = self.sheet.ViewObject
            width = float(view.TitleBlockWidth.Value)
            height = float(view.TitleBlockHeight.Value)
            page_w = float(view.Width.Value)
            page_h = float(view.Height.Value)
            renderer = self.sheet.Proxy.svg_template.renderer()
        except (ReferenceError, RuntimeError, AttributeError):
            return
        if width <= 0 or height <= 0:
            self.setVisible(False)
            return
        self.setVisible(True)
        if abs(width - self.width) > 1e-6 or abs(height - self.height) > 1e-6:
            self.prepareGeometryChange()
            self.width = width
            self.height = height
        if self._svg is not None:
            sx = width / TB_WIDTH
            sy = height / TB_HEIGHT
            self._svg.setTransform(
                QtGui.QTransform().scale(sx, sy), combine=False
            )
        vb = renderer.viewBoxF()
        if vb.width() <= 0 or vb.height() <= 0:
            return
        if renderer.elementExists("frame"):
            frame = renderer.boundsOnElement("frame")
        else:
            frame = vb
        # Natural frame margins inside the page (they stretch with it)
        margin_right = (vb.x() + vb.width()) - (frame.x() + frame.width())
        margin_bottom = (vb.y() + vb.height()) - (frame.y() + frame.height())
        scale_x = page_w / vb.width()
        scale_y = page_h / vb.height()
        # Anchored: never snapped or dragged away from the corner
        self.setPos(
            page_w - margin_right * scale_x - width,
            page_h - margin_bottom * scale_y - height,
        )

    def itemChange(self, change: Any, value: Any) -> Any:
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return value   # anchor position is exact; no grid snap
        return super().itemChange(change, value)

    def boundingRect(self) -> QtCore.QRectF:
        if not self.isVisible():
            return QtCore.QRectF(0, 0, 0, 0)
        # +/-0.5 slack for the 0.4 stroke
        return QtCore.QRectF(-0.5, -0.5, self.width + 1.0, self.height + 1.0)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        g = painter
        try:
            self.sheet.Proxy   # liveness probe
            color = QtGui.QColor.fromRgbF(
                *self.sheet.Proxy.appearance.linesColor()
            )
        except (ReferenceError, RuntimeError, AttributeError):
            return
        values: dict[str, str] = {}
        try:
            from Schematics.Features.Utils.Sheets import pageIndex

            values["title"] = str(self.sheet.Label)
            page, total = pageIndex(self.sheet)
            values["sheet"] = str(page)
            values["sheets"] = str(total)
        except (ReferenceError, RuntimeError, AttributeError, Exception):
            pass

        g.save()
        g.scale(self.width / TB_WIDTH, self.height / TB_HEIGHT)
        pen = QtGui.QPen(color, 0.4)
        g.setPen(pen)
        font = g.font()
        font.setPixelSize(TB_FONT_PX)
        font.setBold(False)
        font.setItalic(False)
        g.setFont(font)
        box_w = 40.0
        box_h = TB_FONT_PX * 1.6
        base = int(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.TextFlag.TextSingleLine
        )
        for key, (x, y, centered) in self.valuePositions.items():
            text = values.get(key, "")
            if not text:
                continue
            align = base | int(
                QtCore.Qt.AlignmentFlag.AlignHCenter if centered
                else QtCore.Qt.AlignmentFlag.AlignLeft
            )
            rect = QtCore.QRectF(
                x - box_w / 2.0 if centered else x, y - TB_FONT_PX, box_w, box_h
            )
            g.drawText(rect, align, text)
        g.restore()
