"""pivy (Coin3D bindings) ships inside the FreeCAD installation and has no
type stubs; this stubPath entry gives the language server a typed view of
the only surface the workbench uses: ``from pivy import coin`` inside
view-provider attach() methods."""

from typing import Any

coin: Any
