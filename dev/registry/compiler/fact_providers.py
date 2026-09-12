"""Canonical provider registration and directory ownership for governed facts."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .fact_loader import is_governed_fact_filename, load_governed_facts
from .loader_cache import toml_file_fingerprint
from .loader_fingerprints import RegistryPathFingerprints

__all__ = [
    "FACT_PROVIDER_REGISTRATIONS",
    "FactProviderCompiler",
    "FactProviderRegistration",
    "collect_registered_fact_provider_fingerprints",
    "compile_registered_fact_providers",
    "registered_fact_provider_directories",
    "reset_registered_fact_providers",
    "validate_fact_provider_directory_ownership",
    "validate_fact_provider_registrations",
]


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class FactProviderCompiler(Protocol):
    """Compile one provider's declarations relative to a registry root."""

    def __call__(self, registry_root: Path) -> tuple[GovernedFact, ...]:
        """Return the provider's strictly validated governed facts."""
        ...


class ModeloFactProjector(Protocol):
    """Project governed facts from the already-compiled modelo authority."""

    def __call__(self, modelos: Iterable[ModeloDefinition]) -> tuple[GovernedFact, ...]:
        """Return facts without reading or relocating modelo parameter files."""
        ...


@dataclass(frozen=True, slots=True)
class FactProviderRegistration:
    """One provider's complete loading, identity, reset, and ownership contract."""

    provider_id: str
    owned_directories: tuple[str, ...]
    compile: FactProviderCompiler
    collect_fingerprints: Callable[[Path], RegistryPathFingerprints]
    reset: Callable[[], None]
    project_modelos: ModeloFactProjector | None = None
    lifecycle_components: tuple[str, ...] = ()
    inherited_identity_domains: tuple[str, ...] = ()


def validate_fact_provider_registrations(
    registrations: Iterable[FactProviderRegistration],
) -> tuple[FactProviderRegistration, ...]:
    """Freeze registrations after refusing ambiguous identity or ownership."""
    frozen = tuple(registrations)
    provider_ids: set[str] = set()
    ownership: list[tuple[PurePosixPath, str]] = []
    for registration in frozen:
        if _PROVIDER_ID.fullmatch(registration.provider_id) is None:
            raise RegistryValidationError(f"invalid governed fact provider id {registration.provider_id!r}")
        if registration.provider_id in provider_ids:
            raise RegistryValidationError(f"duplicate governed fact provider id {registration.provider_id!r}")
        provider_ids.add(registration.provider_id)
        if not registration.owned_directories and registration.project_modelos is None:
            raise RegistryValidationError(
                f"governed fact provider {registration.provider_id!r} must own at least one directory",
            )
        if registration.project_modelos is not None and not registration.inherited_identity_domains:
            raise RegistryValidationError(
                f"projection provider {registration.provider_id!r} must declare its inherited identity domains",
            )
        local_directories: set[PurePosixPath] = set()
        for raw_directory in registration.owned_directories:
            directory = _validated_owned_directory(registration.provider_id, raw_directory)
            if directory in local_directories:
                raise RegistryValidationError(
                    f"governed fact provider {registration.provider_id!r} repeats directory {raw_directory!r}",
                )
            for existing, existing_provider_id in ownership:
                if directory == existing or directory.is_relative_to(existing) or existing.is_relative_to(directory):
                    raise RegistryValidationError(
                        f"governed fact directory {directory.as_posix()!r} owned by {registration.provider_id!r} "
                        f"overlaps {existing.as_posix()!r} owned by {existing_provider_id!r}",
                    )
            local_directories.add(directory)
            ownership.append((directory, registration.provider_id))
    return frozen


def registered_fact_provider_directories() -> dict[str, FactProviderRegistration]:
    """Return each exact governed directory and its canonical provider."""
    return {
        PurePosixPath(directory).as_posix(): registration
        for registration in FACT_PROVIDER_REGISTRATIONS
        for directory in registration.owned_directories
    }


def compile_registered_fact_providers(
    registry_root: Path,
    *,
    modelos: Iterable[ModeloDefinition] | None = None,
) -> GovernedFactCatalogue:
    """Compile every registered provider into one identity-keyed catalogue."""
    compiled_modelos = None if modelos is None else tuple(modelos)
    facts: dict[str, GovernedFact] = {}
    owner_by_fact_id: dict[str, str] = {}
    for registration in FACT_PROVIDER_REGISTRATIONS:
        compiled = registration.compile(registry_root)
        if compiled_modelos is not None and registration.project_modelos is not None:
            compiled = (*compiled, *registration.project_modelos(compiled_modelos))
        for fact in compiled:
            previous_owner = owner_by_fact_id.get(fact.fact_id)
            if previous_owner is not None:
                raise RegistryValidationError(
                    f"governed fact {fact.fact_id!r} from provider {registration.provider_id!r} "
                    f"is already owned by provider {previous_owner!r}",
                )
            owner_by_fact_id[fact.fact_id] = registration.provider_id
            facts[fact.fact_id] = fact.model_copy(update={"provider_id": registration.provider_id})
    return GovernedFactCatalogue(facts=facts)


def collect_registered_fact_provider_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Collect every provider fingerprint in canonical registration order."""
    return tuple(
        fingerprint
        for registration in FACT_PROVIDER_REGISTRATIONS
        for fingerprint in registration.collect_fingerprints(registry_root)
    )


def reset_registered_fact_providers() -> None:
    """Reset every provider-owned cache in canonical registration order."""
    for registration in FACT_PROVIDER_REGISTRATIONS:
        registration.reset()


def validate_fact_provider_directory_ownership(registry_root: Path) -> None:
    """Refuse governed directories outside every registered provider root."""
    owned = registered_fact_provider_directories()
    root = registry_root.resolve()

    def owner_for(relative: str) -> FactProviderRegistration | None:
        path = PurePosixPath(relative)
        return next(
            (
                registration
                for owned_directory, registration in owned.items()
                if path == PurePosixPath(owned_directory) or path.is_relative_to(PurePosixPath(owned_directory))
            ),
            None,
        )

    for entry in scan_directory(root, select=DirectoryEntryKind.DIRECTORIES):
        if any(
            is_governed_fact_filename(path.name)
            for path in scan_directory(entry, pattern="*.toml", select=DirectoryEntryKind.FILES)
        ):
            relative = PurePosixPath(*entry.relative_to(root).parts).as_posix()
            if owner_for(relative) is None:
                raise RegistryValidationError(f"governed fact directory {relative!r} has no registered provider")
    for relative_directory in owned:
        provider_root = root / Path(*PurePosixPath(relative_directory).parts)
        if not provider_root.is_dir():
            continue
        for entry in scan_directory(provider_root, select=DirectoryEntryKind.DIRECTORIES, recursive=True):
            relative = PurePosixPath(*entry.relative_to(root).parts).as_posix()
            if owner_for(relative) is None:
                raise RegistryValidationError(
                    f"governed fact directory {relative!r} has no registered provider",
                )


def _validated_owned_directory(provider_id: str, raw_directory: str) -> PurePosixPath:
    directory = PurePosixPath(raw_directory)
    if (
        not raw_directory
        or "\\" in raw_directory
        or directory.is_absolute()
        or directory.as_posix() != raw_directory
        or any(part in {"", ".", ".."} for part in directory.parts)
    ):
        raise RegistryValidationError(
            f"governed fact provider {provider_id!r} owns invalid relative directory {raw_directory!r}",
        )
    return directory


def _compile_authored_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    return load_governed_facts(registry_root.resolve() / "facts")


def _collect_authored_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    facts_dir = registry_root.resolve() / "facts"
    return tuple(
        toml_file_fingerprint(path.resolve())
        for path in scan_directory(facts_dir, pattern="*.toml", recursive=True, select=DirectoryEntryKind.FILES)
    )


def _reset_authored_fact_provider() -> None:
    """Reset the authored provider, which intentionally owns no local cache."""


def _compile_no_direct_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Return no direct facts for providers that project compiled authority."""
    del registry_root
    return ()


def _collect_no_direct_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Return no duplicate fingerprints for already-identified modelo files."""
    del registry_root
    return ()


def _reset_no_direct_provider() -> None:
    """Reset a projection-only provider, which owns no independent cache."""


def _modelo_parameter_projection_registration() -> FactProviderRegistration:
    from .modelo_projections import (
        MODELO_PARAMETER_PROJECTION_PROVIDER_ID,
        compile_modelo_parameter_projection_facts,
    )

    return FactProviderRegistration(
        provider_id=MODELO_PARAMETER_PROJECTION_PROVIDER_ID,
        owned_directories=(),
        compile=_compile_no_direct_facts,
        collect_fingerprints=_collect_no_direct_fingerprints,
        reset=_reset_no_direct_provider,
        project_modelos=compile_modelo_parameter_projection_facts,
        inherited_identity_domains=("modelos",),
    )


FACT_PROVIDER_REGISTRATIONS = validate_fact_provider_registrations(
    (
        FactProviderRegistration(
            provider_id="authored-facts",
            owned_directories=("facts",),
            compile=_compile_authored_facts,
            collect_fingerprints=_collect_authored_fact_fingerprints,
            reset=_reset_authored_fact_provider,
        ),
        _modelo_parameter_projection_registration(),
    ),
)
"""The sole canonical declaration of governed-fact providers and ownership."""
