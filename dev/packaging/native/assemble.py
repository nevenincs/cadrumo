"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ..uv_constraints import export_runtime_constraints
from .docs_stage import verified_stage
from .hashing import digest
from .layout import backend, entrypoint_files, load_layout
from .package_inventory import DELEGATED_INVENTORIES, USER_DOCS, package_inventory
from .stdlib import bundle as bundle_stdlib


def assemble(
    python: Path,
    dependencies: Path,
    build: Path,
    destination: Path,
    metadata: Path,
    user_docs: Path | None,
    *,
    development: bool = False,
) -> None:
    """Relocate native modules while retaining their qualified import names."""
    root = destination.resolve()
    if root.exists():
        raise FileExistsError(f"Assembly requires a fresh destination: {root}")
    contract = load_layout()
    layout, files = contract["paths"], contract["files"]
    allowed = set(PRODUCT_IDENTITY.cohort_distributions)
    requirements = {}
    for pin in export_runtime_constraints(repo_root=REPO_ROOT):
        requirement = Requirement(pin)
        if requirement.marker is None or requirement.marker.evaluate():
            name = canonicalize_name(requirement.name)
            allowed.add(name)
            requirements[name] = requirement.specifier
    installed = list(importlib.metadata.distributions(path=[str(dependencies)]))
    distributions = {
        canonicalize_name(distribution.metadata["Name"]): distribution.version for distribution in installed
    }
    if set(distributions) != allowed:
        raise ValueError(f"Production dependency closure mismatch: {set(distributions) ^ allowed}")
    for name, specifier in requirements.items():
        if distributions[name] not in specifier:
            raise ValueError(f"Production dependency version differs from lock: {name} {distributions[name]}")
    smoke_modules = {}
    for distribution in installed:
        name = canonicalize_name(distribution.metadata["Name"])
        if name in PRODUCT_IDENTITY.companion_distributions:
            smoke_modules[name] = [PRODUCT_IDENTITY.companion_namespace]
            continue
        if name in contract["smoke_modules"]:
            smoke_modules[name] = contract["smoke_modules"][name]
            continue
        candidates = []
        for member in distribution.files or ():
            parts = list(member.parts)
            if member.suffix != ".py" or any(p in {"tests", "test", "__main__.py"} for p in parts):
                continue
            parts[-1] = member.stem
            if parts[-1] == "__init__":
                parts.pop()
            if parts and all(p.isidentifier() for p in parts):
                candidates.append(parts)
        if not candidates:
            raise ValueError(f"No reviewed Python import surface for distribution {name}")
        selected = min(candidates, key=lambda parts: (len(parts), parts))
        smoke_modules[name] = [".".join(selected)]
    lib = root / layout["stdlib"]
    lib.parent.mkdir(parents=True, exist_ok=True)
    packages = root / layout["packages"]
    native = root / layout["native"]
    native.mkdir(parents=True)
    bootstrap = (REPO_ROOT / "native/interpreter/bootstrap.py").read_text(encoding="utf-8")
    if bootstrap.count("LAYOUT = {}") != 1:
        raise ValueError("Missing bootstrap layout projection marker")
    bootstrap = bootstrap.replace("LAYOUT = {}", f"LAYOUT = {contract!r}")
    build_identity = json.loads(metadata.read_text(encoding="utf-8"))
    bundle_stdlib(
        python / contract["sdk"]["stdlib"],
        lib,
        contract["stdlib_exclude"],
        {
            "_cadrumo_bootstrap": bootstrap.encode(),
            "_cadrumo_native": (REPO_ROOT / "native" / contract["bootstrap"]).read_bytes(),
        },
        build_identity["python"],
    )

    def omit_development(directory: str, names: list[str]) -> set[str]:
        excluded = {"__pycache__", "tests"}
        if Path(directory).resolve() == dependencies.resolve():
            excluded.add("bin")
        return set(names) & excluded

    shutil.copytree(dependencies, packages, ignore=omit_development)
    pruned = []
    for exclusion in contract.get("package_exclusions", []):
        matches = list(packages.glob(exclusion["pattern"]))
        if not matches:
            raise ValueError(f"Package exclusion no longer matches: {exclusion['pattern']}")
        for member in matches:
            if not member.resolve().is_relative_to(packages.resolve()) or not member.is_file():
                raise ValueError(f"Invalid package exclusion: {member}")
            pruned.append(
                {"file": member.relative_to(root).as_posix(), "sha256": digest(member), "reason": exclusion["reason"]}
            )
            member.unlink()
    executable = root / layout["executable"]
    executable.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / executable.name, executable)
    # The native platform context derives the package root from each executable's directory.
    entrypoints = sorted(entrypoint_files(contract).values())
    for name in entrypoints:
        shutil.copy2(build / name, executable.parent / name)
    if development:
        development_executable = root / files["development_executable"]
        development_executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / development_executable.name, development_executable)
    shutil.copy2(build / files["bridge"], native)
    native_manifest = backend(contract).assemble_native(python, packages, native, root, contract)
    modules = native_manifest["modules"]
    paths = native_manifest["python_paths"]
    relocation = native_manifest.pop("relocation")
    patches = native_manifest.pop("patches")
    for key in ("native_manifest", "build_metadata", "package_manifest", "path_file"):
        (root / files[key]).parent.mkdir(parents=True, exist_ok=True)
    (root / files["native_manifest"]).write_text(
        json.dumps(native_manifest, indent=2),
        encoding="utf-8",
    )
    authority = packages / "cadrumo/_data/registry/authority"
    if authority.is_dir():
        authority_destination = root / layout["authority"]
        authority_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(authority, authority_destination)
    docs_declaration = contract["user_docs"]
    docs_prefix = f"{layout['docs']}/{docs_declaration['directory']}"
    docs_manifest = f"{docs_prefix}/{docs_declaration['manifest']}"
    if user_docs is not None:
        shutil.copytree(verified_stage(user_docs, docs_declaration), root / docs_prefix)
    path_file = root / files["path_file"]
    path_file.write_text(
        "# CADRUMO package-relative import paths; executable directives are forbidden.\n"
        + "\n".join(Path(os.path.relpath(root / p, path_file.parent)).as_posix() for p in paths)
        + "\n",
        encoding="utf-8",
    )
    license_file = root / files["python_license"]
    license_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(python / contract["sdk"]["license"], license_file)
    shutil.copy2(metadata, root / files["build_metadata"])
    startup_files = [
        layout["executable"],
        *((executable.parent / name).relative_to(root).as_posix() for name in entrypoints),
        layout["stdlib"],
        files["path_file"],
        files["build_metadata"],
        files["native_manifest"],
        (native / files["bridge"]).relative_to(root).as_posix(),
        (native / files["runtime"]).relative_to(root).as_posix(),
    ]
    if development:
        startup_files.append(files["development_executable"])
    if any(name.startswith(f"{docs_prefix}/") for name in startup_files):
        raise ValueError("Startup files must not belong to a delegated inventory")
    manifest = {
        "build": build_identity,
        "layout": contract,
        "startup_files": startup_files,
        "distributions": distributions,
        "smoke_modules": smoke_modules,
        "python": (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip(),
        "lock_sha256": digest(REPO_ROOT / "uv.lock"),
        "relocation": relocation,
        "patches": patches,
        "pruned": pruned,
        # The documentation tree is inventoried by its own hashed manifest, so interpreter
        # startup never visits it; full package checks expand that delegated inventory.
        "files": {
            relative: digest(root / relative)
            for relative in (p.relative_to(root).as_posix() for p in sorted(root.rglob("*")) if p.is_file())
            if relative == docs_manifest or not relative.startswith(f"{docs_prefix}/")
        },
        DELEGATED_INVENTORIES: {docs_prefix: docs_manifest} if user_docs is not None else {},
        USER_DOCS: {"directory": docs_prefix, "bundled": user_docs is not None},
    }
    observed = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if observed != set(package_inventory(root, manifest)):
        raise ValueError("Assembled files differ from the package inventory")
    (root / files["package_manifest"]).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Assembled {root}: {len(modules)} relocated extension modules")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    documentation = parser.add_mutually_exclusive_group(required=True)
    documentation.add_argument("--user-docs", type=Path)
    documentation.add_argument("--without-user-docs", action="store_true")
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    assemble(
        args.python,
        args.dependencies,
        args.build,
        args.destination,
        args.metadata,
        args.user_docs,
        development=args.development,
    )
