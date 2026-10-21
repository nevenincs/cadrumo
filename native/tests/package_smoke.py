"""Exercise the assembled distribution using its own interpreter."""

import importlib
import importlib.metadata
import importlib.util
import json
import runpy
import secrets
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pikepdf

from cadrumo.adapters.persistence.storage.custody.kdf_supervision import (
    fixed_profile_kdf_fallback,
    wrap_profile_custody_password_material,
)
from cadrumo.core.config import Settings, configured_authority_root
from cadrumo.domain.calculations.registry.authority_store import require_authority_store_available


def require(condition: bool, message: str) -> None:
    """Keep acceptance checks active even when invoked with Python optimization."""
    if not condition:
        raise AssertionError(message)


root = Path(sys.argv[1]).resolve(strict=True)
manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
temporary_root = Settings().cadrumo_temp_dir
temporary_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="cadrumo-package-kdf-", dir=temporary_root) as neutral:
    settings = Settings(cadrumo_local_storage_root=Path(neutral) / "state")
    wrapped = wrap_profile_custody_password_material(
        secret=secrets.token_urlsafe(32),
        dek=secrets.token_bytes(32),
        kdf=fixed_profile_kdf_fallback(salt=secrets.token_bytes(16)),
        associated_data=b"cadrumo-package-kdf-smoke/v1",
        settings=settings,
        timeout_seconds=60,
    )
    require(bool(wrapped.nonce_b64 and wrapped.ciphertext_b64 and wrapped.tag_b64), "Packaged KDF wrap failed")
for helper in ("exit", "quit"):
    result = subprocess.run(
        [sys.executable, "-i", "-q"],
        input=(
            "import sys; print('isolated:', sys.flags.isolated, sys.flags.no_site, sys.flags.no_user_site)\n"
            f"{helper}(17)\n"
        ),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    require(result.returncode == 17, f"Interactive {helper} failed: {result.stderr}")
    require("isolated: 1 0 1" in result.stdout, "Site initialization or interpreter isolation differs")
require("site" in sys.modules, "Interpreter did not initialize site")
require(not sys.modules["site"].ENABLE_USER_SITE, "Interpreter enabled ambient user packages")
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
require(bool(sys.flags.isolated and sys.flags.no_user_site), "Interpreter is not isolated")
require(sys.version_info[:2] == (3, 13), "Wrong CPython minor version")
child = subprocess.check_output(
    [sys.executable, "-c", "import json,sys; print(json.dumps([sys.executable,sys.flags.isolated]))"], text=True
)
executable, isolated = json.loads(child)
require(Path(executable) == Path(sys.executable) and isolated == 1, "Child interpreter escaped package")
sys.stdout.write(f"CADRUMO {importlib.metadata.version('cadrumo')}: {sys.executable}\n")
