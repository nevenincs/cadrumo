"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement

from dev._paths import REPO_ROOT

from .assembly_identity import (
    StagedRecords,
    agent_closure,
    package_binaries,
    stamp_package,
)
from .build_log import BuildLog, display_path
from .build_timing import BuildTimings
from .hashing import digest
from .layout import ApplicationImage
from .package_inventory import DELEGATED_INVENTORIES, USER_DOCS, package_inventory


def write_package_manifest(
    layout: dict[str, str],
    entrypoints: list[str],
    staged_images: tuple[ApplicationImage, ...],
    files: dict[str, str],
    native: Path,
    root: Path,
    development: bool,
    service_descriptors: str | None,
    docs_prefix: str,
    timings: BuildTimings | None,
    docs_manifest: str,
    contract: dict[str, Any],
    interpreter: bool,
    binary_dir: Path,
    build_identity: dict[str, Any],
    build_type: str,
    assembly_identity: dict[str, str],
    distributions: dict[str, str],
    smoke_modules: dict[str, list[str]],
    provenance: Mapping[str, object] | None,
    agent_metadata: Mapping[str, object],
    agent_requirements: dict[str, Requirement],
    tools: dict[str, str],
    relocation: dict[str, str],
    patches: list[dict[str, str]],
    pruned: list[dict[str, str]],
    user_docs: Path | None,
    modules: dict[str, str],
) -> StagedRecords:
    """Write package manifest."""
    startup_files = _startup_files(
        layout, entrypoints, staged_images, files, native, root, development, service_descriptors, docs_prefix
    )
    inventoried_files = _inventory(timings, root, docs_manifest, docs_prefix)
    binaries = package_binaries(contract, interpreter=interpreter, development=development, images=staged_images)
    build_identity, components, staged_records = stamp_package(
        binary_dir,
        root,
        build_identity,
        inventoried_files,
        binaries,
        kind="interpreter" if interpreter else "application",
        build_type=build_type,
        build_member=files["build_metadata"],
        descriptors=service_descriptors,
        packages=layout["packages"],
    )
    (root / files["build_metadata"]).write_text(json.dumps(build_identity, indent=2), encoding="utf-8")
    inventoried_files[files["build_metadata"]] = digest(root / files["build_metadata"])
    inventoried_files = dict(sorted(inventoried_files.items(), key=lambda item: root / item[0]))
    manifest = {
        "assembly": assembly_identity,
        "kind": "interpreter" if interpreter else "application",
        "build": build_identity,
        "layout": contract,
        "startup_files": startup_files,
        "distributions": distributions,
        "smoke_modules": smoke_modules,
        "python": (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip(),
        "lock_sha256": digest(REPO_ROOT / "uv.lock"),
        "inputs": dict(provenance or {}),
        "agent": {"bundled": not interpreter, **agent_metadata}
        | ({} if interpreter else {"dependencies": agent_closure(distributions, agent_requirements)}),
        "components": components,
        "tools": tools,
        "relocation": relocation,
        "patches": patches,
        "pruned": pruned,
        # The documentation tree is inventoried by its own hashed manifest, so interpreter
        # startup never visits it; full package checks expand that delegated inventory.
        "files": inventoried_files,
        DELEGATED_INVENTORIES: {docs_prefix: docs_manifest} if user_docs is not None else {},
        USER_DOCS: {"directory": docs_prefix, "bundled": user_docs is not None},
    }
    observed = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if observed != set(package_inventory(root, manifest)):
        raise ValueError("Assembled files differ from the package inventory")
    (root / files["package_manifest"]).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    BuildLog("assemble").status(f"assembled {display_path(root)}: {len(modules)} relocated extension modules")
    return staged_records


def _startup_files(
    layout: dict[str, str],
    entrypoints: list[str],
    staged_images: tuple[ApplicationImage, ...],
    files: dict[str, str],
    native: Path,
    root: Path,
    development: bool,
    service_descriptors: str | None,
    docs_prefix: str,
) -> list[str]:
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
    if service_descriptors is not None:
        startup_files.append(service_descriptors)
    if any(name.startswith(f"{docs_prefix}/") for name in startup_files):
        raise ValueError("Startup files must not belong to a delegated inventory")
    return startup_files


def _inventory(timings: BuildTimings | None, root: Path, docs_manifest: str, docs_prefix: str) -> dict[str, str]:
    with timings.phase("package-inventory") if timings is not None else nullcontext():
        inventoried_files = {
            relative: digest(root / relative)
            for relative in (p.relative_to(root).as_posix() for p in sorted(root.rglob("*")) if p.is_file())
            if relative == docs_manifest or not relative.startswith(f"{docs_prefix}/")
        }
    return inventoried_files
