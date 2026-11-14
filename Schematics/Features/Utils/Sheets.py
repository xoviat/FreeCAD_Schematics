# -*- coding: utf-8 -*-
###############################################################################
#
#  Sheets.py - multi-page helpers: page order, numbering, index rows.
#
###############################################################################
"""Project-level view over a document's sheets.

Sheets are independent Scheme objects; "pages" are their document order.
This gives every sheet a stable Page N of M number, feeds the drawn page
number, and backs the sheet index (KiCad's hierarchy navigator stand-in
until real hierarchical sheets exist).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import FreeCAD


def schemeObjects(document: Any = None) -> list[Any]:
    """All sheet objects of a document (defaults to the active one)."""
    doc = document if document is not None else FreeCAD.ActiveDocument
    if doc is None:
        return []
    result: list[Any] = []
    try:
        objects = list(doc.Objects)
    except (ReferenceError, RuntimeError, AttributeError):
        return result
    for obj in objects:
        try:
            if hasattr(obj, "Elements"):
                result.append(obj)
        except ReferenceError:
            continue   # object already deleted mid-iteration
    return result


def pageIndex(sheet: Any, document: Any = None) -> tuple[int, int]:
    """(1-based page number, total pages) for a sheet, or (0, 0)."""
    schemes = schemeObjects(document)
    for index, candidate in enumerate(schemes, start=1):
        try:
            if candidate.Name == sheet.Name:
                return (index, len(schemes))
        except (ReferenceError, RuntimeError, AttributeError):
            continue
    return (0, len(schemes))


@dataclass(frozen=True)
class SheetRow:
    """One line of the sheet index."""

    page: int
    name: str       # the sheet's tree label
    symbols: int    # annotated symbols (have a Designator property)
    wires: int


def sheetIndexRows(document: Any = None) -> list[SheetRow]:
    """Index rows for every sheet, in page order."""
    rows: list[SheetRow] = []
    for page, sheet in enumerate(schemeObjects(document), start=1):
        try:
            label = str(sheet.Label)
            elements = list(sheet.Elements)
        except (ReferenceError, RuntimeError, AttributeError):
            continue
        symbols = 0
        wires = 0
        for element in elements:
            try:
                if getattr(element, "Designator", None) is not None:
                    symbols += 1
                if getattr(element, "Type", "") == "Wire":
                    wires += 1
            except (ReferenceError, RuntimeError, AttributeError):
                continue
        rows.append(SheetRow(page=page, name=label, symbols=symbols, wires=wires))
    return rows
