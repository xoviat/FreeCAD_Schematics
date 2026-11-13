#!/usr/bin/env python3
"""Install the Schematics workbench into the local FreeCAD user Mod directory.

Usage:
    python install.py [MOD_DIR]

MOD_DIR defaults to the Mod folder of the newest local FreeCAD install:
  Windows : %APPDATA%\\FreeCAD\\<version>\\Mod   (e.g. v1-1 for FreeCAD 1.1)
            %APPDATA%\\FreeCAD\\Mod             (when no versioned dir exists)
  macOS   : ~/Library/Application Support/FreeCAD/Mod
  Linux   : $XDG_DATA_HOME/FreeCAD/Mod, defaulting to ~/.local/share/FreeCAD/Mod
            (~/.FreeCAD/Mod when only the legacy layout exists)

Only the runtime payload is copied (Init.py, InitGui.py, SCUtils.py and the
Schematics/ Icons/ Art/ Symbols/ Templates/ folders); dev tooling such as
mypy.ini and the verify_*.py scripts stays out. An existing Schematics
folder at the destination is replaced. Restart FreeCAD to load the workbench.
"""

import os
import re
import shutil
import sys

# Runtime files/directories that make up the workbench itself.
PAYLOAD = [
    "Init.py",
    "InitGui.py",
    "SCUtils.py",
    "Schematics",
    "Icons",
    "Art",
    "Symbols",
    "Templates",
    "README.md",
]

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def _version_key(name):
    """Sort key for versioned data dirs: 'v1-1' -> (1, 1), 'v0-21' -> (0, 21)."""
    parts = re.findall(r"\d+", name)
    return tuple(int(p) for p in parts) if parts else ()


def _windows_mod_dir():
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    base = os.path.join(appdata, "FreeCAD")
    if not os.path.isdir(base):
        return os.path.join(base, "Mod")
    versioned = [
        d for d in os.listdir(base)
        if d.startswith("v") and re.search(r"\d", d)
        and os.path.isdir(os.path.join(base, d))
    ]
    # Prefer the newest versioned data dir that already has a Mod folder,
    # so an old data dir never wins over the active FreeCAD version.
    with_mod = [d for d in versioned if os.path.isdir(os.path.join(base, d, "Mod"))]
    candidates = sorted(with_mod or versioned, key=_version_key, reverse=True)
    if candidates:
        return os.path.join(base, candidates[0], "Mod")
    return os.path.join(base, "Mod")


def _linux_mod_dir():
    home = os.path.expanduser("~")
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    modern = os.path.join(xdg, "FreeCAD", "Mod")
    legacy = os.path.join(home, ".FreeCAD", "Mod")
    # Prefer the modern layout whenever its FreeCAD dir exists; fall back to
    # the legacy ~/.FreeCAD layout only if that is all that is present.
    if os.path.isdir(os.path.dirname(modern)) or not os.path.isdir(legacy):
        return modern
    return legacy


def find_mod_dir():
    if sys.platform == "win32":
        return _windows_mod_dir()
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", "FreeCAD", "Mod"
        )
    return _linux_mod_dir()


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(argv) > 1:
        print("usage: python install.py [MOD_DIR]", file=sys.stderr)
        return 2

    src = os.path.dirname(os.path.abspath(__file__))
    for required in ("Init.py", "InitGui.py", "Schematics"):
        if not os.path.exists(os.path.join(src, required)):
            print(f"error: {required} not found next to install.py; "
                  "run this script from the workbench repository", file=sys.stderr)
            return 1

    mod_dir = argv[0] if argv else find_mod_dir()
    dest = os.path.join(mod_dir, "Schematics")

    if os.path.isdir(dest):
        shutil.rmtree(dest)
    elif os.path.exists(dest):
        os.remove(dest)
    os.makedirs(dest, exist_ok=True)

    copied = 0
    for item in PAYLOAD:
        s = os.path.join(src, item)
        if not os.path.exists(s):
            continue  # optional payload piece (e.g. README.md in a trimmed copy)
        d = os.path.join(dest, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, ignore=IGNORE)
        else:
            shutil.copy2(s, d)
        copied += 1

    files = sum(len(f) for _, _, f in os.walk(dest))
    print(f"Installed {copied} payload items ({files} files) -> {dest}")
    print("Restart FreeCAD to load the Schematics workbench.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
