"""Canonical provider registration and directory ownership for governed facts."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from ..errors import RegistryValidationError
from ..loader_cache import toml_file_fingerprint
from ..loader_fingerprints import RegistryPathFingerprints
from .loader import is_governed_fact_filename, load_governed_facts
from .schema import GovernedFact, GovernedFactCatalogue

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


@dataclass(frozen=True, slots=True)
class FactProviderRegistration:
    """One provider's complete loading, identity, reset, and ownership contract."""

    provider_id: str
    owned_directories: tuple[str, ...]
    compile: FactProviderCompiler
    collect_fingerprints: Callable[[Path], RegistryPathFingerprints]
    reset: Callable[[], None]


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
        if not registration.owned_directories:
            raise RegistryValidationError(
                f"governed fact provider {registration.provider_id!r} must own at least one directory",
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


def compile_registered_fact_providers(registry_root: Path) -> GovernedFactCatalogue:
    """Compile every registered provider into one identity-keyed catalogue."""
    facts: dict[str, GovernedFact] = {}
    owner_by_fact_id: dict[str, str] = {}
    for registration in FACT_PROVIDER_REGISTRATIONS:
        for fact in registration.compile(registry_root):
            previous_owner = owner_by_fact_id.get(fact.fact_id)
            if previous_owner is not None:
                raise RegistryValidationError(
                    f"governed fact {fact.fact_id!r} from provider {registration.provider_id!r} "
                    f"is already owned by provider {previous_owner!r}",
                )
            owner_by_fact_id[fact.fact_id] = registration.provider_id
            facts[fact.fact_id] = fact
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
    """Refuse governed top-level or nested directories without an exact owner."""
    owned = registered_fact_provider_directories()
    root = registry_root.resolve()
    for entry in scan_directory(root, select=DirectoryEntryKind.DIRECTORIES):
        if any(
            is_governed_fact_filename(path.name)
            for path in scan_directory(entry, pattern="*.toml", select=DirectoryEntryKind.FILES)
        ):
            relative = PurePosixPath(*entry.relative_to(root).parts).as_posix()
            if relative not in owned:
                raise RegistryValidationError(f"governed fact directory {relative!r} has no registered provider")
    for relative_directory in owned:
        provider_root = root / Path(*PurePosixPath(relative_directory).parts)
        if not provider_root.is_dir():
            continue
        for entry in scan_directory(provider_root, select=DirectoryEntryKind.DIRECTORIES, recursive=True):
            relative = PurePosixPath(*entry.relative_to(root).parts).as_posix()
            if relative not in owned:
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
        for path in scan_directory(facts_dir, pattern="*.toml", select=DirectoryEntryKind.FILES)
    )


def _reset_authored_fact_provider() -> None:
    """Reset the authored provider, which intentionally owns no local cache."""


FACT_PROVIDER_REGISTRATIONS = validate_fact_provider_registrations(
    (
        FactProviderRegistration(
            provider_id="authored-facts",
            owned_directories=("facts",),
            compile=_compile_authored_facts,
            collect_fingerprints=_collect_authored_fact_fingerprints,
            reset=_reset_authored_fact_provider,
        ),
    ),
)
"""The sole canonical declaration of governed-fact providers and ownership."""
