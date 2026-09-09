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
from .loader import load_governed_facts
from .schema import GovernedFact

__all__ = [
    "FACT_PROVIDER_REGISTRATIONS",
    "FactProviderCompiler",
    "FactProviderRegistration",
    "fact_provider_for_directory",
    "registered_fact_provider_directories",
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


def fact_provider_for_directory(directory: str) -> FactProviderRegistration:
    """Resolve an exact governed directory or fail closed when it is unowned."""
    normalized = _validated_owned_directory("lookup", directory).as_posix()
    registration = registered_fact_provider_directories().get(normalized)
    if registration is None:
        raise RegistryValidationError(f"governed fact directory {normalized!r} has no registered provider")
    return registration


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
