"""Canonical data types for planning and proving registry restatement drops."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_assessment as _edition_delta_assessment
from . import edition_delta_order_restoration as _edition_delta_order_restoration
from . import edition_delta_source as _edition_delta_source
from .edition_round_trip import RoundTripFinding, RoundTripReport

__all__ = ("DropOutcome", "DropPlan", "EditionDrop", "FamilyDrop")


@dataclass(frozen=True, slots=True)
class _MemberFragment:
    """One family fragment file, split into its preamble and its member blocks."""

    path: Path
    preamble: str
    blocks: tuple[_edition_delta_source._Block, ...]


@dataclass(frozen=True, slots=True)
class FamilyDrop:
    """What one family of one edition would lose, and what it keeps and why."""

    section: str
    dropped: tuple[str, ...]
    kept_new: tuple[str, ...]
    kept_differs: tuple[str, ...]
    kept_pinned: tuple[str, ...]
    lineage_attestations: tuple[LineageAttestation, ...] = ()
    kept_no_identity: int = 0

    @property
    def stated(self) -> int:
        """How many members the edition states in this family."""
        return (
            len(self.dropped)
            + len(self.kept_new)
            + len(self.kept_differs)
            + len(self.kept_pinned)
            + self.kept_no_identity
        )


@dataclass(frozen=True, slots=True)
class EditionDrop:
    """What one edition would lose across every family the drop accepts."""

    revision_id: str
    predecessor: str | None
    skipped: str | None
    families: tuple[FamilyDrop, ...]

    @property
    def dropped(self) -> int:
        """How many members this edition would stop stating."""
        return sum(len(family.dropped) for family in self.families)


@dataclass(frozen=True, slots=True)
class DropPlan:
    """What a whole modelo would lose, decided without writing anything."""

    modelo_id: str
    editions: tuple[EditionDrop, ...]

    @property
    def dropped(self) -> int:
        """How many members the whole modelo would stop stating."""
        return sum(edition.dropped for edition in self.editions)


@dataclass
class _FamilyDropState:
    dropped: list[str] = field(default_factory=list)
    kept_new: list[str] = field(default_factory=list)
    kept_differs: list[str] = field(default_factory=list)
    kept_pinned: list[str] = field(default_factory=list)
    lineage_attestations: list[LineageAttestation] = field(default_factory=list)
    kept_no_identity: int = 0


@dataclass(frozen=True, slots=True)
class DropOutcome:
    """The result of planning, staging and proving one modelo's drop."""

    plan: DropPlan
    staged_registry: Path | None
    report: RoundTripReport | None
    applied: bool
    changed: bool
    #: Positions written so complete statements keep the order they state.
    order_restorations: tuple[_edition_delta_order_restoration.OrderRestoration, ...] = ()
    #: Every ``(revision, family)`` whose member order those positions change.
    reordered_families: tuple[tuple[str, str], ...] = ()

    @property
    def source_findings(self) -> tuple[RoundTripFinding, ...]:
        """Return reconstruction and effective-data failures."""
        return (
            ()
            if self.report is None
            else tuple(f for f in self.report.findings if _edition_delta_assessment._is_source_finding(f))
        )

    @property
    def publication_readiness_findings(self) -> tuple[RoundTripFinding, ...]:
        """Return findings owned by later authority publication."""
        return (
            ()
            if self.report is None
            else tuple(f for f in self.report.findings if not _edition_delta_assessment._is_source_finding(f))
        )

    @property
    def source_status(self) -> _edition_delta_assessment.SourceMigrationStatus:
        """Return the source replacement acceptance state."""
        if self.source_findings:
            return _edition_delta_assessment.SourceMigrationStatus.REFUSED
        return (
            _edition_delta_assessment.SourceMigrationStatus.APPLIED
            if self.applied
            else _edition_delta_assessment.SourceMigrationStatus.ACCEPTED
        )

    @property
    def publication_readiness_status(self) -> _edition_delta_assessment.PublicationReadinessStatus:
        """Return the separately observed authority-readiness state."""
        if self.publication_readiness_findings:
            return _edition_delta_assessment.PublicationReadinessStatus.FAILED
        return _edition_delta_assessment.PublicationReadinessStatus.NOT_CHECKED

    @property
    def publication_execution_status(self) -> _edition_delta_assessment.PublicationExecutionStatus:
        """Confirm that source migration did not execute publication."""
        return _edition_delta_assessment.PublicationExecutionStatus.NOT_PERFORMED
