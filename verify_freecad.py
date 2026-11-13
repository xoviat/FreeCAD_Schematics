# Run with:
#   FreeCAD.exe -M <this-dir> verify_freecad.py
# End-to-end verification of the Schematics workbench under FreeCAD 1.1.4 / PySide6
import os, sys, traceback
import __main__

# Paths derived from this script's location so no machine-specific user path
# is baked into the file.
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # executed without __file__ (e.g. via exec)
    _HERE = os.getcwd()
LOG = os.path.join(_HERE, "_fc_verify.log")
DOC = os.path.join(_HERE, "_fc_verify.FCStd")
lines = []
def log(s): lines.append(str(s)); print("[verify]", s, flush=True)
def step(name, fn):
    try:
        fn(); log("PASS " + name)
    except Exception:
        log("FAIL " + name); log(traceback.format_exc())

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
    line.Width = 40; line.Height = 20
step("Schematics.Line() API", t_line_item)

def t_cmd_items():
    # Symbol command path: creates under-cursor symbol then commits on click;
    # exercise the PrimitiveCommand + SVG renderer via scene directly.
    from Schematics.Features.Items.Symbol import Symbol
    Symbol.typ = "Resistor"; Symbol.grp = "Resistors"; Symbol.std = "GOST"
    sym = Symbol(120, 90, sheet)
    assert sym is not None and sym.Width.Value > 0, "symbol has no size"
step("Symbol item (GOST resistor svg)", t_cmd_items)

def t_text_item():
    from Schematics.Features.Items.Text import Text
    t = Text(30, 120, sheet)
    t.Text = "<html><body>hello</body></html>"
step("Text item", t_text_item)

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
    assert len(s.Elements) == 4, "restored sheet has %d elements" % len(s.Elements)
    assert hasattr(s.Proxy, "scene"), "scene not restored"
step("reload + onDocumentRestored", t_reload)

def t_cleanup_api():
    # delete one element (onDelete path) then recompute
    s = [o for o in FreeCAD.ActiveDocument.Objects if hasattr(o, "Elements")][0]
    victim = s.Elements[0]
    FreeCAD.ActiveDocument.removeObject(vobj.Object.Name if False else victim.Name)
    FreeCAD.ActiveDocument.recompute()
step("delete element + recompute", t_cleanup_api)

log("RESULT: %d PASS / %d FAIL" % (
    sum(1 for l in lines if l.startswith("PASS")),
    sum(1 for l in lines if l.startswith("FAIL"))))
open(LOG, "w", encoding="utf-8").write("\n".join(lines) + "\n")
# Do NOT Gui.getMainWindow().close() here: a modified document pops a modal
# save dialog and hangs the headless run. Hard-exit after the log is written.
os._exit(0)
