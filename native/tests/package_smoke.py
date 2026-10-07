"""Exercise the assembled distribution using its own interpreter."""

import importlib
import importlib.metadata
import importlib.util
import json
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pikepdf

from cadrumo.core.config import configured_authority_root
from cadrumo.domain.calculations.registry.authority_store import require_authority_store_available


def require(condition: bool, message: str) -> None:
    """Keep acceptance checks active even when invoked with Python optimization."""
    if not condition:
        raise AssertionError(message)


root = Path(sys.argv[1]).resolve(strict=True)
manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
require(sys.pycache_prefix is None, "Packaged bytecode lookup must stay beside its source")
for relative in manifest["files"]:
    if relative.endswith(".py"):
        cache = Path(importlib.util.cache_from_source(str(root / relative)))
        require(
            cache.relative_to(root).as_posix() in manifest["files"],
            f"Bundled source has no inventoried bytecode: {relative}",
        )
entrypoint_smoke = runpy.run_path(str(Path(__file__).with_name("entrypoint_smoke.py")))
entrypoint_smoke["verify_entrypoints"](
    root,
    manifest["layout"]["entrypoints"],
    manifest["layout"]["paths"]["native"],
    manifest["layout"]["entrypoint_suffix"],
)
native_manifest = json.loads((root / manifest["layout"]["files"]["native_manifest"]).read_text(encoding="utf-8"))
for module in sorted(native_manifest["modules"]):
    try:
        for prerequisite in manifest["layout"].get("native_smoke_prerequisites", {}).get(module, []):
            importlib.import_module(prerequisite)
        importlib.import_module(module)
    except Exception as error:
        raise RuntimeError(f"Bundled native import failed: {module}") from error
for distribution, modules in manifest["smoke_modules"].items():
    require(importlib.metadata.version(distribution) == manifest["distributions"][distribution], distribution)
    for module in modules:
        importlib.import_module(module)
for module in (
    "ssl",
    "sqlite3",
    "bz2",
    "lzma",
    "multiprocessing",
    "encodings.utf_8",
    "ctypes",
    "pydantic_core._pydantic_core",
    "cryptography.hazmat.bindings._rust",
    "lxml.etree",
    "PIL._imaging",
    "pikepdf._core",
    "_cffi_backend",
    "rtoml",
    "yaml._yaml",
    "rpds.rpds",
):
    importlib.import_module(module)
with zipfile.ZipFile(root / manifest["layout"]["paths"]["stdlib"]) as library:
    require("encodings/__init__.pyc" in library.namelist(), "Standard library is not bytecode ZIP")
    require(
        not any(n.startswith(("test/", "ensurepip/", "tkinter/", "idlelib/")) for n in library.namelist()),
        "Unpruned stdlib",
    )
require(
    not any((root / p).exists() for p in ("Lib", "Libs", "Scripts", "python/Lib")), "Unexpected SDK directories shipped"
)
authority_root = configured_authority_root()
if authority_root is None:
    raise AssertionError("Bundled authority root is unavailable")
require_authority_store_available(authority_root / "authority.current.json")
if specialized_smoke := manifest["layout"].get("smoke_test"):
    runpy.run_path(str(Path(__file__).with_name(specialized_smoke)))
with pikepdf.Pdf.new() as document:
    document.add_blank_page()
require(
    importlib.metadata.version("cadrumo") == importlib.metadata.version("cadrumo-data-official"),
    "Official cohort mismatch",
)
require(
    importlib.metadata.version("cadrumo") == importlib.metadata.version("cadrumo-data-manuals"),
    "Manual cohort mismatch",
)
require(bool(sys.flags.isolated and sys.flags.no_site), "Interpreter is not isolated")
require(sys.version_info[:2] == (3, 13), "Wrong CPython minor version")
child = subprocess.check_output(
    [sys.executable, "-c", "import json,sys; print(json.dumps([sys.executable,sys.flags.isolated]))"], text=True
)
executable, isolated = json.loads(child)
require(Path(executable) == Path(sys.executable) and isolated == 1, "Child interpreter escaped package")
sys.stdout.write(f"CADRUMO {importlib.metadata.version('cadrumo')}: {sys.executable}\n")
