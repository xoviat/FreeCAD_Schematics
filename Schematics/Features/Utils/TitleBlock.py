# -*- coding: utf-8 -*-
###############################################################################
#
#  TitleBlock.py - fixed-size drawing title block overlaid on the sheet.
#
###############################################################################
"""The sheet's title block (the cartouche in the frame's bottom-right
corner).

Design (per project convention):

- Sheet templates (``Templates/*.svg``) are **geometry only** - the
  frame per sheet, no text baked in.

- The cartouche lives in its own ``Templates/TitleBlock.svg``: grid
  geometry plus *placeholder* text nodes. Placeholders are either
  labels (``schematics:i18n``) or live values (``schematics:value``).

- At sheet creation the placeholders are filled: labels go through
  :func:`PySide6.QtCore.QCoreApplication.translate` - the standard Qt
  Linguist i18n mechanism, which FreeCAD drives from its language
  preference. English source strings are compiled into the code, so
  the default language is English; translations ship as
  ``translations/schematics_<lang>.qm`` (``pyside6-lrelease``), which
  FreeCAD's Translator auto-loads from the user app-data
  ``translations/`` directory (``install.py`` places them there).

- The block is overlaid on the sheet at a **fixed physical size**
  (``TitleBlockWidth``/``TitleBlockHeight`` View properties, defaults
  185x55 mm) regardless of the page size, anchored to the frame's
  bottom-right corner.

- Live values (the sheet's title/Label, page number, page count) are
  drawn natively at paint time so they stay current without
  re-rendering the SVG.
"""

from __future__ import annotations

import os
from typing import Any

from PySide6 import QtCore, QtGui, QtSvg, QtSvgWidgets, QtWidgets

#: Natural size of the title block (matches the cartouche SVG).
TB_WIDTH = 185.0
TB_HEIGHT = 55.0

#: Font size for every title-block text, in sheet units (mm).
TB_FONT_PX = 4

#: Namespace for the placeholder attributes in TitleBlock.svg.
NS = "http://www.freecad.org/wiki/index.php?title=Svg_Namespace"
NSMAP = {"schematics": NS}


def titleBlockTexts() -> dict[str, str]:
    """Resolve the cartouche labels through Qt's translation system.

    English source strings live here (extracted by ``pyside6-lupdate``
    into the .ts files - note it only recognizes the direct
    ``QtCore.QCoreApplication.translate("Schematics", ...)`` call form with literal arguments); the active
    FreeCAD language decides whether a translation is returned.
    """
    return {
        "rev": QtCore.QCoreApplication.translate("Schematics", "Rev."),
        "sheet": QtCore.QCoreApplication.translate("Schematics", "Sheet"),
        "doc_no": QtCore.QCoreApplication.translate("Schematics", "Doc. no."),
        "sign": QtCore.QCoreApplication.translate("Schematics", "Sign"),
        "date": QtCore.QCoreApplication.translate("Schematics", "Date"),
        "drawn": QtCore.QCoreApplication.translate("Schematics", "Drawn"),
        "checked": QtCore.QCoreApplication.translate("Schematics", "Checked"),
        "tech_ctrl": QtCore.QCoreApplication.translate("Schematics", "T. ctrl."),
        "adjunct": QtCore.QCoreApplication.translate("Schematics", "Adjunct"),
        "norm_ctrl": QtCore.QCoreApplication.translate("Schematics", "N. ctrl."),
        "approved": QtCore.QCoreApplication.translate("Schematics", "Appr."),
        "lit": QtCore.QCoreApplication.translate("Schematics", "Lit."),
        "mass": QtCore.QCoreApplication.translate("Schematics", "Mass"),
        "scale": QtCore.QCoreApplication.translate("Schematics", "Scale"),
        "sheets": QtCore.QCoreApplication.translate("Schematics", "Sheets"),
        "title": QtCore.QCoreApplication.translate("Schematics", "Title"),
        "organization": QtCore.QCoreApplication.translate("Schematics", "Organization"),
    }


def titleBlockSvgPath() -> str:
    """Path of the cartouche template (Templates/TitleBlock.svg)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    ))))
    return os.path.join(root, "Templates", "TitleBlock.svg")


def patchTitleBlockSvg(texts: dict[str, str]) -> tuple[bytes, dict[str, tuple[float, float, bool]]]:
    """Fill the i18n placeholders of TitleBlock.svg.

    Returns (svg bytes with translated labels, value positions) where
    value positions map key -> (x, y, centered) for the live values
    that are drawn natively at paint time.
    """
    import xml.etree.ElementTree as ET

    path = titleBlockSvgPath()
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    root = ET.fromstring(data)
    values: dict[str, tuple[float, float, bool]] = {}
    for el in root.iter():
        key = el.get(f"{{{NS}}}i18n")
        if key is not None:
            # Never leave a text node empty: Qt 6.8's SVG renderer
            # crashes (access violation) on <text/> with no content.
            el.text = texts.get(key) or " "
        value_key = el.get(f"{{{NS}}}value")
        if value_key is not None:
            el.text = el.text or " "   # values are drawn natively
            try:
                x = float(el.get("x", "0"))
                y = float(el.get("y", "0"))
            except ValueError:
                continue
            centered = el.get("text-anchor") == "middle"
            values[value_key] = (x, y, centered)
    return ET.tostring(root, encoding="utf-8"), values


class TitleBlockItem(QtWidgets.QGraphicsItem):
    """Sheet-owned cartouche: fixed size, labels resolved at creation."""

    def __init__(
        self, sheet: Any, width: float = TB_WIDTH, height: float = TB_HEIGHT
    ) -> None:
        super().__init__()
        self.sheet = sheet
        self.width = float(width)
        self.height = float(height)
        self.valuePositions: dict[str, tuple[float, float, bool]] = {}
        self.setZValue(-0.9)   # above the frame (-1), below wires (-0.5)

        # Labels are inserted at creation time from the configured
        # language; live values update on paint.
        self.texts: dict[str, str] = titleBlockTexts()
        try:
            data, self.valuePositions = patchTitleBlockSvg(self.texts)
            renderer = QtSvg.QSvgRenderer()
            renderer.load(data)
            if renderer.isValid():
                svg = QtSvgWidgets.QGraphicsSvgItem(self)
                svg.setSharedRenderer(renderer)
                # Keep the renderer alive: setSharedRenderer does not take
                # ownership, and a GC'd wrapper deletes the C++ renderer
                # the item still points at (native AV on first paint).
                self._renderer = renderer
                svg.setFlags(
                    QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemClipsToShape
                )
                svg.setMaximumCacheSize(QtCore.QSize(2000, 2000))
                sx = self.width / TB_WIDTH
                sy = self.height / TB_HEIGHT
                svg.setTransform(QtGui.QTransform().scale(sx, sy), combine=False)
                self._svg = svg
        except Exception:
            # Missing/broken cartouche template: live values alone still
            # render (containment: never raise into the paint/scene path).
            pass

    def boundingRect(self) -> QtCore.QRectF:
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
