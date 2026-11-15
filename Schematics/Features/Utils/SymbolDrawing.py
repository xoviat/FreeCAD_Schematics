# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolDrawing.py - parse/serialize model for the built-in symbol editor.
#
###############################################################################
"""Drawing data model for the symbol editor.

The store keeps symbols as SVG files.  This module splits a file into an
ordered list of *drawing elements*:

* :class:`Shape` - the primitives the built-in editor understands and can
  draw: line, rect, circle, ellipse, polyline, text.
* :class:`RawElement` - anything else (``<path>``, ``<g>`` groups, ...),
  kept verbatim and rendered by the canvas as a static backdrop.  Artwork
  from external editors (Inkscape etc.) stays untouched and byte-stable.

Only *top-level* shape tags are parsed: artwork nested in groups belongs
to the backdrop (the store's symbols keep their ``<g>`` wrappers).

Saving rebuilds the file: original root tag (metadata attributes
updated in place) + drawing elements + line-bound pin rects.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal

from Schematics.Features.Utils.SVGSymbolsCache import extractPins
from Schematics.Features.Utils.SymbolCatalog import SymbolPin

ShapeKind = Literal["line", "rect", "circle", "ellipse", "polyline", "text"]

_ROOT_TAG_RE = re.compile(r"<svg[^>]*>", re.IGNORECASE)
# Same line-bound pattern the loader uses (extractPins' regex cannot
# span newlines, so pin rects must live one per line).
_PIN_RECT_RE = re.compile(r'< *rect .*pin="[^"]*".*(?:/>|</rect>)')
# extractPins only understands this charset for pin names.
_PIN_NAME_RE = re.compile(r"^[A-Za-z0-9.]+$")
_TAG_RE = re.compile(r"<[^>]+>")
_ATTR_RE = re.compile(r"([\w:.-]+)\s*=\s*\"([^\"]*)\"")
_TEXT_OPEN_RE = re.compile(r"<text\b[^>]*>", re.IGNORECASE)
_TEXT_CLOSE_RE = re.compile(r"</text\s*>", re.IGNORECASE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# Pin rects stay line-bound (the loader's regex cannot span newlines).
_PIN_LINE = '<rect schematics:pin="%s" x="%s" y="%s"/>'

NEW_SYMBOL_SVG = (
    '<svg width="20mm" height="20mm" version="1.1" viewBox="0 0 20 20" '
    'xmlns="http://www.w3.org/2000/svg">\n'
    "</svg>\n"
)

_INVALID_NAME_CHARS = set('\\/:*?"<>|')


def _fmt(value: float) -> str:
    return "%g" % value


def _floatAttr(attrs: dict[str, str], name: str, default: float) -> float:
    try:
        return float(attrs.get(name, ""))
    except ValueError:
        return default


def _setRootAttr(tag: str, name: str, value: str) -> str:
    """Set (or add) an attribute on an <svg ...> tag string."""
    escaped = value.replace('"', "'")
    pattern = re.compile(re.escape(name) + r'="[^"]*"')
    if pattern.search(tag):
        return pattern.sub(lambda _m: '%s="%s"' % (name, escaped), tag)
    return tag[:-1] + ' %s="%s"' % (name, escaped) + ">"


@dataclass
class Shape:
    """One editable primitive in SVG user coordinates."""

    kind: ShapeKind
    # line: [x1, y1, x2, y2]; rect: [x, y, w, h];
    # circle: [cx, cy, r]; ellipse: [cx, cy, rx, ry]
    coords: list[float] = field(default_factory=list)
    # polyline vertices
    points: list[tuple[float, float]] = field(default_factory=list)
    # text: the string itself (color lives in stroke, serialized as fill)
    text: str = ""
    stroke: str = "#000000"
    fill: str = "none"
    stroke_width: float = 0.5
    font_size: float = 4.0


@dataclass(frozen=True)
class RawElement:
    """SVG the editor does not model - kept verbatim (backdrop)."""

    text: str


DrawingElement = Shape | RawElement


def parseDrawing(svg: str) -> list[DrawingElement]:
    """Split an SVG into ordered top-level drawing elements.

    Pin rects (``schematics:pin``) are skipped - they belong to the pins
    list, which is passed around separately.  Groups/paths and other
    unmodelled content become one :class:`RawElement` each.
    """
    root = _ROOT_TAG_RE.search(svg)
    if root is None or "</svg>" not in svg:
        raise ValueError("not a symbol file (no <svg>/</svg>)")
    end = svg.rfind("</svg>")
    content = svg[root.end():end]
    elements: list[DrawingElement] = []
    i = 0
    length = len(content)
    while i < length:
        comment = _COMMENT_RE.match(content, i)
        if comment is not None:
            elements.append(RawElement(comment.group(0)))
            i = comment.end()
            continue
        match = _TAG_RE.match(content, i)
        if match is None:
            break
        tag = match.group(0)
        low = tag.lower()
        if low.startswith("</"):
            i = match.end()      # stray closer: drop it
            continue
        self_closing = tag.endswith("/>")
        if not self_closing and low.startswith("<text"):
            close = _TEXT_CLOSE_RE.search(content, match.end())
            if close is not None:
                inner_text = content[match.end():close.start()]
                elements.append(_parseText(tag, inner_text))
                i = close.end()
                continue
        if self_closing and _isShapeTag(low) and "schematics:pin" not in tag:
            elements.append(_parseShapeTag(tag))
            i = match.end()
            continue
        if self_closing:
            elements.append(RawElement(tag))
            i = match.end()
            continue
        # Element with children (g, defs, non-self-closing shapes, ...):
        # swallow it whole as backdrop content.
        name_match = re.match(r"<\s*([A-Za-z][\w:.-]*)", tag)
        name = (name_match.group(1).lower() if name_match else "")
        stack = [name] if name else []
        start = i
        j = match.end()
        while stack and j < length:
            inner = _TAG_RE.match(content, j)
            if inner is None:
                break
            inner_tag = inner.group(0)
            if inner_tag.endswith("/>"):
                j = inner.end()
                continue
            if inner_tag.startswith("</"):
                close_name = re.match(r"</\s*([A-Za-z][\w:.-]*)", inner_tag)
                if close_name and stack and close_name.group(1).lower() == stack[-1]:
                    stack.pop()
                j = inner.end()
                continue
            open_name = re.match(r"<\s*([A-Za-z][\w:.-]*)", inner_tag)
            if open_name:
                stack.append(open_name.group(1).lower())
            j = inner.end()
        elements.append(RawElement(content[start:j]))
        i = j
    return elements


def _isShapeTag(low_tag: str) -> bool:
    return low_tag.startswith(
        ("<line", "<rect", "<circle", "<ellipse", "<polyline")
    )


def _parseShapeTag(tag: str) -> Shape:
    attrs = dict(_ATTR_RE.findall(tag))
    stroke = attrs.get("stroke", "#000000")
    width = _floatAttr(attrs, "stroke-width", 0.5)
    low = tag.lower()
    if low.startswith("<line"):
        return Shape(
            kind="line",
            coords=[
                _floatAttr(attrs, "x1", 0.0),
                _floatAttr(attrs, "y1", 0.0),
                _floatAttr(attrs, "x2", 0.0),
                _floatAttr(attrs, "y2", 0.0),
            ],
            stroke=stroke,
            stroke_width=width,
        )
    if low.startswith("<rect"):
        return Shape(
            kind="rect",
            coords=[
                _floatAttr(attrs, "x", 0.0),
                _floatAttr(attrs, "y", 0.0),
                _floatAttr(attrs, "width", 0.0),
                _floatAttr(attrs, "height", 0.0),
            ],
            stroke=stroke,
            fill=attrs.get("fill", "#ffffff"),
            stroke_width=width,
        )
    if low.startswith("<circle"):
        return Shape(
            kind="circle",
            coords=[
                _floatAttr(attrs, "cx", 0.0),
                _floatAttr(attrs, "cy", 0.0),
                _floatAttr(attrs, "r", 0.0),
            ],
            stroke=stroke,
            fill=attrs.get("fill", "#ffffff"),
            stroke_width=width,
        )
    if low.startswith("<ellipse"):
        return Shape(
            kind="ellipse",
            coords=[
                _floatAttr(attrs, "cx", 0.0),
                _floatAttr(attrs, "cy", 0.0),
                _floatAttr(attrs, "rx", 0.0),
                _floatAttr(attrs, "ry", 0.0),
            ],
            stroke=stroke,
            fill=attrs.get("fill", "#ffffff"),
            stroke_width=width,
        )
    # polyline
    points: list[tuple[float, float]] = []
    tokens = [t for t in re.split(r"[\s,]+", attrs.get("points", "").strip()) if t]
    for idx in range(0, len(tokens) - 1, 2):
        try:
            points.append((float(tokens[idx]), float(tokens[idx + 1])))
        except ValueError:
            continue
    return Shape(
        kind="polyline",
        points=points,
        stroke=stroke,
        fill="none",
        stroke_width=width,
    )


def _parseText(open_tag: str, inner: str) -> Shape:
    attrs = dict(_ATTR_RE.findall(open_tag))
    return Shape(
        kind="text",
        coords=[
            _floatAttr(attrs, "x", 0.0),
            _floatAttr(attrs, "y", 0.0),
        ],
        text=inner,
        # SVG text color is fill; the model keeps it in stroke so the
        # style panel's color button edits it uniformly.
        stroke=attrs.get("fill", "#000000"),
        fill="none",
        font_size=_floatAttr(attrs, "font-size", 4.0),
    )


def serializeShape(shape: Shape) -> str:
    """One single-line SVG element (multi-line would break the loader)."""
    if shape.kind == "line":
        x1, y1, x2, y2 = shape.coords
        return (
            '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
            'stroke-width="%s"/>'
            % (_fmt(x1), _fmt(y1), _fmt(x2), _fmt(y2),
               shape.stroke, _fmt(shape.stroke_width))
        )
    if shape.kind == "rect":
        x, y, w, h = shape.coords
        return (
            '<rect x="%s" y="%s" width="%s" height="%s" fill="%s" '
            'stroke="%s" stroke-width="%s"/>'
            % (_fmt(x), _fmt(y), _fmt(max(w, 0.0)), _fmt(max(h, 0.0)),
               shape.fill, shape.stroke, _fmt(shape.stroke_width))
        )
    if shape.kind == "circle":
        cx, cy, r = shape.coords
        return (
            '<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" '
            'stroke-width="%s"/>'
            % (_fmt(cx), _fmt(cy), _fmt(max(r, 0.0)),
               shape.fill, shape.stroke, _fmt(shape.stroke_width))
        )
    if shape.kind == "ellipse":
        cx, cy, rx, ry = shape.coords
        return (
            '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s" '
            'stroke="%s" stroke-width="%s"/>'
            % (_fmt(cx), _fmt(cy), _fmt(max(rx, 0.0)), _fmt(max(ry, 0.0)),
               shape.fill, shape.stroke, _fmt(shape.stroke_width))
        )
    if shape.kind == "polyline":
        pts = " ".join("%s,%s" % (_fmt(x), _fmt(y)) for x, y in shape.points)
        return (
            '<polyline points="%s" fill="none" stroke="%s" '
            'stroke-width="%s"/>'
            % (pts, shape.stroke, _fmt(shape.stroke_width))
        )
    # text: baseline point, centered on x
    escaped = (
        shape.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    x, y = shape.coords
    return (
        '<text x="%s" y="%s" font-family="Arial" font-size="%s" '
        'fill="%s" text-anchor="middle">%s</text>'
        % (_fmt(x), _fmt(y), _fmt(shape.font_size), shape.stroke, escaped)
    )


def serializeElements(elements: list[DrawingElement]) -> list[str]:
    return [
        e.text if isinstance(e, RawElement) else serializeShape(e)
        for e in elements
    ]


def viewBoxOf(svg: str) -> tuple[float, float, float, float]:
    """(x, y, w, h) of the root tag's viewBox (fallback: size attrs)."""
    root = _ROOT_TAG_RE.search(svg)
    if root is not None:
        m = re.search(
            r'viewBox\s*=\s*"([^"]*)"', root.group(0), re.IGNORECASE
        )
        if m is not None:
            parts = m.group(1).replace(",", " ").split()
            if len(parts) == 4:
                try:
                    return (
                        float(parts[0]), float(parts[1]),
                        float(parts[2]), float(parts[3]),
                    )
                except ValueError:
                    pass
        w = re.search(r'\bwidth\s*=\s*"([\d.]+)(mm)?"', root.group(0), re.I)
        h = re.search(r'\bheight\s*=\s*"([\d.]+)(mm)?"', root.group(0), re.I)
        if w is not None and h is not None:
            return (0.0, 0.0, float(w.group(1)), float(h.group(1)))
    return (0.0, 0.0, 20.0, 20.0)


def saveSymbolFile(
    path: str,
    elements: list[DrawingElement],
    pins: list[SymbolPin],
    description: str = "",
    ref: str = "",
) -> None:
    """Rewrite a symbol file completely: root tag (metadata updated in
    place, everything else byte-preserved) + drawing + line-bound pins."""
    with open(path, "r", encoding="utf-8") as handle:
        data = handle.read()
    root = _ROOT_TAG_RE.search(data)
    if root is None or "</svg>" not in data:
        raise ValueError("not a symbol file (no <svg>/</svg>): " + path)
    tag = root.group(0)
    tag = _setRootAttr(tag, "schematics:description", description)
    tag = _setRootAttr(tag, "schematics:ref", ref)
    lines = serializeElements(elements)
    lines.extend(
        _PIN_LINE % (pin.name, _fmt(pin.x), _fmt(pin.y)) for pin in pins
    )
    body = "\n".join(lines)
    out = data[:root.start()] + tag + "\n"
    if body:
        out += body + "\n"
    out += "</svg>\n"
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(out)


def createNewSymbol(root: str, group: str, name: str) -> str:
    """Create a blank 20x20 symbol file; returns its path.

    Raises ValueError for a bad name, FileExistsError if taken.
    """
    stem = name[:-4] if name.lower().endswith(".svg") else name
    stem = stem.strip()
    if not stem or any(c in stem for c in _INVALID_NAME_CHARS):
        raise ValueError("invalid symbol name: %r" % name)
    dest = os.path.join(root, group) if group else root
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, stem + ".svg")
    if os.path.exists(path):
        raise FileExistsError(path)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(NEW_SYMBOL_SVG)
    return path


def writeSymbol(
    path: str,
    pins: list[SymbolPin],
    description: str | None = None,
    ref: str | None = None,
) -> None:
    """Rewrite a symbol file: replace all pin rects and (optionally) the
    root-tag metadata, leaving the drawing content byte-identical."""
    with open(path, "r", encoding="utf-8") as handle:
        data = handle.read()
    if not _ROOT_TAG_RE.search(data) or "</svg>" not in data:
        raise ValueError("not a symbol file (no <svg>/</svg>): " + path)
    data = _PIN_RECT_RE.sub("", data)
    pin_xml = "".join(
        '<rect schematics:pin="%s" x="%s" y="%s"/>\n'
        % (pin.name, _fmt(pin.x), _fmt(pin.y))
        for pin in pins
    )
    idx = data.rfind("</svg>")
    head = data[:idx]
    if pin_xml and head and not head.endswith("\n"):
        head += "\n"
    data = head + pin_xml + data[idx:]
    if description is not None or ref is not None:
        match = _ROOT_TAG_RE.search(data)
        if match is not None:
            tag = match.group(0)
            new_tag = tag
            if description is not None:
                new_tag = _setRootAttr(new_tag, "schematics:description", description)
            if ref is not None:
                new_tag = _setRootAttr(new_tag, "schematics:ref", ref)
            data = data.replace(tag, new_tag, 1)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(data)


def readSymbol(path: str) -> tuple[str, str, list[SymbolPin]]:
    """Read (description, ref, pins) straight from a file (no cache)."""
    with open(path, "r", encoding="utf-8") as handle:
        data = handle.read()
    _stripped, raw = extractPins(data)
    pins = [SymbolPin(str(n), float(x), float(y)) for n, x, y in raw]
    root = _ROOT_TAG_RE.search(data)
    desc = ""
    ref = ""
    if root is not None:
        m = re.search(r'schematics:description="([^"]*)"', root.group(0))
        if m:
            desc = m.group(1)
        m = re.search(r'schematics:ref="([^"]*)"', root.group(0))
        if m:
            ref = m.group(1)
    return desc, ref, pins


def validatePins(pins: list[SymbolPin]) -> str | None:
    """Return an error message if the pins cannot be written, else None."""
    for pin in pins:
        if not _PIN_NAME_RE.match(pin.name):
            return (
                "Invalid pin name %r - allowed: letters, digits and dot "
                "(the loader's charset)" % pin.name
            )
        if pin.x < 0 or pin.y < 0:
            return "Pin %s has negative coordinates (%g, %g)" % (pin.name, pin.x, pin.y)
    return None
