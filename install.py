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
mypy.ini and the verify_*.py scripts stays out. Compiled translations
(translations/*.qm) are placed in the FreeCAD user app-data
translations/ directory (the parent of Mod/), where FreeCAD's Translator
auto-loads *_<locale>.qm files for the configured language.
The new tree is built and size-verified next to the destination, then
swapped in, so a failed copy exits non-zero with a clear stderr message
and never corrupts an existing installation. Restart FreeCAD to load
the workbench.
"""

import os
import re
import shutil
import sys
import time

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


def _verify_copy(src: str, tmp: str) -> None:
    """Every copied file must exist with the source's size - catches a
    silent partial copy (locked file, disk full) before the swap."""
    for root, _dirs, names in os.walk(tmp):
        for name in names:
            rel = os.path.relpath(os.path.join(root, name), tmp)
            source = os.path.join(src, rel)
            if not os.path.exists(source):
                continue
            if os.path.getsize(source) != os.path.getsize(os.path.join(root, name)):
                raise OSError("size mismatch after copy: %s" % rel)


def _remove_path(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def _swap_into_place(tmp: str, dest: str) -> None:
    """Replace dest with tmp.  The old install only comes down after the
    new tree is fully built, so a failed copy never corrupts it."""
    for attempt in (0, 1):
        try:
            _remove_path(dest)
            break
        except OSError:
            if attempt:
                raise
            time.sleep(0.4)   # transient Windows file lock: retry once
    os.rename(tmp, dest)


def main(argv: list[str]) -> int:
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
    tmp = dest + ".new"

    # Build the new install next to the old one, verify it, then swap.
    # Any failure leaves the existing installation untouched and exits
    # non-zero with a clear message on stderr.
    try:
        _remove_path(tmp)
        os.makedirs(tmp, exist_ok=True)   # file items copy into it first
        copied = 0
        for item in PAYLOAD:
            s = os.path.join(src, item)
            if not os.path.exists(s):
                continue  # optional payload piece (e.g. README.md in a trimmed copy)
            d = os.path.join(tmp, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, ignore=IGNORE)
            else:
                shutil.copy2(s, d)
            copied += 1
        _verify_copy(src, tmp)
        _swap_into_place(tmp, dest)
    except (OSError, shutil.Error) as exc:
        try:
            _remove_path(tmp)
        except OSError:
            pass
        print("install FAILED: %s" % exc, file=sys.stderr)
        print("The existing installation was left untouched (if any).",
              file=sys.stderr)
        return 1

    files = sum(len(f) for _, _, f in os.walk(dest))
    print(f"Installed {copied} payload items ({files} files) -> {dest}")

    # Compiled Qt translations: FreeCAD's Translator scans
    # <user app-data>/translations for *_<locale>.qm (the parent of the
    # Mod directory), so put them there for the configured language.
    qm_src = os.path.join(src, "translations")
    if os.path.isdir(qm_src):
        translations_dir = os.path.join(os.path.dirname(mod_dir), "translations")
        try:
            os.makedirs(translations_dir, exist_ok=True)
            qm_count = 0
            for name in sorted(os.listdir(qm_src)):
                if name.endswith(".qm"):
                    shutil.copy2(
                        os.path.join(qm_src, name),
                        os.path.join(translations_dir, name),
                    )
                    qm_count += 1
        except OSError as exc:
            print("install FAILED (translations): %s" % exc, file=sys.stderr)
            return 1
        if qm_count:
            print(f"Installed {qm_count} translation(s) -> {translations_dir}")

    print("Restart FreeCAD to load the Schematics workbench.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
