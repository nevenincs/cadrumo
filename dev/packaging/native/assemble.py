"""Assemble a fresh Windows interpreter package from explicit build inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from dev._paths import REPO_ROOT


def digest(path: Path) -> str:
    """Hash one build input or delivered file."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def assemble(python: Path, dependencies: Path, build: Path, destination: Path) -> None:
    """Relocate native modules while retaining their qualified import names."""
    root = destination.resolve()
    if root.exists():
        raise FileExistsError(f"Assembly requires a fresh destination: {root}")
    layout = json.loads((REPO_ROOT / "native/package-layout.json").read_text(encoding="utf-8"))["paths"]
    lib = root / layout["stdlib"]
    packages = root / layout["packages"]
    native = root / layout["native"]
    native.mkdir(parents=True)
    shutil.copytree(
        python / "Lib",
        lib,
        ignore=shutil.ignore_patterns(
            "site-packages", "__pycache__", "test", "tests", "idlelib", "tkinter", "ensurepip"
        ),
    )
    shutil.copytree(dependencies, packages, ignore=shutil.ignore_patterns("__pycache__", "bin"))
    shutil.copy2(build / "python.exe", root / layout["executable"])
    shutil.copy2(build / "cadrumo_python.dll", native)
    shutil.copy2(REPO_ROOT / "native/interpreter/bootstrap.py", lib / "_cadrumo_bootstrap.py")
    for source in [*python.glob("*.dll"), *(python / "DLLs").glob("*.dll"), *(python / "DLLs").glob("*.pyd")]:
        shutil.copy2(source, native / source.name)
    modules: dict[str, str] = {}
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
    paths = []
    for pth in packages.glob("*.pth"):
        if pth.name != "pywin32.pth":
            raise ValueError(f"Unreviewed .pth file: {pth.name}")
        for line in pth.read_text().splitlines():
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
        new = "libpaths = (str(pathlib.Path(sys.executable).parent / 'bin/python/packages/pypdfium2_raw/pdfium.dll'),),"
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
    dll_dirs = sorted({p.parent.relative_to(root).as_posix() for p in native.rglob("*.dll")})
    dll_names: dict[str, str] = {}
    for dll in native.rglob("*.dll"):
        identity = dll.name.casefold()
        hashed = digest(dll)
        if identity in dll_names and dll_names[identity] != hashed:
            raise ValueError(f"Ambiguous native dependency basename: {dll.name}")
        dll_names[identity] = hashed
    data = root / "data"
    data.mkdir(exist_ok=True)
    (data / "native-modules.json").write_text(
        json.dumps({"modules": modules, "dll_directories": dll_dirs, "python_paths": paths}, indent=2),
        encoding="utf-8",
    )
    authority = packages / "cadrumo/_data/registry/authority"
    if authority.is_dir():
        shutil.move(authority, root / layout["authority"])
    shutil.copy2(python / "LICENSE.txt", root / "CPython-LICENSE.txt")
    manifest = {
        "python": (REPO_ROOT / "dev/packaging/release-python-version").read_text().strip(),
        "lock_sha256": digest(REPO_ROOT / "uv.lock"),
        "relocation": relocation,
        "patches": patches,
        "files": {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()},
    }
    (data / "package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Assembled {root}: {len(modules)} relocated extension modules")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    assemble(args.python, args.dependencies, args.build, args.destination)
