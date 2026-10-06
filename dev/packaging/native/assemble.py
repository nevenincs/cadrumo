"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ..runtime_wheel_selection import active_requirements
from ..runtime_wheelhouse_contract import target_platform
from .docs_stage import verified_stage
from .hashing import digest
from .layout import ApplicationImage, backend, entrypoint_files, load_layout, staged_application_images
from .package_inventory import DELEGATED_INVENTORIES, USER_DOCS, package_inventory
from .stdlib import bundle as bundle_stdlib


def image_artifact(argument: str) -> tuple[str, Path]:
    """Split one FILE=ARTIFACT argument, refusing an empty side."""
    name, separator, artifact = argument.partition("=")
    if not separator or not name or not artifact:
        raise ValueError(f"Application image arguments take FILE=ARTIFACT: {argument!r}")
    return name, Path(artifact)


def stage_application_images(
    root: Path, images: tuple[ApplicationImage, ...], artifacts: Mapping[str, Path], binary_dir: Path
) -> list[str]:
    """Copy each staged application image from the artifact its CMake target built, refusing any gap."""
    unexpected = sorted(set(artifacts) - {image.file for image in images})
    if unexpected:
        raise ValueError(f"Artifacts were supplied for images this package does not stage: {unexpected}")
    owner = binary_dir.resolve()
    staged = []
    for image in images:
        if image.file not in artifacts:
            raise ValueError(f"No artifact was supplied for application image {image.file}; build {image.target}")
        source = artifacts[image.file].resolve()
        if not source.is_relative_to(owner):
            raise ValueError(f"Application image artifact lies outside the CMake binary directory: {source}")
        if not source.is_file():
            raise FileNotFoundError(f"Application image artifact is missing: {source}; build {image.target}")
        target = root / image.package_path
        if target.exists():
            raise FileExistsError(f"Application image collides with an assembled file: {image.package_path}")
        shutil.copy2(source, target)
        staged.append(image.package_path)
    return staged


def _license_member(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError("SDK license paths must be nonempty relative strings")
    member = PurePosixPath(value)
    if member.is_absolute() or ".." in member.parts or "\\" in value or ":" in value or not member.parts:
        raise ValueError(f"SDK license path is not package-relative: {value!r}")
    return member


def stage_sdk_licenses(root: Path, sdk: Path, contract: Mapping[str, Any]) -> None:
    """Retain CPython's canonical notice and all declared embedded SDK notices."""
    declarations = dict(contract["sdk"].get("licenses", {}))
    declarations[contract["sdk"]["license"]] = contract["files"]["python_license"]
    for source_name, destination_name in declarations.items():
        source_member = _license_member(source_name)
        source = sdk
        for part in source_member.parts:
            source /= part
            if source.is_symlink() or source.is_junction():
                raise ValueError(f"SDK license source is linked: {source}")
        destination = root / _license_member(destination_name)
        if not source.resolve(strict=True).is_relative_to(sdk.resolve(strict=True)):
            raise ValueError(f"SDK license source escapes the SDK: {source}")
        members = [source, *sorted(source.rglob("*"))] if source.is_dir() else [source]
        for member in members:
            if member.is_symlink() or member.is_junction() or not (member.is_dir() or member.is_file()):
                raise ValueError(f"SDK license source is linked or special: {member}")
        if destination.exists():
            raise FileExistsError(f"SDK license collides with a staged file: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def native_assembly_layout(contract: dict[str, Any], provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Bind binary rewriting to the exact tools selected and hashed by CMake."""
    required = {
        "windows": (),
        "linux": ("readelf", "patchelf"),
        "macos": ("install_name_tool", "codesign"),
    }[contract["backend"]]
    if not required:
        return contract
    toolchain = provenance.get("build_toolchain", {})
    tools = toolchain.get("native_tools", {})
    hashes = toolchain.get("native_tool_sha256", {})
    selected = {}
    for name in required:
        value = tools.get(name)
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError(f"Native assembly requires an explicit absolute {name} tool")
        if digest(Path(value)) != hashes.get(name):
            raise ValueError(f"Native assembly tool differs from CMake provenance: {name}")
        selected[name] = value
    projected = dict(contract, native_tools=selected)
    if contract["backend"] == "macos":
        identity = toolchain.get("native_signing_identity")
        if not isinstance(identity, str) or not identity:
            raise ValueError("Native macOS assembly requires an explicit signing identity")
        projected["native_signing_identity"] = identity
    return projected


def assemble(
    python: Path,
    dependencies: Path,
    build: Path,
    destination: Path,
    metadata: Path,
    user_docs: Path | None,
    *,
    images: Mapping[str, Path],
    binary_dir: Path,
    development: bool = False,
    target: str,
    provenance: Mapping[str, object] | None = None,
) -> None:
    """Relocate native modules while retaining their qualified import names."""
    root = destination.resolve()
    if root.exists():
        raise FileExistsError(f"Assembly requires a fresh destination: {root}")
    contract = load_layout(target)
    build_identity = json.loads(metadata.read_text(encoding="utf-8"))
    if build_identity["target"] != target or build_identity["layout_abi"] != contract["abi"]:
        raise ValueError("Build metadata target/layout ABI differs from assembly")
    layout, files = contract["paths"], contract["files"]
    allowed = set(PRODUCT_IDENTITY.cohort_distributions)
    requirements = active_requirements(REPO_ROOT, target_platform(target), build_identity["python"])
    allowed.update(requirements)
    installed = list(importlib.metadata.distributions(path=[str(dependencies)]))
    distributions: dict[str, str] = {
        canonicalize_name(distribution.metadata["Name"]): distribution.version for distribution in installed
    }
    if len(distributions) != len(installed):
        raise ValueError("Duplicate installed distribution metadata")
    if set(distributions) != allowed:
        raise ValueError(f"Production dependency closure mismatch: {set(distributions) ^ allowed}")
    for name, requirement in requirements.items():
        if distributions[name] not in requirement.specifier:
            raise ValueError(f"Production dependency version differs from lock: {name} {distributions[name]}")
    if {distributions[name] for name in PRODUCT_IDENTITY.cohort_distributions} != {build_identity["version"]}:
        raise ValueError("Product cohort versions differ from build metadata")
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
    # Console entrypoints share the native directory; the platform context maps them back to the package root.
    entrypoints = sorted(entrypoint_files(contract).values())
    for relative in entrypoints:
        shutil.copy2(build / Path(relative).name, root / relative)
    # Application images are not interpreter hosts; each enters the startup check only by opting in.
    staged_images = staged_application_images(contract, user_docs=user_docs is not None)
    stage_application_images(root, staged_images, images, binary_dir)
    if development:
        development_executable = root / files["development_executable"]
        development_executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / development_executable.name, development_executable)
    shutil.copy2(build / files["bridge"], native)
    native_manifest = backend(contract).assemble_native(
        python, packages, native, root, native_assembly_layout(contract, provenance or {})
    )
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
    stage_sdk_licenses(root, python, contract)
    shutil.copy2(metadata, root / files["build_metadata"])
    startup_files = [
        layout["executable"],
        *entrypoints,
        *(image.package_path for image in staged_images if image.startup),
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
        "inputs": dict(provenance or {}),
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
    parser.add_argument("--image", action="append", default=[], help="FILE=ARTIFACT for each staged application image")
    parser.add_argument("--binary-dir", type=Path, required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    assemble(
        args.python,
        args.dependencies,
        args.build,
        args.destination,
        args.metadata,
        args.user_docs,
        images=dict(image_artifact(item) for item in args.image),
        binary_dir=args.binary_dir,
        development=args.development,
        target=args.target,
    )
