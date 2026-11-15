# Refusal of responsibility

This software is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

# Description

Among the main features, this editor is oriented to what kind of window is currently active. 
Scheme is currently selected in the treeview is less important.

This means:
* For example, if activate window with 3D view, the buttons associated with schematics workbench is will go out. 
It doesn't matter what scheme is currently selected in treeview, the main thing is which window is currently active.
* Another example, if copy objects and paste it. Objects will be pasted into the window that is currently active. 
It doesn't matter what scheme is selected in the treeview.

It is important to note: if select an object in document treeview, then the window (tab) with a scheme in where 
this object located is automatically activates.

Not supported features:
* A convenient and fast way to make a copy of an existing sheet is not available yet.

## Main concepts

The workbench allows to create sheets for drawing schematics. 
The scheme is a set of symbols (Conventional Graphic Designation) connected with lines (wires).

Each symbol has a pins - areas for connecting wires, just like a real electronic component or electrical apparatus has contacts for connecting wires.

![Pins](Art/Symbols_and_pins.png)

## Add / Delete features

### Create new scheme

Press button <img src="Icons/Toolbars/NewScheme.svg" title="New scheme" width="24"/> with drawing paper and green plus on toolbar.

### Add new symbols

Activate window with scheme and press symbol button.
Also, is possible to change position and rotation of symbol by context menu or from property's tab.

### Draw wires

Press the wire button <img src="Icons/Toolbars/DrawWireMode.svg" title="Draw wire" width="24"/> and left-click on the sheet
to place vertices. Segments follow KiCad's posture: the rubber line snaps to horizontal, vertical and 45° directions
from the previous vertex, while wire ends snap to symbol pins when close enough. Clicking a pin or another wire
**completes the wire there and keeps the tool armed** - the next click starts a new wire (double-click or Enter also
finish; Escape or right-click exits the tool). Wires are first-class document objects: they are saved with the file,
appear in the tree, can be selected, moved and deleted like any other element, and carry a `WireType` (Power, Control,
Hydraulic, Pneumatic, Signal) plus per-wire stroke style (StrokeWidth / StrokeDash) in the property tab.

### Designators and values

Symbols carry KiCad-style `Designator` (K1, R3) and `Value` fields in the property tab, and
annotation follows KiCad's two-step flow:

1. **Placement** shows a placeholder - `R?`, `K?`, `?` - drawn above the symbol. The prefix
   comes from the symbol's library entry (`schematics:ref`, set in the symbol editor) or, until
   one is set, from the store group (Resistors→R, Realys→K, Diodes→VD, Transistors→VT,
   Lamps→H, Commutation→S).
2. **Annotate sheet** replaces placeholders with the smallest free number per prefix
   (`R?` → R1, R2, ...). Placeholders consume no numbers, and a placeholder's own prefix
   wins if the library metadata changed since placement.

The designator is drawn above the symbol and the value below it; the value stays hidden
while it equals the library name, exactly like KiCad's default fields.

### Wire labels

Select a wire and press `L` (KiCad's Add Label): the tag is drawn at the wire's midpoint,
joins same-labelled wires into one named net in the connection check, and marks the wire's
ends as intentionally terminated instead of floating. The tag lives in the wire's `Tag`
property (the property name `Label` is taken by FreeCAD's built-in tree label).

### Check connections

Hovering a wire highlights its whole net in blue - KiCad's net highlight: label groups,
end-to-end contacts and T junctions (an endpoint landing on another wire's body) all join
the closure, and the highlight toggles off when the cursor leaves.

**Check connections** runs a geometric ERC-lite: pins with no wire endpoint and wire ends
resting on neither a pin nor another wire. Connections are matched with the same tolerance
the wire tool snaps with, resolved through the item transforms (rotation-safe). Electrical
pin types and net names are not modelled yet - this checks that the drawing is wired, not
that it is electrically legal.

### Junctions and conductor classes

Where a wire's end lands on another wire, both drawing conventions appear automatically:
a **junction dot** at the contact point (pin terminals stay dot-free - they are symbol
contacts). The `WireType` property carries the conductor class; **Control** and **Signal**
wires default to a dashed style, everything else stays solid, and the per-wire `StrokeDash`
property still overrides the look.

### Pages and sheet index

The title block carries a boxed **Page N of M** indicator (translated with the rest of the
cartouche text), so the loose corner text is gone. `PgUp`/`PgDn`
switch tabs (KiCad's sheet navigation) and the **Sheet index** (`Ctrl+H`, KiCad's hierarchy
navigator) lists all pages with their symbol and wire counts. Real hierarchical sheets
(parent/child references across pages) are not modelled yet - sheets are peers.

**Sheet size** is configurable like in a CAD program: the sheet's *View* properties carry a
**PaperSize** dropdown (`From template`, A0-A5, Letter, Legal, Tabloid) plus the editable
**Orientation**. Standard sizes set the page dimensions directly and the template frame is
stretched to fit (exact for the A-series); `From template` hands the dimensions back to the
SVG template's own viewBox.

**Title block**: the GOST-style cartouche in the frame's bottom-right corner is a real
element in the sheet's **model tree** (like the BOM table) - it is inserted by default when
a sheet is created, is selectable/deletable, and re-anchors itself whenever the template or
page changes. It comes from `Templates/TitleBlock.svg` at a **fixed physical size on every
page size** - controlled by the *View* properties **TitleBlockWidth**/**TitleBlockHeight**
(defaults 185x55 mm, `0` hides it). It shows the sheet title (the object's Label) and the
live page/page-count; its label text is inserted at creation time from the configured
language (see below). Sheet templates themselves are pure geometry (frame paths only,
white paper + frame) and can differ per sheet.

### Language and translations

The default language is **English**, and FreeCAD's configured language
(*Edit > Preferences > General > Language*) decides whether a translation is used - the
standard Qt Linguist pipeline, not a custom mechanism:

- Sheet text is marked with `QtCore.QCoreApplication.translate("Schematics", "...")` in
  `Schematics/Features/Utils/TitleBlock.py`; at sheet creation the
  `schematics:i18n` placeholders in `Templates/TitleBlock.svg` are filled with the
  resolved strings (the SVG carries **no** language text at all).
- English is compiled in (source strings), so no `.qm` is needed for the default.
- Translations live in `translations/schematics_<lang>.ts` (XML, editable) and are compiled
  with `pyside6-lrelease` to `.qm`; `install.py` places them in the FreeCAD user app-data
  `translations/` directory, where FreeCAD's Translator auto-loads `*_*.qm` for the active
  language. Restart FreeCAD after installing or changing translations.
- To add a language: run
  `pyside6-lupdate Schematics/Features/Utils/TitleBlock.py -extensions py -ts translations/schematics_<lang>.ts`,
  fill the `<translation>` entries, then
  `pyside6-lrelease translations/schematics_<lang>.ts -qm translations/schematics_<lang>.qm`
  and re-run `install.py`. Note lupdate only recognizes the direct
  `QtCore.QCoreApplication.translate("context", "...")` form with literal arguments.

### Print and PDF

**File → Print / Print preview** (Ctrl+P) renders the sheet exactly as drawn - page size and
orientation follow the sheet's template (A4/A3, portrait/landscape), fitted without distortion.
**Export PDF…** writes the same rendering to a PDF file.

### Component list

**Component list…** lists every annotated symbol of the sheet (designator, value, symbol,
description) with CSV export and clipboard copy - the device list a machine schematic is
delivered with. Rows are ordered naturally (R1, R2, R10); symbols without a designator are
covered by **Annotate sheet** first.

**Add BOM table** places the same list *on the sheet* as a table object (KiCad/QET table
style): position it like any other element, edit its `Title` in the property tab, and the
rows refresh live as symbols are annotated, renamed or deleted - only position and heading
are stored, the content always mirrors the sheet.

The table's heading sits in one box across the full row width (column separators start
below it). While placing or dragging, a magnet lines the table's **bottom-right corner** up
with the title block's **top-right corner** - each axis independently, so right-edge and
bottom-edge alignment are each useful on their own and together they land the corner. The
snap is measured on the painted edges rather than the geometry: the table's stroked border
paints half a stroke past its path while the title block's SVG border is clipped at its
box, so aiming at the raw corner would overhang by ~1-2 px. Type an exact `X`/`Y` in the
property tab to bypass it; turning off grid snapping disables it too.

### Delete symbol(s)

Select symbol(s) in sheet or in treeview. Press delete key on keyboard.

### Symbol library and editor

`Ctrl+E` (or the toolbar button) opens the **symbol manager**: filter/search, preview with
pins, and `New symbol…` / `Edit…` / `Duplicate` / `Import…` / `Delete…` / `Open folder` /
`Refresh`. `New symbol…` creates a blank SVG in the chosen group and opens it in the
**symbol editor**; `Edit…` (or double-click) opens the selected symbol.

The editor draws directly in FreeCAD: **Select / Line / Rect / Circle / Polyline / Text /
Pin** tools on a snap grid (0.5 mm, toggleable), wheel zoom, pan (drag empty space or the
middle button), move/resize handles, `Del` to remove, `Ctrl+Z/Y` undo/redo, `Fit` to reset
the view. Click with the **Pin** tool to add connection points (drag the dots to move
them); the table edits names and coordinates, and Description / Reference prefix set the
`schematics:description` / `schematics:ref` metadata. Stroke color, width and fill follow
the selection (or become the defaults for the next shape).

Placement snaps to the **ends of existing lines** (line ends, polyline vertices and rect
corners) before falling back to the grid - including the **imported artwork of existing
symbols**, whose path endpoints are snap targets too, so pins land exactly on wire stubs.
The Pin tool draws an **orange ring at the position a click would commit to**, so the
magnet is visible before you press the button. **Hold `Ctrl` while clicking or dragging
for free placement** (bypasses all snapping; the Snap toggle off does the same). `Ctrl+C` / `Ctrl+X` / `Ctrl+V` copy, cut and paste the selected
shape or pin at the cursor (pasting on the original spot nudges it clear); pin copies get
the next free pin number. The pin table and text fields keep their native Qt copy/paste
when they have focus.

Artwork brought in from external SVG tools (`<path>`/`<g>` groups) renders as a static
backdrop - the built-in tools edit line/rect/circle/ellipse/polyline/text shapes, so
existing symbols keep their original artwork byte-for-byte while pins and metadata stay
fully editable.

## Copy / Paste features

### Copy symbol(s)

Select symbol or a few symbols. 
Press right mouse button and select a 'Copy' from context menu or select a 'Edit → Copy' main menu item. 
Activate window which contain scheme sheet where to insert symbols. 
Press right mouse button and select a 'Paste' from context menu or select a 'Edit → Paste' main menu item. 
Symbols copied by context menu will be pasted to current mouse cursor position. 
Symbols pasted through the 'Edit → Paste' main menu item, will be pasted to the same place where they copied.

### Copy a full scheme sheet

This feature not fully supported yet. To make right duplicate of scheme select sheet with all elements,
and Copy and Paste it.

## Sheet customizing features

### Sheet grid

To enable/disable the sheet grid, select scheme in treeview of document and press 
<img src="Icons/Toolbars/Grid.svg" title="Show/hide grid" width="24"/> button on toolbar. 
Also, this feature can be enabled by changing the 'Show Grid' property through the property editor.

### Sheet grid customizing

There are two types of grids: major (coarse) and minor (fine). 
For each of them, is possible to adjust the lines width and lines color by the properties window.

### Snap to grid feature

To enable/disable snap to grid, select scheme in treeview of document and press 
<img src="Icons/Toolbars/Snap.svg" title="Snap to grid on/off" width="24"/> button on toolbar. 
Also, this feature can be enabled by changing the 'Snap Enabled' property through the property editor.

### Change grid spacing

The grid spacing can be set by changing the 'Grid Spacing' property. 
It is also possible to enable a snap to the major grid by changing scheme 'Snap To Major Grid' property.

Note: if specify zero as the grid line width, then the grid line width will be 1 pixel ever, independently of the sheet scale.

### Sheet blueprint displaying mode

This feature allows to represent the scheme in inverted colors.
To change displaying mode, select scheme in treeview of document and set 'Invert colors' property.

## Script examples

For run examples, at first activate Schematics workbench after that copy given code and paste it to FreeCAD Python console.

First script example is creates a empty sheet and generate a 5x5 grid from symbols.

```python
Gui.runCommand('SCNewScheme',0)
for x in range(0,5):
    for y in range(0,5):
        Gui.runCommand('SCLamp',0)
        l = Gui.ActiveDocument.ActiveObject
        l.Object.X = 70 + x * 20
        l.Object.Y = 50 + y * 20
        Gui.runCommand('SCCoil',0)
        r = Gui.ActiveDocument.ActiveObject
        r.Object.X = 80 + x * 20
        r.Object.Y = 60 + y * 20
        r.Object.Rotation.Value = 90

#END
```

Next example shows how to customize scheme sheet grid after creation:

```python
Gui.runCommand('SCNewScheme',0)
sheet = Gui.ActiveDocument.ActiveObject

# Change view properties (presented in View tab)
sheet.Visibility = True

# Change data properties (presented in Data tab)
sheetData = sheet.Object
sheetData.ViewObject.GridVisible = True
sheetData.ViewObject.GridSpacing = '1.00 mm'
sheetData.MajorGridLineEvery = 10
sheetData.MajorGridLineColor = (0.00,0.00,1.00) # Blue
sheetData.MajorGridLineStyle = 2 # Dash style
sheetData.MinorGridLineColor = (1.00,0.00,0.00) # Red
sheetData.MinorGridLineStyle = 1 # Solid style
#END
```

# Development

### Environment setup (type check, lint, editor)

Requires **Python 3.11** (matches FreeCAD's embedded interpreter). From the repository root:

```
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt      # macOS / Linux
.venv\Scripts\python -m pip install -r requirements-dev.txt  # Windows
```

`requirements-dev.txt` pins mypy, ruff, basedpyright and the PySide6/FreeCAD type stubs.
The installed PySide6 is for **type checking only** (its `.pyi` files); at runtime the
workbench uses the PySide6 bundled with FreeCAD. All tool configuration (`mypy.ini`,
`pyrightconfig.json`, `pyproject.toml`, `.zed/`) is relative to the repository root, so
nothing here is machine-specific. The commands below use the Windows form
(`.venv/Scripts/...`); substitute `.venv/bin/...` elsewhere.

## Keyboard shortcuts (KiCad-compatible)

The sheet view follows the KiCad schematic editor's default hotkeys so muscle memory transfers:

| Key | Action |
| --- | --- |
| `A` | Place symbol… (chooser: search, preview, pin list) |
| `W` | Draw wire |
| `R` / `Shift+R` | Rotate selection 90° counter-clockwise / clockwise |
| `X` / `Y` | Mirror selection horizontally / vertically |
| `T` | Add text |
| `L` | Add label to wire (conductor tag) |
| `I` | Add line |
| `Del` | Delete selection |
| `Esc` | Cancel active tool (wire, placement) / clear selection |
| `Home` | Zoom to fit the sheet |
| `PgUp` / `PgDn` | Previous / next sheet tab |
| `Ctrl+H` | Sheet index (page, name, symbol and wire counts) |
| `Enter` / double-click | Finish wire, place the chosen symbol |
| `Ctrl+E` | Symbol manager (symbol editor opens directly for the selected symbol) |
| `Ctrl+C/X/V`, `Ctrl+Z/Y` | Clipboard and undo/redo (FreeCAD defaults) |

Hotkeys are declared as the `Accel` resource on each command and only fire while a
scheme window is active. FreeCAD's shortcut manager still allows rebinding them.
Keys for features that do not exist yet (junction `J`, labels `L`, no-connect `Q`,
properties dialog `E`, cursor-follow move `M`) are deliberately not bound.

### Testing

* `python install.py` copies the workbench into FreeCAD's user Mod directory (restart FreeCAD afterwards).
* `FreeCAD.exe verify_freecad.py` - the end-to-end suite (31 steps): commands, dialogs, save/reload
  persistence, hotkey registration, reports, the wire-drawing state machine and the title block.
  It writes `_fc_verify.log`; a good run ends with `RESULT: 31 PASS / 0 FAIL` and exit code 0.
* `FreeCADCmd.exe verify_imports.py` - module import smoke test (31 modules).
* Known gotcha: verify steps must **not** call `deleteLater()` on dialogs - a pending deferred
  delete races the script's hard `os._exit(0)` and trips a GILState fatal (exit 127). Steps use
  plain scope-exit destruction instead; the chooser step documents this in place.
* Native-crash gotchas found the hard way (both end as *Access violation*, exit 127):
  Qt 6.8's SVG renderer **crashes on `<text/>` with no content** - placeholder text nodes
  must always carry at least a space (the patcher enforces this); and
  `QGraphicsSvgItem.setSharedRenderer()` does **not** take ownership - keep an explicit
  Python reference to the `QSvgRenderer` for as long as the item lives, or the C++ renderer
  is deleted out from under the item on first paint. When a run AVs at a moving line number,
  bisect by disabling the suspect code path before reaching for a native debugger.

### Typing

* New code is fully typed; every file touched gets its signatures annotated incrementally
  (parameters and returns) without behaviour changes.
* `python -m mypy Init.py InitGui.py SCUtils.py Schematics verify_freecad.py verify_imports.py`
is the gate: **0 errors required** before any commit.
* `ruff check .` - rules are pinned in `pyproject.toml` (ruff's defaults broadened across
  releases, so pinning keeps command-line and editor runs identical).
* Editor language servers: `pyrightconfig.json` points basedpyright at `./.venv` (Python 3.11,
  FreeCAD/PySide6 stubs), `typings/` supplies a stub for FreeCAD's bundled `pivy` module, and
  `.zed/settings.json` keeps Zed's default servers while disabling save-time reformatting.
  Goal is **0 basedpyright errors**; `reportAttributeAccessIssue` stays at warning level to
  mark legacy dynamic FreeCAD-property access without blocking - those warnings are known,
  not bugs.