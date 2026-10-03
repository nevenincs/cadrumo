"""Install the assembler's native-module map without site or .pth execution."""

import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path

_DLL_HANDLES = []


class NativeModules(importlib.abc.MetaPathFinder):
    """Resolve only extension identities recorded by the package assembler."""

    def __init__(self, root, modules):
        """Retain the package root and its exact extension inventory."""
        self.root = root
        self.modules = modules

    def find_spec(self, fullname, path=None, target=None):
        """Return a qualified extension spec or defer unrelated imports."""
        relative = self.modules.get(fullname)
        if relative is None:
            return None
        location = self.root / relative
        if not location.is_file():
            raise ImportError(f"Missing bundled native module {fullname}: {location}")
        loader = importlib.machinery.ExtensionFileLoader(fullname, str(location))
        return importlib.util.spec_from_file_location(fullname, location, loader=loader)


def install():
    """Apply explicit wheel paths and retain native search handles until exit."""
    root = Path(sys.executable).parent
    manifest = json.loads((root / "data/native-modules.json").read_text(encoding="utf-8"))
    for relative in manifest["dll_directories"]:
        directory = root / relative
        if not directory.is_dir():
            raise ImportError(f"Missing bundled native directory: {directory}")
        _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    for relative in manifest["python_paths"]:
        sys.path.append(str(root / relative))
    sys.meta_path.insert(0, NativeModules(root, manifest["modules"]))
