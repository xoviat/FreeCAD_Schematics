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

from PySide6 import QtCore

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

    from Schematics.Features.Utils.SVGSymbolsCache import transformUnits

    path = titleBlockSvgPath()
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    # mm -> unitless: QSvgRenderer.defaultSize() must equal the viewBox
    # or the child item renders ~3.5x too large (655x194 px vs 185x55)
    data = transformUnits(data)
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
