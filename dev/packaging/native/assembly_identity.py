"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from typing import Any, cast

from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY

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
from .layout import (
    ApplicationImage,
    bundled_image_files,
    entrypoint_files,
)

ROLE_COMPONENTS = {
    "interpreter": "interpreter",
    "development-interpreter": "interpreter",
    "bridge": "interpreter",
    "entrypoint": "interpreter",
    "bundled-image": "interpreter",
}
_INSTALL_CACHE_KEY = "uv_cache.json"


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
    entries: list[dict[str, Any]] = []
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


def _logical_descriptors(document: Any, tokens: Mapping[str, str]) -> Any:
    """Name each image a service descriptor binds by its logical token, without derived digests."""
    if isinstance(document, list):
        items = cast(list[Any], document)
        return [_logical_descriptors(item, tokens) for item in items]
    if isinstance(document, dict):
        mapping = cast(dict[str, Any], document)
        return {
            key: tokens.get(value, value) if key == "image_digest" else _logical_descriptors(value, tokens)
            for key, value in mapping.items()
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
    _normalize_install_records(content, root)
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


def _normalize_install_records(content: dict[str, str], root: Path) -> None:
    for path in [path for path in content if path.endswith(f".dist-info/{_INSTALL_CACHE_KEY}")]:
        del content[path]
        record = str(PurePosixPath(path).with_name("RECORD"))
        if record in content:
            rows = (root / record).read_bytes().decode("utf-8").splitlines()
            kept = "\n".join(row for row in rows if row.partition(",")[0] != _record_entry(path))
            content[record] = hashlib.sha256(kept.encode("utf-8")).hexdigest()
