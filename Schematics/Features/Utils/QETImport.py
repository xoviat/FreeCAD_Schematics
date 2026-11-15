# -*- coding: utf-8 -*-
###############################################################################
#
#  QETImport.py - parse and convert QElectroTech .elmt elements.
#
###############################################################################
"""Convert QElectroTech elements into store-format SVG symbols.

QElectroTech ships its element library as XML ``.elmt`` files: a
``<definition>`` carrying ``<names>`` (one per language) and a
``<description>`` of drawing primitives plus ``<terminal>`` pins.  This
module turns those files into the SVG files the symbol store keeps:

* primitives become the symbol editor's native shapes where one exists
  (line, rect, circle, ellipse, polyline, text) so imported artwork stays
  editable in the editor, and a backdrop ``<path>`` otherwise (arcs, and
  anything carrying a dash pattern the shape model does not hold);
* ``<terminal>`` elements become ``schematics:pin`` rects applied through
  :func:`SymbolDrawing.renderSymbol`, named ``x1..xN`` like every other
  store symbol (in memory, so the batch layer writes each file once);
* ``<dynamic_text>`` labels are dropped - the workbench draws designator
  and value itself;
* coordinates are moved onto the content bounding box and scaled by
  :data:`SCALE` (0.5 mm per QET unit), which lands a typical QET contact
  (~42 units tall) at ~21 mm, the size the store's own symbols use.

Nothing here reaches the network or QET's installation: point it at a
folder of ``.elmt`` files - a checkout of the official
``qelectrotech/qelectrotech-elements`` repository works, as does the
``elements/`` directory of an installed QElectroTech.  Folder discovery
of *both* file kinds and the batched writing loop live in
:mod:`Schematics.Features.Utils.BatchImport`.
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.sax.saxutils import unescape

from Schematics.Features.Utils.SymbolCatalog import SymbolPin
from Schematics.Features.Utils.SymbolDrawing import renderSymbol

# QET element units -> store millimetres.  QET draws a contact roughly
# 42 units tall, so 0.5 mm/unit lands it at ~21 mm - the size of the
# store's own 20 mm symbols - while keeping imported symbols at their
# QET-relative proportions to each other.
SCALE = 0.5

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_WS = re.compile(r"\s+")
# Names straight out of the file text: scanning a full QET tree (~9k
# files) only needs the display name, and parsing every file with
# ElementTree just to list it took ~8 s where this takes ~2.
_NAME_RE = re.compile(r'<name\s+lang="([^"]*)"\s*>(.*?)</name>', re.DOTALL)
# <names> comes right after <uuid> in every .elmt, so a prefix read picks
# the names out without touching the rest of the file.
_NAME_PREFIX_BYTES = 8192
# QET font strings: "Liberation Sans,9,-1,5,50,0,0,0,0,0,Regular".
_FONT_SIZE_RE = re.compile(r"^[^,]*,(\d+(?:\.\d+)?)")
_POINTS_PER_MM = 25.4 / 72.0

# Dash patterns for the line-style values QET writes; anything unknown
# stays solid (the shape model has no dash field, so dashed primitives
# are emitted as backdrop <path>s and kept verbatim on save).
_DASHES: dict[str, str] = {
    "dashed": "1 .5",
    "dotted": ".3 .4",
    "dash-dotted": "1 .4 .15 .4",
    "dashdot": "1 .4 .15 .4",
}
_THIN_WEIGHTS = frozenset({"ultrathin", "extra thin", "thin"})
_HEAVY_WEIGHTS = frozenset({"strong", "very strong", "verystrong"})


class QETImportError(Exception):
    """A ``.elmt`` file could not be converted."""


@dataclass(frozen=True)
class QETElementInfo:
    """One discovered element, as shown in the import dialog."""

    path: str
    name: str
    category: str  # folder of the .elmt relative to the scan root
    stem: str      # sanitized store file stem


@dataclass(frozen=True)
class QETSymbol:
    """A converted element, ready to be written into the store."""

    stem: str
    name: str
    svg: str                       # complete file text, pins included
    pins: list[SymbolPin]
    notes: tuple[str, ...] = ()    # what was skipped during conversion


# ----------------------------------------------------------------------
# Primitives (parsed form)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _Style:
    color: str = "#000000"
    fill: str = "none"
    width: float = 0.5
    dash: str = ""


@dataclass(frozen=True)
class _Line:
    x1: float
    y1: float
    x2: float
    y2: float
    style: _Style


@dataclass(frozen=True)
class _Poly:
    points: tuple[tuple[float, float], ...]
    closed: bool
    style: _Style


@dataclass(frozen=True)
class _Rect:
    x: float
    y: float
    w: float
    h: float
    style: _Style


@dataclass(frozen=True)
class _Circle:
    cx: float
    cy: float
    r: float
    style: _Style


@dataclass(frozen=True)
class _Ellipse:
    cx: float
    cy: float
    rx: float
    ry: float
    style: _Style


@dataclass(frozen=True)
class _Arc:
    x: float
    y: float
    w: float
    h: float
    start: float
    angle: float
    style: _Style


@dataclass(frozen=True)
class _Text:
    x: float
    y: float
    text: str
    size: float
    color: str
    rotation: float


_Primitive = _Line | _Poly | _Rect | _Circle | _Ellipse | _Arc | _Text


@dataclass
class _Definition:
    names: dict[str, str]
    primitives: list[_Primitive]
    terminals: list[tuple[float, float]]
    dropped: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------
def findQETElements(root: str) -> list[str]:
    """Every ``.elmt`` file under *root*, sorted, recursively."""
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            if filename.lower().endswith(".elmt"):
                found.append(os.path.join(dirpath, filename))
    return sorted(found)


def symbolStem(name: str) -> str:
    """Sanitize an element name into a portable file stem."""
    text = _INVALID_CHARS.sub(" ", name)
    text = " ".join(_WS.split(text)).strip(" .")
    if len(text) > 80:
        text = text[:80].rstrip(" .")
    return text or "symbol"


def scanQETElements(root: str) -> list[QETElementInfo]:
    """Discover elements under *root* with the names the dialog shows.

    Names are read with a text regex rather than a full parse so a whole
    QET checkout lists in a couple of seconds; files the regex misses
    fall back to the real parser, and files that do not parse at all are
    left out here (conversion reports them if they are ever selected).
    """
    infos: list[QETElementInfo] = []
    for path in findQETElements(root):
        stem_path = os.path.splitext(os.path.basename(path))[0]
        names = _quickNames(path)
        if not names:
            try:
                names = _parseDefinition(path).names
            except QETImportError:
                continue
        name = _displayName(names, stem_path)
        infos.append(
            QETElementInfo(
                path=path,
                name=name,
                category=categoryOf(path, root),
                stem=symbolStem(name),
            )
        )
    infos.sort(key=lambda info: (info.category.lower(), info.name.lower()))
    return infos


def categoryOf(path: str, root: str) -> str:
    """Folder of *path* relative to *root*, '/'-separated ("" at root)."""
    folder = os.path.dirname(os.path.relpath(path, root))
    return "" if folder in (".", "") else folder.replace(os.sep, "/")


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------
def _floatAttr(attrs: dict[str, str], name: str, default: float = 0.0) -> float:
    try:
        return float(attrs.get(name, ""))
    except ValueError:
        return default


def _styleOf(attrs: dict[str, str]) -> _Style:
    color = "#000000"
    fill = "none"
    weight = "normal"
    line_style = "normal"
    for chunk in attrs.get("style", "").split(";"):
        key, sep, value = chunk.partition(":")
        if not sep:
            continue
        key = key.strip().lower()
        value = value.strip().lower()
        if key == "color" and value:
            color = value
        elif key == "filling" and value:
            fill = value
        elif key == "line-weight" and value:
            weight = value
        elif key == "line-style" and value:
            line_style = value
    if attrs.get("color"):  # <text color="#000000">
        color = attrs["color"]
    if weight in _THIN_WEIGHTS:
        width = 0.25
    elif weight in _HEAVY_WEIGHTS:
        width = 0.75
    else:
        width = 0.5
    return _Style(
        color=color, fill=fill, width=width, dash=_DASHES.get(line_style, "")
    )


def _pointsOf(attrs: dict[str, str]) -> tuple[tuple[float, float], ...]:
    """QET polygons list their vertices as x1,y1,x2,y2,..."""
    count = 0
    while "x%d" % (count + 1) in attrs:
        count += 1
    points: list[tuple[float, float]] = []
    for index in range(1, count + 1):
        try:
            points.append(
                (float(attrs["x%d" % index]), float(attrs["y%d" % index]))
            )
        except (KeyError, ValueError):
            break
    return tuple(points)


def _fontMm(spec: str) -> float:
    match = _FONT_SIZE_RE.match(spec)
    if match is None:
        return 3.0
    try:
        return float(match.group(1)) * _POINTS_PER_MM
    except ValueError:
        return 3.0


def _parseDefinition(path: str) -> _Definition:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        raise QETImportError("cannot parse XML: %s" % exc) from exc
    root = tree.getroot()
    if root.tag != "definition":
        raise QETImportError("not a QET element (root <%s>)" % root.tag)

    names: dict[str, str] = {}
    for node in root.findall("./names/name"):
        lang = node.get("lang", "")
        text = (node.text or "").strip()
        if lang and text and lang not in names:
            names[lang] = text

    description = root.find("description")
    if description is None:
        raise QETImportError("element has no <description>")

    defn = _Definition(names=names, primitives=[], terminals=[])
    for node in description:
        tag = node.tag
        attrs = node.attrib
        if tag == "line":
            defn.primitives.append(
                _Line(
                    _floatAttr(attrs, "x1"),
                    _floatAttr(attrs, "y1"),
                    _floatAttr(attrs, "x2"),
                    _floatAttr(attrs, "y2"),
                    _styleOf(attrs),
                )
            )
        elif tag == "polygon":
            points = _pointsOf(attrs)
            if len(points) >= 2:
                defn.primitives.append(
                    _Poly(
                        points,
                        attrs.get("closed", "false").lower() == "true",
                        _styleOf(attrs),
                    )
                )
        elif tag == "rect":
            defn.primitives.append(
                _Rect(
                    _floatAttr(attrs, "x"),
                    _floatAttr(attrs, "y"),
                    _floatAttr(attrs, "width"),
                    _floatAttr(attrs, "height"),
                    _styleOf(attrs),
                )
            )
        elif tag == "circle":
            defn.primitives.append(
                _Circle(
                    _floatAttr(attrs, "cx"),
                    _floatAttr(attrs, "cy"),
                    _floatAttr(attrs, "r"),
                    _styleOf(attrs),
                )
            )
        elif tag == "ellipse":
            defn.primitives.append(
                _Ellipse(
                    _floatAttr(attrs, "cx"),
                    _floatAttr(attrs, "cy"),
                    _floatAttr(attrs, "rx"),
                    _floatAttr(attrs, "ry"),
                    _styleOf(attrs),
                )
            )
        elif tag == "arc":
            defn.primitives.append(
                _Arc(
                    _floatAttr(attrs, "x"),
                    _floatAttr(attrs, "y"),
                    _floatAttr(attrs, "width"),
                    _floatAttr(attrs, "height"),
                    _floatAttr(attrs, "start"),
                    _floatAttr(attrs, "angle"),
                    _styleOf(attrs),
                )
            )
        elif tag == "text":
            text = attrs.get("text", "")
            if text:
                defn.primitives.append(
                    _Text(
                        _floatAttr(attrs, "x"),
                        _floatAttr(attrs, "y"),
                        text,
                        _fontMm(attrs.get("font", "")),
                        attrs.get("color", "#000000"),
                        _floatAttr(attrs, "rotation"),
                    )
                )
        elif tag == "terminal":
            defn.terminals.append(
                (_floatAttr(attrs, "x"), _floatAttr(attrs, "y"))
            )
        elif tag == "dynamic_text":
            # Designator/value labels: the workbench draws those itself.
            defn.dropped.append("dynamic_text")
        else:
            defn.dropped.append(tag)
    return defn


def _displayName(names: dict[str, str], fallback: str) -> str:
    if names.get("en"):
        return names["en"]
    for text in names.values():
        if text:
            return text
    return fallback


def _quickNames(path: str) -> dict[str, str]:
    """``<name lang=...>`` pairs read as text, in document order.

    Only a file whose names start unusually late costs the full read.
    """
    try:
        with open(path, "rb") as handle:
            names = _namesFromText(
                handle.read(_NAME_PREFIX_BYTES).decode("utf-8", "replace")
            )
        if names:
            return names
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return _namesFromText(handle.read())
    except OSError:
        return {}


def _namesFromText(data: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for lang, text in _NAME_RE.findall(data):
        text = unescape(text).strip()
        if lang and text and lang not in names:
            names[lang] = text
    return names


# ----------------------------------------------------------------------
# Conversion
# ----------------------------------------------------------------------
def _fmt(value: float) -> str:
    return "%g" % value


def _bounds(
    defn: _Definition,
) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for prim in defn.primitives:
        if isinstance(prim, _Line):
            xs += [prim.x1, prim.x2]
            ys += [prim.y1, prim.y2]
        elif isinstance(prim, _Poly):
            xs += [p[0] for p in prim.points]
            ys += [p[1] for p in prim.points]
        elif isinstance(prim, _Rect):
            xs += [prim.x, prim.x + prim.w]
            ys += [prim.y, prim.y + prim.h]
        elif isinstance(prim, _Circle):
            xs += [prim.cx - prim.r, prim.cx + prim.r]
            ys += [prim.cy - prim.r, prim.cy + prim.r]
        elif isinstance(prim, _Ellipse):
            xs += [prim.cx - prim.rx, prim.cx + prim.rx]
            ys += [prim.cy - prim.ry, prim.cy + prim.ry]
        elif isinstance(prim, _Arc):
            xs += [prim.x, prim.x + prim.w]
            ys += [prim.y, prim.y + prim.h]
        elif isinstance(prim, _Text):
            # Baseline anchor; estimate the ink so labels are not clipped.
            xs += [prim.x, prim.x + 0.6 * len(prim.text) * prim.size]
            ys += [prim.y - prim.size, prim.y + 0.3 * prim.size]
    xs += [p[0] for p in defn.terminals]
    ys += [p[1] for p in defn.terminals]
    if not xs or not ys:
        raise QETImportError("no drawable geometry")
    return min(xs), min(ys), max(xs), max(ys)


def _strokeAttrs(style: _Style) -> str:
    text = ' stroke="%s" stroke-width="%s"' % (style.color, _fmt(style.width))
    if style.dash:
        text += ' stroke-dasharray="%s"' % style.dash
    return text


def _arcPath(prim: _Arc, tx: float, ty: float) -> str:
    """QET arcs are Qt arcs: a bounding box, a start angle and a sweep.

    Qt measures degrees counter-clockwise from 3 o'clock with y down,
    which is SVG's sweep-flag 0 direction.
    """
    x = (prim.x + tx) * SCALE
    y = (prim.y + ty) * SCALE
    w = prim.w * SCALE
    h = prim.h * SCALE
    cx, cy = x + w / 2.0, y + h / 2.0
    rx, ry = abs(w / 2.0), abs(h / 2.0)

    def point(degrees: float) -> tuple[float, float]:
        radians = math.radians(degrees)
        return cx + rx * math.cos(radians), cy - ry * math.sin(radians)

    sx, sy = point(prim.start)
    ex, ey = point(prim.start + prim.angle)
    large = 1 if abs(prim.angle) > 180.0 else 0
    sweep = 0 if prim.angle > 0 else 1
    return "M %s %s A %s %s %d %d %s %s" % (
        _fmt(sx), _fmt(sy), _fmt(rx), _fmt(ry),
        large, sweep, _fmt(ex), _fmt(ey),
    )


def _emitPrimitive(prim: _Primitive, tx: float, ty: float) -> str:
    def m(x: float, y: float) -> tuple[float, float]:
        return (x + tx) * SCALE, (y + ty) * SCALE

    # Dashed artwork and arcs become backdrop <path>s: the shape model
    # has no dash field and no arc, so native shapes would lose them on
    # the next save.  RawElement keeps <path> byte-for-byte.
    if isinstance(prim, _Arc):
        return '<path d="%s" fill="none"%s/>' % (
            _arcPath(prim, tx, ty),
            _strokeAttrs(prim.style),
        )
    if isinstance(prim, _Text):
        x, y = m(prim.x, prim.y)
        escaped = (
            prim.text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        body = (
            '<text x="%s" y="%s" font-family="Arial" font-size="%s" '
            'fill="%s" text-anchor="start">%s</text>'
            % (_fmt(x), _fmt(y), _fmt(prim.size), prim.color, escaped)
        )
        if abs(prim.rotation) > 1e-9:
            # Wrapped in a group so the editor keeps it verbatim instead
            # of flattening the rotation away on save.
            return '<g transform="rotate(%s %s %s)">%s</g>' % (
                _fmt(prim.rotation), _fmt(x), _fmt(y), body,
            )
        return body

    style = prim.style
    if style.dash:
        if isinstance(prim, _Line):
            x1, y1 = m(prim.x1, prim.y1)
            x2, y2 = m(prim.x2, prim.y2)
            return '<path d="M %s %s L %s %s" fill="none"%s/>' % (
                _fmt(x1), _fmt(y1), _fmt(x2), _fmt(y2),
                _strokeAttrs(style),
            )
        if isinstance(prim, _Poly):
            head, *rest = prim.points
            x0, y0 = m(head[0], head[1])
            chunks = ["M %s %s" % (_fmt(x0), _fmt(y0))]
            for px, py in rest:
                xx, yy = m(px, py)
                chunks.append("L %s %s" % (_fmt(xx), _fmt(yy)))
            if prim.closed:
                chunks.append("Z")
            return '<path d="%s" fill="%s"%s/>' % (
                " ".join(chunks), style.fill, _strokeAttrs(style),
            )
        # fall through to the native shapes below

    if isinstance(prim, _Line):
        x1, y1 = m(prim.x1, prim.y1)
        x2, y2 = m(prim.x2, prim.y2)
        return '<line x1="%s" y1="%s" x2="%s" y2="%s"%s/>' % (
            _fmt(x1), _fmt(y1), _fmt(x2), _fmt(y2), _strokeAttrs(style),
        )
    if isinstance(prim, _Rect):
        x, y = m(prim.x, prim.y)
        return (
            '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"%s/>'
            % (
                _fmt(x), _fmt(y),
                _fmt(max(prim.w, 0.0) * SCALE), _fmt(max(prim.h, 0.0) * SCALE),
                style.fill, _strokeAttrs(style),
            )
        )
    if isinstance(prim, _Circle):
        cx, cy = m(prim.cx, prim.cy)
        return '<circle cx="%s" cy="%s" r="%s" fill="%s"%s/>' % (
            _fmt(cx), _fmt(cy), _fmt(max(prim.r, 0.0) * SCALE),
            style.fill, _strokeAttrs(style),
        )
    if isinstance(prim, _Ellipse):
        cx, cy = m(prim.cx, prim.cy)
        return (
            '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s"%s/>'
            % (
                _fmt(cx), _fmt(cy),
                _fmt(max(prim.rx, 0.0) * SCALE), _fmt(max(prim.ry, 0.0) * SCALE),
                style.fill, _strokeAttrs(style),
            )
        )
    # _Poly
    assert isinstance(prim, _Poly)
    points = list(prim.points)
    if prim.closed and points and points[0] != points[-1]:
        points.append(points[0])
    pairs = []
    for px, py in points:
        xx, yy = m(px, py)
        pairs.append("%s,%s" % (_fmt(xx), _fmt(yy)))
    return '<polyline points="%s" fill="%s"%s/>' % (
        " ".join(pairs), style.fill, _strokeAttrs(style),
    )


def convertQETFile(path: str) -> QETSymbol:
    """Convert one ``.elmt`` file into store SVG, pins and stem.

    Raises :class:`QETImportError` when the file is not a convertible
    QET element.
    """
    defn = _parseDefinition(path)
    fallback = os.path.splitext(os.path.basename(path))[0]
    name = _displayName(defn.names, fallback)
    x0, y0, _x1, _y1 = _bounds(defn)
    tx, ty = -x0, -y0
    width = (_x1 - x0) * SCALE
    height = (_y1 - y0) * SCALE

    pins = [
        SymbolPin("x%d" % (index + 1), (px + tx) * SCALE, (py + ty) * SCALE)
        for index, (px, py) in enumerate(defn.terminals)
    ]
    for pin in pins:
        if pin.x < 0 or pin.y < 0:
            raise QETImportError(
                "pin %s lands outside the symbol (%g, %g)"
                % (pin.name, pin.x, pin.y)
            )

    body = [_emitPrimitive(prim, tx, ty) for prim in defn.primitives]
    if not body:
        raise QETImportError("no drawable geometry")

    notes: list[str] = []
    if defn.dropped:
        counts: dict[str, int] = {}
        for tag in defn.dropped:
            counts[tag] = counts.get(tag, 0) + 1
        notes.append(
            "skipped %s"
            % ", ".join("%sx%d" % (tag, n) for tag, n in sorted(counts.items()))
        )
    if not pins:
        notes.append("no terminals (no pins)")

    svg = "".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>\n',
            '<svg width="%smm" height="%smm" version="1.1" '
            'viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg" '
            'xmlns:schematics="http://">\n' % (
                _fmt(width), _fmt(height), _fmt(width), _fmt(height),
            ),
            "".join(line + "\n" for line in body),
            "</svg>\n",
        ]
    )
    return QETSymbol(
        stem=symbolStem(name),
        name=name,
        # Pins and description applied in memory: the batch layer writes
        # this text once instead of writing and then rewriting it.
        svg=renderSymbol(svg, pins, description=name),
        pins=pins,
        notes=tuple(notes),
    )


# (Folder-level discovery and the batched write loop live in BatchImport.)
