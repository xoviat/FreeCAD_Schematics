# -*- coding: utf-8 -*-
###############################################################################
#
#  BatchImport.py - folder scan and batched writing of store symbols.
#
###############################################################################
"""Import symbols from a folder: QElectroTech ``.elmt`` files and
store-format ``.svg`` files in one pass.

:mod:`Schematics.Features.Utils.QETImport` converts a single QET
element; this module is the batch layer the import dialog drives:

* :func:`scanImportFolder` - walk a folder once and report both kinds
  as :class:`ImportItem` rows for the selection list;
* :func:`importSymbolItems` - write the ticked items into a target
  group, skipping names the store already has, reporting progress and
  honouring a cancellation callback for the dialog's worker thread.

Kept free of Qt so the suites can exercise it directly.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from Schematics.Features.Utils.QETImport import (
    QETImportError,
    categoryOf,
    convertQETFile,
    scanQETElements,
    symbolStem,
)

Kind = Literal["svg", "qet"]


@dataclass(frozen=True)
class ImportItem:
    """One candidate found in the scanned folder."""

    path: str
    name: str        # file stem (svg) or element name (qet)
    category: str    # folder under the scanned root, "/"-separated
    kind: Kind


@dataclass(frozen=True)
class ImportReport:
    """Outcome of a batch import."""

    imported: list[str]
    skipped: list[str]                 # name already in the store
    failed: list[tuple[str, str]]      # (path, reason)
    notes: list[str] = field(default_factory=list)
    cancelled: bool = False


def scanImportFolder(folder: str) -> list[ImportItem]:
    """Every ``.svg`` and ``.elmt`` symbol under *folder*, recursively.

    SVG files need no parsing - the stem is the name; QET names come
    from :func:`scanQETElements`.
    """
    items: list[ImportItem] = []
    for dirpath, _dirnames, filenames in os.walk(folder):
        for filename in sorted(filenames):
            if not filename.lower().endswith(".svg"):
                continue
            path = os.path.join(dirpath, filename)
            items.append(
                ImportItem(
                    path=path,
                    name=filename[:-4],
                    category=categoryOf(path, folder),
                    kind="svg",
                )
            )
    for info in scanQETElements(folder):
        items.append(
            ImportItem(
                path=info.path,
                name=info.name,
                category=info.category,
                kind="qet",
            )
        )
    items.sort(
        key=lambda item: (item.category.lower(), item.kind, item.name.lower())
    )
    return items


def _copySvg(source: str, dest: str) -> None:
    """Copy a store SVG, keeping the repository's LF-only line ends."""
    with open(
        source, "r", encoding="utf-8", errors="replace", newline=""
    ) as handle:
        data = handle.read()
    if "<svg" not in data:
        raise ValueError("not an SVG file")
    with open(dest, "w", encoding="utf-8", newline="") as handle:
        handle.write(data.replace("\r\n", "\n"))


def _discard(path: str) -> None:
    """Remove a half-written file; already-gone is fine."""
    try:
        os.remove(path)
    except OSError:
        pass


def importSymbolItems(
    items: Sequence[ImportItem],
    destDir: str,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    groupByCategory: bool = False,
) -> ImportReport:
    """Write *items* into ``destDir``, skipping names already present.

    With *groupByCategory*, ``destDir`` is the store root and every item
    is written into a group equal to its category (a nested path, so two
    source folders never collide); otherwise ``destDir`` is the one
    target group and everything lands flat in it.

    *progress* is called after every item as ``(done, total)``;*cancelled* is polled before each item.  Stopping mid-batch never
    leaves a partial symbol: each file is written whole or not at all.
    """
    imported: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    notes: list[str] = []
    total = len(items)
    os.makedirs(destDir, exist_ok=True)
    # Skip checks are per destination: the same stem under two different
    # categories is two symbols, not a duplicate.
    done: dict[str, set[str]] = {}
    for index, item in enumerate(items):
        if cancelled is not None and cancelled():
            return ImportReport(
                imported=imported,
                skipped=skipped,
                failed=failed,
                notes=notes,
                cancelled=True,
            )
        stem = symbolStem(item.name)
        target = destDir
        if groupByCategory:
            parts = [part for part in item.category.split("/") if part]
            if parts:
                target = os.path.join(destDir, *parts)
        dest = os.path.join(target, stem + ".svg")
        written = done.setdefault(target, set())
        if stem in written or os.path.exists(dest):
            # Re-importing an unchanged folder must be a no-op, so the
            # existing file wins and is not parsed or rewritten.
            skipped.append(stem)
        elif item.kind == "svg":
            try:
                os.makedirs(target, exist_ok=True)
                _copySvg(item.path, dest)
                imported.append(stem)
                written.add(stem)
            except (OSError, ValueError) as exc:
                failed.append((item.path, str(exc)))
                _discard(dest)
        else:
            symbol = None
            try:
                symbol = convertQETFile(item.path)
            except QETImportError as exc:
                failed.append((item.path, str(exc)))
            except Exception as exc:  # one bad file must not stop the batch
                failed.append((item.path, "%s: %s" % (type(exc).__name__, exc)))
            if symbol is not None:
                try:
                    os.makedirs(target, exist_ok=True)
                    with open(dest, "w", encoding="utf-8", newline="") as handle:
                        handle.write(symbol.svg)
                    imported.append(symbol.stem)
                    written.add(symbol.stem)
                    for note in symbol.notes:
                        entry = "%s: %s" % (symbol.stem, note)
                        if entry not in notes:
                            notes.append(entry)
                except OSError as exc:
                    failed.append((item.path, "write failed: %s" % exc))
                    _discard(dest)
        if progress is not None:
            progress(index + 1, total)
    return ImportReport(
        imported=imported, skipped=skipped, failed=failed, notes=notes
    )
