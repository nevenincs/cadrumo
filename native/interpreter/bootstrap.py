"""Install the assembler's native-module map without site or .pth execution."""

import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from typing import override

_cadrumo_native = importlib.import_module("_cadrumo_native")

LAYOUT = {}


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ImportError(f"Invalid package-relative path: {relative}")
    return path


def _delegated_inventory(root, manifest):
    """Merge each hash-checked delegated inventory strictly beneath its prefix; refuse collisions."""
    inventory = dict(manifest["files"])
    delegated = manifest.get("delegated_inventories", {})
    # Documentation may be absent only because the manifest says so; the inventory must agree.
    statement = manifest.get("user_docs")
    directory = statement.get("directory") if isinstance(statement, dict) else None
    if not isinstance(directory, str) or not directory or not isinstance(statement.get("bundled"), bool):
        raise ImportError("Package manifest does not state whether user documentation is bundled")
    if statement["bundled"] != (directory in delegated) or (
        not statement["bundled"] and any(name.startswith(f"{directory}/") for name in inventory)
    ):
        raise ImportError(f"Package documentation statement disagrees with its inventory: {directory}")
    for prefix, member in delegated.items():
        if member not in manifest["files"] or not member.startswith(f"{prefix}/"):
            raise ImportError(f"Invalid delegated inventory: {member}")
        path = _inside(root, member)
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != manifest["files"][member]:
                raise ImportError(f"Damaged or mixed bundled file: {member}")
        base = _inside(root, prefix)
        for relative, digest in json.loads(path.read_text(encoding="utf-8"))["files"].items():
            if "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
                raise ImportError(f"Invalid delegated package path: {relative}")
            _inside(base, relative)
            key = f"{prefix}/{relative}"
            if key in inventory:
                raise ImportError(f"Delegated package path collides with a package file: {key}")
            inventory[key] = digest
    return inventory


def verify(full=False):
    """Refuse mixed builds and missing/damaged runtime inputs; optionally hash every file."""
    root = (Path(sys.executable).parent / LAYOUT["package_root_from_executable"]).resolve()
    files = LAYOUT["files"]
    manifest = json.loads(_inside(root, files["package_manifest"]).read_text(encoding="utf-8"))
    identity = manifest["build"]
    for key in ("version", "build_number", "build_date"):
        if str(identity[key]) != str(vars(sys)["cadrumo_build"][key]):
            raise ImportError(f"Incompatible CADRUMO package build: {key}")
    if identity["python"] != ".".join(map(str, sys.version_info[:3])):
        raise ImportError("Incompatible CADRUMO CPython version")
    for relative in manifest["files"]:
        if not _inside(root, relative).is_file():
            raise ImportError(f"Missing bundled file: {relative}")
    inventory = _delegated_inventory(root, manifest) if full else manifest["files"]
    if full:
        observed = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        expected = set(inventory) | {files["package_manifest"]}
        if observed != expected:
            raise ImportError(f"Unexpected package files: {observed - expected}")
    required = inventory if full else manifest["startup_files"]
    for relative in required:
        path = _inside(root, relative)
        if not path.is_file():
            raise ImportError(f"Missing bundled file: {relative}")
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != inventory[relative]:
            raise ImportError(f"Damaged or mixed bundled file: {relative}")


class NativeModules(importlib.abc.MetaPathFinder):
    """Resolve only extension identities recorded by the package assembler."""

    def __init__(self, root, modules):
        """Retain the package root and its exact extension inventory."""
        self.root = root
        self.modules = modules

    @override
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


def run_entrypoint(name):
    """Run one declared console script exactly as its installed wrapper would."""
    if name not in LAYOUT["entrypoints"]:
        raise ImportError(f"Undeclared console entrypoint: {name}")
    # Deferred so ordinary interpreter startup does not load metadata discovery.
    import importlib.metadata

    matches = importlib.metadata.entry_points(group="console_scripts", name=name)
    if len(matches) != 1:
        raise ImportError(f"Console entrypoint must resolve exactly once: {name}")
    sys.argv[0] = name
    raise SystemExit(next(iter(matches)).load()())


def install():
    """Apply explicit wheel paths and retain native search handles until exit."""
    root = (Path(sys.executable).parent / LAYOUT["package_root_from_executable"]).resolve()
    verify()
    manifest = json.loads(_inside(root, LAYOUT["files"]["native_manifest"]).read_text(encoding="utf-8"))
    _cadrumo_native.prepare(root, manifest)
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
