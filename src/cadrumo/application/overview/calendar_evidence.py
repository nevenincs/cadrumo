"""Calendar event dedup and filing-evidence reconciliation for the overview read model.

Extracted from :mod:`~cadrumo.application.overview.calendar` (size-budget
split) to keep the calendar module and its ``build_overview_calendar``
entry point under their line-count overrides. This module owns two
cohesive concerns:

* Deterministic dedup of observed :class:`OverviewCalendarEvent` rows
  across multiple local snapshots (``_calendar_event_sort_key``,
  ``_dedupe_calendar_events``), shared by every calendar-events builder.
* Reconciling already-loaded local and AEAT-side signals -- filed Modelo
  records, observed register events, filed-declaration observations,
  persisted calculation observations, live justificante captures, and
  loaded justificante metadata -- into typed
  :class:`OverviewCalendarFilingEvidence` rows
  (:func:`calendar_filing_evidence_from_sources`), and merging that
  evidence back onto calendar entries and events.

This module is local-only and pure with respect to I/O, exactly like its
parent: it never starts a live AEAT read and never verifies a
justificante by fetching external state; it only reconciles evidence the
caller has already loaded.

See Also:
    :mod:`cadrumo.application.overview.calendar`
        Composes :func:`calendar_filing_evidence_from_sources` and the
        other builders here into :func:`~cadrumo.application.overview.calendar.build_overview_calendar`.
    :mod:`cadrumo.application.overview.calendar`
        Composes this evidence projection into the overview calendar.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...application.operator_actions.catalogue import next_action
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.period import Period as _Period
from ...domain.calculations.registry.applicability_routes import TaxRoute
from ..calculations.observations_repository import ObservationSourceKind
from ..calculations.ports import FiledDeclaracionObservationProtocol
from ._calendar_evidence_sources import (
    authenticated_identity_matches_expected as _authenticated_identity_matches_expected,
)
from ._calendar_evidence_sources import (
    filing_axes_from_modelo_record as _filing_axes_from_modelo_record,
)
from ._calendar_evidence_sources import (
    filing_evidence_from_calculation_observation as _filing_evidence_from_calculation_observation,
)
from ._calendar_evidence_sources import (
    filing_evidence_from_filed_declaration_observation as _filing_evidence_from_filed_declaration_observation,
)
from ._calendar_evidence_sources import (
    filing_evidence_from_justificante_capture_snapshot as _filing_evidence_from_justificante_capture_snapshot,
)
from ._calendar_evidence_sources import (
    filing_evidence_from_modelo_record as _filing_evidence_from_modelo_record,
)
from ._calendar_evidence_sources import (
    filing_evidence_from_observed_event as _filing_evidence_from_observed_event,
)
from ._calendar_evidence_sources import (
    is_active_aeat_filing_status as _is_active_aeat_filing_status,
)
from ._calendar_evidence_sources import (
    justificante_csv_key as _justificante_csv_key,
)
from ._calendar_evidence_sources import (
    justificantes_by_csv as _justificantes_by_csv,
)
from .calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewLocalFilingState,
)

if TYPE_CHECKING:
    from ...domain.justificante.schema import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ..calculations.observations_repository import ObservationEnvelopePayload
    from ..live.justificante import JustificanteCaptureSnapshot

_AEAT_SUBMISSION_RANK: MappingProxyType[OverviewAeatSubmissionState, int] = MappingProxyType(
    {
        OverviewAeatSubmissionState.NOT_OBSERVED: 0,
        OverviewAeatSubmissionState.SUBMITTED_OBSERVED: 1,
        OverviewAeatSubmissionState.ACCEPTED: 2,
        OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: 3,
    },
)


@dataclass(frozen=True, slots=True)
class _CalendarFilingEvidenceContext:
    """Already-loaded metadata shared by every filing-evidence projection."""

    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]]
    verified_filed_artefact_refs: frozenset[str]
    verified_filed_csv_by_ref: Mapping[str, str]
    expected_tax_id: str | None


def _calendar_event_sort_key(event: OverviewCalendarEvent) -> tuple[date, str, str, str]:
    """Return the deterministic sort key for observed calendar events."""
    return (
        event.event_date,
        event.event_type.value,
        event.modelo or "",
        event.reference_id,
    )


def _dedupe_calendar_events(events: list[OverviewCalendarEvent]) -> tuple[OverviewCalendarEvent, ...]:
    """Deduplicate repeated observations across multiple local snapshots."""
    by_key: dict[tuple[object, ...], OverviewCalendarEvent] = {}
    for event in events:
        key = (
            event.event_type,
            event.event_date,
            event.source,
            event.reference_id,
            event.modelo,
            event.filing_year,
            event.period,
        )
        by_key[key] = event
    return tuple(sorted(by_key.values(), key=_calendar_event_sort_key))


NO_AEAT_HISTORY_NOTICE_CODE = "overview.no_aeat_history"
"""Notice code for a workable profile carrying no official AEAT observation."""


def no_aeat_history_notice(
    observation_source_kinds: tuple[ObservationSourceKind, ...],
    *,
    tax_route: TaxRoute | None = None,
) -> Notice | None:
    """Point a workable profile with no AEAT-sourced history at the history pull.

    Fires only when NOT ONE persisted calculation observation carries an official
    AEAT source kind. A profile with even one is not a fresh profile any more, so
    the nudge would be noise; a profile with none has nothing AEAT-sourced to
    reconcile against, and until this shipped nothing told the operator that a
    single verb would fetch it.

    Keyed on the official-source predicate rather than on an empty observation
    list, deliberately. A profile whose only observations are locally filed or
    operator-entered has the same gap as one with no observations at all -- it
    holds nothing AEAT ever confirmed -- and testing for emptiness would leave
    exactly that taxpayer unprompted.

    Returns ``None`` when any official observation exists, so an onboarded
    profile stays quiet.

    **Takes the source kinds, not the observations, and the narrowing is the
    point.** Reading ``source_kind`` off an untyped payload classified EVIDENCE
    AUTHORITY by attribute NAME, and that name is not unique to this axis: the
    aggregation observation envelopes carry a field spelled identically that
    means CAPTURE PROVENANCE -- which ingestion path wrote a row -- and answers
    to a different closed set. Nothing in a duck-typed read distinguishes them,
    so widening this function's input was a one-line change away from grading
    capture provenance as AEAT confirmation. Asking for the enum makes the two
    axes non-interchangeable at the call site, where the caller holds the
    payload and knows which one it has.

    Args:
        observation_source_kinds: Every persisted calculation observation's
            source kind, across every modelo.
        tax_route: The active profile's :func:`~domain.calculations.registry.derive_tax_route`
            branch, when known. A Sociedades filer
            (:attr:`~domain.calculations.registry.TaxRoute.IMPUESTO_SOCIEDADES`)
            has no whole-history sweep to recommend: the bulk filed-data
            capture planner structurally diverts Modelo 200 and 202 -- the
            Sociedades filer's own direct-tax obligations -- into typed
            unsupported rows, because this deployment's registry declares no
            authenticated filed-declarations read surface for them. Pointing
            such a taxpayer at the sweep verb recommends a verb that can never
            fetch what the notice is about, so this route carries no action
            and a route-specific message instead. ``None`` (the default)
            keeps the whole-history-sweep suggestion for every other route.
    """
    if any(source_kind.is_official_aeat for source_kind in observation_source_kinds):
        return None
    if tax_route is TaxRoute.IMPUESTO_SOCIEDADES:
        return Notice(
            action=None,
            severity=NoticeSeverity.INFO,
            code=NO_AEAT_HISTORY_NOTICE_CODE,
            message=tr(
                "overview.no_aeat_history_sociedades",
            ),
            context={"observation_count": str(len(observation_source_kinds))},
        )
    return Notice(
        action=next_action("operator.live.filed.pull_all"),
        severity=NoticeSeverity.INFO,
        code=NO_AEAT_HISTORY_NOTICE_CODE,
        message=tr(
            "overview.no_aeat_history",
        ),
        context={"observation_count": str(len(observation_source_kinds))},
    )


def calendar_filing_evidence_from_sources(
    *,
    filing_records: tuple[ModeloRecord, ...] = (),
    observed_events: tuple[OverviewCalendarEvent, ...] = (),
    filed_declaration_observations: tuple[FiledDeclaracionObservationProtocol, ...] = (),
    verified_filed_declaration_artefact_refs: tuple[str, ...] = (),
    verified_filed_declaration_artefact_csvs: Mapping[str, str] | None = None,
    calculation_observations: tuple[ObservationEnvelopePayload, ...] = (),
    justificante_capture_snapshots: tuple[JustificanteCaptureSnapshot, ...] = (),
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    """Build :class:`OverviewCalendarFilingEvidence` from local records and observed AEAT signals.

    The function is pure and intentionally accepts already-loaded
    records. CLI/storage code owns I/O; this projection only reconciles
    the existing local :class:`~ModeloRecord` catalogue,
    calendar-visible AEAT register events,
    :class:`~cadrumo.adapters.outbound.aeat.sede.FiledDeclaracionObservation`
    rows, persisted calculation observations from justificante capture,
    :class:`~cadrumo.application.live.JustificanteCaptureSnapshot` rows, and
    already-loaded justificante metadata. The
    ``filing_records`` are filed :class:`ModeloRecord` rows whose
    external justificante references are only promoted to
    ``justificante_verified`` when matching persisted metadata exists
    for the same CSV/model/year/period/taxpayer. Filed-declaration
    observations are only promoted to ``justificante_verified`` when
    their justificante artefact storage reference is listed in
    ``verified_filed_declaration_artefact_refs`` by the storage layer
    that loaded and hashed the encrypted artefact body.

    The result keeps :class:`OverviewLocalFilingState` and
    :class:`OverviewAeatSubmissionState` independent so imported AEAT
    baselines, local filings, observed submissions, and verified
    justificantes do not overwrite each other's meaning.
    """
    context = _CalendarFilingEvidenceContext(
        justificantes_by_csv=_justificantes_by_csv(justificantes),
        verified_filed_artefact_refs=frozenset(verified_filed_declaration_artefact_refs),
        verified_filed_csv_by_ref=verified_filed_declaration_artefact_csvs or {},
        expected_tax_id=expected_tax_id,
    )
    by_key, event_specific = _collect_calendar_filing_evidence(
        context=context,
        filing_records=filing_records,
        observed_events=observed_events,
        filed_declaration_observations=filed_declaration_observations,
        calculation_observations=calculation_observations,
        justificante_capture_snapshots=justificante_capture_snapshots,
    )
    return _finalize_calendar_filing_evidence(by_key, event_specific)


def _collect_calendar_filing_evidence(
    *,
    context: _CalendarFilingEvidenceContext,
    filing_records: tuple[ModeloRecord, ...],
    observed_events: tuple[OverviewCalendarEvent, ...],
    filed_declaration_observations: tuple[FiledDeclaracionObservationProtocol, ...],
    calculation_observations: tuple[ObservationEnvelopePayload, ...],
    justificante_capture_snapshots: tuple[JustificanteCaptureSnapshot, ...],
) -> tuple[
    dict[tuple[str, int, str], OverviewCalendarFilingEvidence],
    list[OverviewCalendarFilingEvidence],
]:
    """Collect source projections while preserving their established precedence order."""
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}
    _merge_projected_evidence(
        by_key,
        (
            _filing_evidence_from_modelo_record(
                record,
                justificantes_by_csv=context.justificantes_by_csv,
                expected_tax_id=context.expected_tax_id,
            )
            for record in filing_records
        ),
    )
    _merge_projected_evidence(
        by_key,
        (
            _filing_evidence_from_observed_event(event, expected_tax_id=context.expected_tax_id)
            for event in observed_events
        ),
    )
    filed_evidence = _filed_declaration_evidence_from_sources(
        filed_declaration_observations,
        expected_tax_id=context.expected_tax_id,
        verified_artefact_refs=context.verified_filed_artefact_refs,
        verified_artefact_csv_by_ref=context.verified_filed_csv_by_ref,
    )
    _merge_projected_evidence(by_key, filed_evidence)
    event_specific = [evidence for evidence in filed_evidence if evidence.justificante_verified]
    _merge_projected_evidence(
        by_key,
        (
            _filing_evidence_from_calculation_observation(
                payload,
                expected_tax_id=context.expected_tax_id,
                justificantes_by_csv=context.justificantes_by_csv,
            )
            for payload in calculation_observations
        ),
    )
    _merge_projected_evidence(
        by_key,
        (
            _filing_evidence_from_justificante_capture_snapshot(
                snapshot,
                justificantes_by_csv=context.justificantes_by_csv,
                expected_tax_id=context.expected_tax_id,
            )
            for snapshot in justificante_capture_snapshots
        ),
    )
    return by_key, event_specific


def _merge_projected_evidence(
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence],
    candidates: Iterable[OverviewCalendarFilingEvidence | None],
) -> None:
    """Merge non-null source projections into the canonical obligation map."""
    for evidence in candidates:
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)


def _filed_declaration_evidence_from_sources(
    observations: tuple[FiledDeclaracionObservationProtocol, ...],
    *,
    expected_tax_id: str | None,
    verified_artefact_refs: frozenset[str],
    verified_artefact_csv_by_ref: Mapping[str, str],
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    """Project filed-declaration observations, omitting rejected rows."""
    projected: list[OverviewCalendarFilingEvidence] = []
    for observation in observations:
        evidence = _filing_evidence_from_filed_declaration_observation(
            observation,
            expected_tax_id=expected_tax_id,
            verified_artefact_refs=verified_artefact_refs,
            verified_artefact_csv_by_ref=verified_artefact_csv_by_ref,
        )
        if evidence is not None:
            projected.append(evidence)
    return tuple(projected)


def _finalize_calendar_filing_evidence(
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence],
    event_specific: list[OverviewCalendarFilingEvidence],
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    """Keep aggregate and filed-observation identities, then sort deterministically."""
    unique: dict[tuple[str | None, int | None, str | None, str | None], OverviewCalendarFilingEvidence] = {}
    for evidence in (*by_key.values(), *event_specific):
        key = _calendar_filing_evidence_identity(evidence)
        existing = unique.get(key)
        unique[key] = evidence if existing is None else _stronger_filing_evidence(existing, evidence)
    return tuple(sorted(unique.values(), key=_calendar_filing_evidence_sort_key))


def _calendar_filing_evidence_identity(
    evidence: OverviewCalendarFilingEvidence,
) -> tuple[str | None, int | None, str | None, str | None]:
    """Return the output identity, retaining one row per verified filed reference."""
    key_reference = evidence.aeat_reference_id if evidence.evidence_source == "filed_declaration_observation" else None
    period_token = evidence.period.registry_token if evidence.period is not None else None
    return evidence.modelo, evidence.filing_year, period_token, key_reference


def _merge_filing_evidence(
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence],
    candidate: OverviewCalendarFilingEvidence,
) -> None:
    """Merge one evidence row into the canonical (modelo, year, registry_token) key."""
    if candidate.modelo is None or candidate.filing_year is None or candidate.period is None:
        return
    key = (candidate.modelo, candidate.filing_year, candidate.period.registry_token)
    existing = by_key.get(key)
    merged = candidate if existing is None else _stronger_filing_evidence(existing, candidate)
    by_key[key] = merged


def _stronger_filing_evidence(
    existing: OverviewCalendarFilingEvidence,
    candidate: OverviewCalendarFilingEvidence,
) -> OverviewCalendarFilingEvidence:
    """Return a deterministic merge preserving the strongest independent axes."""
    local = max((existing, candidate), key=_local_evidence_semantic_key)
    aeat = max((existing, candidate), key=_aeat_evidence_semantic_key)
    conflict_reference_ids = _merged_conflict_reference_ids(existing, candidate)
    return existing.model_copy(
        update={
            "local_filing_state": local.local_filing_state,
            "local_filing_record_id": local.local_filing_record_id,
            "local_calculation_revision_id": local.local_calculation_revision_id,
            "local_filed_at": local.local_filed_at,
            "aeat_submission_state": aeat.aeat_submission_state,
            "aeat_submitted_at": aeat.aeat_submitted_at,
            "aeat_reference_id": aeat.aeat_reference_id,
            "aeat_snapshot_id": aeat.aeat_snapshot_id,
            "aeat_evidence_kind": aeat.aeat_evidence_kind,
            "aeat_evidence_conflict_reference_ids": conflict_reference_ids,
            "verified_justificante_csv": aeat.verified_justificante_csv,
            "justificante_required": existing.justificante_required or candidate.justificante_required,
            "justificante_verified": aeat.justificante_verified,
            "evidence_source": aeat.evidence_source,
        },
    )


def _local_evidence_semantic_key(evidence: OverviewCalendarFilingEvidence) -> tuple[object, ...]:
    """Return a complete deterministic precedence key for the local axis."""
    return (
        evidence.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE,
        evidence.local_filing_state.value,
        evidence.local_filed_at.isoformat() if evidence.local_filed_at is not None else "",
        evidence.local_filing_record_id or "",
        evidence.local_calculation_revision_id or "",
    )


def _aeat_evidence_semantic_key(evidence: OverviewCalendarFilingEvidence) -> tuple[object, ...]:
    """Return a complete deterministic precedence key for the AEAT axis."""
    return (
        _AEAT_SUBMISSION_RANK[evidence.aeat_submission_state],
        evidence.justificante_verified,
        evidence.aeat_submitted_at.isoformat() if evidence.aeat_submitted_at is not None else "",
        _clean_reference_id(evidence.aeat_reference_id) or "",
        str(evidence.aeat_snapshot_id or ""),
        evidence.aeat_evidence_kind or "",
        _clean_reference_id(evidence.verified_justificante_csv) or "",
        evidence.evidence_source or "",
    )


def _merged_conflict_reference_ids(
    existing: OverviewCalendarFilingEvidence,
    candidate: OverviewCalendarFilingEvidence,
) -> tuple[str, ...]:
    """Return normalized AEAT evidence references that disagree for one obligation."""
    references = [
        *existing.aeat_evidence_conflict_reference_ids,
        *candidate.aeat_evidence_conflict_reference_ids,
        *_conflicting_reference_additions(existing, candidate),
    ]
    return tuple(sorted({reference for reference in references if reference}))


def _conflicting_reference_additions(
    existing: OverviewCalendarFilingEvidence,
    candidate: OverviewCalendarFilingEvidence,
) -> tuple[str, ...]:
    """Return newly observed identifiers when the two AEAT axes disagree."""
    existing_ref = _clean_reference_id(existing.aeat_reference_id)
    candidate_ref = _clean_reference_id(candidate.aeat_reference_id)
    existing_csv = _clean_reference_id(existing.verified_justificante_csv)
    candidate_csv = _clean_reference_id(candidate.verified_justificante_csv)
    if existing_csv is not None and candidate_csv is not None:
        return _conflicting_csv_references(existing_csv, candidate_csv)
    if _cross_namespace_references_match(existing_csv, candidate_ref, candidate_csv, existing_ref):
        return ()
    return _conflicting_reference_pair(existing_ref, candidate_ref)


def _conflicting_csv_references(existing_csv: str, candidate_csv: str) -> tuple[str, ...]:
    """Return both CSV identifiers only when verified receipts differ."""
    return () if existing_csv == candidate_csv else (existing_csv, candidate_csv)


def _cross_namespace_references_match(
    existing_csv: str | None,
    candidate_ref: str | None,
    candidate_csv: str | None,
    existing_ref: str | None,
) -> bool:
    """Whether one receipt CSV and the opposite expediente reference agree."""
    return (existing_csv is not None and candidate_ref is not None and candidate_ref == existing_csv) or (
        candidate_csv is not None and existing_ref is not None and existing_ref == candidate_csv
    )


def _conflicting_reference_pair(existing_ref: str | None, candidate_ref: str | None) -> tuple[str, ...]:
    """Return both expediente references when they differ."""
    if existing_ref is None or candidate_ref is None or existing_ref == candidate_ref:
        return ()
    return existing_ref, candidate_ref


def _clean_reference_id(reference_id: str | None) -> str | None:
    """Return an AEAT evidence reference in the canonical comparison form, or ``None``.

    Delegates to the module's one CSV comparison form rather than carrying a
    second: the references cleaned here are compared against justificante CSVs
    in the same identity space -- the live-capture path stamps a receipt's CSV
    as the evidence ``reference_id`` -- so both sides have to agree on one key.
    This site previously stripped only and then casefolded at each comparison,
    which produced a lowercase key the canonical uppercase contract refuses and
    left the module with two forms for one identifier. Normalising once here
    means the comparisons below are plain equality.
    """
    return _justificante_csv_key(reference_id or "") or None


def _calendar_filing_evidence_sort_key(
    evidence: OverviewCalendarFilingEvidence,
) -> tuple[object, ...]:
    _p = evidence.period
    return (
        evidence.modelo or "",
        evidence.filing_year or 0,
        _p.registry_token if _p is not None else "",
        _local_evidence_semantic_key(evidence),
        _aeat_evidence_semantic_key(evidence),
    )


def merge_calendar_filing_evidence(
    *groups: tuple[OverviewCalendarFilingEvidence, ...],
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    """Join reconciled evidence groups by natural address deterministically."""
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}
    for item in (row for group in groups for row in group):
        _merge_filing_evidence(by_key, item)
    return tuple(sorted(by_key.values(), key=_calendar_filing_evidence_sort_key))


def _calendar_entry_filing_evidence(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarFilingEvidence:
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}
    for item in evidence:
        _merge_filing_evidence(by_key, item)
    match = by_key.get((modelo, filing_year, period.registry_token))
    if match is not None:
        return match.model_copy(update={"modelo": modelo, "filing_year": filing_year, "period": period})
    return OverviewCalendarFilingEvidence(modelo=modelo, filing_year=filing_year, period=period)


def _calendar_events_with_filing_evidence(
    events: tuple[OverviewCalendarEvent, ...],
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> tuple[OverviewCalendarEvent, ...]:
    enriched = [_calendar_event_with_filing_evidence(event, evidence) for event in events]
    return _dedupe_calendar_events(enriched)


def _calendar_event_with_filing_evidence(
    event: OverviewCalendarEvent,
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarEvent:
    """Promote one event only when a stronger matching AEAT state is available."""
    if event.event_type is not OverviewCalendarEventType.FILING or _calendar_event_filing_target(event) is None:
        return event
    row = _calendar_event_filing_evidence(event=event, evidence=evidence)
    if row is None:
        return event
    current_state = event.aeat_submission_state or OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    if _AEAT_SUBMISSION_RANK[row.aeat_submission_state] <= _AEAT_SUBMISSION_RANK[current_state]:
        return event
    return event.model_copy(
        update={
            "aeat_submission_state": row.aeat_submission_state,
            "aeat_submitted_at": row.aeat_submitted_at or event.aeat_submitted_at,
            "justificante_verified": row.justificante_verified,
            "verified_justificante_csv": row.verified_justificante_csv,
        },
    )


def _calendar_event_filing_evidence(
    *,
    event: OverviewCalendarEvent,
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarFilingEvidence | None:
    target = _calendar_event_filing_target(event)
    if target is None:
        return None
    modelo, filing_year, period = target
    matching_refs = tuple(
        item
        for item in evidence
        if _calendar_event_evidence_matches(
            item,
            reference_id=event.reference_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
        )
    )
    if not matching_refs:
        return None
    return _strongest_filing_evidence(matching_refs)


def _calendar_event_filing_target(event: OverviewCalendarEvent) -> tuple[str, int, _Period] | None:
    """Return an active event's natural filing target, or reject the event."""
    if event.modelo is None or event.filing_year is None or event.period is None:
        return None
    if event.status is not None and not _is_active_aeat_filing_status(event.status):
        return None
    return event.modelo, event.filing_year, event.period


def _calendar_event_evidence_matches(
    evidence: OverviewCalendarFilingEvidence,
    *,
    reference_id: str,
    modelo: str,
    filing_year: int,
    period: _Period,
) -> bool:
    """Whether one evidence row addresses the event's exact reference and target."""
    return (
        evidence.aeat_reference_id == reference_id
        and evidence.modelo == modelo
        and evidence.filing_year == filing_year
        and evidence.period is not None
        and evidence.period.registry_token == period.registry_token
    )


def _strongest_filing_evidence(
    evidence_rows: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarFilingEvidence:
    """Fold matching rows through the axis-aware merge precedence."""
    strongest = evidence_rows[0]
    for candidate in evidence_rows[1:]:
        strongest = _stronger_filing_evidence(strongest, candidate)
    return strongest


authenticated_identity_matches_expected = _authenticated_identity_matches_expected
calendar_entry_filing_evidence = _calendar_entry_filing_evidence
calendar_events_with_filing_evidence = _calendar_events_with_filing_evidence
dedupe_calendar_events = _dedupe_calendar_events
filing_axes_from_modelo_record = _filing_axes_from_modelo_record
filing_evidence_from_justificante_capture_snapshot = _filing_evidence_from_justificante_capture_snapshot
is_active_aeat_filing_status = _is_active_aeat_filing_status
justificantes_by_csv = _justificantes_by_csv
