# -*- coding: utf-8 -*-
###############################################################################
#
#  Reports.py - component lists (the machine-schematic deliverable).
#
###############################################################################
"""Report generation over a sheet's annotated symbols.

The data comes from the Gap-3 fields (Designator/Value) and the symbol
store metadata (description); rows are plain dataclasses so tests and
future report types (cable lists, terminal plans) share one model.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Any, Iterable

from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog

REPORT_HEADERS: tuple[str, ...] = (
    "Designator",
    "Value",
    "Symbol",
    "Description",
)


@dataclass(frozen=True)
class ComponentRow:
    """One device line of a component list."""

    designator: str
    value: str
    symbol: str        # "Group/Name" in the store
    description: str


_DESIGNATOR_RE = re.compile(r"^([A-Za-z.]*)(\d*)$")


def _designatorSortKey(row: ComponentRow) -> tuple[str, int, str]:
    """Natural ordering: R1, R2, R10 (not R1, R10, R2)."""
    match = _DESIGNATOR_RE.match(row.designator)
    if match is None:
        return ("\uffff", 0, row.designator)
    prefix, number = match.group(1), match.group(2)
    return (prefix, int(number) if number else 0, row.designator)


def componentRows(sheet: Any, catalog: SymbolCatalog | None = None) -> list[ComponentRow]:
    """One row per symbol on the sheet, ordered by designator.

    Symbols with a blank designator are unannotated devices and are not
    listed - an empty BOM line would be noise, not a component.
    """
    cat = catalog if catalog is not None else SymbolCatalog()
    rows: list[ComponentRow] = []
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return rows
    for element in elements:
        try:
            designator = getattr(element, "Designator", None)
            if designator is None:
                continue   # not a symbol (wire, rectangle, text, ...)
            designator = str(designator)
            if not designator.strip():
                continue   # unannotated: no BOM line (KiCad/QET skip it too)
            entry = cat.find_by_instance(element)
            if entry is not None:
                symbol = "%s/%s" % (entry.group or "(root)", entry.name)
                description = cat.meta(entry).description
            else:
                symbol = str(getattr(element, "Type", ""))
                description = ""
            rows.append(
                ComponentRow(
                    designator=designator,
                    value=str(getattr(element, "Value", "")),
                    symbol=symbol,
                    description=description,
                )
            )
        except (ReferenceError, RuntimeError, AttributeError):
            continue
    rows.sort(key=_designatorSortKey)
    return rows


def symbolCount(sheet: Any) -> int:
    """How many component rows a sheet would produce, without building the
    symbol catalog.

    Row count only needs each element's Designator; the catalog (which
    walks the whole symbol store) is only needed for the symbol name and
    description that componentRows fills in. Size math on the sheet runs
    per mouse-move while dragging, so it must stay cheap - verify pins
    the two to the same number, blank designators excluded in both.
    """
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return 0
    count = 0
    for element in elements:
        try:
            designator = getattr(element, "Designator", None)
            if designator is not None and str(designator).strip():
                count += 1
        except (ReferenceError, RuntimeError, AttributeError):
            continue   # half-deleted element; componentRows skips it too
    return count


def componentListText(rows: Iterable[ComponentRow]) -> str:
    """Aligned plain-text table (console, log, quick paste)."""
    materialized = list(rows)
    widths = [len(header) for header in REPORT_HEADERS]
    for row in materialized:
        for index, cell in enumerate(
            (row.designator, row.value, row.symbol, row.description)
        ):
            widths[index] = max(widths[index], len(cell))
    lines = [
        "  ".join(header.ljust(widths[i]) for i, header in enumerate(REPORT_HEADERS)),
        "  ".join("-" * width for width in widths),
    ]
    for row in materialized:
        cells = (row.designator, row.value, row.symbol, row.description)
        lines.append(
            "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()
        )
    return "\n".join(lines) + "\n"


def writeCsv(path: str, rows: Iterable[ComponentRow]) -> None:
    """Write the component list as CSV (Excel/spreadsheet friendly)."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(REPORT_HEADERS)
        for row in rows:
            writer.writerow((row.designator, row.value, row.symbol, row.description))
