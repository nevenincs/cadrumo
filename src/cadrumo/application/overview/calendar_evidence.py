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
    :mod:`cadrumo.application.overview`
        Public facade that re-exports :func:`calendar_filing_evidence_from_sources`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...application.operator_actions import next_action
from ...core import Period as _Period
from ...core import normalise_aeat_csv
from ...core.i18n import tr
from ...core.identity import same_tax_identifier
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry.applicability_routes import TaxRoute
from ...domain.modelos.filing_record import is_justificante_backed_external_evidence
from ..calculations import ObservationSourceKind, is_official_aeat_observation_source
from .calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewLocalFilingState,
)

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionObservation
    from ...domain.justificante import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ..calculations import ObservationEnvelopePayload
    from ..live.justificante import JustificanteCaptureSnapshot

_AEAT_SUBMISSION_RANK: MappingProxyType[OverviewAeatSubmissionState, int] = MappingProxyType(
    {
        OverviewAeatSubmissionState.NOT_OBSERVED: 0,
        OverviewAeatSubmissionState.SUBMITTED_OBSERVED: 1,
        OverviewAeatSubmissionState.ACCEPTED: 2,
        OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: 3,
    },
)


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
                default=(
                    "This profile holds no filing evidence AEAT confirmed. The automated retrieval sweep "
                    "cannot fetch Impuesto sobre Sociedades filing history (Modelo 200/202); check it "
                    "directly at the AEAT sede."
                ),
            ),
            context={"observation_count": str(len(observation_source_kinds))},
        )
    return Notice(
        action=next_action("operator.live.filed.pull_all"),
        severity=NoticeSeverity.INFO,
        code=NO_AEAT_HISTORY_NOTICE_CODE,
        message=tr(
            "overview.no_aeat_history",
            default=(
                "This profile holds no filing evidence AEAT confirmed. Retrieve the filing history AEAT holds for it."
            ),
        ),
        context={"observation_count": str(len(observation_source_kinds))},
    )


def calendar_filing_evidence_from_sources(
    *,
    filing_records: tuple[ModeloRecord, ...] = (),
    observed_events: tuple[OverviewCalendarEvent, ...] = (),
    filed_declaration_observations: tuple[FiledDeclaracionObservation, ...] = (),
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
    by_key: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}  # (modelo, year, registry_token)
    event_specific: list[OverviewCalendarFilingEvidence] = []
    justificantes_by_csv = _justificantes_by_csv(justificantes)
    verified_filed_artefact_refs = frozenset(verified_filed_declaration_artefact_refs)
    verified_filed_csv_by_ref = verified_filed_declaration_artefact_csvs or {}
    for record in filing_records:
        evidence = _filing_evidence_from_modelo_record(
            record,
            justificantes_by_csv=justificantes_by_csv,
            expected_tax_id=expected_tax_id,
        )
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    for event in observed_events:
        evidence = _filing_evidence_from_observed_event(event, expected_tax_id=expected_tax_id)
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    for observation in filed_declaration_observations:
        evidence = _filing_evidence_from_filed_declaration_observation(
            observation,
            expected_tax_id=expected_tax_id,
            verified_artefact_refs=verified_filed_artefact_refs,
            verified_artefact_csv_by_ref=verified_filed_csv_by_ref,
        )
        if evidence is not None:
            if evidence.justificante_verified:
                event_specific.append(evidence)
            _merge_filing_evidence(by_key, evidence)
    for payload in calculation_observations:
        evidence = _filing_evidence_from_calculation_observation(
            payload,
            expected_tax_id=expected_tax_id,
            justificantes_by_csv=justificantes_by_csv,
        )
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    for snapshot in justificante_capture_snapshots:
        evidence = _filing_evidence_from_justificante_capture_snapshot(
            snapshot,
            justificantes_by_csv=justificantes_by_csv,
            expected_tax_id=expected_tax_id,
        )
        if evidence is not None:
            _merge_filing_evidence(by_key, evidence)
    unique: dict[tuple[str | None, int | None, str | None, str | None], OverviewCalendarFilingEvidence] = {}
    for evidence in (*by_key.values(), *event_specific):
        key_reference = (
            evidence.aeat_reference_id if evidence.evidence_source == "filed_declaration_observation" else None
        )
        _period_token = evidence.period.registry_token if evidence.period is not None else None
        key = (evidence.modelo, evidence.filing_year, _period_token, key_reference)
        existing = unique.get(key)
        unique[key] = evidence if existing is None else _stronger_filing_evidence(existing, evidence)
    return tuple(sorted(unique.values(), key=_calendar_filing_evidence_sort_key))


def _justificantes_by_csv(justificantes: tuple[Justificante, ...]) -> dict[str, tuple[Justificante, ...]]:
    """Index loaded justificante metadata by CSV/reference identifier."""
    grouped: dict[str, list[Justificante]] = {}
    for justificante in justificantes:
        csv = justificante.csv.strip()
        if csv:
            grouped.setdefault(_justificante_csv_key(csv), []).append(justificante)
    return {key: tuple(values) for key, values in grouped.items()}


def _justificante_csv_key(csv: str) -> str:
    """Return the canonical lookup key for AEAT CSV identifiers.

    Delegates to the one comparison form rather than restating it. This site
    previously casefolded, which produced a lowercase key that the canonical
    uppercase contract refuses -- so one identifier had two keys depending on
    which surface built it.
    """
    return normalise_aeat_csv(csv)


def _filing_evidence_from_modelo_record(
    record: ModeloRecord,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project one local Modelo filing record into calendar evidence."""
    if record.status.value.lower() != "vigente":
        return None
    return _filing_axes_from_modelo_record(
        record,
        justificantes_by_csv=justificantes_by_csv,
        expected_tax_id=expected_tax_id,
    )


def _filing_axes_from_modelo_record(
    record: ModeloRecord,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence:
    """Return the local and AEAT filing axes for one Modelo filing record."""
    modelo = str(record.modelo)
    filing_year = int(record.filing_year)
    period = record.period
    external_evidence = record.external_evidence
    local_state = _local_filing_state_from_modelo_record(record)
    aeat_state = OverviewAeatSubmissionState.NOT_OBSERVED
    aeat_evidence_kind = None
    aeat_reference_id = None
    aeat_submitted_at = None
    justificante_verified = False
    verified_justificante_csv = None
    aeat_accepted = record.aeat_accepted
    if aeat_accepted and external_evidence is not None:
        aeat_state = OverviewAeatSubmissionState.ACCEPTED
    if external_evidence is not None:
        kind = getattr(external_evidence, "kind", None)
        aeat_evidence_kind = str(getattr(kind, "value", kind))
        aeat_reference_id = str(external_evidence.reference_id)
        if aeat_accepted and is_justificante_backed_external_evidence(external_evidence.kind):
            verified_justificante = _modelo_record_verified_justificante(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                reference_id=aeat_reference_id,
                justificantes_by_csv=justificantes_by_csv,
                expected_tax_id=expected_tax_id,
            )
            if verified_justificante is not None:
                aeat_state = OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
                aeat_submitted_at = verified_justificante.presented_at
                justificante_verified = True
                verified_justificante_csv = verified_justificante.csv
        elif aeat_accepted and aeat_state is OverviewAeatSubmissionState.NOT_OBSERVED:
            aeat_state = OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    return OverviewCalendarFilingEvidence(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        local_filing_state=local_state,
        local_filing_record_id=str(record.filing_record_id),
        local_calculation_revision_id=str(record.calculation_revision_id),
        local_filed_at=record.filed_at,
        aeat_submission_state=aeat_state,
        aeat_submitted_at=aeat_submitted_at,
        aeat_reference_id=aeat_reference_id,
        aeat_evidence_kind=aeat_evidence_kind,
        verified_justificante_csv=verified_justificante_csv,
        justificante_verified=justificante_verified,
        evidence_source="modelo_filing_record",
    )


def _modelo_record_verified_justificante(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    reference_id: str,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    """Return matching justificante metadata for a Modelo record external reference."""
    expected = (expected_tax_id or "").strip()
    if not expected:
        return None
    candidates = justificantes_by_csv.get(_justificante_csv_key(reference_id), ())
    matching = tuple(
        justificante
        for justificante in candidates
        if _justificante_matches_calendar_target(
            justificante,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            expected_tax_id=expected,
        )
    )
    if not matching or len(matching) != len(candidates):
        return None
    return matching[0]


def _justificante_matches_calendar_target(
    justificante: Justificante,
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    expected_tax_id: str,
) -> bool:
    return justificante.matches_filing_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        tax_id=expected_tax_id,
    )


def _local_filing_state_from_modelo_record(record: ModeloRecord) -> OverviewLocalFilingState:
    """Return the local-app axis for one current Modelo record.

    ``external_evidence`` is the AEAT axis and must not erase the local
    meaning of a filing record. A normal local filing that later receives live
    AEAT evidence remains ``ready_to_file``; only records created through the
    external baseline import command use the imported-baseline state.
    """
    filed_by = record.filed_by.strip().lower()
    if filed_by == "aeat-import" or filed_by.startswith("aeat-import:"):
        return OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
    return OverviewLocalFilingState.READY_TO_FILE


def _filing_evidence_from_observed_event(
    event: OverviewCalendarEvent,
    *,
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project an active filing event into AEAT-side obligation evidence."""
    if event.event_type is not OverviewCalendarEventType.FILING:
        return None
    if event.modelo is None or event.filing_year is None or event.period is None:
        return None
    if event.status is not None and not _is_active_aeat_filing_status(event.status):
        return None
    state = event.aeat_submission_state
    if state is None:
        return None
    if not _authenticated_identity_matches_expected(event.authenticated_identity, expected_tax_id):
        return None
    return OverviewCalendarFilingEvidence(
        modelo=event.modelo,
        filing_year=event.filing_year,
        period=event.period,
        aeat_submission_state=state,
        aeat_submitted_at=event.aeat_submitted_at
        or datetime.combine(event.event_date, datetime.min.time(), tzinfo=UTC),
        aeat_reference_id=event.reference_id,
        aeat_snapshot_id=event.snapshot_id,
        verified_justificante_csv=event.verified_justificante_csv,
        justificante_verified=bool(event.justificante_verified),
        evidence_source=event.source,
    )


def _authenticated_identity_matches_expected(
    authenticated_identity: str | None,
    expected_tax_id: str | None,
) -> bool:
    if not expected_tax_id:
        return True
    return same_tax_identifier(authenticated_identity, expected_tax_id)


def _filing_evidence_from_filed_declaration_observation(
    observation: FiledDeclaracionObservation,
    *,
    expected_tax_id: str | None,
    verified_artefact_refs: frozenset[str],
    verified_artefact_csv_by_ref: Mapping[str, str],
) -> OverviewCalendarFilingEvidence | None:
    """Project one captured filed-declaration observation into evidence.

    The observation must belong to the expected authenticated identity and must
    be an active ``ALTA`` register row. Justificante verification is granted
    only when the storage layer has already verified and supplied the encrypted
    justificante artefact reference and CSV.
    """
    if expected_tax_id and not same_tax_identifier(observation.authenticated_identity, expected_tax_id):
        return None
    if not _is_active_aeat_filing_status(observation.status):
        return None
    justificante = next(
        (
            artefact
            for artefact in observation.artefacts
            if artefact.kind == "justificante_pdf"
            and artefact.storage_ref is not None
            and artefact.storage_ref in verified_artefact_refs
        ),
        None,
    )
    verified = justificante is not None
    verified_csv = None
    if justificante is not None and justificante.storage_ref is not None:
        verified_csv = verified_artefact_csv_by_ref.get(justificante.storage_ref)
    if verified and not verified_csv:
        verified = False
    return OverviewCalendarFilingEvidence(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        aeat_submission_state=(
            OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
            if verified
            else OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        ),
        aeat_submitted_at=observation.presented_at,
        aeat_reference_id=observation.expediente_id,
        aeat_evidence_kind="aeat_justificante_pdf" if verified else "filed_declaration_observation",
        verified_justificante_csv=verified_csv if verified else None,
        justificante_verified=verified,
        evidence_source="filed_declaration_observation",
    )


def _is_active_aeat_filing_status(status: str | None) -> bool:
    """Return whether an AEAT register row represents the current accepted filing."""
    return (status or "").strip().upper() == "ALTA"


def _filing_evidence_from_calculation_observation(
    payload: ObservationEnvelopePayload,
    *,
    expected_tax_id: str | None,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
) -> OverviewCalendarFilingEvidence | None:
    """Project official calculation observations into AEAT-submitted evidence.

    Only official AEAT source kinds with active register metadata are accepted.
    A matching loaded :class:`~cadrumo.domain.justificante.Justificante` upgrades
    the row to :attr:`OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED`;
    otherwise the row remains submitted-observed evidence.
    """
    source_kind = payload.source_kind
    if not is_official_aeat_observation_source(source_kind):
        return None
    source_metadata = payload.source_metadata
    if not source_metadata:
        return None
    status = str(source_metadata.get("aeat_register_status", "")).strip()
    if not _is_active_aeat_filing_status(status):
        return None
    aeat_expediente_id = str(source_metadata.get("aeat_expediente_id") or "").strip()
    if not aeat_expediente_id:
        return None
    authenticated_identity = str(source_metadata.get("authenticated_identity", ""))
    if expected_tax_id and not same_tax_identifier(authenticated_identity, expected_tax_id):
        return None
    observation = payload.observation
    _obs_year = observation.filing_year
    _obs_period = observation.filing_period
    if _obs_period is not None:
        if _obs_period.filing_year != _obs_year:
            return None
    else:
        # filing_period is derived at construction from filing_year and period,
        # so it is absent only when a caller passed None explicitly. The model
        # permits that, so the fallback stays live rather than being deleted as
        # unreachable.
        try:
            _obs_period = _period_from_registry_token(_obs_year, observation.period)
        except ValueError:
            return None
    verified_justificante = _calculation_observation_verified_justificante(
        modelo=str(observation.modelo),
        filing_year=_obs_year,
        period=_obs_period,
        source_metadata=source_metadata,
        justificantes_by_csv=justificantes_by_csv,
        expected_tax_id=expected_tax_id,
    )
    verified = verified_justificante is not None
    return OverviewCalendarFilingEvidence(
        modelo=str(observation.modelo),
        filing_year=_obs_year,
        period=_obs_period,
        aeat_submission_state=(
            OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
            if verified
            else OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        ),
        aeat_submitted_at=verified_justificante.presented_at
        if verified_justificante is not None
        else payload.captured_at,
        aeat_reference_id=aeat_expediente_id,
        aeat_evidence_kind=source_kind.value,
        verified_justificante_csv=verified_justificante.csv if verified_justificante is not None else None,
        justificante_verified=verified,
        evidence_source=source_kind.value,
    )


def _calculation_observation_verified_justificante(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    source_metadata: Mapping[str, object],
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    """Resolve filed-history observation metadata to matching persisted justificante metadata."""
    expected = str(expected_tax_id or source_metadata.get("authenticated_identity") or "").strip()
    if not expected:
        return None
    for csv in _metadata_justificante_csv_candidates(source_metadata):
        candidates = justificantes_by_csv.get(_justificante_csv_key(csv), ())
        matching = tuple(
            justificante
            for justificante in candidates
            if _justificante_matches_calendar_target(
                justificante,
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                expected_tax_id=expected,
            )
        )
        if not matching or len(matching) != len(candidates):
            continue
        return matching[0]
    return None


def _filing_evidence_from_justificante_capture_snapshot(
    snapshot: JustificanteCaptureSnapshot,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project one verified live justificante capture into AEAT-side evidence.

    The persisted snapshot is accepted only when it is active, carries a typed
    :class:`~cadrumo.core.Period`, and resolves to loaded
    :class:`~cadrumo.domain.justificante.Justificante` metadata for the same filing
    target.
    """
    if not _capture_snapshot_is_active(snapshot):
        return None
    if snapshot.period.filing_year != snapshot.filing_year:
        return None
    verified_justificante = _capture_snapshot_verified_justificante(
        snapshot,
        justificantes_by_csv=justificantes_by_csv,
        expected_tax_id=expected_tax_id,
    )
    if verified_justificante is None:
        return None
    source_kind = str(getattr(snapshot, "source_kind", "aeat_sede_live_capture") or "aeat_sede_live_capture")
    return OverviewCalendarFilingEvidence(
        modelo=snapshot.modelo,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        aeat_submission_state=OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
        aeat_submitted_at=verified_justificante.presented_at,
        aeat_reference_id=snapshot.expediente_id,
        aeat_snapshot_id=snapshot.snapshot_id,
        aeat_evidence_kind=source_kind,
        verified_justificante_csv=verified_justificante.csv,
        justificante_verified=True,
        evidence_source=source_kind,
    )


def _capture_snapshot_is_active(snapshot: JustificanteCaptureSnapshot) -> bool:
    state = getattr(snapshot, "state", None)
    return str(getattr(state, "value", state)).strip().lower() == "active"


def _capture_snapshot_verified_justificante(
    snapshot: JustificanteCaptureSnapshot,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    expected = (expected_tax_id or "").strip()
    candidates = justificantes_by_csv.get(_justificante_csv_key(snapshot.csv), ())
    matching = tuple(
        justificante
        for justificante in candidates
        if _justificante_matches_calendar_target(
            justificante,
            modelo=snapshot.modelo,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            expected_tax_id=expected or justificante.tax_id,
        )
    )
    if not matching or len(matching) != len(candidates):
        return None
    return matching[0]


def _metadata_justificante_csv_candidates(source_metadata: Mapping[str, object]) -> tuple[str, ...]:
    """Return normalized single/plural justificante CSV metadata candidates."""
    csvs: list[str] = []
    for key in ("aeat_justificante_csv", "justificante_csv"):
        value = source_metadata.get(key)
        cleaned = str(value or "").strip()
        if cleaned:
            csvs.append(cleaned)
    plural = str(source_metadata.get("aeat_justificante_csvs") or "").strip()
    if plural:
        csvs.extend(item.strip() for item in plural.split(",") if item.strip())
    return tuple(dict.fromkeys(csvs))


def _period_from_registry_token(filing_year: int, registry_token: str) -> _Period:
    return _Period.from_year_and_code(filing_year, registry_token)


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
    """Return a merged row preserving the strongest local and AEAT axes."""
    local = existing
    conflict_reference_ids = _merged_conflict_reference_ids(existing, candidate)
    if (
        existing.local_filing_state is OverviewLocalFilingState.NOT_READY_TO_FILE
        and candidate.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE
    ):
        local = local.model_copy(
            update={
                "local_filing_state": candidate.local_filing_state,
                "local_filing_record_id": candidate.local_filing_record_id,
                "local_calculation_revision_id": candidate.local_calculation_revision_id,
                "local_filed_at": candidate.local_filed_at,
            },
        )
    if conflict_reference_ids != local.aeat_evidence_conflict_reference_ids:
        local = local.model_copy(update={"aeat_evidence_conflict_reference_ids": conflict_reference_ids})
    if _AEAT_SUBMISSION_RANK[candidate.aeat_submission_state] >= _AEAT_SUBMISSION_RANK[local.aeat_submission_state]:
        local = local.model_copy(
            update={
                "aeat_submission_state": candidate.aeat_submission_state,
                "aeat_submitted_at": _merged_aeat_submitted_at(local, candidate),
                "aeat_reference_id": candidate.aeat_reference_id or local.aeat_reference_id,
                "aeat_snapshot_id": candidate.aeat_snapshot_id or local.aeat_snapshot_id,
                "aeat_evidence_kind": candidate.aeat_evidence_kind or local.aeat_evidence_kind,
                "aeat_evidence_conflict_reference_ids": conflict_reference_ids,
                "verified_justificante_csv": candidate.verified_justificante_csv or local.verified_justificante_csv,
                "justificante_verified": candidate.justificante_verified or local.justificante_verified,
                "evidence_source": candidate.evidence_source or local.evidence_source,
            },
        )
    return local


def _merged_aeat_submitted_at(
    existing: OverviewCalendarFilingEvidence,
    candidate: OverviewCalendarFilingEvidence,
) -> datetime | None:
    """Prefer official justificante presentation time over local capture time."""
    if (
        existing.justificante_verified
        and candidate.justificante_verified
        and existing.aeat_submitted_at is not None
        and _AEAT_SUBMISSION_RANK[candidate.aeat_submission_state]
        == _AEAT_SUBMISSION_RANK[existing.aeat_submission_state]
    ):
        return existing.aeat_submitted_at
    return candidate.aeat_submitted_at or existing.aeat_submitted_at


def _merged_conflict_reference_ids(
    existing: OverviewCalendarFilingEvidence,
    candidate: OverviewCalendarFilingEvidence,
) -> tuple[str, ...]:
    """Return normalized AEAT evidence references that disagree for one obligation."""
    references: list[str] = [
        *existing.aeat_evidence_conflict_reference_ids,
        *candidate.aeat_evidence_conflict_reference_ids,
    ]
    existing_ref = _clean_reference_id(existing.aeat_reference_id)
    candidate_ref = _clean_reference_id(candidate.aeat_reference_id)
    existing_csv = _clean_reference_id(existing.verified_justificante_csv)
    candidate_csv = _clean_reference_id(candidate.verified_justificante_csv)
    if existing_csv is not None and candidate_csv is not None:
        if existing_csv == candidate_csv:
            return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
        references.extend((existing_csv, candidate_csv))
        return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
    if existing_csv is not None and candidate_ref is not None and candidate_ref == existing_csv:
        return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
    if candidate_csv is not None and existing_ref is not None and existing_ref == candidate_csv:
        return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
    if existing_ref is not None and candidate_ref is not None and existing_ref != candidate_ref:
        references.extend((existing_ref, candidate_ref))
    return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))


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
) -> tuple[str, int, str]:
    _p = evidence.period
    return (evidence.modelo or "", evidence.filing_year or 0, _p.registry_token if _p is not None else "")


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
    enriched: list[OverviewCalendarEvent] = []
    for event in events:
        if event.event_type is not OverviewCalendarEventType.FILING:
            enriched.append(event)
            continue
        if event.status is not None and not _is_active_aeat_filing_status(event.status):
            enriched.append(event)
            continue
        if event.modelo is None or event.filing_year is None or event.period is None:
            enriched.append(event)
            continue
        row = _calendar_event_filing_evidence(event=event, evidence=evidence)
        if row is None:
            enriched.append(event)
            continue
        current_state = event.aeat_submission_state or OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        if _AEAT_SUBMISSION_RANK[row.aeat_submission_state] <= _AEAT_SUBMISSION_RANK[current_state]:
            enriched.append(event)
            continue
        enriched.append(
            event.model_copy(
                update={
                    "aeat_submission_state": row.aeat_submission_state,
                    "aeat_submitted_at": row.aeat_submitted_at or event.aeat_submitted_at,
                    "justificante_verified": row.justificante_verified,
                    "verified_justificante_csv": row.verified_justificante_csv,
                },
            ),
        )
    return _dedupe_calendar_events(enriched)


def _calendar_event_filing_evidence(
    *,
    event: OverviewCalendarEvent,
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> OverviewCalendarFilingEvidence | None:
    if event.modelo is None or event.filing_year is None or event.period is None:
        return None
    if event.status is not None and not _is_active_aeat_filing_status(event.status):
        return None
    matching_refs = tuple(
        item
        for item in evidence
        if item.aeat_reference_id == event.reference_id
        and item.modelo == event.modelo
        and item.filing_year == event.filing_year
        and item.period is not None
        and item.period.registry_token == event.period.registry_token
    )
    if not matching_refs:
        return None
    row = matching_refs[0]
    for candidate in matching_refs[1:]:
        row = _stronger_filing_evidence(row, candidate)
    return row


authenticated_identity_matches_expected = _authenticated_identity_matches_expected
calendar_entry_filing_evidence = _calendar_entry_filing_evidence
calendar_events_with_filing_evidence = _calendar_events_with_filing_evidence
dedupe_calendar_events = _dedupe_calendar_events
filing_axes_from_modelo_record = _filing_axes_from_modelo_record
filing_evidence_from_justificante_capture_snapshot = _filing_evidence_from_justificante_capture_snapshot
is_active_aeat_filing_status = _is_active_aeat_filing_status
justificantes_by_csv = _justificantes_by_csv
