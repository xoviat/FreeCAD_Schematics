# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolCatalog.py - discovery and metadata for the SVG symbol store.
#
###############################################################################
"""Single source of truth for symbol files under ``Symbols/<standard>``.

The toolbar historically walked the store itself; the chooser, the manager
and future tooling all go through this catalog instead, so discovery rules
(group layout, pin parsing, root-tag metadata) live in one place.

Symbol files follow the existing convention::

    <svg width="30mm" height="20mm" viewBox="0 0 30 20" ...
         xmlns:schematics="http://"
         schematics:ref="K" schematics:description="Contactor coil">
      <g stroke="#000000" fill="none" stroke-width=".5"> ...drawing... </g>
      <rect schematics:pin="A1" x="5" y="10"/>
    </svg>

``schematics:ref`` (auto-annotation prefix) and ``schematics:description``
are optional; pins are zero-size rects parsed by the workbench cache.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from SCUtils import pathToSymbolsFolder

# Root tag metadata (optional, read from the raw file).
_ROOT_TAG_RE = re.compile(r"<svg[^>]*>")
_DESC_RE = re.compile(r'schematics:description="([^"]*)"')
_REF_RE = re.compile(r'schematics:ref="([^"]*)"')


@dataclass(frozen=True)
class SymbolPin:
    """One connection point in SVG user coordinates."""

    name: str
    x: float
    y: float


@dataclass(frozen=True)
class SymbolMeta:
    """Optional metadata carried in the root <svg> tag."""

    description: str = ""
    ref: str = ""


@dataclass(frozen=True)
class SymbolEntry:
    """One symbol file in the store."""

    standard: str   # store root below Symbols/, currently always "GOST"
    group: str      # subdirectory ('' = files directly under the root)
    name: str       # file stem; this is the symbol's Type on sheet objects
    path: str       # absolute file path

    @property
    def key(self) -> str:
        """Cache key in the same ``Standard\\Group\\Name`` form the
        workbench loader uses."""
        return "\\".join(p for p in (self.standard, self.group, self.name) if p)

    @property
    def display_name(self) -> str:
        return self.name


class SymbolCatalog:
    """Walks the symbol store and answers queries about its contents."""

    def __init__(self, standard: str = "GOST", root: str | None = None) -> None:
        self.standard = standard
        # root override: tests point the catalog at a temp store
        self.root = root if root is not None else os.path.join(
            pathToSymbolsFolder, standard
        )
        self._entries: list[SymbolEntry] = []
        self._by_key: dict[str, SymbolEntry] = {}
        self._meta_cache: dict[str, SymbolMeta] = {}
        self.refresh()

    def refresh(self) -> None:
        """Re-walk the store (after import/delete/rename in the manager)."""
        self._entries = []
        self._by_key = {}
        self._meta_cache = {}
        if not os.path.isdir(self.root):
            return
        for dirpath, _dirnames, filenames in os.walk(self.root):
            rel = os.path.relpath(dirpath, self.root)
            group = "" if rel == "." else rel.replace(os.sep, "\\")
            for filename in sorted(filenames):
                if not filename.lower().endswith(".svg"):
                    continue
                name = filename[:-4]
                entry = SymbolEntry(
                    standard=self.standard,
                    group=group,
                    name=name,
                    path=os.path.join(dirpath, filename),
                )
                self._entries.append(entry)
                self._by_key[entry.key] = entry
        self._entries.sort(key=lambda e: (e.group, e.name.lower()))
        self._by_key = {e.key: e for e in self._entries}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def all(self) -> list[SymbolEntry]:
        return list(self._entries)

    def groups(self) -> list[str]:
        seen: dict[str, None] = {}
        for entry in self._entries:
            seen.setdefault(entry.group, None)
        return list(seen)

    def symbols_in(self, group: str) -> list[SymbolEntry]:
        return [e for e in self._entries if e.group == group]

    def find(self, name: str, group: str = "", standard: str | None = None) -> SymbolEntry | None:
        key = "\\".join(p for p in (standard or self.standard, group, name) if p)
        return self._by_key.get(key)

    def find_by_instance(self, obj: object) -> SymbolEntry | None:
        """Resolve a sheet object's Standard/Group/Type back to the store."""
        try:
            standard = str(getattr(obj, "Standard", self.standard))
            group = str(getattr(obj, "Group", ""))
            typ = str(getattr(obj, "Type", ""))
        except (ReferenceError, RuntimeError, AttributeError):
            return None
        if not typ:
            return None
        return self.find(typ, group, standard)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    def load(self, entry: SymbolEntry) -> tuple[str, list[tuple[str, float, float]]]:
        """Return (svg data with pins stripped, [(name, x, y), ...]).
        Delegates to the workbench cache in SVGSymbolsCache."""
        from Schematics.Features.Utils.SVGSymbolsCache import loadSVGSymbol
        return loadSVGSymbol(entry.key)

    def pins(self, entry: SymbolEntry) -> list[SymbolPin]:
        _data, raw = self.load(entry)
        return [SymbolPin(name=str(n), x=float(x), y=float(y)) for n, x, y in raw]

    def meta(self, entry: SymbolEntry) -> SymbolMeta:
        """Read optional schematics:ref / schematics:description from the
        root tag (cached per path until refresh())."""
        cached = self._meta_cache.get(entry.path)
        if cached is not None:
            return cached
        meta = SymbolMeta()
        try:
            with open(entry.path, "r", encoding="utf-8") as handle:
                head = handle.read(4096)
        except OSError:
            self._meta_cache[entry.path] = meta
            return meta
        root = _ROOT_TAG_RE.search(head)
        if root is not None:
            tag = root.group(0)
            desc = _DESC_RE.search(tag)
            ref = _REF_RE.search(tag)
            meta = SymbolMeta(
                description=desc.group(1) if desc else "",
                ref=ref.group(1) if ref else "",
            )
        self._meta_cache[entry.path] = meta
        return meta
