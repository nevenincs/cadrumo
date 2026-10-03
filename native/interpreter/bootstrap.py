"""Install the assembler's native-module map without site or .pth execution."""

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path

_DLL_HANDLES = []
LAYOUT = {}


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ImportError(f"Invalid package-relative path: {relative}")
    return path


def verify(full=False):
    """Refuse mixed builds and missing/damaged runtime inputs; optionally hash every file."""
    root = Path(sys.executable).parent.resolve()
    files = LAYOUT["files"]
    manifest = json.loads(_inside(root, files["package_manifest"]).read_text(encoding="utf-8"))
    identity = manifest["build"]
    for key in ("version", "build_number", "build_date"):
        if str(identity[key]) != str(sys.cadrumo_build[key]):
            raise ImportError(f"Incompatible CADRUMO package build: {key}")
    if identity["python"] != ".".join(map(str, sys.version_info[:3])):
        raise ImportError("Incompatible CADRUMO CPython version")
    for relative in manifest["files"]:
        if not _inside(root, relative).is_file():
            raise ImportError(f"Missing bundled file: {relative}")
    if full:
        observed = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        expected = set(manifest["files"]) | {files["package_manifest"]}
        if observed != expected:
            raise ImportError(f"Unexpected package files: {observed - expected}")
    required = manifest["files"] if full else manifest["startup_files"]
    for relative in required:
        path = _inside(root, relative)
        if not path.is_file():
            raise ImportError(f"Missing bundled file: {relative}")
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != manifest["files"][relative]:
            raise ImportError(f"Damaged or mixed bundled file: {relative}")


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
    root = Path(sys.executable).parent.resolve()
    verify()
    manifest = json.loads(_inside(root, LAYOUT["files"]["native_manifest"]).read_text(encoding="utf-8"))
    for relative in manifest["dll_directories"]:
        directory = _inside(root, relative)
        if not directory.is_dir():
            raise ImportError(f"Missing bundled native directory: {directory}")
        _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    path_file = _inside(root, LAYOUT["files"]["path_file"])
    actual_paths = []
    for line in path_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("import ") or line.startswith("import\t"):
            raise ImportError("Executable .pth directives are forbidden")
        directory = _inside(root, (path_file.parent / line).relative_to(root))
        if not directory.is_dir():
            raise ImportError(f"Missing package path: {directory}")
        actual_paths.append(directory.relative_to(root).as_posix())
        if str(directory) not in sys.path:
            sys.path.append(str(directory))
    if actual_paths != manifest["python_paths"]:
        raise ImportError("Package .pth does not match the assembled import contract")
    sys.meta_path.insert(0, NativeModules(root, manifest["modules"]))
