"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.metadata import Distribution
from pathlib import Path
from typing import Any, cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ..runtime_wheel_selection import active_requirements
from ..runtime_wheelhouse_contract import target_platform
from .agent import resolved_requirements
from .assembly_identity import (
    import_surface,
    installed_distributions,
)
from .build_stamp import (
    BUILD_TYPES,
)
from .layout import (
    bundled_images,
    load_layout,
)
from .product import BUNDLED_EXTRAS


def validate_closure(
    build_type: str,
    destination: Path,
    target: str,
    metadata: Path,
    interpreter: bool,
    dependencies: Path | None,
    user_docs: Path | None,
    images: Mapping[str, Path],
    agent_dependencies: Path | None,
) -> tuple[
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
    dict[str, str],
    dict[str, Requirement],
    list[Distribution],
    dict[str, str],
]:
    """Validate closure."""
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
    agent_requirements, installed, distributions = _dependency_closure(
        interpreter, target, build_identity, agent_dependencies, dependencies
    )
    return root, contract, build_identity, layout, files, agent_requirements, installed, distributions


def validate_identity(
    interpreter: bool,
    provenance: Mapping[str, object] | None,
    contract: dict[str, Any],
    distributions: dict[str, str],
    build_identity: dict[str, Any],
    agent_runtime: Path | None,
    installed: list[Distribution],
) -> tuple[Mapping[str, object], dict[str, list[str]]]:
    """Validate identity."""
    agent_metadata: object = {} if interpreter else (provenance or {}).get("agent", {})
    if not isinstance(agent_metadata, Mapping):
        raise ValueError("Agent build provenance must be a mapping")
    agent_metadata = cast(Mapping[str, object], agent_metadata)
    _validate_agent(interpreter, contract, distributions, agent_metadata, build_identity, agent_runtime)
    smoke_modules = _smoke_modules(installed, contract)
    return agent_metadata, smoke_modules


def _dependency_closure(
    interpreter: bool,
    target: str,
    build_identity: dict[str, Any],
    agent_dependencies: Path | None,
    dependencies: Path | None,
) -> tuple[dict[str, Requirement], list[Distribution], dict[str, str]]:
    allowed: set[str] = set() if interpreter else set(PRODUCT_IDENTITY.cohort_distributions)
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
    _requirement_versions(requirements, distributions)
    return agent_requirements, installed, distributions


def _smoke_modules(installed: list[Distribution], contract: dict[str, Any]) -> dict[str, list[str]]:
    smoke_modules: dict[str, list[str]] = {}
    for distribution in installed:
        name = canonicalize_name(distribution.metadata["Name"])
        if name in PRODUCT_IDENTITY.companion_distributions:
            smoke_modules[name] = [PRODUCT_IDENTITY.companion_namespace]
            continue
        if name in contract["smoke_modules"]:
            smoke_modules[name] = contract["smoke_modules"][name]
            continue
        smoke_modules[name] = [import_surface(name, distribution.files or ())]
    return smoke_modules


def _validate_agent(
    interpreter: bool,
    contract: dict[str, Any],
    distributions: dict[str, str],
    agent_metadata: Mapping[str, object],
    build_identity: dict[str, Any],
    agent_runtime: Path | None,
) -> None:
    for image, declaration in ({} if interpreter else bundled_images(contract)).items():
        if declaration["distribution"] not in distributions:
            raise ValueError(f"Bundled image {image} names a distribution the package does not bundle")
    _validate_versions(interpreter, distributions, agent_metadata, build_identity)
    if not interpreter and agent_runtime is None:
        raise ValueError("Application assembly requires the built agent runtime closure")
    if interpreter and agent_runtime is not None:
        raise ValueError("Standalone interpreter assembly does not consume an agent runtime")


def _requirement_versions(requirements: dict[str, Requirement], distributions: dict[str, str]) -> None:
    for name, requirement in requirements.items():
        if distributions[name] not in requirement.specifier:
            raise ValueError(f"Production dependency version differs from lock: {name} {distributions[name]}")


def _validate_versions(
    interpreter: bool,
    distributions: dict[str, str],
    agent_metadata: Mapping[str, object],
    build_identity: dict[str, Any],
) -> None:
    if not interpreter and distributions["cadrumo-agent"] != agent_metadata.get("version"):
        raise ValueError("Installed agent version differs from the built wheel")
    if not interpreter and {distributions[name] for name in PRODUCT_IDENTITY.cohort_distributions} != {
        build_identity["version"]
    }:
        raise ValueError("Product cohort versions differ from build metadata")
