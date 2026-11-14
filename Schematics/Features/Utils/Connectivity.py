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


def wireTag(wire: Any) -> str:
    """The wire's label ( means unlabelled)."""
    try:
        return str(getattr(wire, "Tag", "") or "")
    except (ReferenceError, RuntimeError, AttributeError):
        return ""


def labeledNets(sheet: Any) -> dict[str, list[str]]:
    """{label: [wire object Names]} for all labelled wires."""
    nets: dict[str, list[str]] = {}
    for wire in _wires(sheet):
        tag = wireTag(wire)
        if not tag:
            continue
        try:
            nets.setdefault(tag, []).append(str(wire.Name))
        except (ReferenceError, RuntimeError, AttributeError):
            continue
    return nets


def danglingEnds(sheet: Any) -> list[tuple[str, int]]:
    """Wire endpoints resting on neither a pin nor another wire end.

    Returns (wire object Name, 0|1) - first or last vertex.
    """
    tol = connectionTolerance(sheet)
    pins = list(pinPositions(sheet).values())
    # A labelled wire's ends terminate a net on purpose (KiCad labels):
    # only unlabelled ends can be "floating".
    labelled = {str(wire.Name) for wire in _wires(sheet) if wireTag(wire)}
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
        if wireName in labelled:
            continue
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


def wireByName(sheet: Any, name: str) -> Any | None:
    """The wire object with this Name, or None."""
    for wire in _wires(sheet):
        try:
            if str(wire.Name) == name:
                return wire
        except (ReferenceError, RuntimeError, AttributeError):
            continue
    return None


def _wirePolyline(sheet: Any, wire: Any) -> list[QtCore.QPointF]:
    """Scene positions of every wire vertex (>= 2 points)."""
    try:
        item = wire.Proxy.item
        points = list(wire.Points)
    except (ReferenceError, RuntimeError, AttributeError):
        return []
    if len(points) < 2:
        return []
    vertices: list[QtCore.QPointF] = []
    for vertex in points:
        try:
            vertices.append(
                item.mapToScene(QtCore.QPointF(vertex.x, vertex.y))
            )
        except (ReferenceError, RuntimeError, AttributeError):
            return []
    return vertices


def _pointSegmentDistance(
    point: QtCore.QPointF,
    start: QtCore.QPointF,
    end: QtCore.QPointF,
) -> float:
    """Distance from point to the segment start-end (0 when on it)."""
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    seg_sq = dx * dx + dy * dy
    if seg_sq <= 0.0:
        return math.hypot(point.x() - start.x(), point.y() - start.y())
    t = ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / seg_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(point.x() - (start.x() + t * dx), point.y() - (start.y() + t * dy))


def netClosure(sheet: Any, seed: str) -> set[str]:
    """All wires joined to the seed wire.

    Joins: identical label (KiCad net labels), endpoint-to-endpoint
    contact within tolerance, or an endpoint landing on another wire's
    body (T junction - the drawing tools snap, so users draw these
    naturally). Fixed-point expansion, bounded by the wire count.
    """
    tol = connectionTolerance(sheet)
    names: list[str] = []
    tags: dict[str, str] = {}
    lines: dict[str, list[QtCore.QPointF]] = {}
    for wire in _wires(sheet):
        try:
            name = str(wire.Name)
        except (ReferenceError, RuntimeError, AttributeError):
            continue
        names.append(name)
        tags[name] = wireTag(wire)
        lines[name] = _wirePolyline(sheet, wire)
    if seed not in lines:
        return {seed} if seed else set()

    members: set[str] = {seed}
    changed = True
    while changed:
        changed = False
        member_labels = {tags[m] for m in members if tags.get(m)}
        member_ends = [
            (m, lines[m][i]) for m in members if lines[m] for i in (0, -1)
        ]
        member_segments = [
            (lines[m][i], lines[m][i + 1])
            for m in members
            if lines[m]
            for i in range(len(lines[m]) - 1)
        ]
        for name in names:
            if name in members or not lines[name]:
                continue
            joined = bool(tags.get(name) and tags[name] in member_labels)
            if not joined:
                ends = (lines[name][0], lines[name][-1])
                joined = any(
                    math.hypot(e.x() - m.x(), e.y() - m.y()) <= tol
                    for e in ends
                    for _mn, m in member_ends
                )
            if not joined:
                our_segments = [
                    (lines[name][i], lines[name][i + 1])
                    for i in range(len(lines[name]) - 1)
                ]
                joined = any(
                    _pointSegmentDistance(e, a, b) <= tol
                    for e in (lines[name][0], lines[name][-1])
                    for a, b in member_segments
                ) or any(
                    _pointSegmentDistance(m, a, b) <= tol
                    for _mn, m in member_ends
                    for a, b in our_segments
                )
            if joined:
                members.add(name)
                changed = True
    return members


def junctionPoints(sheet: Any, wire: Any) -> list[QtCore.QPointF]:
    """Own endpoints that land on ANOTHER wire (body or end) - where the
    drawing convention puts a junction dot. Pin terminals are excluded:
    those ends are symbol contacts, not wire crossings."""
    tol = connectionTolerance(sheet)
    own = _wirePolyline(sheet, wire)
    if len(own) < 2:
        return []
    try:
        own_name = str(wire.Name)
    except (ReferenceError, RuntimeError, AttributeError):
        return []
    others: list[list[QtCore.QPointF]] = []
    for other in _wires(sheet):
        try:
            if str(other.Name) == own_name:
                continue
        except (ReferenceError, RuntimeError, AttributeError):
            continue
        line = _wirePolyline(sheet, other)
        if line:
            others.append(line)
    if not others:
        return []
    dots: list[QtCore.QPointF] = []
    for end in (own[0], own[-1]):
        for line in others:
            hit = any(
                _pointSegmentDistance(end, line[i], line[i + 1]) <= tol
                for i in range(len(line) - 1)
            )
            if hit:
                dots.append(end)
                break
    return dots


def onWireBody(sheet: Any, pos: QtCore.QPointF, tol: float | None = None) -> bool:
    """True when pos lies on any wire - endpoints and body alike (the
    places where a drawn wire should terminate, KiCad-style)."""
    if tol is None:
        tol = connectionTolerance(sheet)
    for wire in _wires(sheet):
        line = _wirePolyline(sheet, wire)
        for i in range(len(line) - 1):
            if _pointSegmentDistance(pos, line[i], line[i + 1]) <= tol:
                return True
    return False


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
        lines.append("All pins and wire ends are connected.")
    nets = labeledNets(sheet)
    for label in sorted(nets):
        lines.append("net %s: %s" % (label, ", ".join(sorted(nets[label]))))
    return "\n".join(lines) + "\n"
