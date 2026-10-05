"""Import health models."""

from __future__ import annotations

from typing import Final, TypedDict

RATCHET_SCHEMA_VERSION: Final[int] = 1


SIGNAL_SCHEMA_VERSION: Final[int] = 2


class GraphSummary(TypedDict):
    """Parsed Import Linter graph facts used by the health verdict."""

    contracts_broken: int
    contracts_kept: int
    contracts_total: int
    broken_contract_names: list[str]
    contract_status: dict[str, str]
    dependencies: int
    files: int


class EvidenceRow(TypedDict):
    """Source location evidence for one direct import."""

    line: int
    path: str


class OccurrenceRow(TypedDict):
    """Normalized identity and multiplicity of one import occurrence."""

    contract: str
    evidence: list[EvidenceRow]
    fingerprint: str
    import_form: str
    imported_symbols: list[str]
    lexical_scope: str
    multiplicity: int
    source_module: str
    target_module: str
    test_scoped: bool


class OccurrenceSummary(TypedDict):
    """Counts and digest for one occurrence inventory."""

    contract_occurrences: int
    by_contract: dict[str, int]
    by_import_form: dict[str, int]
    non_test_scoped_occurrences: int
    test_scoped_occurrences: int
    inventory_digest: str
    unique_contract_occurrences: int
    unique_import_occurrences: int


class CandidateSummary(OccurrenceSummary):
    """Separate hard and advisory occurrence accounting."""

    advisory_by_contract: dict[str, int]
    advisory_by_lane_pair: dict[str, int]
    advisory_non_test_scoped_occurrences: int
    advisory_occurrences: int
    advisory_test_scoped_occurrences: int
    advisory_unique_occurrences: int


class CandidateInventory(TypedDict):
    """Timestamped direct import inventories and their closed summaries."""

    advisory_occurrences: list[OccurrenceRow]
    generated_at: str
    occurrences: list[OccurrenceRow]
    schema_version: int
    summary: CandidateSummary


class RatchetCounts(TypedDict):
    """Closed counts for import debt and retirement states."""

    approved_active: int
    root_boundary: int
    new_unapproved: int
    expanded_existing: int
    expired: int
    malformed: int
    regressed_retired: int
    retirement_candidates: int
    retirement_ready: int
    retired_verified: int
    retired_source_removed: int


class RatchetEntry(TypedDict):
    """Validated debt approval bound to one import fingerprint."""

    fingerprint: str
    source_module: str
    target_module: str
    import_form: str
    imported_symbols: list[str]
    lexical_scope: str
    contract: str
    owner: str
    reason: str
    capability: str
    multiplicity: int
    created_on: str
    expires_on: str
    status: str


class RatchetReport(TypedDict):
    """Ratchet reconciliation evidence and accounting."""

    baseline_status: str
    counts: RatchetCounts
    detail_counts: dict[str, int]
    details: dict[str, list[str]]
    path: str
    schema_version: int
