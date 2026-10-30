"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping
from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast

from dev._paths import COMPONENT_PINS_ROOT, REPO_ROOT

from .agent_runtime import stage_agent_runtime
from .agent_runtime_validation import load_runtime_declaration
from .assembly_images import (
    named_application_images,
    native_assembly_layout,
    stage_application_images,
    stage_sdk_licenses,
)
from .assembly_transaction import AssemblyReuse
from .browser_archive_coverage import verify_browser_archive_coverage
from .build_paths import build_paths
from .build_timing import BuildTimings
from .docs_stage import verified_stage
from .hashing import digest
from .layout import (
    ApplicationImage,
    backend,
    bundled_image_files,
    entrypoint_files,
)
from .linux_desktop_runtime import stage as stage_linux_desktop_runtime
from .service_descriptors import stage_service_descriptors
from .stdlib import bundle as bundle_stdlib
from .stdlib import bundle_identity, compile_packages_bytecode, compiler_identity
from .tree_copy import copy_tree


def stage_stdlib(
    root: Path,
    layout: dict[str, str],
    contract: dict[str, Any],
    binary_dir: Path,
    python: Path,
    build_identity: dict[str, Any],
    timings: BuildTimings | None,
    reuse: AssemblyReuse,
) -> tuple[Path, Path, dict[str, str]]:
    """Stage stdlib."""
    lib = root / layout["stdlib"]
    lib.parent.mkdir(parents=True, exist_ok=True)
    packages = root / layout["packages"]
    native = root / layout["native"]
    native.mkdir(parents=True)
    bootstrap = (REPO_ROOT / "native/interpreter/bootstrap.py").read_text(encoding="utf-8")
    if bootstrap.count("LAYOUT = {}") != 1:
        raise ValueError("Missing bootstrap layout projection marker")
    bootstrap = bootstrap.replace("LAYOUT = {}", f"LAYOUT = {contract!r}")
    generated = build_paths(binary_dir)["generated"] / "contract.json"
    package_fixed = json.loads(generated.read_text(encoding="utf-8"))["application_environment"]["package_fixed"]
    marker = "PACKAGE_FIXED_ENVIRONMENT_NAMES = ()"
    if bootstrap.count(marker) != 1:
        raise ValueError("Missing bootstrap fixed environment projection marker")
    bootstrap = bootstrap.replace(marker, f"PACKAGE_FIXED_ENVIRONMENT_NAMES = {tuple(sorted(package_fixed))!r}")
    bootstrap_modules = {
        "_cadrumo_bootstrap": bootstrap.encode(),
        "_cadrumo_native": (REPO_ROOT / "native" / contract["bootstrap"]).read_bytes(),
    }
    stdlib_identity = bundle_identity(
        python / contract["sdk"]["stdlib"], contract["stdlib_exclude"], bootstrap_modules, build_identity["python"]
    )
    assembly_identity = {"stdlib": stdlib_identity, "bytecode": compiler_identity()}
    with timings.phase("stdlib-bytecode-zip") if timings is not None else nullcontext():
        previous_stdlib = reuse.verified(layout["stdlib"])
        if previous_stdlib is not None and reuse.manifest.get("assembly", {}).get("stdlib") == stdlib_identity:
            reuse.link(previous_stdlib, lib)
        else:
            bundle_stdlib(
                python / contract["sdk"]["stdlib"],
                lib,
                contract["stdlib_exclude"],
                bootstrap_modules,
                build_identity["python"],
            )
    return packages, native, assembly_identity


def stage_dependencies(
    dependencies: Path | None,
    timings: BuildTimings | None,
    packages: Path,
    reuse: AssemblyReuse,
    agent_runtime: Path | None,
    agent_metadata: Mapping[str, object],
    interpreter: bool,
    contract: dict[str, Any],
    root: Path,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Stage dependencies."""

    def omit_development(directory: str, names: list[str]) -> set[str]:
        excluded = {"__pycache__", "tests"}
        if dependencies is not None and Path(directory).resolve() == dependencies.resolve():
            excluded.add("bin")
        return set(names) & excluded

    with timings.phase("dependency-copy") if timings is not None else nullcontext():
        if dependencies is None:
            packages.mkdir(parents=True)
        else:
            copy_tree(dependencies, packages, ignore=omit_development, copy_function=reuse.copy)
    tools: dict[str, str] = {}
    if agent_runtime is not None:
        with timings.phase("agent-runtime-copy") if timings is not None else nullcontext():
            source = agent_metadata.get("source")
            if not isinstance(source, str):
                raise ValueError("Agent build provenance names no source project")
            declaration = load_runtime_declaration(Path(source))
            stage_agent_runtime(
                agent_runtime,
                packages.parent,
                declaration=declaration,
                copy_function=reuse.copy,
            )
            tools["node"] = declaration["node_version"]
    pruned = [*_prune_packages(interpreter, contract, packages, root), *_prune_local_install_records(packages, root)]
    return tools, pruned


def stage_binaries(
    root: Path,
    layout: dict[str, str],
    build: Path,
    reuse: AssemblyReuse,
    interpreter: bool,
    contract: dict[str, Any],
    images: Mapping[str, Path],
    binary_dir: Path,
    development: bool,
    files: dict[str, str],
    native: Path,
    timings: BuildTimings | None,
    python: Path,
    packages: Path,
    provenance: Mapping[str, object] | None,
    target: str,
) -> tuple[
    list[str],
    tuple[ApplicationImage, ...],
    dict[str, str],
    str | None,
    list[str],
    dict[str, str],
    list[dict[str, str]],
    dict[str, Any],
]:
    """Stage binaries."""
    executable = root / layout["executable"]
    executable.parent.mkdir(parents=True, exist_ok=True)
    reuse.copy(build / executable.name, executable)
    # Console entrypoints share the native directory; the platform context maps them back to the package root.
    entrypoints = (
        [] if interpreter else sorted((*entrypoint_files(contract).values(), *bundled_image_files(contract).values()))
    )
    for relative in entrypoints:
        reuse.copy(build / Path(relative).name, root / relative)
    # Application images are not interpreter hosts; each enters the startup check only by opting in.
    staged_images = () if interpreter else named_application_images(contract, images)
    stage_application_images(root, staged_images, images, binary_dir, copy_function=reuse.copy)
    if not interpreter:
        stage_linux_desktop_runtime(root, contract)
    if development:
        development_executable = root / files["development_executable"]
        development_executable.parent.mkdir(parents=True, exist_ok=True)
        reuse.copy(build / development_executable.name, development_executable)
    reuse.copy(build / files["bridge"], native / files["bridge"])
    native_manifest = _relocate_native(timings, contract, provenance, python, packages, native, root, reuse)
    modules = native_manifest["modules"]
    if not interpreter:
        # The native component engine reads its pin tables from the package, beside the authority.
        pins = root / layout["component_pins"]
        shutil.copytree(COMPONENT_PINS_ROOT, pins, copy_function=reuse.copy)
        # The packaged browser setup refuses archives no pin authenticates, so a package whose own
        # pins do not cover its own Playwright driver could never set its browser up.
        verify_browser_archive_coverage(packages, pins, target)
    service_descriptors = None if interpreter else stage_service_descriptors(root, contract, staged_images)
    paths = native_manifest["python_paths"]
    relocation = native_manifest.pop("relocation")
    patches = native_manifest.pop("patches")
    return entrypoints, staged_images, modules, service_descriptors, paths, relocation, patches, native_manifest


def stage_metadata(
    root: Path,
    files: dict[str, str],
    packages: Path,
    layout: dict[str, str],
    contract: dict[str, Any],
    user_docs: Path | None,
    reuse: AssemblyReuse,
    paths: list[str],
    python: Path,
    timings: BuildTimings | None,
    assembly_identity: dict[str, str],
    build_identity: dict[str, Any],
    native_manifest: dict[str, Any],
) -> tuple[str, str]:
    """Stage metadata."""
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
        shutil.copytree(verified_stage(user_docs, docs_declaration), root / docs_prefix, copy_function=reuse.copy)
    path_file = root / files["path_file"]
    path_file.write_text(
        "# CADRUMO package-relative import paths; executable directives are forbidden.\n"
        + "\n".join(Path(os.path.relpath(root / p, path_file.parent)).as_posix() for p in paths)
        + "\n",
        encoding="utf-8",
    )
    stage_sdk_licenses(root, python, contract)
    with timings.phase("dependency-bytecode") if timings is not None else nullcontext():
        reuse_bytecode = reuse.manifest.get("assembly", {}).get("bytecode") == assembly_identity["bytecode"]
        compile_packages_bytecode(
            packages,
            prefix=layout["packages"],
            version=build_identity["python"],
            previous=reuse.previous / layout["packages"] if reuse_bytecode else None,
            previous_files=reuse.manifest.get("files", {}) if reuse_bytecode else None,
        )
    return docs_prefix, docs_manifest


def _prune_packages(interpreter: bool, contract: dict[str, Any], packages: Path, root: Path) -> list[dict[str, str]]:
    pruned: list[dict[str, str]] = []
    exclusions = [] if interpreter else cast(list[dict[str, str]], contract.get("package_exclusions", []))
    for exclusion in exclusions:
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
    return pruned


def _prune_local_install_records(packages: Path, root: Path) -> list[dict[str, str]]:
    """Drop each installer record that names a wheel file on the build host."""
    pruned: list[dict[str, str]] = []
    for record in sorted(packages.glob("*.dist-info/direct_url.json")):
        url = json.loads(record.read_text(encoding="utf-8")).get("url")
        if not isinstance(url, str) or not url.startswith("file:"):
            continue
        pruned.append(
            {
                "file": record.relative_to(root).as_posix(),
                "sha256": digest(record),
                "reason": "Installer record of the build host's wheel location",
            }
        )
        record.unlink()
    return pruned


def _relocate_native(
    timings: BuildTimings | None,
    contract: dict[str, Any],
    provenance: Mapping[str, object] | None,
    python: Path,
    packages: Path,
    native: Path,
    root: Path,
    reuse: AssemblyReuse,
) -> dict[str, Any]:
    with timings.phase("native-relocation") if timings is not None else nullcontext():
        platform = backend(contract)
        native_layout = native_assembly_layout(contract, provenance or {})
        native_manifest = (
            platform.assemble_native(python, packages, native, root, native_layout, copy_function=reuse.copy)
            if contract["backend"] == "windows"
            else platform.assemble_native(python, packages, native, root, native_layout)
        )
    return native_manifest
