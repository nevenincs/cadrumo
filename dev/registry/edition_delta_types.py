"""Typed planning results for registry edition delta migration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

__all__ = ("BlockedCause", "EditionPlan", "KeptReason", "LiftCounts", "MigrationPlan", "PredecessorBasis")


class PredecessorBasis(StrEnum):
    """How an edition's predecessor declaration was decided."""

    FIRST = "first"
    ADJACENT = "adjacent"
    DECLARED = "declared"
    STORAGE = "storage"
    DECLARED_ROOT = "declared_root"
    BLOCKED = "blocked"
    #: The edition's inheritance is left exactly as authored and only its
    #: restatement is lifted, because the modelo is already delta-authored and
    #: is proven against its chain rather than against a full copy.
    LIFT_ONLY = "lift_only"


class BlockedCause(StrEnum):
    """Why an edition cannot be delta-authored exactly against its adjacent earlier edition."""

    OVERLAPPING_PREDECESSOR = "overlapping_predecessor"
    #: Renamed fragments would state the edition's new rows out of their full-copy order.
    ROW_ORDER = "row_order"
    UNRETIRED_WITHDRAWAL = "unretired_withdrawal"
    PREDECESSOR_ROW_WITHOUT_LINEAGE = "predecessor_row_without_lineage"
    #: Includes a planned delta the loader refuses to materialise, such as a
    #: lineage carried twice or an undeclared repurpose; the detail is its refusal.
    TRANSFORMATION_FAILED = "transformation_failed"


class KeptReason(StrEnum):
    """Why a row of a delta edition stays stated."""

    NEW_LINEAGE = "new_lineage"
    DIFFERS = "differs"
    NOT_EXACT = "screen_identical_not_exact"


@dataclass(frozen=True, slots=True)
class LiftCounts:
    """How many restated references an edition stops stating."""

    row_source_refs: int = 0
    constraint_source_refs: int = 0
    row_orden_legal_refs: int = 0
    constraint_orden_legal_refs: int = 0

    def total(self) -> int:
        """Return the number of lifted references of every kind."""
        return (
            self.row_source_refs
            + self.constraint_source_refs
            + self.row_orden_legal_refs
            + self.constraint_orden_legal_refs
        )


@dataclass(frozen=True, slots=True)
class EditionPlan:
    """What the migration writes for one edition, and the counts that justify it."""

    revision_id: str
    basis: PredecessorBasis
    predecessor: str | None
    blocked: tuple[BlockedCause, ...]
    source_default: tuple[str, ...] | None
    source_default_withheld: str | None
    rows_before: int
    stated_ids: tuple[str, ...]
    inherited_ids: tuple[str, ...]
    lifted: LiftCounts
    kept: Mapping[KeptReason, int]
    not_exact: tuple[str, ...]
    comments_dropped: int
    reviewed_against: str | None
    dependencies: tuple[str, ...] = ()
    blocked_detail: tuple[str, ...] = ()
    casilla_overrides: tuple[dict[str, object], ...] = ()
    casilla_removals: tuple[dict[str, object], ...] = ()
    casilla_positions: tuple[dict[str, object], ...] = ()
    lineage_attestations: tuple[LineageAttestation, ...] = ()

    @property
    def is_delta(self) -> bool:
        """Whether the edition is compacted against an explicit dependency."""
        return self.predecessor is not None and self.basis in {
            PredecessorBasis.ADJACENT,
            PredecessorBasis.DECLARED,
            PredecessorBasis.STORAGE,
        }


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """Every edition's plan for one modelo, in validity order."""

    modelo_id: str
    editions: tuple[EditionPlan, ...]
    already_delta_authored: bool

    def blocked_roots(self) -> tuple[str, ...]:
        """Return blocked editions retained unchanged as readable full-copy roots."""
        return tuple(edition.revision_id for edition in self.editions if edition.basis is PredecessorBasis.BLOCKED)

    def completed(self) -> tuple[str, ...]:
        """Return revisions whose authored representation is compacted."""
        return tuple(edition.revision_id for edition in self.editions if edition.is_delta)

    def unchanged(self) -> tuple[str, ...]:
        """Return readable revisions retained unchanged, excluding blockers."""
        return tuple(
            edition.revision_id
            for edition in self.editions
            if not edition.is_delta and edition.basis is not PredecessorBasis.BLOCKED
        )
