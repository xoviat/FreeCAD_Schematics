# -*- coding: utf-8 -*-
###############################################################################
#
#  Annotate.py - KiCad-style reference designators for symbols.
#
###############################################################################
"""Reference designators (K1, R3, ...) and value fields.

The reference prefix comes from the symbol's library entry
(``schematics:ref``, edited in the symbol manager's pin editor); symbols
without a prefix are skipped until one is set. Placement auto-annotates
via :func:`autoDesignate`; :func:`annotateSheet` fills the rest, like
KiCad's Annotate dialog.
"""

from __future__ import annotations

from typing import Any

from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog


def refPrefix(obj: Any, catalog: SymbolCatalog | None = None) -> str:
    """Reference prefix (R, K, Y, ...) from the symbol's metadata."""
    try:
        standard = str(obj.Standard)
        group = str(obj.Group)
        typ = str(obj.Type)
    except (ReferenceError, RuntimeError, AttributeError):
        return ""
    if not typ:
        return ""
    cat = catalog if catalog is not None else SymbolCatalog(standard)
    entry = cat.find(typ, group, standard)
    if entry is None:
        return ""
    return cat.meta(entry).ref


def takenDesignators(sheet: Any) -> set[str]:
    """All designators already used on a sheet (for collision-free picks)."""
    taken: set[str] = set()
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return taken
    for element in elements:
        designator = getattr(element, "Designator", "")
        if designator:
            taken.add(str(designator))
    return taken


def nextDesignator(prefix: str, taken: set[str]) -> str:
    """Smallest free ``prefix + number`` (R1, R2, ...)."""
    number = 1
    while "%s%d" % (prefix, number) in taken:
        number += 1
    return "%s%d" % (prefix, number)


def autoDesignate(obj: Any, sheet: Any, catalog: SymbolCatalog | None = None) -> str:
    """Annotate a freshly placed symbol. Returns the designator, or ""
    when nothing was assigned (already set, no sheet, or no prefix)."""
    try:
        if getattr(obj, "Designator", ""):
            return str(obj.Designator)
        if not getattr(obj, "Value", ""):
            obj.Value = str(obj.Type)
    except (ReferenceError, RuntimeError, AttributeError):
        return ""
    if sheet is None:
        from Schematics.Features.Utils.MDI import tryToGetSchemeFromActiveWindow
        sheet = tryToGetSchemeFromActiveWindow()
    if sheet is None:
        return ""
    prefix = refPrefix(obj, catalog)
    if not prefix:
        return ""
    designator = nextDesignator(prefix, takenDesignators(sheet))
    try:
        obj.Designator = designator
    except (ReferenceError, RuntimeError, AttributeError):
        return ""
    return designator


def annotateSheet(sheet: Any, catalog: SymbolCatalog | None = None) -> tuple[int, int]:
    """Fill empty designators on a sheet using each symbol's prefix.

    Returns ``(assigned, skipped)`` where skipped counts symbols whose
    library entry has no reference prefix yet.
    """
    cat = catalog if catalog is not None else SymbolCatalog()
    assigned = 0
    skipped = 0
    taken = takenDesignators(sheet)
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return assigned, skipped
    for element in elements:
        try:
            designator = getattr(element, "Designator", None)
            if designator is None:
                continue   # not a symbol (wire, rectangle, text, ...)
            if designator:
                continue   # already annotated
            prefix = refPrefix(element, cat)
            if not prefix:
                skipped += 1
                continue
            new = nextDesignator(prefix, taken)
            element.Designator = new
            taken.add(new)
            if not getattr(element, "Value", ""):
                element.Value = str(element.Type)
            assigned += 1
        except (ReferenceError, RuntimeError, AttributeError):
            continue
    return assigned, skipped
