# -*- coding: utf-8 -*-
###############################################################################
#
#  Connectivity.py - wire endpoints vs symbol pins.
#
###############################################################################
"""Connectivity model for a sheet.

Wires are polylines and symbols carry named pins; a connection exists
where a wire's *endpoints* sit within the snap tolerance of a pin - the
same tolerance the wire drawing uses when snapping, so anything the user
drew "connected" is connected here.

Positions are resolved through ``QGraphicsItem.mapToScene`` (ground
truth, rotation-safe), never through the legacy ``pinsXY`` bookkeeping.

This is the foundation for ERC-style checks, hover highlighting and
conductor numbering; it intentionally reports *geometry*, not electrical
types.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PySide6 import QtCore


@dataclass(frozen=True)
class Connection:
    """One wire endpoint sitting on one symbol pin."""

    symbol: str    # object Name of the symbol
    pin: str       # pin name from the SVG (schematics:pin)
    wire: str      # object Name of the wire


def _sheetScene(sheet: Any) -> Any:
    return getattr(getattr(sheet, "Proxy", None), "scene", None)


def connectionTolerance(sheet: Any) -> float:
    """Snap radius shared with the wire drawing tool."""
    scene = _sheetScene(sheet)
    if scene is not None and hasattr(scene, "wirePinTolerance"):
        try:
            return float(scene.wirePinTolerance())
        except (ReferenceError, RuntimeError, AttributeError, TypeError):
            pass
    return 3.0


def pinPositions(sheet: Any) -> dict[tuple[str, str], QtCore.QPointF]:
    """{(symbol object Name, pin name): scene position} for all pins."""
    result: dict[tuple[str, str], QtCore.QPointF] = {}
    scene = _sheetScene(sheet)
    if scene is None:
        return result
    for item in scene.items():
        if getattr(item, "drawMode", False):
            continue   # placement preview, not a placed symbol
        pins = getattr(item, "pins", None)
        obj = getattr(item, "obj", None)
        if not pins or obj is None:
            continue
        try:
            objName = str(obj.Name)
        except (ReferenceError, RuntimeError, AttributeError):
            continue
        for pin in pins:
            try:
                name, px, py = pin
                position = item.mapToScene(QtCore.QPointF(float(px), float(py)))
            except (ReferenceError, RuntimeError, TypeError, ValueError):
                continue
            result[(objName, str(name))] = position
    return result


def wireEndPoints(sheet: Any, wire: Any) -> list[QtCore.QPointF]:
    """Scene positions of a wire's first and last vertex."""
    try:
        item = wire.Proxy.item
        points = list(wire.Points)
    except (ReferenceError, RuntimeError, AttributeError):
        return []
    if len(points) < 2:
        return []
    ends: list[QtCore.QPointF] = []
    for vertex in (points[0], points[-1]):
        try:
            ends.append(item.mapToScene(QtCore.QPointF(vertex.x, vertex.y)))
        except (ReferenceError, RuntimeError, AttributeError):
            return []
    return ends


def _wires(sheet: Any) -> list[Any]:
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return []
    return [o for o in elements if getattr(o, "Type", "") == "Wire"]


def connections(sheet: Any) -> list[Connection]:
    """Every wire endpoint that lands on a symbol pin."""
    pins = pinPositions(sheet)
    if not pins:
        return []
    tol = connectionTolerance(sheet)
    result: list[Connection] = []
    for wire in _wires(sheet):
        try:
            wireName = str(wire.Name)
        except (ReferenceError, RuntimeError, AttributeError):
            continue
        for end in wireEndPoints(sheet, wire):
            for (symbol, pin), position in pins.items():
                if math.hypot(end.x() - position.x(), end.y() - position.y()) <= tol:
                    result.append(Connection(symbol=symbol, pin=pin, wire=wireName))
    return result


def unwiredPins(sheet: Any) -> list[tuple[str, str]]:
    """Pins with no wire endpoint on them, as (symbol, pin) pairs."""
    connected = {(c.symbol, c.pin) for c in connections(sheet)}
    return [key for key in sorted(pinPositions(sheet)) if key not in connected]


def danglingEnds(sheet: Any) -> list[tuple[str, int]]:
    """Wire endpoints resting on neither a pin nor another wire end.

    Returns (wire object Name, 0|1) - first or last vertex.
    """
    tol = connectionTolerance(sheet)
    pins = list(pinPositions(sheet).values())
    ends: list[tuple[str, int, QtCore.QPointF]] = []
    for wire in _wires(sheet):
        try:
            wireName = str(wire.Name)
        except (ReferenceError, RuntimeError, AttributeError):
            continue
        for index, position in enumerate(wireEndPoints(sheet, wire)):
            ends.append((wireName, index, position))

    dangling: list[tuple[str, int]] = []
    for wireName, index, position in ends:
        if any(
            math.hypot(position.x() - p.x(), position.y() - p.y()) <= tol
            for p in pins
        ):
            continue
        touchingOther = any(
            (otherWire, otherIndex) != (wireName, index)
            and math.hypot(position.x() - o.x(), position.y() - o.y()) <= tol
            for otherWire, otherIndex, o in ends
        )
        if not touchingOther:
            dangling.append((wireName, index))
    return dangling


def _symbolLabel(obj: Any) -> str:
    designator = getattr(obj, "Designator", "")
    if designator:
        return str(designator)
    return str(getattr(obj, "Type", getattr(obj, "Name", "?")))


def connectionReport(sheet: Any) -> str:
    """Human-readable check result (empty problems = success line)."""
    labels: dict[str, str] = {}
    try:
        elements = list(sheet.Elements)
    except (ReferenceError, RuntimeError, AttributeError):
        return "Sheet is not available.\n"
    for element in elements:
        try:
            labels[str(element.Name)] = _symbolLabel(element)
        except (ReferenceError, RuntimeError, AttributeError):
            continue

    lines: list[str] = []
    for symbol, pin in unwiredPins(sheet):
        lines.append("%s: pin %s is not connected" % (labels.get(symbol, symbol), pin))
    for wireName, index in danglingEnds(sheet):
        which = "first" if index == 0 else "last"
        lines.append("wire %s: %s end is floating" % (wireName, which))
    if not lines:
        return "All pins and wire ends are connected.\n"
    return "\n".join(lines) + "\n"
