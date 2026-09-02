"""Frontend-neutral calendar-evidence provider.

The provider accepts source values that an entrypoint or composition root has
already loaded.  It owns neither repositories nor remote reads; its only job is
to preserve the authority/freshness of each evidence axis and delegate the
actual reconciliation to :func:`calendar_filing_evidence_from_sources`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .calendar_evidence import calendar_filing_evidence_from_sources
from .calendar_models import OverviewAeatSubmissionState, OverviewCalendarFilingEvidence, OverviewLocalFilingState
from .home import HomeAvailability, HomeZoneState

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionObservation
    from ...domain.justificante import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ..calculations.observations_repository import ObservationEnvelopePayload
    from ..live.justificante import JustificanteCaptureSnapshot
    from .calendar_models import OverviewCalendarEvent


@dataclass(frozen=True, slots=True)
class CalendarEvidenceSources:
    """Already-loaded sources consumed by the calendar evidence reconciler.

    Verified artefact CSVs use a sorted tuple rather than a mutable mapping so
    the source bundle stays immutable and has a deterministic representation.
    """

    filing_records: tuple[ModeloRecord, ...] = ()
    observed_events: tuple[OverviewCalendarEvent, ...] = ()
    filed_declaration_observations: tuple[FiledDeclaracionObservation, ...] = ()
    verified_filed_declaration_artefact_refs: tuple[str, ...] = ()
    verified_filed_declaration_artefact_csvs: tuple[tuple[str, str], ...] = ()
    calculation_observations: tuple[ObservationEnvelopePayload, ...] = ()
    justificante_capture_snapshots: tuple[JustificanteCaptureSnapshot, ...] = ()
    justificantes: tuple[Justificante, ...] = ()

    def __post_init__(self) -> None:
        """Reject order-dependent or ambiguous verified-artefact metadata."""
        refs = tuple(ref for ref, _csv in self.verified_filed_declaration_artefact_csvs)
        if refs != tuple(sorted(refs)):
            raise ValueError("verified filed-declaration artefact CSVs must be sorted by reference")
        if len(set(refs)) != len(refs):
            raise ValueError("verified filed-declaration artefact CSV references must be unique")


@dataclass(frozen=True, slots=True)
class CalendarEvidenceReadOutcome:
    """One already-completed source read with explicit authority and freshness."""

    state: HomeZoneState
    value: CalendarEvidenceSources | None = None

    def __post_init__(self) -> None:
        """Keep source values consistent with their declared availability."""
        observable = self.state.availability in {
            HomeAvailability.AVAILABLE,
            HomeAvailability.STALE,
        }
        if observable and self.value is None:
            raise ValueError("an available or stale evidence read requires its loaded source bundle")
        if not observable and self.value is not None:
            raise ValueError("a locked, never-captured, or unavailable evidence read cannot carry source values")


@dataclass(frozen=True, slots=True)
class CalendarEvidenceProjection:
    """Reconciled evidence plus independent local and AEAT source truth."""

    local_state: HomeZoneState
    aeat_state: HomeZoneState
    evidence: tuple[OverviewCalendarFilingEvidence, ...] = field(default_factory=tuple)


def build_calendar_evidence_projection(
    *,
    local: CalendarEvidenceReadOutcome,
    aeat: CalendarEvidenceReadOutcome,
    expected_tax_id: str | None = None,
) -> CalendarEvidenceProjection:
    """Reconcile already-loaded sources without performing implicit I/O.

    ``STALE`` is observable: its last known values and ``observed_at`` survive
    unchanged.  The other non-observable states never become a false empty or a
    false submission claim.  The underlying reconciler owns all strength,
    identity, and natural ``(modelo, filing year, period)`` joins.
    """
    local_sources = local.value or CalendarEvidenceSources()
    aeat_sources = aeat.value or CalendarEvidenceSources()
    evidence = calendar_filing_evidence_from_sources(
        filing_records=local_sources.filing_records,
        observed_events=aeat_sources.observed_events,
        filed_declaration_observations=aeat_sources.filed_declaration_observations,
        verified_filed_declaration_artefact_refs=aeat_sources.verified_filed_declaration_artefact_refs,
        verified_filed_declaration_artefact_csvs=dict(aeat_sources.verified_filed_declaration_artefact_csvs),
        calculation_observations=aeat_sources.calculation_observations,
        justificante_capture_snapshots=aeat_sources.justificante_capture_snapshots,
        justificantes=aeat_sources.justificantes,
        expected_tax_id=expected_tax_id,
    )
    return CalendarEvidenceProjection(
        local_state=local.state,
        aeat_state=aeat.state,
        evidence=tuple(
            _mask_unobservable_axes(row, local_state=local.state, aeat_state=aeat.state) for row in evidence
        ),
    )


def _mask_unobservable_axes(
    row: OverviewCalendarFilingEvidence,
    *,
    local_state: HomeZoneState,
    aeat_state: HomeZoneState,
) -> OverviewCalendarFilingEvidence:
    """Prevent one unavailable axis from erasing or overstating the other."""
    updates: dict[str, object] = {}
    if local_state.availability not in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}:
        updates.update(
            local_filing_state=OverviewLocalFilingState.NOT_READY_TO_FILE,
            local_filing_record_id=None,
            local_calculation_revision_id=None,
            local_filed_at=None,
        )
    if aeat_state.availability not in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}:
        updates.update(
            aeat_submission_state=OverviewAeatSubmissionState.NOT_OBSERVED,
            aeat_submitted_at=None,
            aeat_reference_id=None,
            aeat_snapshot_id=None,
            aeat_evidence_kind=None,
            aeat_evidence_conflict_reference_ids=(),
            verified_justificante_csv=None,
            justificante_verified=False,
        )
    return row if not updates else row.model_copy(update=updates)


__all__ = [
    "CalendarEvidenceProjection",
    "CalendarEvidenceReadOutcome",
    "CalendarEvidenceSources",
    "build_calendar_evidence_projection",
]
