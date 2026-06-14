"""Calendar aggregation and evidence merge for the overview application facade.

Use of :class:`Schedule`, :class:`TaxpayerProfile` for compliance. Derives
per-deadline filing evidence from filed :class:`ModeloRecord` rows so the
calendar reflects which obligations already carry a justificante.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core import Period as _Period
from ...core.external_constants import IVA_REGIME_MODELOS
from ...core.i18n import tr as _tr
from ...core.logging import get_logger as _get_logger
from ...core.time import now
from ...domain.calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability
from ...domain.calculations.registry.applicability import taxpayer_model_is_declared as _taxpayer_model_is_declared
from ...domain.deadlines import DeadlineEngine as _DeadlineEngine
from ...domain.deadlines import ModeloDeadline as _ModeloDeadline
from ...domain.deadlines import Schedule as _Schedule
from ...domain.deadlines import ScheduleProducer as _ScheduleProducer
from ...domain.deadlines import TaxpayerProfile as _TaxpayerProfile
from ...domain.deadlines import shift_deadline as _shift_deadline
from ...domain.deadlines._errors import NoDeadlineWindowsError as _NoDeadlineWindowsError
from ...domain.deadlines._festivos import DeadlineValidationError as _DeadlineValidationError
from ._calendar_models import (
    CalendarCompleteness,
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    SuppressedCalendarEntry,
    user_state_for,
)
from ._calendar_models import (
    CalendarWarning as CalendarWarning,
)
from ._calendar_models import (
    OverviewCensoEnrolmentState as OverviewCensoEnrolmentState,
)
from ._calendar_models import (
    OverviewPeriodState as OverviewPeriodState,
)
from ._calendar_models import (
    OverviewStatusReport as OverviewStatusReport,
)
from ._calendar_warnings import (
    _build_completeness_and_warnings,
    _calendar_aeat_evidence_conflict_warnings,
    _calendar_censo_enrolment_state,
    _calendar_censo_reconciliation_warnings,
    _calendar_unverified_justificante_warnings,
)
from ._calendar_warnings import (
    calendar_applicability_profile_keys_for_modelo as calendar_applicability_profile_keys_for_modelo,
)
from ._calendar_warnings import (
    calendar_censo_enrolment_profile_keys as calendar_censo_enrolment_profile_keys,
)

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede import FiledDeclaracionObservation
    from ...domain.justificante import Justificante
    from ...domain.modelos import ModeloRecord
    from ..live._expedientes import PersistedExpedientesSnapshot
    from ..live._justificante import JustificanteCaptureSnapshot
    from ..live._notifications import PersistedNotificationsSnapshot

_log = _get_logger(__name__)
_IVA_REGIME_MODELOS = IVA_REGIME_MODELOS
_JUSTIFICANTE_BACKED_EVIDENCE_KINDS = frozenset(
    {
        "aeat_csv_register",
        "aeat_justificante_pdf",
        "aeat_live_capture",
    },
)
_OFFICIAL_CALCULATION_SOURCE_KINDS = frozenset(
    {
        "aeat_sede_justificante",
        "aeat_sede_live_capture",
        "aeat_csv_register",
    },
)
_AEAT_SUBMISSION_RANK: MappingProxyType[OverviewAeatSubmissionState, int] = MappingProxyType(
    {
        OverviewAeatSubmissionState.NOT_OBSERVED: 0,
        OverviewAeatSubmissionState.SUBMITTED_OBSERVED: 1,
        OverviewAeatSubmissionState.ACCEPTED: 2,
        OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: 3,
    },
)


def _entry_intersects_range(
    obligation: _ModeloDeadline,
    calendar_range: OverviewCalendarRange,
) -> bool:
    """Return whether ``obligation``'s [opens_on, closes_on] intersects the range."""
    return obligation.closes_on >= calendar_range.from_date and obligation.opens_on <= calendar_range.to_date


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


def calendar_events_from_expedientes_snapshots(
    snapshots: tuple[PersistedExpedientesSnapshot, ...],
    calendar_range: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarEvent, ...]:
    """Project persisted AEAT declaration-register snapshots into :class:`OverviewCalendarEvent` tuples."""
    events: list[OverviewCalendarEvent] = []
    for snapshot in sorted(snapshots, key=lambda item: item.captured_at):
        if not _authenticated_identity_matches_expected(
            getattr(snapshot, "authenticated_identity", None),
            expected_tax_id,
        ):
            continue
        for declaration in snapshot.declarations:
            event_date = declaration.presented_at.date()
            if not calendar_range.covers(event_date):
                continue
            _period = declaration.period
            summary = f"Modelo {declaration.modelo} {declaration.ejercicio} {_period.registry_token} filed at AEAT"
            aeat_submission_state = (
                OverviewAeatSubmissionState.SUBMITTED_OBSERVED
                if _is_active_aeat_filing_status(declaration.estado)
                else None
            )
            events.append(
                OverviewCalendarEvent(
                    event_type=OverviewCalendarEventType.FILING,
                    event_date=event_date,
                    source="aeat_sede_expedientes",
                    summary=summary,
                    reference_id=declaration.expediente_id,
                    snapshot_id=snapshot.snapshot_id,
                    modelo=declaration.modelo,
                    filing_year=declaration.ejercicio,
                    period=_period,
                    status=declaration.estado,
                    source_url=snapshot.source_url,
                    authenticated_identity=snapshot.authenticated_identity,
                    aeat_submission_state=aeat_submission_state,
                    aeat_submitted_at=declaration.presented_at if aeat_submission_state is not None else None,
                    justificante_verified=False if aeat_submission_state is not None else None,
                ),
            )
    return _dedupe_calendar_events(events)


def calendar_events_from_notification_snapshots(
    snapshots: tuple[PersistedNotificationsSnapshot, ...],
    calendar_range: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarEvent, ...]:
    """Project persisted AEAT notifications and communications into :class:`OverviewCalendarEvent` tuples."""
    events: list[OverviewCalendarEvent] = []
    for snapshot in sorted(snapshots, key=lambda item: item.captured_at):
        snapshot_identity = getattr(snapshot, "authenticated_identity", None)
        if snapshot_identity is not None and not _authenticated_identity_matches_expected(
            snapshot_identity,
            expected_tax_id,
        ):
            continue
        for row in snapshot.rows:
            if not _notification_matches_expected_tax_id(
                row,
                expected_tax_id,
                allow_missing_row_identity=snapshot_identity is not None,
            ):
                continue
            event_date = row.fecha_notificacion or row.fecha_emision
            if not calendar_range.covers(event_date):
                continue
            read_state = "read" if row.leida is True else "unread" if row.leida is False else None
            status = read_state or row.tipo
            summary = row.concepto.strip() or row.tipo
            events.append(
                OverviewCalendarEvent(
                    event_type=OverviewCalendarEventType.MESSAGE,
                    event_date=event_date,
                    source="aeat_sede_notifications",
                    summary=summary,
                    reference_id=row.certificado_id,
                    snapshot_id=snapshot.snapshot_id,
                    status=status,
                    source_url=str(row.source_url),
                ),
            )
    return _dedupe_calendar_events(events)


def calendar_events_from_justificante_capture_snapshots(
    snapshots: tuple[JustificanteCaptureSnapshot, ...],
    calendar_range: OverviewCalendarRange,
    *,
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarEvent, ...]:
    """Project verified live justificante captures into calendar filing events.

    Returns a tuple of :class:`OverviewCalendarEvent`.
    """
    justificantes_by_csv = _justificantes_by_csv(justificantes)
    events: list[OverviewCalendarEvent] = []
    for snapshot in sorted(snapshots, key=lambda item: item.captured_at):
        evidence = _filing_evidence_from_justificante_capture_snapshot(
            snapshot,
            justificantes_by_csv=justificantes_by_csv,
            expected_tax_id=expected_tax_id,
        )
        if evidence is None:
            continue
        submitted_at = evidence.aeat_submitted_at or snapshot.captured_at
        event_date = submitted_at.date()
        if not calendar_range.covers(event_date):
            continue
        events.append(
            OverviewCalendarEvent(
                event_type=OverviewCalendarEventType.FILING,
                event_date=event_date,
                source="aeat_sede_live_capture",
                summary=(
                    f"Modelo {snapshot.modelo} {snapshot.filing_year} "
                    f"{snapshot.period.registry_token} live justificante"
                ),
                reference_id=snapshot.expediente_id,
                snapshot_id=snapshot.snapshot_id,
                modelo=snapshot.modelo,
                filing_year=snapshot.filing_year,
                period=snapshot.period,
                status="ALTA",
                aeat_submission_state=OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
                aeat_submitted_at=submitted_at,
                justificante_verified=True,
                verified_justificante_csv=evidence.verified_justificante_csv,
            ),
        )
    return _dedupe_calendar_events(events)


def _notification_matches_expected_tax_id(
    row: object,
    expected_tax_id: str | None,
    *,
    allow_missing_row_identity: bool = False,
) -> bool:
    expected = (expected_tax_id or "").strip().upper()
    if not expected:
        return True
    row_tax_ids = {
        str(getattr(row, "titular_nif", "") or "").strip().upper(),
        str(getattr(row, "destinatario_nif", "") or "").strip().upper(),
    }
    row_tax_ids.discard("")
    if not row_tax_ids:
        return allow_missing_row_identity
    return expected in row_tax_ids


def build_overview_calendar_events(
    *,
    calendar_range: OverviewCalendarRange,
    expedientes_snapshots: tuple[PersistedExpedientesSnapshot, ...] = (),
    notification_snapshots: tuple[PersistedNotificationsSnapshot, ...] = (),
    justificante_capture_snapshots: tuple[JustificanteCaptureSnapshot, ...] = (),
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarEvent, ...]:
    """Build :class:`OverviewCalendarEvent` tuples from persisted local live-read snapshots."""
    events = [
        *calendar_events_from_expedientes_snapshots(
            expedientes_snapshots,
            calendar_range,
            expected_tax_id=expected_tax_id,
        ),
        *calendar_events_from_notification_snapshots(
            notification_snapshots,
            calendar_range,
            expected_tax_id=expected_tax_id,
        ),
        *calendar_events_from_justificante_capture_snapshots(
            justificante_capture_snapshots,
            calendar_range,
            justificantes=justificantes,
            expected_tax_id=expected_tax_id,
        ),
    ]
    return _dedupe_calendar_events(events)


def calendar_events_from_modelo_records(
    filing_records: tuple[ModeloRecord, ...],
    calendar_range: OverviewCalendarRange,
    *,
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarEvent, ...]:
    """Project persisted Modelo filing records into calendar filing events.

    Args:
        filing_records: The persisted :class:`ModeloRecord` filings to project.
        calendar_range: The window that bounds which records become events.
        justificantes: Optional AEAT justificantes corroborating the filings.
        expected_tax_id: The taxpayer NIF the justificantes must match.

    Returns:
        A tuple of :class:`OverviewCalendarEvent`, one per in-range record.
    """
    justificantes_by_csv = _justificantes_by_csv(justificantes)
    events: list[OverviewCalendarEvent] = []
    for record in sorted(
        filing_records,
        key=lambda item: (item.filed_at, str(item.modelo), item.period.registry_token),
    ):
        evidence = _filing_axes_from_modelo_record(
            record,
            justificantes_by_csv=justificantes_by_csv,
            expected_tax_id=expected_tax_id,
        )
        event_date = _modelo_record_calendar_event_date(record, evidence)
        if not calendar_range.covers(event_date):
            continue
        events.append(
            OverviewCalendarEvent(
                event_type=OverviewCalendarEventType.FILING,
                event_date=event_date,
                source="modelo_filing_record",
                reference_id=record.filing_record_id,
                summary=f"Modelo {record.modelo} {record.period} filing record",
                modelo=str(record.modelo),
                filing_year=int(record.filing_year),
                period=record.period,
                status=f"{evidence.local_filing_state.value}:{record.status.value}",
                aeat_submission_state=evidence.aeat_submission_state,
                aeat_submitted_at=evidence.aeat_submitted_at,
                justificante_verified=evidence.justificante_verified,
                verified_justificante_csv=evidence.verified_justificante_csv,
            ),
        )
    return _dedupe_calendar_events(events)


def _modelo_record_calendar_event_date(record: ModeloRecord, evidence: OverviewCalendarFilingEvidence) -> date:
    """Return the event date for a local Modelo record's calendar projection."""
    if evidence.justificante_verified and evidence.aeat_submitted_at is not None:
        return evidence.aeat_submitted_at.date()
    return record.filed_at.date()


def calendar_filing_evidence_from_sources(
    *,
    filing_records: tuple[ModeloRecord, ...] = (),
    observed_events: tuple[OverviewCalendarEvent, ...] = (),
    filed_declaration_observations: tuple[FiledDeclaracionObservation, ...] = (),
    verified_filed_declaration_artefact_refs: tuple[str, ...] = (),
    verified_filed_declaration_artefact_csvs: Mapping[str, str] | None = None,
    calculation_observations: tuple[object, ...] = (),
    justificante_capture_snapshots: tuple[JustificanteCaptureSnapshot, ...] = (),
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    """Build :class:`OverviewCalendarFilingEvidence` tuples from local records and AEAT observations.

    The function is pure and intentionally accepts already-loaded
    records. CLI/storage code owns I/O; this projection only reconciles
    the existing local Modelo filing catalogue, calendar-visible AEAT
    register events, persisted calculation observations from
    justificante capture, and already-loaded justificante metadata. The
    ``filing_records`` are filed :class:`ModeloRecord` rows whose
    external justificante references are only promoted to
    ``justificante_verified`` when matching persisted metadata exists
    for the same CSV/model/year/period/taxpayer. Filed-declaration
    observations are only promoted to ``justificante_verified`` when
    their justificante artefact storage reference is listed in
    ``verified_filed_declaration_artefact_refs`` by the storage layer
    that loaded and hashed the encrypted artefact body.
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
    """Return the canonical lookup key for AEAT CSV identifiers."""
    return csv.strip().casefold()


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
    aeat_accepted = bool(getattr(record, "aeat_accepted", False))
    if aeat_accepted and external_evidence is not None:
        aeat_state = OverviewAeatSubmissionState.ACCEPTED
    if external_evidence is not None:
        kind = getattr(external_evidence, "kind", None)
        aeat_evidence_kind = str(getattr(kind, "value", kind))
        aeat_reference_id = str(external_evidence.reference_id)
        if aeat_accepted and aeat_evidence_kind in _JUSTIFICANTE_BACKED_EVIDENCE_KINDS:
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
    expected = (expected_tax_id or "").strip().upper()
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
    return (
        justificante.tax_id.strip().upper() == expected_tax_id.strip().upper()
        and justificante.modelo.strip() == modelo
        and str(justificante.ejercicio or "").strip() == str(filing_year)
        and justificante.period == period
    )


def _local_filing_state_from_modelo_record(record: ModeloRecord) -> OverviewLocalFilingState:
    """Return the local-app axis for one current Modelo record.

    ``external_evidence`` is the AEAT axis and must not erase the local
    meaning of a filing record. A normal local filing that later receives live
    AEAT evidence remains ``ready_to_file``; only records created through the
    external baseline import command use the imported-baseline state.
    """
    filed_by = str(getattr(record, "filed_by", "")).strip().lower()
    if filed_by == "aeat-import" or filed_by.startswith("aeat-import:"):
        return OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
    return OverviewLocalFilingState.READY_TO_FILE


def _filing_evidence_from_observed_event(
    event: OverviewCalendarEvent,
    *,
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project an AEAT calendar event into per-obligation evidence."""
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
    expected = (expected_tax_id or "").strip().upper()
    if not expected:
        return True
    actual = (authenticated_identity or "").strip().upper()
    return bool(actual) and actual == expected


def _filing_evidence_from_filed_declaration_observation(
    observation: FiledDeclaracionObservation,
    *,
    expected_tax_id: str | None,
    verified_artefact_refs: frozenset[str],
    verified_artefact_csv_by_ref: Mapping[str, str],
) -> OverviewCalendarFilingEvidence | None:
    """Project a captured AEAT filed-declaration observation into calendar evidence."""
    expected = (expected_tax_id or "").strip().upper()
    if expected and observation.authenticated_identity.strip().upper() != expected:
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
    payload: object,
    *,
    expected_tax_id: str | None,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
) -> OverviewCalendarFilingEvidence | None:
    """Project a persisted calculation observation into AEAT-submitted evidence."""
    source_kind = str(getattr(payload, "source_kind", ""))
    if source_kind not in _OFFICIAL_CALCULATION_SOURCE_KINDS:
        return None
    source_metadata = getattr(payload, "source_metadata", None)
    source_metadata = source_metadata if isinstance(source_metadata, Mapping) else {}
    if not source_metadata:
        return None
    status = str(source_metadata.get("aeat_register_status", "")).strip()
    if not _is_active_aeat_filing_status(status):
        return None
    aeat_expediente_id = str(source_metadata.get("aeat_expediente_id") or "").strip()
    if not aeat_expediente_id:
        return None
    expected = (expected_tax_id or "").strip().upper()
    authenticated_identity = str(source_metadata.get("authenticated_identity", "")).strip().upper()
    if expected and (not authenticated_identity or authenticated_identity != expected):
        return None
    observation = getattr(payload, "observation", None)
    if observation is None:
        return None
    _obs_year = int(observation.filing_year)
    _obs_period = getattr(observation, "filing_period", None)
    if isinstance(_obs_period, _Period):
        if _obs_period.filing_year != _obs_year:
            return None
    else:
        registry_token = observation.period
        if not isinstance(registry_token, str):
            return None
        try:
            _obs_period = _period_from_registry_token(_obs_year, registry_token)
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
        else getattr(payload, "captured_at", None),
        aeat_reference_id=aeat_expediente_id,
        aeat_evidence_kind=source_kind,
        verified_justificante_csv=verified_justificante.csv if verified_justificante is not None else None,
        justificante_verified=verified,
        evidence_source=source_kind,
    )


def _calculation_observation_verified_justificante(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    source_metadata: Mapping[object, object],
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    """Resolve filed-history observation metadata to matching persisted justificante metadata."""
    expected = str(expected_tax_id or source_metadata.get("authenticated_identity") or "").strip().upper()
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
    """Project one verified live justificante capture into AEAT-side evidence."""
    if not _capture_snapshot_is_active(snapshot):
        return None
    if not isinstance(snapshot.period, _Period):
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
    expected = (expected_tax_id or "").strip().upper()
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


def _metadata_justificante_csv_candidates(source_metadata: Mapping[object, object]) -> tuple[str, ...]:
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
    """Return a merged evidence row preserving the strongest signal on each axis."""
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
    """Prefer official justificante presentation time over later local capture time."""
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
        if existing_csv.casefold() == candidate_csv.casefold():
            return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
        references.extend((existing_csv, candidate_csv))
        return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
    if existing_csv is not None and candidate_ref is not None and candidate_ref.casefold() == existing_csv.casefold():
        return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
    if candidate_csv is not None and existing_ref is not None and existing_ref.casefold() == candidate_csv.casefold():
        return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))
    if existing_ref is not None and candidate_ref is not None and existing_ref.casefold() != candidate_ref.casefold():
        references.extend((existing_ref, candidate_ref))
    return tuple(dict.fromkeys(sorted(ref for ref in references if ref)))


def _clean_reference_id(reference_id: str | None) -> str | None:
    cleaned = (reference_id or "").strip()
    return cleaned or None


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


def _calendar_entry_from_obligation(
    obligation: _ModeloDeadline,
    *,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
) -> OverviewCalendarEntry:
    try:
        shift = _shift_deadline(
            obligation.closes_on,
            modelo=obligation.modelo,
            ccaa_code=None,
        )
        adjusted = shift.adjusted_close_date
        reason = shift.shift_reason
        holiday_refs = shift.holiday_refs
        jurisdictions = shift.jurisdictions
    except _DeadlineValidationError as exc:
        _log.debug(
            "overview calendar ignored deadline shift validation error",
            extra={
                "modelo": obligation.modelo,
                "period": obligation.period,
                "error_type": type(exc).__name__,
            },
        )
        adjusted = obligation.closes_on
        reason = "calendar_unavailable"
        holiday_refs = ()
        jurisdictions = ()
    period = obligation.period
    return OverviewCalendarEntry(
        modelo=obligation.modelo,
        period=period,
        opens_on=obligation.opens_on,
        closes_on=obligation.closes_on,
        adjusted_closes_on=adjusted,
        shift_reason=reason,
        holiday_refs=holiday_refs,
        jurisdictions=jurisdictions,
        payment_cutoff_on=obligation.payment_cutoff_on,
        status=obligation.status,
        user_state=user_state_for(obligation.status),
        recovery=obligation.recovery,
        filing_year=period.year,
        censo_enrolment_state=_calendar_censo_enrolment_state(
            modelo=obligation.modelo,
            live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        ),
        filing_evidence=_calendar_entry_filing_evidence(
            modelo=obligation.modelo,
            filing_year=period.year,
            period=period,
            evidence=filing_evidence,
        ),
    )


def build_overview_calendar(
    profile: _TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    *,
    today: date,
    engine: _ScheduleProducer | None = None,
    raw_values: Mapping[str, object] | None = None,
    show_suppressed: bool = False,
    events: tuple[OverviewCalendarEvent, ...] = (),
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...] = (),
    live_censo_verified_profile_keys: tuple[str, ...] | None = None,
) -> OverviewCalendar:
    """Build a typed calendar view for ``profile`` over ``calendar_range``.

    Composes the existing :class:`aeat.domain.deadlines.DeadlineEngine`
    over each year the range spans, filters obligations to those whose
    filing window intersects the range, attaches the user-state
    mapping, and returns the typed result.

    Args:
        profile: The operator's :class:`_TaxpayerProfile`.
        calendar_range: Inclusive date window to enumerate.
        today: Reference date for engine status classification.
        engine: Optional :class:`_ScheduleProducer` the caller wants to
            share across queries — a concrete
            :class:`aeat.domain.deadlines.DeadlineEngine` or any object
            satisfying the schedule-producing protocol. When ``None``,
            a default :class:`_DeadlineEngine` is constructed.
        raw_values: Optional mapping of casilla id to raw value, forwarded
            to the engine for user-state annotation. When ``None``, the
            engine uses an empty mapping.
        show_suppressed: When ``True``, populate
            :attr:`OverviewCalendar.suppressed_entries` with the
            obligations filtered out by a non-``APPLICABLE``
            applicability verdict. Default is ``False`` — the standard
            calendar view excludes suppressed rows from the payload
            entirely.
        events: Optional observed calendar events, usually projected
            from persisted local live-read snapshots by the CLI.
        filing_evidence: Optional local/AEAT evidence rows keyed to
            calendar obligations. These rows are preloaded by callers
            that own storage access; the calendar builder only merges
            them onto legal deadline entries.
        live_censo_verified_profile_keys: Optional profile paths whose
            current values carry live Modelo 036 / censo provenance.
            When supplied, active Modelo rows whose applicability cannot
            be tied to any such path receive a blocking calendar warning.

    A year inside the range with no registered deadline windows is
    treated as a "no data yet" state: that year contributes zero
    entries and the calendar still succeeds for every year that does
    have window data. This is the same graceful degradation
    ``overview explain`` applies to a modelo/year pair with no
    registered windows.

    Returns:
        A :class:`OverviewCalendar` with one entry per
        ``(modelo, period)`` whose filing window intersects the range.
    """
    if not _taxpayer_model_is_declared(profile):
        # An undeclared taxpayer model yields an explicit
        # incomplete answer — never a confident wrong obligation. The
        # engine does not fall back to the autónomo guess.
        return OverviewCalendar(
            range=calendar_range,
            entries=(),
            generated_at=now(),
            warnings=(),
            completeness=CalendarCompleteness(),
            taxpayer_model_declared=False,
            incomplete_reason=_tr("cli.overview.taxpayer_model_undeclared"),
            events=_calendar_events_with_filing_evidence(events, filing_evidence),
        )

    deadline_engine = engine if engine is not None else _DeadlineEngine()
    schedules: list[_Schedule] = []
    for year in calendar_range.covered_years():
        try:
            schedules.append(deadline_engine.compute(profile, year, today=today))
        except _NoDeadlineWindowsError as exc:
            # A year inside the range with no registered deadline
            # windows is a normal "no data yet" state, not an error
            # (registry-track gap R1). The year contributes zero
            # entries; the calendar still answers for every year that
            # does have window data. This catch is deliberately the
            # narrow ``_NoDeadlineWindowsError`` subtype: a genuine
            # registry-integrity fault (validation failure,
            # profile-condition evaluation failure) raises the bare
            # ``ScheduleComputationError`` and must propagate — masking
            # it here would silently hide a corrupt registry. This
            # mirrors the graceful degradation ``overview explain``
            # applies via the same narrow catch.
            _log.debug(
                "overview calendar ignored covered year with no registered deadline windows",
                extra={"year": year, "error_type": type(exc).__name__},
            )
            continue

    entries: list[OverviewCalendarEntry] = []
    suppressed: list[SuppressedCalendarEntry] = []
    for schedule in schedules:
        for obligation in schedule.obligations:
            if not _entry_intersects_range(obligation, calendar_range):
                continue
            # Each modelo's applicability is DERIVED from the taxpayer
            # model. Only a positively ``APPLICABLE`` verdict earns a
            # calendar row. An obligation the taxpayer model excludes
            # (``NOT_APPLICABLE`` — e.g. Modelo 130 for a pure landlord)
            # is dropped; so is a cuota self-assessment routed to the
            # attribution pass-through (``ATTRIBUTION_PASS_THROUGH`` — a
            # comunidad de bienes owes no IS / IRPF cuota of its own);
            # so is a modelo the seed table cannot yet decide
            # (``INCOMPLETE`` — no seed rule). Surfacing any of these as
            # a confident due row would diverge from ``explain`` and
            # re-create the confident-wrong-obligation defect. The seed
            # covers the core persona set; full per-modelo coverage is a
            # deferred expansion (see ``_SEED_COVERAGE_NOTICE``).
            applicability = derive_modelo_applicability(profile, obligation.modelo)
            if applicability.verdict is not ApplicabilityVerdict.APPLICABLE:
                if show_suppressed:
                    suppressed.append(
                        SuppressedCalendarEntry(
                            modelo=obligation.modelo,
                            period=obligation.period,
                            verdict=applicability.verdict,
                            reason=applicability.reason,
                        ),
                    )
                continue
            entries.append(
                _calendar_entry_from_obligation(
                    obligation,
                    filing_evidence=filing_evidence,
                    live_censo_verified_profile_keys=live_censo_verified_profile_keys,
                ),
            )

    entries.sort(key=lambda entry: (entry.closes_on, entry.modelo, entry.period.year, entry.period.registry_token))
    suppressed.sort(key=lambda s: (s.modelo, s.period.year, s.period.registry_token))
    entries_tuple = tuple(entries)
    completeness, warnings = _build_completeness_and_warnings(raw_values, entries_tuple)
    censo_warnings = _calendar_censo_reconciliation_warnings(
        entries=entries_tuple,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
    )
    enriched_events = _calendar_events_with_filing_evidence(events, filing_evidence)
    justificante_warnings = _calendar_unverified_justificante_warnings(
        entries=entries_tuple,
        events=enriched_events,
    )
    evidence_conflict_warnings = _calendar_aeat_evidence_conflict_warnings(entries=entries_tuple)
    return OverviewCalendar(
        range=calendar_range,
        entries=entries_tuple,
        generated_at=now(),
        warnings=warnings + censo_warnings + justificante_warnings + evidence_conflict_warnings,
        completeness=completeness,
        suppressed_entries=tuple(suppressed),
        events=enriched_events,
    )
