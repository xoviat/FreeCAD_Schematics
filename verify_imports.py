import traceback
import importlib
mods = [
 'SCUtils', 'Schematics.Utils', 'Schematics.API',
 'Schematics.Features.Utils.QtEnums', 'Schematics.Features.Utils.Snap',
 'Schematics.Features.Utils.SVG', 'Schematics.Features.Utils.SVGSymbolsCache',
 'Schematics.Features.Utils.SoftMigration', 'Schematics.Features.Utils.CopyPaste',
 'Schematics.Features.Items.SchemeObjectItem', 'Schematics.Features.Items.SchemeObject',
 'Schematics.Features.Items.Rectangle', 'Schematics.Features.Items.Line',
 'Schematics.Features.Items.Ellipse', 'Schematics.Features.Items.Polyline',
 'Schematics.Features.Items.Text', 'Schematics.Features.Items.Symbol',
 'Schematics.Features.Items.MarkersMixin', 'Schematics.Features.Items.StrokeMixin',
 'Schematics.Features.GridMixin', 'Schematics.Features.CursorItemMixin',
 'Schematics.Features.SchemeViewAndScene', 'Schematics.Features.SchemeContextMenu',
 'Schematics.Features.SchemeFeature', 'Schematics.Features.Functions.Effects',
 'Schematics.Features.Functions.TextStyle', 'Schematics.Features.Functions.Transforms',
 'Schematics.Features.Utils.MDI', 'Schematics.Features.Utils.ActionsReplacer',
 'Schematics.Features.Utils.Printing', 'Schematics.Features.Observers',
]
fails = 0
for m in mods:
    try:
        importlib.import_module(m)
        print('PASS import', m)
    except Exception:
        fails += 1
        print('FAIL import', m)
        traceback.print_exc()
print('RESULT: %d/%d imports ok' % (len(mods)-fails, len(mods)))
