"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from .assembly_identity import (
    StagedRecords,
    record_staging,
)
from .assembly_images import (
    image_artifact,
)
from .assembly_manifest import write_package_manifest
from .assembly_staging import stage_binaries, stage_dependencies, stage_metadata, stage_stdlib
from .assembly_transaction import AssemblyReuse, assembly_candidate
from .assembly_validation import validate_closure, validate_identity
from .build_directory import require_enrolled_build, require_enrolled_output
from .build_stamp import (
    BUILD_TYPES,
)
from .build_timing import BuildTimings
from .layout import (
    load_layout,
)


def assemble(
    python: Path,
    dependencies: Path | None,
    build: Path,
    destination: Path,
    metadata: Path,
    user_docs: Path | None,
    *,
    images: Mapping[str, Path],
    binary_dir: Path,
    build_type: str,
    development: bool = False,
    interpreter: bool = False,
    target: str,
    provenance: Mapping[str, object] | None = None,
    agent_runtime: Path | None = None,
    agent_dependencies: Path | None = None,
    timings: BuildTimings | None = None,
) -> None:
    """Publish a complete candidate, retaining the old package if any phase fails.

    ``agent_dependencies`` is the agent build directory holding the resolution of the
    agent wheel against both projects' locks; the installed closure must equal
    Cadrumo's base closure with those resolved versions and the agent itself.
    """
    contract = load_layout(target)
    with assembly_candidate(
        destination, contract["files"]["package_manifest"], rewrite_native=contract["backend"] != "windows"
    ) as (candidate, reuse):
        staged_records = _assemble_candidate(
            python,
            dependencies,
            build,
            candidate,
            metadata,
            user_docs,
            images=images,
            binary_dir=binary_dir,
            build_type=build_type,
            development=development,
            interpreter=interpreter,
            target=target,
            provenance=provenance,
            agent_runtime=agent_runtime,
            agent_dependencies=agent_dependencies,
            timings=timings,
            reuse=reuse,
        )
    # The stage is published; its build records now name what it holds.
    record_staging(binary_dir, staged_records)


def _assemble_candidate(
    python: Path,
    dependencies: Path | None,
    build: Path,
    destination: Path,
    metadata: Path,
    user_docs: Path | None,
    *,
    images: Mapping[str, Path],
    binary_dir: Path,
    build_type: str,
    development: bool,
    interpreter: bool,
    target: str,
    provenance: Mapping[str, object] | None,
    agent_runtime: Path | None,
    agent_dependencies: Path | None,
    timings: BuildTimings | None,
    reuse: AssemblyReuse,
) -> StagedRecords:
    """Relocate native modules while retaining their qualified import names."""
    root, contract, build_identity, layout, files, agent_requirements, installed, distributions = validate_closure(
        build_type, destination, target, metadata, interpreter, dependencies, user_docs, images, agent_dependencies
    )
    agent_metadata, smoke_modules = validate_identity(
        interpreter, provenance, contract, distributions, build_identity, agent_runtime, installed
    )
    packages, native, assembly_identity = stage_stdlib(
        root, layout, contract, binary_dir, python, build_identity, timings, reuse
    )
    tools, pruned = stage_dependencies(
        dependencies, timings, packages, reuse, agent_runtime, agent_metadata, interpreter, contract, root
    )
    entrypoints, staged_images, modules, service_descriptors, paths, relocation, patches, native_manifest = (
        stage_binaries(
            root,
            layout,
            build,
            reuse,
            interpreter,
            contract,
            images,
            binary_dir,
            development,
            files,
            native,
            timings,
            python,
            packages,
            provenance,
            target,
        )
    )
    docs_prefix, docs_manifest = stage_metadata(
        root,
        files,
        packages,
        layout,
        contract,
        user_docs,
        reuse,
        paths,
        python,
        timings,
        assembly_identity,
        build_identity,
        native_manifest,
    )
    return write_package_manifest(
        layout,
        entrypoints,
        staged_images,
        files,
        native,
        root,
        development,
        service_descriptors,
        docs_prefix,
        timings,
        docs_manifest,
        contract,
        interpreter,
        binary_dir,
        build_identity,
        build_type,
        assembly_identity,
        distributions,
        smoke_modules,
        provenance,
        agent_metadata,
        agent_requirements,
        tools,
        relocation,
        patches,
        pruned,
        user_docs,
        modules,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--agent-runtime", type=Path, required=True)
    parser.add_argument("--agent-dependencies", type=Path, required=True)
    parser.add_argument("--build", type=require_enrolled_output, required=True)
    parser.add_argument("--destination", type=require_enrolled_output, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    documentation = parser.add_mutually_exclusive_group(required=True)
    documentation.add_argument("--user-docs", type=Path)
    documentation.add_argument("--without-user-docs", action="store_true")
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--image", action="append", default=[], help="FILE=ARTIFACT for each staged application image")
    parser.add_argument("--binary-dir", type=require_enrolled_build, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--config", choices=tuple(BUILD_TYPES), required=True)
    args = parser.parse_args()
    if not args.destination.is_relative_to(args.binary_dir) or not args.build.is_relative_to(args.binary_dir):
        parser.error("Assembly inputs and destination must belong to the selected binary directory")
    assemble(
        args.python,
        args.dependencies,
        args.build,
        args.destination,
        args.metadata,
        args.user_docs,
        images=dict(image_artifact(item) for item in args.image),
        binary_dir=args.binary_dir,
        build_type=BUILD_TYPES[args.config],
        development=args.development,
        target=args.target,
        agent_runtime=args.agent_runtime,
        agent_dependencies=args.agent_dependencies,
    )
