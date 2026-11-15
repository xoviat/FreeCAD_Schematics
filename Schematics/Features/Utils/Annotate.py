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

#: Fallback reference prefixes by store group (GOST conventions) for
#: symbols whose library entry has no schematics:ref yet. The pin
#: editor's ref always wins over this table.
GROUP_PREFIXES: dict[str, str] = {
    "Resistors": "R",
    "Relays": "K",        # relays / contactors
    "Diodes": "VD",
    "Transistors": "VT",
    "Lamps": "H",
    "Commutation": "S",   # switches and buttons
}


def refPrefix(obj: Any, catalog: SymbolCatalog | None = None) -> str:
    """Reference prefix (R, K, Y, ...) from the symbol's metadata,
    falling back to the group table; empty when nothing is known."""
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
    if entry is not None:
        meta_ref = cat.meta(entry).ref
        if meta_ref:
            return meta_ref
    return GROUP_PREFIXES.get(group, "")


def takenDesignators(sheet: Any) -> set[str]:
    """All *numbered* designators already used on a sheet (placeholders
    ending in '?' are pending, they consume no numbers)."""
    taken: set[str] = set()
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return taken
    for element in elements:
        designator = getattr(element, "Designator", "")
        if designator and not str(designator).endswith("?"):
            taken.add(str(designator))
    return taken


def nextDesignator(prefix: str, taken: set[str]) -> str:
    """Smallest free ``prefix + number`` (R1, R2, ...)."""
    number = 1
    while "%s%d" % (prefix, number) in taken:
        number += 1
    return "%s%d" % (prefix, number)


def autoDesignate(obj: Any, sheet: Any, catalog: SymbolCatalog | None = None) -> str:
    """Mark a freshly placed symbol with a KiCad-style placeholder
    (``R?`` - prefix plus question mark; bare ``?`` when no prefix is
    known). Numbers are assigned by :func:`annotateSheet`, like KiCad's
    Annotate step. Returns the placeholder, or "" when nothing was set."""
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
    placeholder = (refPrefix(obj, catalog) or "") + "?"
    try:
        obj.Designator = placeholder
    except (ReferenceError, RuntimeError, AttributeError):
        return ""
    return placeholder


def annotateSheet(sheet: Any, catalog: SymbolCatalog | None = None) -> tuple[int, int]:
    """Assign numbers to pending symbols on a sheet, KiCad-style:
    replaces ``R?`` placeholders (and empty designators) with the
    smallest free number per prefix.

    Returns ``(assigned, skipped)`` where skipped counts symbols whose
    placeholder/library prefix is still unknown.
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
            designator = str(designator)
            if designator and not designator.endswith("?"):
                continue   # already numbered
            # A placeholder carries its own prefix ("K?" stays K even if
            # the library metadata changed since placement).
            prefix = designator[:-1] if designator.endswith("?") else ""
            if not prefix:
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
