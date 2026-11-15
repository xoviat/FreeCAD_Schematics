# Run with (install the workbench first — python install.py):
#   FreeCAD.exe verify_freecad.py
# End-to-end verification of the Schematics workbench under FreeCAD 1.1.4 / PySide6
import os
import sys
import traceback
import __main__

# Paths derived from this script's location so no machine-specific user path
# is baked into the file.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # executed without __file__ (e.g. via exec)
    _HERE = os.getcwd()
LOG = os.path.join(_HERE, "_fc_verify.log")
DOC = os.path.join(_HERE, "_fc_verify.FCStd")
lines: list[str] = []
def log(s):
    lines.append(str(s))
    print("[verify]", s, flush=True)
def step(name, fn):
    try:
        fn()
        log("PASS " + name)
    except Exception:
        log("FAIL " + name)
        log(traceback.format_exc())

import FreeCAD
import FreeCADGui as Gui

def t_activate_wb():
    assert Gui.activateWorkbench("SchematicsWorkbench"), "activateWorkbench returned False"
step("activate SchematicsWorkbench", t_activate_wb)

def t_new_scheme():
    Gui.runCommand("SCNewScheme")
    assert FreeCAD.ActiveDocument is not None
    assert any(o.TypeId == "App::FeaturePython" and hasattr(o, "Elements")
               for o in FreeCAD.ActiveDocument.Objects), "no scheme object created"
step("SCNewScheme command", t_new_scheme)

sheet = None
def t_find_sheet():
    global sheet
    sheet = [o for o in FreeCAD.ActiveDocument.Objects if hasattr(o, "Elements")][0]
step("find sheet object", t_find_sheet)

def t_api_object():
    # README example: Schematics.* in the console
    assert "Schematics" in dir(__builtins__) or "Schematics" in globals() or True
    import __main__
    assert hasattr(__main__, "Schematics"), "Schematics API not exposed in __main__"
    api = __main__.Schematics
    rect = api.Rectangle(70, 50, sheet)
    assert rect is not None
    assert abs(float(rect.X.Value) - 70) < 1e-6, rect.X.Value
step("Schematics.Rectangle() API (console exposure)", t_api_object)

def t_line_item():
    line = __main__.Schematics.Line(10, 10, sheet)
    line.Width = 40
    line.Height = 20
step("Schematics.Line() API", t_line_item)

def t_wire_item():
    wire = __main__.Schematics.Wire([(5, 5), (45, 5), (45, 35)], sheet)
    assert wire is not None
    assert len(wire.Points) == 3, "wire has %d points" % len(wire.Points)
    assert abs(float(wire.X.Value) - 5) < 1e-6, wire.X.Value
    assert wire.WireType == "Power", wire.WireType
    assert wire.Proxy.item is not None, "wire item not added to scene"
step("Schematics.Wire() first-class object", t_wire_item)

def t_cmd_items():
    # Symbol command path: creates under-cursor symbol then commits on click;
    # exercise the PrimitiveCommand + SVG renderer via scene directly.
    from Schematics.Features.Items.Symbol import Symbol
    Symbol.typ = "Resistor"
    Symbol.grp = "Resistors"
    Symbol.std = "GOST"
    sym = Symbol(120, 90, sheet)
    assert sym is not None and sym.Width.Value > 0, "symbol has no size"
step("Symbol item (GOST resistor svg)", t_cmd_items)

def t_text_item():
    from Schematics.Features.Items.Text import Text
    t = Text(30, 120, sheet)
    t.Text = "<html><body>hello</body></html>"
step("Text item", t_text_item)

def t_symbol_chooser():
    from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog
    from Schematics.Features.Dialogs.SymbolChooser import SymbolChooser, note_recent
    cat = SymbolCatalog()
    entries = cat.all()
    assert len(entries) >= 5, "catalog found %d symbols" % len(entries)
    assert "Resistors" in cat.groups(), cat.groups()
    withpins = [e for e in entries if len(cat.pins(e)) >= 2]
    assert withpins, "no symbol exposes >= 2 pins"
    note_recent(withpins[0].key)
    dlg = SymbolChooser(catalog=cat)
    assert dlg.tree.topLevelItemCount() >= 2, dlg.tree.topLevelItemCount()
    # search filter must not hide everything
    dlg.search.setText("res")
    visible = sum(
        1 for i in range(dlg.tree.topLevelItemCount())
        for j in range(-1, dlg.tree.topLevelItem(i).childCount())
        if not (
            dlg.tree.topLevelItem(i).isHidden() if j < 0
            else dlg.tree.topLevelItem(i).child(j).isHidden()
        )
    )
    assert visible >= 1, "search filter hid everything"
    assert isinstance(cat.meta(withpins[0]).description, str)
    # No deleteLater()/processEvents() here: a pending deferred delete
    # races this script's hard os._exit(0) and trips a GILState fatal
    # (exit 127). The dialog is destroyed by refcount on return instead;
    # the real command path uses a plain local + exec() and never defers.
    dlg.close()
step("symbol catalog + chooser dialog", t_symbol_chooser)

def t_transforms():
    from Schematics.Features.Functions.Transforms import hFlip, vFlip, turnLeft, turnRight
    s = [o for o in FreeCAD.ActiveDocument.Objects if getattr(o, "Type", "") == "Resistor"][0]
    before = float(s.Rotation.Value)
    turnLeft(s)
    turnRight(s)
    assert float(s.Rotation.Value) == before, (before, s.Rotation.Value)
    # Mirrors must not raise: setAnchor(True) used to be a TypeError, and a
    # Python error escaping into Qt is exactly how the delete-key AV happened
    hFlip(s)
    vFlip(s)
    hFlip(s)
    vFlip(s)   # double flip restores the original transform
    FreeCAD.ActiveDocument.recompute()
step("transform commands (KiCad R/Shift+R/X/Y)", t_transforms)

def t_designators():
    from Schematics.Features.Items.Symbol import Symbol
    from Schematics.Features.Utils.Annotate import (
        GROUP_PREFIXES,
        annotateSheet,
        nextDesignator,
        refPrefix,
    )
    syms = [o for o in FreeCAD.ActiveDocument.Objects
            if getattr(o, "Type", "") == "Resistor"]
    assert syms, "no resistor placed"
    first = syms[0]
    # Placement shows the KiCad-style placeholder: prefix from
    # schematics:ref (Resistor.svg has "R"), else the group table
    assert first.Designator == "R?", first.Designator
    assert first.Value == "Resistor", first.Value
    assert refPrefix(first) == "R", refPrefix(first)
    assert GROUP_PREFIXES.get("Resistors") == "R", GROUP_PREFIXES
    # store group is spelled Relays - the folder used to be "Realys"
    assert GROUP_PREFIXES.get("Relays") == "K", GROUP_PREFIXES
    assert "Realys" not in GROUP_PREFIXES, GROUP_PREFIXES
    from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog
    groups = SymbolCatalog().groups()
    assert "Relays" in groups, groups
    assert "Realys" not in groups, groups
    relay = SymbolCatalog().find("Coil", "Relays", "GOST")
    assert relay is not None, "relay symbols not found under Relays"

    Symbol.typ = "Resistor"
    Symbol.grp = "Resistors"
    Symbol.std = "GOST"
    second = Symbol(160, 90, sheet)
    assert second.Designator == "R?", second.Designator

    # Annotate assigns numbers; placeholders consume none (R1, R2 in order)
    assigned, skipped = annotateSheet(sheet)
    assert assigned == 2, (assigned, skipped)
    assert first.Designator == "R1", first.Designator
    assert second.Designator == "R2", second.Designator

    # a cleared designator refills without collisions
    first.Designator = ""
    assigned, _skipped = annotateSheet(sheet)
    assert assigned == 1, assigned
    assert first.Designator == "R1", first.Designator
    assert nextDesignator("R", {"R1", "R2"}) == "R3"

    # a placeholder's own prefix wins over library metadata ("K?" -> K1)
    first.Designator = "K?"
    annotateSheet(sheet)
    assert first.Designator == "K1", first.Designator
    first.Designator = "R1"   # restore the state later steps expect
    FreeCAD.ActiveDocument.recompute()
step("designators + annotation (KiCad-style)", t_designators)

def t_component_list():
    import csv
    import os
    import tempfile
    from Schematics.Features.Dialogs.ComponentList import ComponentListDialog
    from Schematics.Features.Utils.Reports import (
        componentListText,
        componentRows,
        writeCsv,
    )

    rows = componentRows(sheet)
    desigs = [r.designator for r in rows]
    assert "R1" in desigs and "R2" in desigs, desigs
    # natural ordering: R1 before R2 (and R2 before R10 if it existed)
    assert desigs.index("R1") < desigs.index("R2"), desigs
    r1 = next(r for r in rows if r.designator == "R1")
    assert r1.value == "Resistor", r1.value
    assert r1.symbol.endswith("/Resistor"), r1.symbol

    text = componentListText(rows)
    assert "Designator" in text and "R1" in text and "R2" in text

    tmp = tempfile.mkdtemp(prefix="sc_report_")
    try:
        path = os.path.join(tmp, "components.csv")
        writeCsv(path, rows)
        with open(path, "r", encoding="utf-8", newline="") as fh:
            parsed = list(csv.reader(fh))
        assert parsed[0][0] == "Designator", parsed[0]
        assert any(line[0] == "R1" for line in parsed[1:]), parsed
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    dialog = ComponentListDialog(rows)
    assert dialog.table.rowCount() == len(rows)
    dialog.close()   # no deleteLater: races the hard os._exit() at the end
step("component list (rows, text, csv, dialog)", t_component_list)

def t_print_pdf():
    import os
    import shutil
    import tempfile
    from Schematics.Features.Utils.Printing import (
        exportPdf,
        pageSizeFor,
        pageOrientationFor,
        sheetSizeMm,
    )

    width, height = sheetSizeMm(sheet)
    assert width > 0 and height > 0, (width, height)
    # the default template is A4 landscape: 420x297
    assert pageSizeFor(width, height).id() != \
        __import__("PySide6").QtGui.QPageSize.PageSizeId.A4 or width > height
    orientation = pageOrientationFor(width, height)
    assert orientation in (
        __import__("PySide6").QtGui.QPageLayout.Orientation.Landscape,
        __import__("PySide6").QtGui.QPageLayout.Orientation.Portrait,
    ), orientation

    tmp = tempfile.mkdtemp(prefix="sc_pdf_")
    try:
        path = os.path.join(tmp, "sheet.pdf")
        exportPdf(sheet, path)
        assert os.path.exists(path), "PDF not written"
        with open(path, "rb") as fh:
            header = fh.read(5)
        assert header == b"%PDF-", header
        assert os.path.getsize(path) > 1000, os.path.getsize(path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
step("PDF export (QPdfWriter)", t_print_pdf)

def t_connectivity():
    from Schematics.Features.Dialogs.ConnectionCheck import ConnectionCheckDialog
    from Schematics.Features.Utils.Connectivity import (
        connections,
        connectionReport,
        danglingEnds,
        pinPositions,
        unwiredPins,
    )

    pins = pinPositions(sheet)
    # two resistors, two pins each
    assert len(pins) >= 4, pins
    # the pre-existing test wire floats in space: everything unwired
    assert len(unwiredPins(sheet)) >= 4, unwiredPins(sheet)
    assert len(danglingEnds(sheet)) >= 1, danglingEnds(sheet)

    # wire R1's two pins together: both ends connect, pins become wired
    r1 = [o for o in FreeCAD.ActiveDocument.Objects
          if getattr(o, "Designator", "") == "R1"][0]
    r1pins = [pos for (name, _pin), pos in pins.items() if name == r1.Name]
    assert len(r1pins) == 2, r1pins
    __main__.Schematics.Wire(
        [(r1pins[0].x(), r1pins[0].y()), (r1pins[1].x(), r1pins[1].y())], sheet
    )
    conns = connections(sheet)
    assert len(conns) >= 2, conns
    assert all(c.symbol == r1.Name for c in conns), conns
    remaining = unwiredPins(sheet)
    assert len(remaining) == len(pins) - 2, (len(pins), remaining)
    # R1's own ends are on pins now; only the old wire still floats
    assert len(danglingEnds(sheet)) >= 1

    report = connectionReport(sheet)
    assert "not connected" in report and "floating" in report, report
    dialog = ConnectionCheckDialog(report)
    dialog.close()   # no deleteLater: races the hard os._exit()
step("connectivity model + connection check", t_connectivity)

def t_wire_labels():
    from Schematics.Features.Utils.Connectivity import (
        connectionReport,
        danglingEnds,
        labeledNets,
        unwiredPins,
    )

    wires = [o for o in FreeCAD.ActiveDocument.Objects
             if getattr(o, "Type", "") == "Wire"]
    assert len(wires) == 2, len(wires)
    unlabelled = wires[0]   # the original floating test wire
    tagged = wires[1]

    # label grows the item's bounding rect (room for the text)
    plainHeight = tagged.Proxy.item.boundingRect().height()
    tagged.Tag = "X1"
    taggedHeight = tagged.Proxy.item.boundingRect().height()
    assert taggedHeight > plainHeight, (plainHeight, taggedHeight)
    assert labeledNets(sheet) == {"X1": [tagged.Name]}, labeledNets(sheet)

    # a labelled wire's ends terminate a net on purpose: not floating
    unlabelled.Tag = "X1"
    assert danglingEnds(sheet) == [], danglingEnds(sheet)

    report = connectionReport(sheet)
    assert "net X1" in report, report
    # geometry unchanged: R2's pins are still unwired
    remaining = unwiredPins(sheet)
    assert len(remaining) == 2, remaining

    unlabelled.Tag = ""   # back to the connectivity-step state
    assert danglingEnds(sheet) != []
step("wire labels (Tag) + labelled nets", t_wire_labels)

def t_net_hover():
    from Schematics.Features.Utils.Connectivity import (
        netClosure,
        wireByName,
    )

    wires = [o for o in FreeCAD.ActiveDocument.Objects
             if getattr(o, "Type", "") == "Wire"]
    assert len(wires) == 2, len(wires)
    first, second = wires

    # T junction: the new wire's start lands on the first wire's body
    # (segment (45,5)-(45,35))
    third = __main__.Schematics.Wire([(45, 20), (60, 20)], sheet)
    closure = netClosure(sheet, first.Name)
    assert third.Name in closure, (closure, third.Name)
    assert second.Name not in closure, closure

    # labels join wires regardless of geometry
    first.Tag = "N1"
    second.Tag = "N1"
    closure = netClosure(sheet, first.Name)
    assert second.Name in closure and third.Name in closure, closure

    # highlight flags propagate to every member and clear together
    item0 = first.Proxy.item
    item0._setNetHighlight(True)
    assert item0._netHighlight is True
    for name in netClosure(sheet, first.Name):
        member = wireByName(sheet, name)
        assert member is not None
        assert member.Proxy.item._netHighlight is True, name
    item0._setNetHighlight(False)
    for name in netClosure(sheet, first.Name):
        member = wireByName(sheet, name)
        assert member.Proxy.item._netHighlight is False, name

    first.Tag = ""
    second.Tag = ""
step("net closure + hover highlight", t_net_hover)

def t_multi_page():
    from Schematics.Features.Dialogs.SheetIndex import SheetIndexDialog
    from Schematics.Features.Utils.Sheets import (
        pageIndex,
        schemeObjects,
        sheetIndexRows,
    )

    # one sheet so far: page 1 of 1
    page, total = pageIndex(sheet)
    assert (page, total) == (1, 1), (page, total)

    # a second sheet makes the numbering real
    Gui.runCommand("SCNewScheme")
    schemes = schemeObjects()
    assert len(schemes) == 2, len(schemes)
    first_page, first_total = pageIndex(schemes[0])
    second_page, second_total = pageIndex(schemes[1])
    assert (first_page, first_total) == (1, 2), (first_page, first_total)
    assert (second_page, second_total) == (2, 2), (second_page, second_total)

    rows = sheetIndexRows()
    assert len(rows) == 2, rows
    assert rows[0].symbols == 2, rows[0]     # R1, R2 on page 1
    assert rows[0].wires == 3, rows[0]       # original + R1 link + T junction
    assert rows[1].symbols == 0 and rows[1].wires == 0, rows[1]

    dialog = SheetIndexDialog(rows)
    assert dialog.table.rowCount() == 2
    dialog.close()   # no deleteLater: races the hard os._exit()
step("page numbers + sheet index", t_multi_page)

def t_wire_visuals():
    from Schematics.Features.Items.Wire import DASHED_WIRE_TYPES
    from Schematics.Features.Utils.Connectivity import junctionPoints

    assert DASHED_WIRE_TYPES == ("Control", "Signal"), DASHED_WIRE_TYPES

    wires = [o for o in FreeCAD.ActiveDocument.Objects
             if getattr(o, "Type", "") == "Wire"]
    assert len(wires) == 3, len(wires)
    first, second, third = wires

    # the T junction: the third wire's start sits on the first wire's
    # body, so the third wire gets a junction dot there - and only it
    # (the first wire's own ends touch nothing)
    dots_third = junctionPoints(sheet, third)
    assert len(dots_third) == 1, dots_third
    assert abs(dots_third[0].x() - 45.0) < 0.01 and abs(dots_third[0].y() - 20.0) < 0.01, dots_third
    assert junctionPoints(sheet, first) == [], junctionPoints(sheet, first)
    # second wire's ends are on pins (terminals, not wire crossings)
    assert junctionPoints(sheet, second) == [], junctionPoints(sheet, second)

    # conductor class roundtrip
    first.WireType = "Control"
    assert first.WireType == "Control", first.WireType
    first.WireType = "Power"
    FreeCAD.ActiveDocument.recompute()
step("junction dots + conductor classes", t_wire_visuals)

def t_wire_draw_ux():
    from PySide6 import QtCore
    from Schematics.Features.Utils.Snap import constrainAngle

    # KiCad posture: nearest of horizontal / vertical / 45 degrees
    origin = QtCore.QPointF(0, 0)
    assert constrainAngle(origin, QtCore.QPointF(10, 3)) == QtCore.QPointF(10, 0)
    assert constrainAngle(origin, QtCore.QPointF(3, 10)) == QtCore.QPointF(0, 10)
    assert constrainAngle(origin, QtCore.QPointF(8, 8)) == QtCore.QPointF(8, 8)
    assert constrainAngle(origin, QtCore.QPointF(-6, 2)) == QtCore.QPointF(-6, 0)

    scene = sheet.Proxy.scene
    # resolver: a pin wins over posture; posture otherwise (then grid)
    from Schematics.Features.Utils.Connectivity import pinPositions
    pins = pinPositions(sheet)
    some_pin = next(iter(pins.values()))
    resolved = scene._resolveWirePoint(
        QtCore.QPointF(some_pin.x() + 0.4, some_pin.y() + 0.4),
        QtCore.QPointF(0, 0),
    )
    assert resolved == some_pin, (resolved, some_pin)
    posted = scene._resolveWirePoint(QtCore.QPointF(50, 52), QtCore.QPointF(50, 40))
    assert posted.x() == 50.0, posted   # vertical posture survives grid snap

    # finish keeps the tool armed; cancel exits (KiCad's flow)
    before = len([o for o in FreeCAD.ActiveDocument.Objects
                  if getattr(o, "Type", "") == "Wire"])
    scene.startWireDraw()
    assert scene.drawingWire is True
    scene.wirePoints = [QtCore.QPointF(0, 0), QtCore.QPointF(10, 0)]
    scene.finishWireDraw()
    assert scene.drawingWire is True, "finish must keep the wire tool armed"
    assert scene.wirePoints == [], scene.wirePoints
    after = len([o for o in FreeCAD.ActiveDocument.Objects
                 if getattr(o, "Type", "") == "Wire"])
    assert after == before + 1, (before, after)
    scene.cancelWireDraw()
    assert scene.drawingWire is False
step("wire drawing UX (posture + finish-on-connection)", t_wire_draw_ux)

def t_sheet_size():
    from Schematics.Features.Utils.Sheets import (
        PAPER_SIZES,
        paperSizeMm,
    )

    v = sheet.ViewObject
    # pure helper: portrait dims, orientation swap, template sentinel
    assert paperSizeMm("A4", "Portrait") == (210.0, 297.0)
    assert paperSizeMm("A4", "Landscape") == (297.0, 210.0)
    assert paperSizeMm("Letter", "Portrait") == (215.9, 279.4)
    assert paperSizeMm("From template") is None
    assert PAPER_SIZES[0] == "From template" and "A1" in PAPER_SIZES

    # the sheet starts template-owned (Default.svg is 420x297 landscape)
    assert str(v.PaperSize) == "From template", v.PaperSize
    assert abs(float(v.Width.Value) - 420.0) < 0.01, v.Width
    assert abs(float(v.Height.Value) - 297.0) < 0.01, v.Height

    # CAD-style dropdown: standard size + orientation
    v.PaperSize = "A4"   # sheet orientation is Landscape here
    assert abs(float(v.Width.Value) - 297.0) < 0.01, v.Width
    assert abs(float(v.Height.Value) - 210.0) < 0.01, v.Height
    v.Orientation = "Portrait"
    assert abs(float(v.Width.Value) - 210.0) < 0.01, v.Width
    assert abs(float(v.Height.Value) - 297.0) < 0.01, v.Height
    v.PaperSize = "Letter"
    assert abs(float(v.Width.Value) - 215.9) < 0.01, v.Width
    assert abs(float(v.Height.Value) - 279.4) < 0.01, v.Height

    # back to template-owned dimensions (aspect restores orientation)
    v.PaperSize = "From template"
    assert abs(float(v.Width.Value) - 420.0) < 0.01, v.Width
    assert abs(float(v.Height.Value) - 297.0) < 0.01, v.Height
    assert str(v.Orientation) == "Landscape", v.Orientation
    FreeCAD.ActiveDocument.recompute()
step("paper size property (A4/Letter/template)", t_sheet_size)

def t_title_block():
    from PySide6 import QtCore, QtGui

    from Schematics.Features.Utils.TitleBlock import (
        titleBlockSvgPath,
        titleBlockTexts,
    )

    v = sheet.ViewObject
    # the cartouche is a real tree element, inserted by default
    tbs = [o for o in sheet.Elements if getattr(o, "Type", "") == "TitleBlock"]
    assert len(tbs) == 1, "default title block element missing"
    assert tbs[0].Proxy.item is not None
    # defaults match the cartouche SVG's natural size
    assert abs(float(v.TitleBlockWidth.Value) - 185.0) < 0.01, v.TitleBlockWidth
    assert abs(float(v.TitleBlockHeight.Value) - 55.0) < 0.01, v.TitleBlockHeight

    # labels resolve through Qt translate(): English is the default,
    # but a Russian-configured FreeCAD may have the .qm active already
    texts = titleBlockTexts()
    assert texts["sheet"] in ("Sheet", "Лист"), texts
    assert "sheets" not in texts, "page box uses one phrase now"
    assert len(texts) == 16, len(texts)
    # the boxed page phrase is a translated format string
    fmt = QtCore.QCoreApplication.translate("Schematics", "Page %1 of %2")
    assert fmt.replace("%1", "1").replace("%2", "1") == "Page 1 of 1", fmt

    # the cartouche is overlaid at a fixed physical size...
    rect0 = sheet.Proxy.titleBlockRect()
    assert rect0 is not None, "title block not drawn"
    w0, h0 = rect0.width(), rect0.height()
    assert abs(w0 - 185.0) < 0.5 and abs(h0 - 55.0) < 0.5, (w0, h0)
    # ...anchored inside the frame at the page's bottom-right
    assert rect0.right() <= float(v.Width.Value) + 0.5
    assert rect0.bottom() <= float(v.Height.Value) + 0.5
    assert rect0.left() > 0 and rect0.top() > 0

    # same size on a different page (A4 landscape: 297x210)
    v.PaperSize = "A4"
    rect1 = sheet.Proxy.titleBlockRect()
    assert rect1 is not None
    assert abs(rect1.width() - w0) < 0.01 and abs(rect1.height() - h0) < 0.01, \
        (rect1.width(), rect1.height())

    # configurable from the View tab
    v.TitleBlockWidth = "150 mm"
    rect2 = sheet.Proxy.titleBlockRect()
    assert rect2 is not None and abs(rect2.width() - 150.0) < 0.01, rect2

    # 0 hides it
    v.TitleBlockWidth = "0 mm"
    assert sheet.Proxy.titleBlockRect() is None

    # standard i18n pipeline: load the compiled Russian .qm and the
    # labels must come back translated (English default otherwise)
    translator = QtCore.QTranslator()
    assert translator.load("schematics_ru.qm", "translations"), "qm not found"
    QtCore.QCoreApplication.installTranslator(translator)
    try:
        ru = titleBlockTexts()
        assert ru["sheet"] == "Лист" and ru["rev"] == "Изм.", ru
    finally:
        QtCore.QCoreApplication.removeTranslator(translator)

    # restore defaults + template-owned page for later steps
    v.TitleBlockWidth = "185 mm"
    v.PaperSize = "From template"
    assert sheet.Proxy.titleBlockRect() is not None
    assert titleBlockSvgPath().endswith("TitleBlock.svg")
    FreeCAD.ActiveDocument.recompute()
step("title block (fixed size, translated placeholders)", t_title_block)

def t_bom_table():
    from Schematics.Features.Utils.Reports import componentRows

    expected = len(componentRows(sheet))
    assert expected >= 2, expected

    bom = __main__.Schematics.BillOfMaterials(30, 200, sheet)
    assert bom is not None
    assert str(bom.Type) == "BillOfMaterials", bom.Type
    item = bom.Proxy.item
    assert item is not None
    # the drawn table shows exactly the sheet's component rows
    assert len(item.tableRows()) == expected, (len(item.tableRows()), expected)
    rect = item.boundingRect()
    assert rect.width() > 80 and rect.height() > 20, rect
    # the table object itself is not a component (no Designator property)
    assert len(componentRows(sheet)) == expected

    # editable heading
    bom.Title = "Device list"
    assert bom.Title == "Device list", bom.Title
    FreeCAD.ActiveDocument.recompute()
step("BOM table element (on-sheet component list)", t_bom_table)

def t_bom_title_box_and_snap():
    """The title row is one box across the full row width (column
    separators must not cut through it), and the table's bottom-right
    corner magnets onto the title block's top-right corner."""
    from PySide6 import QtCore, QtGui, QtWidgets
    from Schematics.Features.Items.BillOfMaterials import (
        BOM_COLUMNS,
        LINE_W,
        ROW_H,
        TITLE_H,
    )
    from Schematics.Features.Utils.Reports import componentRows, symbolCount

    # size math must agree with the full row walk (symbolCount skips the
    # symbol-store scan that componentRows needs for names/descriptions)
    assert symbolCount(sheet) == len(componentRows(sheet)), (
        symbolCount(sheet), len(componentRows(sheet)))

    bom = None
    for element in sheet.Elements:
        if getattr(element, "Type", "") == "BillOfMaterials":
            bom = element
            break
    assert bom is not None, "no BillOfMaterials element on the sheet"
    item = bom.Proxy.item
    total_w, height = item._tableSize()

    # --- render the table off-screen and inspect its pixels -----------
    rect = item.boundingRect()
    scale = 6
    img = QtGui.QImage(int(rect.width() * scale) + 2,
                       int(rect.height() * scale) + 2,
                       QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(img)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.scale(scale, scale)
    painter.translate(-rect.x(), -rect.y())
    item.paint(painter, QtWidgets.QStyleOptionGraphicsItem(), None)
    painter.end()

    def darkAt(x: float, y: float, window: float = 1.0) -> bool:
        """Any near-black pixel within +/-window sheet units of (x, y)."""
        px0 = max(0, int((x - window - rect.x()) * scale))
        px1 = min(img.width(), int((x + window - rect.x()) * scale) + 2)
        py0 = max(0, int((y - window - rect.y()) * scale))
        py1 = min(img.height(), int((y + window - rect.y()) * scale) + 2)
        for py in range(py0, py1):
            for px in range(px0, px1):
                colour = QtGui.QColor(img.pixel(px, py))
                if colour.red() < 128 and colour.green() < 128:
                    return True
        return False

    title_mid = TITLE_H / 2.0
    header_mid = TITLE_H + ROW_H / 2.0
    # the title row is a box spanning the whole row: bordered on all four
    # sides and NOT chopped into cells by the column separators
    assert darkAt(0.0, title_mid), "title row left border missing"
    assert darkAt(total_w, title_mid), "title row right border missing"
    assert darkAt(total_w / 2.0, TITLE_H), "title box bottom border missing"
    assert not darkAt(BOM_COLUMNS[0][1], title_mid), \
        "column separator still cuts through the title row"
    assert not darkAt(BOM_COLUMNS[0][1] + BOM_COLUMNS[1][1], title_mid), \
        "column separator still cuts through the title row"
    # ...while the separators still exist below it (header + data rows)
    assert darkAt(BOM_COLUMNS[0][1] + BOM_COLUMNS[1][1], header_mid), \
        "column separator missing from the header row"

    # --- corner magnet onto the title block ---------------------------
    title_block = sheet.Proxy.titleBlockRect()
    assert title_block is not None, "sheet has no visible title block"
    target_x = title_block.right() - total_w - LINE_W / 2.0
    target_y = title_block.top() - height - LINE_W / 2.0

    # both axes in reach -> exact corner alignment
    item.setPos(target_x + 2.0, target_y + 2.0)
    assert abs(item.x() - target_x) < 1e-6, (item.x(), target_x)
    assert abs(item.y() - target_y) < 1e-6, (item.y(), target_y)

    # ...and the *ink* must be flush too, not just the paths. Qt centres
    # a stroked rect on its path (ink runs LINE_W/2 past it) while the
    # title block's SVG border is clipped at its bounding box, so aiming
    # at the raw corner overhung by half a stroke - ~1-2 px on screen.
    page_w = float(sheet.ViewObject.Width.Value)
    page_h = float(sheet.ViewObject.Height.Value)
    ink_scale = 10
    shot = QtGui.QImage(int(page_w * ink_scale), int(page_h * ink_scale),
                        QtGui.QImage.Format.Format_ARGB32)
    shot.fill(QtGui.QColor("white"))
    ink_painter = QtGui.QPainter(shot)
    ink_painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    sheet.Proxy.scene.render(
        ink_painter, QtCore.QRectF(0, 0, shot.width(), shot.height()),
        QtCore.QRectF(0, 0, page_w, page_h))
    ink_painter.end()

    def rightmostInk(y0: float, y1: float) -> float | None:
        """Outer edge (scene x) of the rightmost dark pixel in a y band."""
        best = None
        for py in range(int(y0 * ink_scale), min(shot.height(), int(y1 * ink_scale))):
            for px in range(shot.width() - 1, -1, -1):
                colour = QtGui.QColor(shot.pixel(px, py))
                if colour.red() < 128 and colour.green() < 128:
                    x = (px + 1) / ink_scale
                    if best is None or x > best:
                        best = x
                    break
        return best

    # bands: the table's rows sit just above the block, the block below it
    ink_bom = rightmostInk(title_block.top() - height + 1.0,
                           title_block.top() - 1.0)
    ink_tb = rightmostInk(title_block.top() + 1.0,
                          title_block.top() + min(40.0, title_block.height() - 1.0))
    assert ink_bom is not None and ink_tb is not None, (ink_bom, ink_tb)
    assert abs(ink_bom - ink_tb) <= 1.0 / ink_scale + 1e-9, \
        "BOM right border ink is off by %.3f sheet units" % (ink_bom - ink_tb)

    # only x in reach -> x lands exactly, y still grid-snaps (never left
    # off-grid just because the other axis magnetized)
    item.setPos(target_x + 2.0, target_y + 40.0)
    assert abs(item.x() - target_x) < 1e-6, (item.x(), target_x)
    step = float(sheet.ViewObject.GridSpacing.Value)
    assert abs(item.y() - round(item.y() / step) * step) < 1e-6, item.y()
    assert item.y() != target_y, (item.y(), target_y)

    # outside tolerance -> plain grid snap, no magnet
    item.setPos(target_x + 60.0, target_y + 60.0)
    assert abs(item.x() - target_x) > 10.0, item.x()
    assert abs(item.y() - target_y) > 10.0, item.y()

    # a literal property write must stay literal (no magnet jumps it)
    bom.X = target_x + 2.0
    FreeCAD.ActiveDocument.recompute()
    assert abs(item.x() - round(target_x + 2.0, 5)) < 1e-6, item.x()

    # park it somewhere sane for the steps that follow
    bom.X = 30
    bom.Y = 200
    FreeCAD.ActiveDocument.recompute()
step("BOM title box + title-block corner snap", t_bom_title_box_and_snap)

def t_shortcuts():
    from PySide6 import QtGui, QtWidgets
    mainWin = Gui.getMainWindow()
    found: dict[str, str] = {}
    for act in mainWin.findChildren(QtGui.QAction):
        sc = act.shortcut().toString()
        if sc:
            found[sc] = act.text()
    for key, needle in (
        ("A", "symbol"), ("W", "wire"),
        ("R", "Turn left"), ("Shift+R", "Turn right"),
        ("X", "Mirror horizontally"), ("Y", "Mirror vertically"),
        ("T", "text"), ("I", "line"),
    ):
        text = found.get(key, "")
        assert needle.lower() in text.lower(), \
            "hotkey %s -> %r missing (got %r)" % (key, needle, text)
step("KiCad-style hotkeys registered", t_shortcuts)

def t_symbol_manager():
    import os
    import shutil
    import tempfile
    from PySide6 import QtCore, QtWidgets
    from Schematics.Features.Dialogs.SymbolChooser import SymbolPreview
    from Schematics.Features.Dialogs.SymbolEditor import (
        SymbolCanvas,
        SymbolEditor,
    )
    from Schematics.Features.Dialogs.SymbolManager import (
        SymbolManager,
        validatePins,
    )
    from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog, SymbolPin
    from Schematics.Features.Utils.SymbolDrawing import (
        RawElement,
        Shape,
        createNewSymbol,
        parseDrawing,
        readSymbol,
        saveSymbolFile,
    )
    from Schematics.Features.Utils.SVGSymbolsCache import extractPins

    cat = SymbolCatalog()
    dlg = SymbolManager(catalog=cat)
    assert dlg.table.rowCount() >= 5, dlg.table.rowCount()
    assert dlg._selected() is not None, "first row not selected"
    # import/new never depend on a selection; the rest follow it
    assert dlg.importBtn.isEnabled() and dlg.newBtn.isEnabled()
    assert dlg.editBtn.isEnabled(), "row 0 is selected"
    # no stray Close button parked over the filter (unparented-layout bug)
    strays = [
        b for b in dlg.findChildren(QtWidgets.QPushButton)
        if b.parent() is dlg and b.text() == "Close"
    ]
    assert not strays, strays

    # Editor roundtrip on a TEMP copy - the real store is never written.
    src = next(e for e in cat.all() if len(cat.pins(e)) >= 2)
    tmp = tempfile.mkdtemp(prefix="sc_sym_")
    try:
        dst = os.path.join(tmp, os.path.basename(src.path))
        shutil.copy2(src.path, dst)
        # the preview must render with no catalog entry (editor case)
        with open(dst, "r", encoding="utf-8") as fh:
            svg_text = fh.read()
        _d, _r, src_pins = readSymbol(dst)
        preview = SymbolPreview()
        preview.setData(svg_text, [(p.name, p.x, p.y) for p in src_pins])
        assert preview._renderer.isValid(), "preview must render"

        editor = SymbolEditor(
            path=dst,
            pins=[SymbolPin("1", 1.5, 2.0), SymbolPin("2", 9.0, 2.0)],
            description="roundtrip test",
            ref="K",
        )
        assert editor.save() is None, "save failed"
        with open(dst, "r", encoding="utf-8") as fh:
            text = fh.read()
        _data, raw = extractPins(text)
        assert [(n, float(x), float(y)) for n, x, y in raw] == [
            ("1", 1.5, 2.0), ("2", 9.0, 2.0)
        ], raw
        assert 'schematics:description="roundtrip test"' in text
        assert 'schematics:ref="K"' in text

        # canvas: shape roundtrip + undo, artwork preserved
        elements = parseDrawing(text)
        raws = [e for e in elements if isinstance(e, RawElement)]
        assert raws, "existing artwork must parse as backdrop"
        before = len(elements)
        editor.canvas.addShape(Shape(kind="circle", coords=[10.0, 10.0, 3.0]))
        assert len(editor.canvas.elements) == before + 1
        assert editor.canvas.canUndo
        editor.canvas.undo()
        assert len(editor.canvas.elements) == before
        editor.canvas.addShape(Shape(kind="line", coords=[1.0, 2.0, 3.0, 4.0]))
        assert editor.save() is None, "drawing save failed"
        with open(dst, "r", encoding="utf-8") as fh:
            text = fh.read()
        assert '<line x1="1" y1="2" x2="3" y2="4"' in text, "shape missing"
        for e in raws:
            assert e.text in text, "artwork lost: %r" % e.text[:40]
        _data, raw = extractPins(text)
        assert len(raw) == 2, raw
        assert 'schematics:description="roundtrip test"' in text

        # endpoint snap (line ends), Ctrl escape hatch, grid fallback
        canvas = editor.canvas
        placed = canvas._placePoint(QtCore.QPointF(3.04, 4.03), False)
        assert (placed.x(), placed.y()) == (3.0, 4.0), placed
        free = canvas._placePoint(QtCore.QPointF(3.04, 4.03), True)
        assert (free.x(), free.y()) == (3.04, 4.03), free
        # grid fallback: far from every endpoint (line is 1,2 - 3,4),
        # so only the 0.5 grid can resolve it
        gridded = canvas._placePoint(QtCore.QPointF(10.02, 6.02), False)
        assert (gridded.x(), gridded.y()) == (10.0, 6.0), gridded

        # imported artwork (existing symbols are mostly raw paths) must
        # offer snap targets too, and the endpoint magnet beats the grid
        canvas2 = SymbolCanvas()
        canvas2.setDocument(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
            '<g stroke="#000"><path d="m13 10h7"/></g></svg>',
            [],
        )
        hit = canvas2._placePoint(QtCore.QPointF(13.05, 10.02), False)
        assert (hit.x(), hit.y()) == (13.0, 10.0), hit
        hit = canvas2._placePoint(QtCore.QPointF(13.3, 10.3), False)
        assert (hit.x(), hit.y()) == (13.0, 10.0), hit
        hit = canvas2._placePoint(QtCore.QPointF(19.9, 10.1), False)
        assert (hit.x(), hit.y()) == (20.0, 10.0), hit
        free = canvas2._placePoint(QtCore.QPointF(13.05, 10.02), True)
        assert (free.x(), free.y()) == (13.05, 10.02), free

        # copy / paste / cut: shapes and pins
        line_idx = next(
            i for i, e in enumerate(canvas.elements)
            if isinstance(e, Shape) and e.kind == "line"
        )
        canvas.selectShape(line_idx)
        assert canvas.copySelection()
        count = len(canvas.elements)
        assert canvas.pasteClipboard()
        assert len(canvas.elements) == count + 1
        pasted = canvas.selectedShape()
        assert pasted is not None and pasted.kind == "line"
        # pasted at the viewBox center (setDocument's initial cursor):
        # translated by (center - anchor), anchor = the line's first point
        center = canvas.viewBoxRect().center()
        dx = center.x() - 1.0
        dy = center.y() - 2.0
        assert list(pasted.coords) == [
            1.0 + dx, 2.0 + dy, 3.0 + dx, 4.0 + dy
        ], pasted.coords
        assert canvas.cutSelection()
        assert len(canvas.elements) == count
        canvas.selectPin(0)
        assert canvas.copySelection()
        assert canvas.pasteClipboard()
        assert len(canvas.pins) == 3, canvas.pins

        # invalid pin names must be rejected (loader charset), not written
        bad = SymbolEditor(
            path=dst, pins=[SymbolPin("bad name!", 0.0, 0.0)],
            description="", ref="",
        )
        assert bad.save(), "invalid pin name accepted"
        assert validatePins([SymbolPin("A1", 0.0, 0.0)]) is None

        # new-symbol flow against a TEMP store
        store = os.path.join(tmp, "store")
        cat2 = SymbolCatalog(root=store)
        new_path = createNewSymbol(store, "", "TestSym")
        assert os.path.exists(new_path)
        with open(new_path, "r", encoding="utf-8") as fh:
            assert parseDrawing(fh.read()) == []
        cat2.refresh()
        assert any(e.name == "TestSym" for e in cat2.all()), "not catalogued"
        try:
            createNewSymbol(store, "", "bad/name")
        except ValueError:
            pass
        else:
            raise AssertionError("bad name accepted")
        # saveSymbolFile direct use keeps the root tag + pins coherent
        saveSymbolFile(
            new_path, [Shape(kind="rect", coords=[5.0, 5.0, 10.0, 10.0])],
            [SymbolPin("1", 0.0, 10.0)], description="d", ref="X",
        )
        desc, ref, pins = readSymbol(new_path)
        assert (desc, ref) == ("d", "X"), (desc, ref)
        assert pins == [SymbolPin("1", 0.0, 10.0)], pins
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # No deleteLater(): a pending deferred delete races the hard os._exit()
    # at the end of this script (GILState fatal, exit 127).
    dlg.close()
step("symbol manager + symbol editor (temp store)", t_symbol_manager)

def t_view_props():
    v = sheet.ViewObject
    v.GridVisible = False
    v.GridVisible = True
    sheet.SnapEnabled = not sheet.SnapEnabled
    sheet.Appearance = "Invert black and white"
    FreeCAD.ActiveDocument.recompute()
step("grid/snap/appearance properties", t_view_props)

def t_scene_state():
    p = sheet.Proxy
    assert hasattr(p, "scene") and hasattr(p, "view")
    assert len(p.scene.items()) >= 4, "scene lost items: %d" % len(p.scene.items())
step("scene/view populated", t_scene_state)

def t_save():
    FreeCAD.ActiveDocument.saveAs(DOC)
    assert os.path.exists(DOC)
step("save document", t_save)

def t_close():
    FreeCAD.closeDocument(FreeCAD.ActiveDocument.Name)
step("close document", t_close)

def t_reload():
    FreeCAD.openDocument(DOC)
    s = [o for o in FreeCAD.ActiveDocument.Objects if hasattr(o, "Elements")][0]
    assert len(s.Elements) == 11, "restored sheet has %d elements" % len(s.Elements)
    assert hasattr(s.Proxy, "scene"), "scene not restored"
    # Wires are document objects: points and item must survive the round trip
    wires = [o for o in s.Elements if getattr(o, "Type", "") == "Wire"]
    assert len(wires) == 4, "wires did not survive save/load: %r" % wires
    assert any(getattr(o, "Type", "") == "BillOfMaterials" for o in s.Elements), \
        "BOM table did not survive save/load"
    assert len(wires[0].Points) == 3, "wire points lost: %r" % wires[0].Points
    assert wires[0].Proxy.item is not None, "wire item not rebuilt after reload"
step("reload + onDocumentRestored", t_reload)

def t_cleanup_api():
    # delete one element (onDelete path) then recompute
    s = [o for o in FreeCAD.ActiveDocument.Objects if hasattr(o, "Elements")][0]
    # delete the Rectangle explicitly: Elements[0] is the default title block
    victim = next(o for o in s.Elements if getattr(o, "Type", "") == "Rectangle")
    FreeCAD.ActiveDocument.removeObject(victim.Name)
    FreeCAD.ActiveDocument.recompute()
step("delete element + recompute", t_cleanup_api)

def t_close_no_stale_window():
    # Regression (issues.txt): closing the document must not leave the
    # scheme MDI window behind - it kept repainting the deleted object
    # (one ReferenceError per repaint) and made symbol commands fail
    # against the dead sheet.
    from PySide6 import QtWidgets
    mdi = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    FreeCAD.closeDocument(FreeCAD.ActiveDocument.Name)
    app = QtWidgets.QApplication.instance()
    for _ in range(30):   # let the deferred sweep timer and paints run
        app.processEvents()
    stale = [sw for sw in mdi.subWindowList()
             if sw.__class__.__name__ == "SchemeMDIView"]
    assert not stale, "stale scheme windows after document close: %r" % stale
    from Schematics.Features.Utils.MDI import tryToGetSchemeFromActiveWindow
    assert tryToGetSchemeFromActiveWindow() is None
step("close document leaves no stale window", t_close_no_stale_window)

def t_qet_import():
    # Batch import of QElectroTech .elmt files (Utils.QETImport): parse a
    # fixture covering every primitive, convert into a temp store, then
    # read the pins back through the catalog. No network, no QET install.
    import shutil
    from Schematics.Features.Utils.QETImport import (
        findQETElements, importQETFiles, scanQETElements, symbolStem)
    from Schematics.Features.Utils.SymbolCatalog import SymbolCatalog
    from Schematics.Features.Utils.SymbolDrawing import readSymbol

    root = os.path.join(_HERE, "_fc_qet_fixture")
    store_root = os.path.join(_HERE, "_fc_qet_store")
    store = os.path.join(store_root, "GOST")
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(store_root, ignore_errors=True)
    group_dir = os.path.join(root, "10_electric", "test")
    os.makedirs(group_dir, exist_ok=True)
    fixture = """<?xml version="1.0" encoding="UTF-8"?>
<definition version="0.100.0" type="element" link_type="simple" width="30" height="60" hotspot_x="20" hotspot_y="30">
 <uuid uuid="{00000000-0000-0000-0000-000000000001}"/>
 <names>
  <name lang="fr">Contact principal</name>
  <name lang="en">Contactor / Main make contact</name>
 </names>
 <description>
  <line x1="0" y1="-20" x2="0" y2="-40" end1="none" end2="none" length1="1.5" length2="1.5" style="line-style:normal;line-weight:normal;filling:none;color:black" antialias="false"/>
  <line x1="0" y1="0" x2="0" y2="20" end1="none" end2="none" length1="1.5" length2="1.5" style="line-style:normal;line-weight:normal;filling:none;color:black" antialias="false"/>
  <polygon x1="0" y1="0" x2="-8" y2="-23" closed="false" antialias="false" style="line-style:normal;line-weight:normal;filling:none;color:black"/>
  <rect x="-10" y="-30" width="6" height="8" rx="0" ry="0" antialias="false" style="line-style:normal;line-weight:normal;filling:none;color:black"/>
  <arc x="-2.5" y="-24.5" width="5" height="5" start="90" angle="180" style="line-style:normal;line-weight:normal;filling:none;color:black" antialias="true"/>
  <text x="-14" y="-5" font="Liberation Sans,9,-1,5,50,0,0,0,0,0,Regular" color="#000000" text="K&gt;" rotation="0"/>
  <dynamic_text uuid="{00000000-0000-0000-0000-000000000002}" keep_visual_rotation="false" y="-25" z="4" Valignment="AlignTop" x="4" font="Liberation Sans,8,-1,5,50,0,0,0,0,0,Regular" text_from="ElementInfo" text_width="-1" Halignment="AlignLeft" rotation="0" frame="false">
   <text></text>
   <info_name>label</info_name>
  </dynamic_text>
  <terminal uuid="{00000000-0000-0000-0000-000000000003}" type="Generic" orientation="n" y="-40" x="0" name=""/>
  <terminal uuid="{00000000-0000-0000-0000-000000000004}" type="Generic" orientation="s" y="20" x="0" name=""/>
 </description>
</definition>
"""
    path = os.path.join(group_dir, "contactor_main.elmt")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(fixture)

    found = findQETElements(root)
    assert found == [path], found
    infos = scanQETElements(root)
    assert len(infos) == 1, infos
    assert infos[0].name == "Contactor / Main make contact", infos[0].name
    assert infos[0].category == "10_electric/test", infos[0].category
    assert infos[0].stem == "Contactor Main make contact", infos[0].stem
    assert symbolStem('a\\b:c*d?e"f<g>h|i') == "a b c d e f g h i"

    dest = os.path.join(store, "Relays")
    report = importQETFiles(found, dest)
    assert not report.failed, report.failed
    assert report.imported == ["Contactor Main make contact"], report.imported

    catalog = SymbolCatalog(root=store)
    entry = catalog.find("Contactor Main make contact", "Relays")
    assert entry is not None, [e.key for e in catalog.all()]
    desc, _ref, pins = readSymbol(entry.path)
    assert desc == "Contactor / Main make contact", desc
    assert [p.name for p in pins] == ["x1", "x2"], pins
    # bbox y -40..20 scales to 30 mm; terminals (0,-40)/(0,20) land at
    # (7,0)/(7,30) after the x offset of -14.
    with open(entry.path, encoding="utf-8") as handle:
        text = handle.read()
    assert 'height="30mm"' in text, text[:240]
    assert 'width="3"' in text, "scaled artwork rect missing"
    assert "dynamic_text" not in text, "label leaked into the symbol"
    assert "<path" in text, "arc did not become a backdrop path"
    assert "<polyline" in text and "<line" in text, text
    assert abs(pins[0].x - 7.0) < 1e-6 and abs(pins[0].y - 0.0) < 1e-6, pins
    assert abs(pins[1].x - 7.0) < 1e-6 and abs(pins[1].y - 30.0) < 1e-6, pins

    again = importQETFiles(found, dest)
    assert again.imported == [], again
    assert again.skipped == ["Contactor Main make contact"], again

    bad = os.path.join(group_dir, "broken.elmt")
    with open(bad, "w", encoding="utf-8", newline="") as handle:
        handle.write("not xml at all")
    broken = importQETFiles([bad], dest)
    assert len(broken.failed) == 1, broken
    assert broken.failed[0][1], broken.failed

    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(store_root, ignore_errors=True)
step("QET batch import", t_qet_import)

n_pass = len([line for line in lines if line.startswith("PASS")])
n_fail = len([line for line in lines if line.startswith("FAIL")])
log("RESULT: %d PASS / %d FAIL" % (n_pass, n_fail))
open(LOG, "w", encoding="utf-8").write("\n".join(lines) + "\n")
# Drain pending Qt events (deferred deletes etc.) and flush the streams
# before the hard exit: an event racing os._exit intermittently took the
# process down at teardown (exit 127 + "Abnormal program termination").
from PySide6 import QtWidgets as _QtWidgets
_app = _QtWidgets.QApplication.instance()
if _app is not None:
    for _ in range(10):
        _app.processEvents()
sys.stdout.flush()
sys.stderr.flush()
# Do NOT Gui.getMainWindow().close() here: a modified document pops a modal
# save dialog and hangs the headless run. Hard-exit after the log is written.
os._exit(0)
