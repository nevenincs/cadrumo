"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ..runtime_wheel_selection import active_requirements
from ..runtime_wheelhouse_contract import target_platform
from .agent import resolved_requirements
from .agent_runtime import load_runtime_declaration, stage_agent_runtime
from .assembly_transaction import AssemblyReuse, assembly_candidate
from .browser_archive_coverage import verify_browser_archive_coverage
from .build_directory import require_enrolled_build, require_enrolled_output
from .build_log import BuildLog, display_path
from .build_paths import build_paths
from .build_stamp import (
    ACTION_COMPONENTS,
    BUILD_TYPES,
    SETTLED,
    BuildStamp,
    ComponentIdentity,
    display_version,
    native_settled,
    package_identity,
    read_identity,
    read_record,
    settle_record,
)
from .build_timing import BuildTimings
from .docs_stage import verified_stage
from .hashing import digest
from .layout import (
    ApplicationImage,
    application_images,
    backend,
    bundled_image_files,
    bundled_images,
    entrypoint_files,
    load_layout,
)
from .linux_desktop_runtime import stage as stage_linux_desktop_runtime
from .package_inventory import DELEGATED_INVENTORIES, USER_DOCS, package_inventory
from .product import BUNDLED_EXTRAS
from .service_descriptors import stage_service_descriptors
from .stdlib import bundle as bundle_stdlib
from .stdlib import bundle_identity, compile_packages_bytecode, compiler_identity
from .tree_copy import copy_tree


def image_artifact(argument: str) -> tuple[str, Path]:
    """Split one FILE=ARTIFACT argument, refusing an empty side."""
    name, separator, artifact = argument.partition("=")
    if not separator or not name or not artifact:
        raise ValueError(f"Application image arguments take FILE=ARTIFACT: {argument!r}")
    return name, Path(artifact)


def named_application_images(layout: Mapping[str, Any], artifacts: Mapping[str, Path]) -> tuple[ApplicationImage, ...]:
    """Return the declared images CMake named with an artifact, in declaration order.

    CMake alone decides which images a package stages; an artifact for an undeclared
    image is refused when staging.
    """
    return tuple(image for image in application_images(dict(layout)) if image.file in artifacts)


def stage_application_images(
    root: Path,
    images: tuple[ApplicationImage, ...],
    artifacts: Mapping[str, Path],
    binary_dir: Path,
    *,
    copy_function: Callable[[Path, Path], object] = shutil.copy2,
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
        copy_function(source, target)
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


ROLE_COMPONENTS = {
    "interpreter": "interpreter",
    "development-interpreter": "interpreter",
    "bridge": "interpreter",
    "entrypoint": "interpreter",
    "bundled-image": "interpreter",
}
"""The interpreter hosts share one component; an application image is the component of its role."""


def component_of(role: str) -> str:
    """Name the build component whose identity a staged binary of ``role`` embeds."""
    return ROLE_COMPONENTS.get(role, role)


def package_binaries(
    contract: Mapping[str, Any], *, interpreter: bool, development: bool, images: Iterable[ApplicationImage]
) -> list[tuple[str, str]]:
    """Return ``(role, package path)`` of every Cadrumo-built native binary the package stages."""
    paths, files = contract["paths"], contract["files"]
    native = paths["native"]
    entries = [("interpreter", paths["executable"]), ("bridge", f"{native}/{files['bridge']}")]
    if development:
        entries.append(("development-interpreter", files["development_executable"]))
    if not interpreter:
        entries += [("entrypoint", path) for path in entrypoint_files(dict(contract)).values()]
        entries += [("bundled-image", path) for path in bundled_image_files(dict(contract)).values()]
        entries += [
            ("desktop" if image.desktop else image.name.removeprefix("cadrumo-"), image.package_path)
            for image in images
        ]
    return sorted(entries, key=lambda entry: entry[1])


def package_components(
    binaries: Iterable[tuple[str, str]], identities: Mapping[str, ComponentIdentity], build_type: str
) -> list[dict[str, Any]]:
    """Name every staged Cadrumo-built binary with the identity of the component it was compiled as.

    Each component has its own build id and sequence, which change only when its inputs do.
    The bundled CPython runtime and extension modules are reported through ``python`` and
    ``distributions`` instead.
    """
    entries = []
    for role, path in binaries:
        identity = identities[component_of(role)]
        entries.append(
            {
                "name": PurePosixPath(path).stem,
                "role": role,
                "path": path,
                "component": identity.component,
                "version": identity.version,
                "build_id": identity.stamp.build_id,
                "build_sequence": identity.stamp.build_sequence,
                "build_date": identity.stamp.build_date,
                "build_type": build_type,
                "display_version": display_version(identity.version, identity.stamp.build_id, build_type),
            }
        )
    return entries


def component_identities(
    binary_dir: Path, binaries: Iterable[tuple[str, str]], configuration: str
) -> dict[str, ComponentIdentity]:
    """Read the identity every component the staged binaries belong to was compiled with in ``configuration``."""
    return {
        name: read_identity(binary_dir, name, configuration)
        for name in sorted({component_of(role) for role, _ in binaries})
    }


# The file uv writes into a locally built distribution's metadata as its install-time cache key.
_INSTALL_CACHE_KEY = "uv_cache.json"


def _logical_descriptors(document: Any, tokens: Mapping[str, str]) -> Any:
    """Name each image a service descriptor binds by its logical token, without derived digests."""
    if isinstance(document, list):
        return [_logical_descriptors(item, tokens) for item in document]
    if isinstance(document, dict):
        return {
            key: tokens.get(value, value) if key == "image_digest" else _logical_descriptors(value, tokens)
            for key, value in document.items()
            if key != "descriptor_digest"
        }
    return document


def logical_inventory(
    root: Path,
    files: Mapping[str, str],
    binaries: Iterable[tuple[str, str]],
    identities: Mapping[str, ComponentIdentity],
    *,
    descriptors: str | None,
) -> dict[str, str]:
    """Return the staged inventory with every native binary named by the component it was built from.

    A component fingerprint determines its images, while their linked bytes need not be
    reproducible; the service descriptors, which bind those bytes, are compared through the
    same names. Every other staged file keeps its content hash.
    """
    content = dict(files)
    tokens: dict[str, str] = {}
    for role, path in binaries:
        identity = identities[component_of(role)]
        token = f"{identity.component}:{identity.fingerprint}"
        if path in content:
            tokens[content[path]] = token
            content[path] = token
    if descriptors is not None and descriptors in content:
        document = _logical_descriptors(json.loads((root / descriptors).read_bytes()), tokens)
        content[descriptors] = hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()
    # The installer stamps a locally built distribution with the time it installed it, and
    # its RECORD lists that file's hash; neither is content the source determines.
    for path in [path for path in content if path.endswith(f".dist-info/{_INSTALL_CACHE_KEY}")]:
        del content[path]
        record = str(PurePosixPath(path).with_name("RECORD"))
        if record in content:
            rows = (root / record).read_bytes().decode("utf-8").splitlines()
            kept = "\n".join(row for row in rows if row.partition(",")[0] != _record_entry(path))
            content[record] = hashlib.sha256(kept.encode("utf-8")).hexdigest()
    return content


def _record_entry(path: str) -> str:
    """Name a dist-info member the way its distribution's RECORD lists it, relative to site-packages."""
    member = PurePosixPath(path)
    return f"{member.parent.name}/{member.name}"


def package_fingerprint(
    files: Mapping[str, str],
    identities: Mapping[str, ComponentIdentity],
    *,
    kind: str,
    build_type: str,
) -> str:
    """Hash what the package ships: its logical staged inventory and the native identities it carries.

    Only staged content counts. The Python payload's producer fingerprints are keyed on inputs
    (a checkout edit that changes no staged byte still moves them), so they stay in their own
    build records and out of the package identity; the staged files they produced already
    count byte for byte, deterministic bytecode included.
    """
    document = {
        "kind": kind,
        "build_type": build_type,
        "files": dict(sorted(files.items())),
        "components": {name: identity.fingerprint for name, identity in sorted(identities.items())},
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StagedRecords:
    """What one staging tells each component's build record, applied once the stage is published."""

    configuration: str
    package: str
    artifacts: Mapping[str, Mapping[str, str]]
    settled: Mapping[str, bool]


def _distribution(record: str) -> str:
    """Name the distribution whose ``*.dist-info/RECORD`` this package path is."""
    return canonicalize_name(PurePosixPath(record).parent.name.removesuffix(".dist-info").rpartition("-")[0])


def staged_artifacts(
    files: Mapping[str, str], binaries: Iterable[tuple[str, str]], *, packages: str
) -> dict[str, dict[str, str]]:
    """Group the staged artifact digests by the component that produced them.

    Native components own their images; the product payload owns the distribution
    RECORDs of the product cohort, and the agent payload its own RECORD.
    """
    artifacts: dict[str, dict[str, str]] = {}
    for role, path in binaries:
        if path in files:
            artifacts.setdefault(component_of(role), {})[path] = files[path]
    cohort = {canonicalize_name(name) for name in PRODUCT_IDENTITY.cohort_distributions}
    for path, value in files.items():
        if PurePosixPath(path).parent.parent.as_posix() != packages or not path.endswith(".dist-info/RECORD"):
            continue
        name = _distribution(path)
        if name == "cadrumo-agent":
            artifacts.setdefault(ACTION_COMPONENTS["agent"], {})[path] = value
        elif name in cohort:
            artifacts.setdefault(ACTION_COMPONENTS["product"], {})[path] = value
    return artifacts


def record_staging(binary_dir: Path, staged: StagedRecords) -> None:
    """Settle the build records of everything a published stage holds, with its artifact digests.

    A native component settles when its inputs still give the fingerprint it was compiled
    from; a payload producer keeps the state its own build recorded.
    """
    for component, artifacts in sorted(staged.artifacts.items()):
        if component in staged.settled:
            settled = staged.settled[component]
        else:
            record = read_record(binary_dir, component)
            if record is None:
                continue
            settled = record["state"] == SETTLED
        settle_record(
            binary_dir,
            component,
            settled=settled,
            configuration=staged.configuration,
            package=staged.package,
            artifacts=artifacts,
        )


def package_build_record(shared: Mapping[str, Any], stamp: BuildStamp, build_type: str) -> dict[str, Any]:
    """Return the staged build record: the shared metadata plus this package's own identity and build type.

    ``shared`` keeps the interpreter hosts' identity under ``interpreter``; the top-level
    identity is the package's, allocated at staging time and compiled into no binary.
    """
    if build_type not in BUILD_TYPES.values():
        raise ValueError(f"Unknown build type: {build_type!r}")
    return {
        **shared,
        "build_id": stamp.build_id,
        "build_sequence": stamp.build_sequence,
        "build_number": stamp.build_sequence,
        "build_date": stamp.build_date,
        "build_type": build_type,
        "display_version": display_version(shared["version"], stamp.build_id, build_type),
    }


def stamp_package(
    binary_dir: Path,
    root: Path,
    shared: Mapping[str, Any],
    files: Mapping[str, str],
    binaries: Iterable[tuple[str, str]],
    *,
    kind: str,
    build_type: str,
    build_member: str,
    descriptors: str | None,
    packages: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], StagedRecords]:
    """Return the package's build record, components and staged records, keyed on its logical content.

    ``files`` is the package inventory of the stage at ``root``; the build record itself and
    the package manifest are left out, since they carry the result. Restaging the same
    logical content, including a rebuild of unchanged components, keeps the identity. The
    staged records are applied with :func:`record_staging` once the stage is published.
    """
    staged = list(binaries)
    configuration = next(name for name, value in BUILD_TYPES.items() if value == build_type)
    identities = component_identities(binary_dir, staged, configuration)
    content = logical_inventory(
        root,
        {member: value for member, value in files.items() if member != build_member},
        staged,
        identities,
        descriptors=descriptors,
    )
    stamp = package_identity(binary_dir, package_fingerprint(content, identities, kind=kind, build_type=build_type))
    package = (build_paths(binary_dir)["stage"] / configuration / "app").resolve()
    records = StagedRecords(
        configuration=configuration,
        package=package.relative_to(binary_dir.resolve()).as_posix(),
        artifacts=staged_artifacts(files, staged, packages=packages),
        settled=native_settled(binary_dir, sorted(identities), configuration=configuration),
    )
    return (
        package_build_record(shared, stamp, build_type),
        package_components(staged, identities, build_type),
        records,
    )


def agent_closure(distributions: Mapping[str, str], requirements: Iterable[str]) -> list[dict[str, str]]:
    """Return the agent's resolved runtime closure as installed, sorted by name."""
    return [{"name": name, "version": distributions[name]} for name in sorted(requirements)]


def _shortest_first(parts: list[str]) -> tuple[int, list[str]]:
    return len(parts), parts


def import_surface(name: str, recorded: Iterable[PurePath | str]) -> str:
    """Return the shortest importable module a distribution's RECORD lists, to smoke-import it.

    RECORD paths are POSIX by specification, but some wheels (ormsgpack's) write
    Windows separators, so either separator delimits a path.
    """
    candidates: list[list[str]] = []
    for member in recorded:
        path = PurePosixPath(str(member).replace("\\", "/"))
        parts = list(path.parts)
        if path.suffix != ".py" or any(p in {"tests", "test", "__main__.py"} for p in parts):
            continue
        parts[-1] = path.stem
        if parts[-1] == "__init__":
            parts.pop()
        if parts and all(p.isidentifier() for p in parts):
            candidates.append(parts)
    if not candidates:
        raise ValueError(f"No reviewed Python import surface for distribution {name}")
    selected: list[str] = min(candidates, key=_shortest_first)
    return ".".join(selected)


def installed_distributions(dependencies: Path) -> list[importlib.metadata.Distribution]:
    """Return the staged distributions, refusing a ``*.dist-info`` directory without metadata.

    Such a directory is left behind when an install replaced a distribution only
    partly; it names no distribution, so the closure it belongs to cannot be checked.
    """
    broken = sorted(path.name for path in dependencies.glob("*.dist-info") if not (path / "METADATA").is_file())
    if broken:
        raise ValueError(
            f"Staged dependencies in {dependencies} hold distribution metadata directories without METADATA: "
            f"{', '.join(broken)}. Rebuild the product dependencies (python_product) from a clean dependency closure."
        )
    return list(importlib.metadata.distributions(path=[str(dependencies)]))


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
    if build_type not in BUILD_TYPES.values():
        raise ValueError(f"Unknown build type: {build_type!r}")
    root = destination.resolve()
    contract = load_layout(target)
    build_identity = json.loads(metadata.read_text(encoding="utf-8"))
    if build_identity["target"] != target or build_identity["layout_abi"] != contract["abi"]:
        raise ValueError("Build metadata target/layout ABI differs from assembly")
    layout, files = contract["paths"], contract["files"]
    if interpreter and (dependencies is not None or user_docs is not None or images):
        raise ValueError("Standalone interpreter assembly does not consume application inputs")
    if not interpreter and dependencies is None:
        raise ValueError("Application assembly requires product dependencies")
    allowed = set() if interpreter else set(PRODUCT_IDENTITY.cohort_distributions)
    requirements = (
        {}
        if interpreter
        else active_requirements(REPO_ROOT, target_platform(target), build_identity["python"], extras=BUNDLED_EXTRAS)
    )
    allowed.update(requirements)
    agent_requirements: dict[str, Requirement] = {}
    if not interpreter:
        if agent_dependencies is None:
            raise ValueError("Application assembly requires the agent's resolved dependencies")
        agent_requirements = resolved_requirements(agent_dependencies, target, build_identity["python"])
        requirements.update(agent_requirements)
        allowed.update(agent_requirements)
        allowed.add("cadrumo-agent")
    installed = [] if dependencies is None else installed_distributions(dependencies)
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
    agent_metadata = {} if interpreter else (provenance or {}).get("agent", {})
    if not isinstance(agent_metadata, Mapping):
        raise ValueError("Agent build provenance must be a mapping")
    for image, declaration in ({} if interpreter else bundled_images(contract)).items():
        if declaration["distribution"] not in distributions:
            raise ValueError(f"Bundled image {image} names a distribution the package does not bundle")
    if not interpreter and distributions["cadrumo-agent"] != agent_metadata.get("version"):
        raise ValueError("Installed agent version differs from the built wheel")
    if not interpreter and {distributions[name] for name in PRODUCT_IDENTITY.cohort_distributions} != {
        build_identity["version"]
    }:
        raise ValueError("Product cohort versions differ from build metadata")
    if not interpreter and agent_runtime is None:
        raise ValueError("Application assembly requires the built agent runtime closure")
    if interpreter and agent_runtime is not None:
        raise ValueError("Standalone interpreter assembly does not consume an agent runtime")
    smoke_modules = {}
    for distribution in installed:
        name = canonicalize_name(distribution.metadata["Name"])
        if name in PRODUCT_IDENTITY.companion_distributions:
            smoke_modules[name] = [PRODUCT_IDENTITY.companion_namespace]
            continue
        if name in contract["smoke_modules"]:
            smoke_modules[name] = contract["smoke_modules"][name]
            continue
        smoke_modules[name] = [import_surface(name, distribution.files or ())]
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
    pruned = []
    for exclusion in [] if interpreter else contract.get("package_exclusions", []):
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
    with timings.phase("native-relocation") if timings is not None else nullcontext():
        platform = backend(contract)
        native_layout = native_assembly_layout(contract, provenance or {})
        native_manifest = (
            platform.assemble_native(python, packages, native, root, native_layout, copy_function=reuse.copy)
            if contract["backend"] == "windows"
            else platform.assemble_native(python, packages, native, root, native_layout)
        )
    modules = native_manifest["modules"]
    if not interpreter:
        # The packaged browser setup refuses archives no pin authenticates, so a package whose own
        # pins do not cover its own Playwright driver could never set its browser up.
        verify_browser_archive_coverage(packages, target)
    service_descriptors = None if interpreter else stage_service_descriptors(root, contract, staged_images)
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
    with timings.phase("package-inventory") if timings is not None else nullcontext():
        inventoried_files = {
            relative: digest(root / relative)
            for relative in (p.relative_to(root).as_posix() for p in sorted(root.rglob("*")) if p.is_file())
            if relative == docs_manifest or not relative.startswith(f"{docs_prefix}/")
        }
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
