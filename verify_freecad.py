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
    assert len(s.Elements) == 5, "restored sheet has %d elements" % len(s.Elements)
    assert hasattr(s.Proxy, "scene"), "scene not restored"
    # Wires are document objects: points and item must survive the round trip
    wires = [o for o in s.Elements if getattr(o, "Type", "") == "Wire"]
    assert len(wires) == 1, "wire did not survive save/load: %r" % wires
    assert len(wires[0].Points) == 3, "wire points lost: %r" % wires[0].Points
    assert wires[0].Proxy.item is not None, "wire item not rebuilt after reload"
step("reload + onDocumentRestored", t_reload)

def t_cleanup_api():
    # delete one element (onDelete path) then recompute
    s = [o for o in FreeCAD.ActiveDocument.Objects if hasattr(o, "Elements")][0]
    victim = s.Elements[0]
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
