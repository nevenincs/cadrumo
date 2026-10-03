"""Shared result types and immutable policy values for registry collapse verification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypedDict

from cadrumo.domain.calculations.registry.facts.payloads import GovernedFactFamily
from cadrumo.domain.calculations.registry.facts.resolution import (
    BracketFactQuery,
    EntitySetFactQuery,
    EventFactQuery,
    MappingFactQuery,
    MultiOutputFactQuery,
    OverrideFactQuery,
    ScalarFactQuery,
)
from cadrumo.domain.calculations.registry.keyed_families import CANONICAL_FAMILY_SPECS
from cadrumo.domain.calculations.registry.schema import (
    REVISION_SCHEMA_FAMILY_FIELDS,
)

_MODELOS: Final = "modelos"


_REPRESENTATION_ONLY: Final = frozenset(
    {
        "inherited_from",
        "predecessor",
        "casilla_storage_baseline",
        "casilla_overrides",
        "casilla_removals",
        "casilla_positions",
        "lineage_attestations",
        "family_storage_baseline",
        "family_overrides",
        "family_removals",
        "family_positions",
        "cleared_families",
        "scoped_families",
    }
)


_FACT_QUERY_TYPES: Final = {
    GovernedFactFamily.SCALAR: ScalarFactQuery,
    GovernedFactFamily.BRACKET: BracketFactQuery,
    GovernedFactFamily.MAPPING: MappingFactQuery,
    GovernedFactFamily.ENTITY_SET: EntitySetFactQuery,
    GovernedFactFamily.OVERRIDE: OverrideFactQuery,
    GovernedFactFamily.EVENT: EventFactQuery,
    GovernedFactFamily.MULTI_OUTPUT: MultiOutputFactQuery,
}


_EXPECTED_ASSESSMENT_FAMILIES: Final = REVISION_SCHEMA_FAMILY_FIELDS | frozenset(
    spec.section for spec in CANONICAL_FAMILY_SPECS if spec.singleton
)


class ModeloOutcome(StrEnum):
    """Closed per-model result vocabulary for registry-wide execution."""

    ALREADY_MINIMAL = "already_minimal"
    CONVERTED = "converted_candidate"
    PARTIAL = "partially_converted"
    REFUSED = "refused"
    UNASSESSED = "unassessed_dependency"


class CheckStatus(StrEnum):
    """Machine-readable status for one verification limb."""

    PASSED = "passed"
    FAILED = "failed"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class RootEligibility(StrEnum):
    """Storage-baseline eligibility of one revision/family edge."""

    EXISTING_INHERITANCE = "valid_existing_inheritance"
    CANDIDATE = "storage_baseline_candidate"
    INCOMPATIBLE = "incompatible_branch"
    UNRESOLVED = "unresolved_baseline_eligibility"
    FIRST_REVISION = "first_revision"


@dataclass(frozen=True, slots=True)
class FingerprintEntry:
    """One immutable file-content receipt."""

    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class RequestCoordinate:
    """One canonical temporal request exercised by the verifier."""

    filing_year: int
    period: str
    on: str | None
    revision_id: str | None
    case: str


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """One independent verification result and its exact differences."""

    status: CheckStatus
    checked: int
    differences: tuple[Mapping[str, object], ...] = ()
    detail: str | None = None


class FindingTransition(TypedDict):
    """Exact finding-set delta between two measurements."""

    removed: list[str]
    added: list[str]
    unchanged: int
