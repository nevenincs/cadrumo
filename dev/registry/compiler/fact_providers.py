"""Canonical provider registration and directory ownership for governed facts.

The authored-facts boundary in this module is intentionally independent of the
Modelo compiler.  ``compile_authored_fact_catalogue`` is the production-facing
entry point for a facts-only publication: it reads only ``<registry>/facts``,
validates every declaration through the governed-fact schema, and returns a
deterministically keyed catalogue.  The broader provider function remains
available for the full registry compiler, where Modelo projections are
explicitly supplied by the caller.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Protocol

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import (
    EntitySetFactPayload,
    GovernedFact,
    GovernedFactCatalogue,
)

from .fact_loader import is_governed_fact_filename, load_governed_facts
from .loader_cache import toml_file_fingerprint
from .loader_fingerprints import RegistryPathFingerprints

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloDefinition

__all__ = [
    "AUTHORED_FACT_PROVIDER_ID",
    "FACTS_CANDIDATE_SCHEMA",
    "FACT_PROVIDER_REGISTRATIONS",
    "FactProviderCompiler",
    "FactProviderRegistration",
    "collect_registered_fact_provider_fingerprints",
    "compile_authored_fact_catalogue",
    "compile_registered_fact_providers",
    "deterministic_fact_index",
    "fact_catalogue_digest",
    "registered_fact_provider_directories",
    "reset_registered_fact_providers",
    "serialize_fact_catalogue",
    "validate_fact_provider_directory_ownership",
    "validate_fact_provider_registrations",
]


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
AUTHORED_FACT_PROVIDER_ID = "authored-facts"
"""The provider identity attached to directly authored fact declarations."""

FACTS_CANDIDATE_SCHEMA = "cadrumo-governed-facts-candidate-v1"
"""Versioned schema marker for the deterministic facts-only candidate bytes."""

_MODELO_SCOPED_AUTHORED_FACTS: Mapping[str, str] = {
    "liva-orden-lorca-reduction": "303",
}
"""Authored facts whose legal authority is compiled with one modelo's supplements."""


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


def deterministic_fact_index(
    facts: Mapping[str, GovernedFact] | Iterable[GovernedFact],
) -> dict[str, GovernedFact]:
    """Return a semantic-ID keyed fact index in stable lexical order.

    The source loader preserves filename order for review and duplicate-error
    reporting.  Publication must not depend on that incidental order, so the
    candidate boundary rekeys every fact by its semantic ``fact_id`` and sorts
    those IDs before constructing the catalogue payload.

    A mapping is accepted for callers that already have a catalogue; an
    iterable is accepted for the authored loader.  In both forms, duplicate
    semantic identities and mismatched mapping keys fail closed.
    """
    if isinstance(facts, Mapping):
        entries = tuple(facts.items())
        for key, fact in entries:
            if key != fact.fact_id:
                raise RegistryValidationError(
                    f"governed fact catalogue key {key!r} does not match fact_id {fact.fact_id!r}",
                )
    else:
        entries = tuple((fact.fact_id, fact) for fact in facts)
    indexed: dict[str, GovernedFact] = {}
    for fact_id, fact in sorted(entries, key=lambda item: item[0]):
        if fact_id in indexed:
            raise RegistryValidationError(f"governed fact {fact_id!r} is declared more than once")
        indexed[fact_id] = fact
    return indexed


def compile_authored_fact_catalogue(registry_root: Path) -> GovernedFactCatalogue:
    """Compile only directly authored facts, without loading any Modelo data.

    ``registry_root`` is the canonical ``.../registry/aeat`` root.  The facts
    directory must exist and contain at least one declaration: a facts-only
    publication must never turn missing source data into an empty successful
    candidate.  Each file is parsed by :func:`load_governed_facts`, which
    applies the complete governed-fact Pydantic schema and refuses generated
    variants in authored files.

    The returned catalogue carries compiler-owned provider provenance and is
    keyed deterministically by semantic fact ID.  No Modelo revision loader,
    projection, or validation is reachable from this function.
    """
    facts_dir = registry_root.resolve() / "facts"
    if not facts_dir.is_dir():
        raise RegistryLoadError(f"authored governed-facts directory is missing: {facts_dir}")
    authored = load_governed_facts(facts_dir)
    if not authored:
        raise RegistryLoadError(f"authored governed-facts directory contains no TOML declarations: {facts_dir}")
    indexed = deterministic_fact_index(
        fact.model_copy(update={"provider_id": AUTHORED_FACT_PROVIDER_ID}) for fact in authored
    )
    return GovernedFactCatalogue(facts=indexed)


def serialize_fact_catalogue(catalogue: GovernedFactCatalogue) -> bytes:
    """Serialize a deterministic facts-only candidate payload for publication.

    This is a candidate projection, not the full authority artifact.  The
    authority publisher remains the owner of the artifact envelope and its
    unrelated catalogues; this byte representation gives that publisher an
    auditable facts index and a stable digest without requiring Modelo input.
    """
    indexed = deterministic_fact_index(catalogue.facts)

    def serialize_fact(fact: GovernedFact) -> dict[str, object]:
        serialized = fact.model_dump(mode="json")
        for variant_index, variant in enumerate(fact.variants):
            if isinstance(variant.payload, EntitySetFactPayload):
                # Entity-set members are semantically unordered, but the
                # schema materialises them as a frozenset.  Canonical
                # candidate bytes must impose an order before hashing or
                # fresh processes can disagree.
                serialized["variants"][variant_index]["payload"]["entities"] = sorted(
                    serialized["variants"][variant_index]["payload"]["entities"],
                )
        return serialized

    return canonical_json_bytes(
        {
            "schema": FACTS_CANDIDATE_SCHEMA,
            "facts": {fact_id: serialize_fact(fact) for fact_id, fact in indexed.items()},
        },
    )


def fact_catalogue_digest(catalogue: GovernedFactCatalogue) -> str:
    """Return the lowercase SHA-256 digest of the canonical facts candidate."""
    return sha256_hex(serialize_fact_catalogue(catalogue))


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
    present_modelo_ids = None if compiled_modelos is None else {str(modelo.id) for modelo in compiled_modelos}
    facts: dict[str, GovernedFact] = {}
    owner_by_fact_id: dict[str, str] = {}
    for registration in FACT_PROVIDER_REGISTRATIONS:
        compiled = registration.compile(registry_root)
        if compiled_modelos is not None and registration.project_modelos is not None:
            compiled = (*compiled, *registration.project_modelos(compiled_modelos))
        for fact in compiled:
            required_modelo = _MODELO_SCOPED_AUTHORED_FACTS.get(fact.fact_id)
            if (
                required_modelo is not None
                and present_modelo_ids is not None
                and required_modelo not in present_modelo_ids
            ):
                continue
            previous_owner = owner_by_fact_id.get(fact.fact_id)
            if previous_owner is not None:
                raise RegistryValidationError(
                    f"governed fact {fact.fact_id!r} from provider {registration.provider_id!r} "
                    f"is already owned by provider {previous_owner!r}",
                )
            owner_by_fact_id[fact.fact_id] = registration.provider_id
            facts[fact.fact_id] = fact.model_copy(update={"provider_id": registration.provider_id})
    return GovernedFactCatalogue(facts=deterministic_fact_index(facts))


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
            provider_id=AUTHORED_FACT_PROVIDER_ID,
            owned_directories=("facts",),
            compile=_compile_authored_facts,
            collect_fingerprints=_collect_authored_fact_fingerprints,
            reset=_reset_authored_fact_provider,
        ),
        _modelo_parameter_projection_registration(),
    ),
)
"""The sole canonical declaration of governed-fact providers and ownership."""
