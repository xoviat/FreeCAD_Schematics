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
* It is possible to draw wires, but you will not be able to select, modify or delete them once created. 
Also, the wires are not written to the file when saving.
* Printing a drawing is not possible yet.
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

### Delete symbol(s)

Select symbol(s) in sheet or in treeview. Press delete key on keyboard.

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
        Gui.runCommand('SCRelayCoil',0)
        r = Gui.ActiveDocument.ActiveObject
        r.Object.X = 80 + x * 20
        r.Object.Y = 60 + y * 20
        r.Object.Rotation.Value = 90

#END
```

Next example shows how to customize scheme sheet after creation:

```python
Gui.runCommand('SCNewScheme',0)
sheet = Gui.ActiveDocument.ActiveObject

# Change view properties (presented in View tab)
sheet.Visibility = True

# Change data properties (presented in Data tab)
sheetData = sheet.Object
sheetData.GridVisible = True
sheetData.GridSpacing = '1.00 mm'
sheetData.MajorGridLineEvery = 10
sheetData.MajorGridLineColor = (0.00,0.00,1.00) # Blue
sheetData.MajorGridLineStyle = 2 # Dash style
sheetData.MinorGridLineColor = (1.00,0.00,0.00) # Red
sheetData.MinorGridLineStyle = 1 # Solid style
#END
```