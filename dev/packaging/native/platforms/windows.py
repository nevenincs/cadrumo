"""Windows SDK, PE relocation and dependency compatibility operations."""

from __future__ import annotations

import importlib
import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from dev._paths import REPO_ROOT

from ..hashing import digest
from .pe import imports as pe_imports
from .windows_verify import verify as windows_verify


def assemble_native(python: Path, packages: Path, native: Path, root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Relocate PE modules and apply the reviewed Windows wheel loader patches."""
    modules: dict[str, str] = {}
    for source in [*python.glob("*.dll"), *(python / "DLLs").glob("*.dll"), *(python / "DLLs").glob("*.pyd")]:
        target = native / source.name
        shutil.copy2(source, target)
        if source.suffix.lower() == ".pyd":
            modules[source.stem] = target.relative_to(root).as_posix()
    relocation = {}
    for source in sorted(packages.rglob("*")):
        if source.suffix.lower() not in {".pyd", ".dll", ".exe"}:
            continue
        relative = source.relative_to(packages)
        target = native / "packages" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)
        relocation[source.relative_to(root).as_posix()] = target.relative_to(root).as_posix()
        if source.suffix.lower() == ".pyd":
            parts = list(relative.parts)
            parts[-1] = parts[-1].split(".")[0]
            if parts[0] in {"win32", "pythonwin"}:
                parts = parts[1:]
            modules[".".join(parts)] = target.relative_to(root).as_posix()
            if parts[0] == "win32comext":
                modules[".".join(["win32com", *parts[1:]])] = target.relative_to(root).as_posix()
    # These pywin32 extension DLLs export ordinary Python module initializers.
    for name in ("pywintypes", "pythoncom"):
        target = native / "packages/pywin32_system32" / f"{name}313.dll"
        if target.is_file():
            modules[name] = target.relative_to(root).as_posix()
    paths = [packages.relative_to(root).as_posix()]
    for pth in packages.glob("*.pth"):
        if pth.name != "pywin32.pth":
            raise ValueError(f"Unreviewed .pth file: {pth.name}")
        for line in pth.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line == "import pywin32_bootstrap":
                continue
            resolved = (packages / line).resolve()
            if not resolved.is_relative_to(packages) or not resolved.is_dir():
                raise ValueError(f"Invalid wheel path directive: {line}")
            paths.append(resolved.relative_to(root).as_posix())
        pth.unlink()
    # ctypesgen checks a file relative to bindings.py before loading it. Project
    # its one concrete DLL location; do not replace ctypes or global import policy.
    bindings = packages / "pypdfium2_raw/bindings.py"
    patches = []
    if bindings.is_file():
        before = digest(bindings)
        source = bindings.read_text(encoding="utf-8")
        old = "libpaths = ('./{prefix}{name}.{suffix}',),"
        relative_dll = (native / "packages/pypdfium2_raw/pdfium.dll").relative_to(root).as_posix()
        new = f"libpaths = (str(pathlib.Path(sys.executable).parent / {relative_dll!r}),),"
        if source.count(old) != 1:
            raise ValueError("Unrecognized pypdfium2 ctypesgen loader")
        bindings.write_text(source.replace(old, new), encoding="utf-8")
        patches.append(
            {
                "file": bindings.relative_to(root).as_posix(),
                "before": before,
                "after": digest(bindings),
                "reason": "Relocated explicit pdfium DLL path",
            }
        )
    com_init = packages / "win32com/__init__.py"
    if com_init.is_file():
        before = digest(com_init)
        source = com_init.read_text(encoding="utf-8")
        old = "if not __frozen:\n    SetupEnvironment()"
        new = (
            "__path__.append(os.path.abspath(os.path.join(__path__[0], '..', 'win32comext')))\n"
            "__gen_path__ = os.path.join(os.environ['XDG_CACHE_HOME'], 'pywin32', 'gen_py')"
        )
        if source.count(old) != 1:
            raise ValueError("Unrecognized pywin32 environment initialization")
        com_init.write_text(source.replace(old, new), encoding="utf-8")
        patches.append(
            {
                "file": com_init.relative_to(root).as_posix(),
                "before": before,
                "after": digest(com_init),
                "reason": "Use bundled COM extensions and user-root cache; exclude host Python registry paths",
            }
        )
    # Entrypoint hosts run from the native directory: no bundled DLL there may shadow a host import.
    bundled = {p.name.casefold() for p in native.glob("*.dll")}
    for host in native.glob("*.exe"):
        shadowed = pe_imports(host) & bundled
        if shadowed:
            raise ValueError(f"Bundled DLLs shadow {host.name} imports: {sorted(shadowed)}")
    loader_files = [p for p in native.rglob("*") if p.suffix.lower() in {".dll", ".pyd"}]
    imported_pyds = {name for p in loader_files for name in pe_imports(p) if name.endswith(".pyd")}
    searched_files = [p for p in loader_files if p.suffix.lower() == ".dll" or p.name.casefold() in imported_pyds]
    missing = imported_pyds - {p.name.casefold() for p in searched_files}
    if missing:
        raise ValueError(f"Missing transitive extension libraries: {sorted(missing)}")
    dll_dirs = sorted({p.parent.relative_to(root).as_posix() for p in searched_files})
    dll_names: dict[str, str] = {}
    for dll in searched_files:
        identity = dll.name.casefold()
        hashed = digest(dll)
        if identity in dll_names and dll_names[identity] != hashed:
            raise ValueError(f"Ambiguous native dependency basename: {dll.name}")
        dll_names[identity] = hashed
    return {
        "modules": modules,
        "dll_directories": dll_dirs,
        "python_paths": paths,
        "relocation": relocation,
        "patches": patches,
    }


def external_probe(destination: Path) -> list[str]:
    """Install a harmless real Windows executable to prove an explicit PATH override."""
    name = "cadrumo-override-probe.exe"
    shutil.copy2(Path(os.environ["SYSTEMROOT"]) / "System32/where.exe", destination / name)
    return [name, "/?"]


def provision_sdk(destination: Path, pin: str, tools: dict[str, Any], contract: dict[str, Any]) -> Path:
    """Acquire and hash-check the official Windows NuGet SDK."""
    archive = destination / f"python.{pin}.nupkg"
    url = tools["cpython_source"].format(version=pin)
    if not url.startswith("https://api.nuget.org/"):
        raise ValueError("CPython SDK must come from the pinned HTTPS NuGet origin")
    if not archive.exists():
        with httpx.stream("GET", url, timeout=120) as response, archive.open("wb") as output:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                output.write(chunk)
    if digest(archive) != tools["cpython_sha256"]:
        raise ValueError("CPython SDK SHA256 mismatch")
    sdk = destination / Path(contract["sdk"]["root"]).parts[0]
    if not sdk.exists():
        with zipfile.ZipFile(archive) as package:
            for member in package.namelist():
                if not (sdk / member).resolve().is_relative_to(sdk):
                    raise ValueError("SDK archive contains an escaping path")
            package.extractall(sdk)
    return destination / str(contract["sdk"]["root"])


def resources(
    destination: Path, version: str, number: int, date: str, tools: Path, entrypoints: dict[str, str]
) -> None:
    """Render the canonical icon and one PE version resource per native executable."""
    if not 0 <= number <= 65535:
        raise ValueError("Windows resource build number must be between 0 and 65535")
    metadata = json.loads((destination / "build.json").read_text(encoding="utf-8"))
    publisher = _rc_string(metadata["publisher"])
    sys.path.insert(0, str(tools))
    renderer = importlib.import_module("resvg_py")
    png = renderer.svg_to_bytes(
        svg_path=str(REPO_ROOT / "docs/_static/cadrumo-favicon.svg"), width=256, height=256, skip_system_fonts=True
    )
    with Image.open(io.BytesIO(png)) as icon:
        icon.save(destination / "cadrumo.ico", format="ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    numeric = ",".join([*version.split(".")[:3], str(number)])
    descriptions = {"interpreter": "CADRUMO controlled Python interpreter"} | {
        f"entrypoint-{name}": description for name, description in entrypoints.items()
    }
    for stem, description in descriptions.items():
        resource = _version_resource(destination, numeric, version, number, date, publisher, _rc_string(description))
        (destination / f"{stem}.rc").write_text(resource, encoding="utf-8")


def _rc_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)[:-1] + '\\0"'


def _version_resource(
    destination: Path, numeric: str, version: str, number: int, date: str, publisher: str, description: str
) -> str:
    return f'''#include <winver.h>
1 ICON "{(destination / "cadrumo.ico").as_posix()}"
1 VERSIONINFO
FILEVERSION {numeric}
PRODUCTVERSION {numeric}
FILEFLAGSMASK VS_FFI_FILEFLAGSMASK
#if CADRUMO_DEVELOPMENT
FILEFLAGS VS_FF_DEBUG
#else
FILEFLAGS 0
#endif
FILEOS VOS_NT_WINDOWS32
FILETYPE VFT_APP
BEGIN
 BLOCK "StringFileInfo"
 BEGIN
  BLOCK "040904b0"
  BEGIN
   VALUE "CompanyName", {publisher}
   VALUE "ProductName", "CADRUMO\\0"
   VALUE "FileDescription", {description}
   VALUE "FileVersion", "{version}.{number}\\0"
   VALUE "ProductVersion", "{version}\\0"
   VALUE "BuildDate", "{date}\\0"
  END
 END
 BLOCK "VarFileInfo"
 BEGIN
  VALUE "Translation", 0x0409, 1200
 END
END
'''


def verify(package: Path, *, destination: Path | None, product: bool, build_root: Path | None) -> None:
    """Run the Windows hostile-loader acceptance suite."""
    windows_verify(package, destination=destination, product=product, build_root=build_root)


def analyze_trace(directory: Path) -> None:
    """Check lossless Windows kernel-file events for the scoped process tree."""
    from .windows_trace_analysis import analyze

    analyze(directory)
