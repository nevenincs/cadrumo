"""Assemble a fresh Windows interpreter package from explicit build inputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ..uv_constraints import export_runtime_constraints
from .stdlib import bundle as bundle_stdlib


def digest(path: Path) -> str:
    """Hash one build input or delivered file."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def assemble(
    python: Path, dependencies: Path, build: Path, destination: Path, metadata: Path, *, development: bool = False
) -> None:
    """Relocate native modules while retaining their qualified import names."""
    root = destination.resolve()
    if root.exists():
        raise FileExistsError(f"Assembly requires a fresh destination: {root}")
    contract = json.loads((REPO_ROOT / "native/package-layout.json").read_text(encoding="utf-8"))
    layout, files = contract["paths"], contract["files"]
    allowed = set(PRODUCT_IDENTITY.cohort_distributions)
    for pin in export_runtime_constraints(repo_root=REPO_ROOT):
        requirement = Requirement(pin)
        if requirement.marker is None or requirement.marker.evaluate():
            allowed.add(canonicalize_name(requirement.name))
    distributions = {
        canonicalize_name(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions(path=[str(dependencies)])
    }
    if set(distributions) != allowed:
        raise ValueError(f"Production dependency closure mismatch: {set(distributions) ^ allowed}")
    lib = root / layout["stdlib"]
    packages = root / layout["packages"]
    native = root / layout["native"]
    native.mkdir(parents=True)
    bootstrap = (REPO_ROOT / "native/interpreter/bootstrap.py").read_text(encoding="utf-8")
    if bootstrap.count("LAYOUT = {}") != 1:
        raise ValueError("Missing bootstrap layout projection marker")
    bootstrap = bootstrap.replace("LAYOUT = {}", f"LAYOUT = {contract!r}")
    identity = json.loads(metadata.read_text(encoding="utf-8"))
    bundle_stdlib(python / "Lib", lib, contract["stdlib_exclude"], bootstrap.encode(), identity["python"])
    shutil.copytree(dependencies, packages, ignore=shutil.ignore_patterns("__pycache__", "bin", "tests"))
    shutil.copy2(build / "python.exe", root / layout["executable"])
    if development:
        shutil.copy2(build / files["development_executable"], root / files["development_executable"])
    shutil.copy2(build / files["bridge"], native)
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
    paths = [packages.relative_to(root).as_posix()]
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
    (root / files["native_manifest"]).write_text(
        json.dumps({"modules": modules, "dll_directories": dll_dirs, "python_paths": paths}, indent=2),
        encoding="utf-8",
    )
    authority = packages / "cadrumo/_data/registry/authority"
    if authority.is_dir():
        shutil.move(authority, root / layout["authority"])
    path_file = root / files["path_file"]
    path_file.write_text(
        "# CADRUMO package-relative import paths; executable directives are forbidden.\n"
        + "\n".join((root / p).relative_to(path_file.parent).as_posix() for p in paths)
        + "\n",
        encoding="utf-8",
    )
    license_file = root / files["python_license"]
    license_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(python / "LICENSE.txt", license_file)
    shutil.copy2(metadata, root / files["build_metadata"])
    startup_files = [
        layout["executable"],
        layout["stdlib"],
        files["path_file"],
        files["build_metadata"],
        files["native_manifest"],
        (native / files["bridge"]).relative_to(root).as_posix(),
        (native / files["runtime"]).relative_to(root).as_posix(),
    ]
    if development:
        startup_files.append(files["development_executable"])
    manifest = {
        "build": identity,
        "layout": contract,
        "startup_files": startup_files,
        "distributions": distributions,
        "python": (REPO_ROOT / "dev/packaging/release-python-version").read_text().strip(),
        "lock_sha256": digest(REPO_ROOT / "uv.lock"),
        "relocation": relocation,
        "patches": patches,
        "files": {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()},
    }
    (root / files["package_manifest"]).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Assembled {root}: {len(modules)} relocated extension modules")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    assemble(args.python, args.dependencies, args.build, args.destination, args.metadata, development=args.development)
