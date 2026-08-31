"""Calendar aggregation and evidence merge for the overview read model.

The facade composes a :class:`~cadrumo.domain.deadlines.Schedule` from
:class:`~cadrumo.domain.deadlines.TaxpayerProfile` facts and projects
already-loaded local state into :class:`OverviewCalendar` DTOs. Legal
obligation rows come from the deadline engine; observed
:class:`OverviewCalendarEvent` rows and :class:`OverviewCalendarFilingEvidence`
rows come from persisted Modelo records, local live-read snapshots, and
loaded justificante metadata supplied by the caller.

This module is local-only and pure with respect to I/O: it never starts a
live AEAT read and never verifies a justificante by fetching external
state. It only reconciles evidence the storage or CLI layer has already
loaded, preserving distinct :class:`OverviewLocalFilingState` and
:class:`OverviewAeatSubmissionState` axes.

See Also:
    :mod:`cadrumo.application.overview`
        Public facade that re-exports these calendar builders and DTOs.
    :class:`~cadrumo.domain.deadlines.DeadlineEngine`
        Deadline authority that produces the legal obligation schedule merged
        into the overview calendar.
    :func:`~cadrumo.application.overview.calendar_filing_evidence_from_sources`
        Pure evidence merge for local filing records, live captures,
        filed-declaration observations, and loaded justificante metadata.
    :class:`~cadrumo.application.live.JustificanteCaptureSnapshot`
        Persisted live justificante capture projected as AEAT-side evidence
        only when matching metadata is already loaded.
    :class:`~ModeloRecord`
        Local filing record projected on the local filing axis, separate from
        AEAT submission state.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

from ...core.external_constants import IVA_REGIME_MODELOS
from ...core.i18n import tr as _tr
from ...core.identity import same_tax_identifier
from ...core.logging import get_logger as _get_logger
from ...core.modelo import Modelo as _Modelo
from ...core.notificacion_estado_servicio import NotificacionEstadoServicio as _NotificacionEstadoServicio
from ...core.notificacion_estado_servicio import (
    resolve_notificacion_estado_servicio as _resolve_notificacion_estado_servicio,
)
from ...core.post_filing_event import PostFilingEventKind as _PostFilingEventKind
from ...core.post_filing_event import classify_post_filing_event_kind as _classify_post_filing_event_kind
from ...core.post_filing_event import post_filing_event_is_actionable as _post_filing_event_is_actionable
from ...core.time.clock import now
from ...domain.calculations.registry.applicability import ApplicabilityVerdict as _ApplicabilityVerdict
from ...domain.calculations.registry.applicability import derive_modelo_applicability as _derive_modelo_applicability
from ...domain.calculations.registry.applicability import taxpayer_model_is_declared as _taxpayer_model_is_declared
from ...domain.deadlines.engine import DeadlineEngine as _DeadlineEngine
from ...domain.deadlines.engine import ScheduleProducer as _ScheduleProducer
from ...domain.deadlines.engine import classify_obligation_status as _classify_obligation_status
from ...domain.deadlines.errors import DeadlineValidationError as _DeadlineValidationError
from ...domain.deadlines.errors import NoDeadlineWindowsError as _NoDeadlineWindowsError
from ...domain.deadlines.festivos import shift_deadline as _shift_deadline
from ...domain.deadlines.models import ModeloDeadline as _ModeloDeadline
from ...domain.deadlines.models import ObligationStatus as _ObligationStatus
from ...domain.deadlines.models import Schedule as _Schedule
from ...domain.deadlines.models import TaxpayerProfile as _TaxpayerProfile
from ...domain.deadlines.plazo import resolve_filing_window as _resolve_filing_window
from ...domain.modelos.work_unit import WorkUnit as _WorkUnit
from ...domain.modelos.work_unit import WorkUnitState as _WorkUnitState
from .calendar_evidence import (
    authenticated_identity_matches_expected as _authenticated_identity_matches_expected,
)
from .calendar_evidence import (
    calendar_entry_filing_evidence as _calendar_entry_filing_evidence,
)
from .calendar_evidence import (
    calendar_events_with_filing_evidence as _calendar_events_with_filing_evidence,
)
from .calendar_evidence import (
    dedupe_calendar_events as _dedupe_calendar_events,
)
from .calendar_evidence import (
    filing_axes_from_modelo_record as _filing_axes_from_modelo_record,
)
from .calendar_evidence import (
    filing_evidence_from_justificante_capture_snapshot as _filing_evidence_from_justificante_capture_snapshot,
)
from .calendar_evidence import (
    is_active_aeat_filing_status as _is_active_aeat_filing_status,
)
from .calendar_evidence import (
    justificantes_by_csv as _justificantes_by_csv,
)
from .calendar_models import (
    CalendarCompleteness as _CalendarCompleteness,
)
from .calendar_models import (
    OverviewAeatSubmissionState as _OverviewAeatSubmissionState,
)
from .calendar_models import (
    OverviewCalendar as _OverviewCalendar,
)
from .calendar_models import (
    OverviewCalendarEntry as _OverviewCalendarEntry,
)
from .calendar_models import (
    OverviewCalendarEntrySource as _OverviewCalendarEntrySource,
)
from .calendar_models import (
    OverviewCalendarEvent as _OverviewCalendarEvent,
)
from .calendar_models import (
    OverviewCalendarEventType as _OverviewCalendarEventType,
)
from .calendar_models import (
    OverviewCalendarFilingEvidence as _OverviewCalendarFilingEvidence,
)
from .calendar_models import (
    OverviewCalendarRange as _OverviewCalendarRange,
)
from .calendar_models import (
    OverviewLocalFilingState as _OverviewLocalFilingState,
)
from .calendar_models import (
    SuppressedCalendarEntry as _SuppressedCalendarEntry,
)
from .calendar_models import (
    user_state_for as _user_state_for,
)
from .calendar_warnings import (
    _build_completeness_and_warnings,
    _calendar_aeat_evidence_conflict_warnings,
    _calendar_censo_enrolment_state,
    _calendar_censo_reconciliation_warnings,
    _calendar_regime_incompatibility_warnings,
    _calendar_unverified_justificante_warnings,
)
from .coverage import build_obligation_coverage
from .next_actions import declare_next_action as _declare_next_action

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition
    from ...domain.justificante import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ..live.expedientes import PersistedExpedientesSnapshot
    from ..live.justificante import JustificanteCaptureSnapshot
    from ..live.notifications import PersistedNotificationsSnapshot

_log = _get_logger(__name__)
_IVA_REGIME_MODELOS = IVA_REGIME_MODELOS
_DEFAULT_LOCAL_WORK_UNIT_DUE_SOON_DAYS = 14
_LOCAL_WORK_UNIT_APPLIES_BECAUSE = (
    "Local modelo work unit created by the operator; registry deadline window unavailable or not surfaced."
)


def _entry_intersects_range(
    obligation: _ModeloDeadline,
    calendar_range: _OverviewCalendarRange,
) -> bool:
    """Return whether ``obligation``'s [opens_on, closes_on] intersects the range."""
    return obligation.closes_on >= calendar_range.from_date and obligation.opens_on <= calendar_range.to_date


def _calendar_entry_key(entry: _OverviewCalendarEntry) -> tuple[str, int, str]:
    return (
        entry.modelo,
        entry.filing_year or entry.period.filing_year,
        entry.period.registry_token,
    )


def _work_unit_key(unit: _WorkUnit) -> tuple[str, int, str]:
    return (str(unit.modelo), unit.filing_year, unit.period.registry_token)


def _registry_window_for_work_unit(unit: _WorkUnit) -> DeadlineWindowDefinition | None:
    """Return a registry deadline window for ``unit`` when one is bundled.

    Window matching belongs to the deadline domain, which owns the year/token
    rule and the no-window behaviour. Overview is a projection: it consumes the
    same window the extemporaneidad surface consumes and reads the ``opens_on``
    and ``payment_cutoff_on`` fields that surface does not need.
    """
    return _resolve_filing_window(str(unit.modelo), unit.filing_year, unit.period)


def _work_unit_window_dates(unit: _WorkUnit) -> tuple[date, date, date | None]:
    """Return the calendar span used to place a local work unit row."""
    window = _registry_window_for_work_unit(unit)
    if window is not None:
        return window.opens_on, window.closes_on, window.payment_cutoff_on
    if unit.period.has_date_span():
        return unit.period.start_date, unit.period.end_date, None
    anchor = unit.created_at.date()
    return anchor, anchor, None


def _work_unit_intersects_range(unit: _WorkUnit, calendar_range: _OverviewCalendarRange) -> bool:
    opens_on, closes_on, _payment_cutoff_on = _work_unit_window_dates(unit)
    return closes_on >= calendar_range.from_date and opens_on <= calendar_range.to_date


def _work_unit_has_filing_pointers(unit: _WorkUnit) -> bool:
    return unit.filed_calculation_revision_id is not None or unit.current_filing_record_id is not None


def _filing_evidence_has_local_state(
    unit: _WorkUnit,
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...],
) -> bool:
    key = _work_unit_key(unit)
    for evidence in filing_evidence:
        if evidence.modelo is None or evidence.filing_year is None or evidence.period is None:
            continue
        evidence_key = (evidence.modelo, evidence.filing_year, evidence.period.registry_token)
        if evidence_key == key and evidence.local_filing_state is not _OverviewLocalFilingState.NOT_READY_TO_FILE:
            return True
    return False


def _local_work_unit_status(
    unit: _WorkUnit,
    closes_on: date,
    today: date,
    due_soon_days: int,
) -> _ObligationStatus:
    """Classify a local work unit, applying overview's filing gate first.

    The filing-pointer gate is overview's own concern and is the only
    intentional difference from the deadline engine's classification: a unit
    the operator has already filed locally is FILED regardless of dates. Every
    date boundary past that gate is the deadline domain's to decide, so it is
    delegated rather than restated.
    """
    if _work_unit_has_filing_pointers(unit):
        return _ObligationStatus.FILED
    return _classify_obligation_status(closes_on, today, due_soon_days)


def _filing_evidence_with_work_unit_pointers(
    unit: _WorkUnit,
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...],
) -> tuple[_OverviewCalendarFilingEvidence, ...]:
    if not _work_unit_has_filing_pointers(unit):
        return filing_evidence
    if _filing_evidence_has_local_state(unit, filing_evidence):
        return filing_evidence
    pointer_evidence = _OverviewCalendarFilingEvidence(
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
        local_filing_state=_OverviewLocalFilingState.READY_TO_FILE,
        local_filing_record_id=unit.current_filing_record_id,
        local_calculation_revision_id=unit.filed_calculation_revision_id,
        evidence_source="work_unit_filing_pointers",
    )
    return (*filing_evidence, pointer_evidence)


def _annotate_entry_with_work_unit(entry: _OverviewCalendarEntry, unit: _WorkUnit) -> _OverviewCalendarEntry:
    return entry.model_copy(
        update={
            "local_work_unit_id": unit.work_unit_id,
            "local_work_unit_name": unit.name,
            "local_work_unit_revision_id": unit.revision_id,
        },
    )


def _calendar_entry_from_work_unit(
    unit: _WorkUnit,
    *,
    today: date,
    due_soon_days: int,
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
) -> _OverviewCalendarEntry:
    opens_on, closes_on, payment_cutoff_on = _work_unit_window_dates(unit)
    effective_filing_evidence = _filing_evidence_with_work_unit_pointers(unit, filing_evidence)
    obligation = _ModeloDeadline(
        modelo=_Modelo(str(unit.modelo)),
        period=unit.period,
        opens_on=opens_on,
        closes_on=closes_on,
        payment_cutoff_on=payment_cutoff_on,
        status=_local_work_unit_status(unit, closes_on, today, due_soon_days),
        applies_because=_LOCAL_WORK_UNIT_APPLIES_BECAUSE,
        boe_references=(),
        recovery=None,
    )
    return _calendar_entry_from_obligation(
        obligation,
        filing_evidence=effective_filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
    ).model_copy(
        update={
            "source": _OverviewCalendarEntrySource.LOCAL_WORK_UNIT,
            "local_work_unit_id": unit.work_unit_id,
            "local_work_unit_name": unit.name,
            "local_work_unit_revision_id": unit.revision_id,
        },
    )


def _merge_work_units_into_entries(
    entries: tuple[_OverviewCalendarEntry, ...],
    *,
    work_units: tuple[_WorkUnit, ...],
    calendar_range: _OverviewCalendarRange,
    today: date,
    due_soon_days: int,
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
) -> tuple[_OverviewCalendarEntry, ...]:
    merged = list(entries)
    registry_index = {_calendar_entry_key(entry): index for index, entry in enumerate(entries)}
    annotated_registry_keys: set[tuple[str, int, str]] = set()
    for unit in sorted(
        (item for item in work_units if item.state is not _WorkUnitState.DESCARTADO),
        key=lambda item: (str(item.modelo), item.filing_year, item.period.registry_token, item.work_unit_id),
    ):
        key = _work_unit_key(unit)
        existing_index = registry_index.get(key)
        if existing_index is not None and key not in annotated_registry_keys:
            merged[existing_index] = _annotate_entry_with_work_unit(merged[existing_index], unit)
            annotated_registry_keys.add(key)
            continue
        if not _work_unit_intersects_range(unit, calendar_range):
            continue
        merged.append(
            _calendar_entry_from_work_unit(
                unit,
                today=today,
                due_soon_days=due_soon_days,
                filing_evidence=filing_evidence,
                live_censo_verified_profile_keys=live_censo_verified_profile_keys,
            ),
        )
    return tuple(
        sorted(
            merged,
            key=lambda entry: (
                entry.closes_on,
                entry.modelo,
                entry.period.filing_year,
                entry.period.registry_token,
                entry.local_work_unit_id or "",
            ),
        ),
    )


def calendar_events_from_expedientes_snapshots(
    snapshots: tuple[PersistedExpedientesSnapshot, ...],
    calendar_range: _OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
) -> tuple[_OverviewCalendarEvent, ...]:
    """Project persisted declaration-register snapshots into calendar events.

    Each in-range declaration becomes an :class:`OverviewCalendarEvent` when
    its authenticated identity matches ``expected_tax_id``. Only active
    ``ALTA`` rows carry :attr:`OverviewAeatSubmissionState.SUBMITTED_OBSERVED`;
    non-active rows remain historical events and cannot upgrade
    :class:`OverviewCalendarFilingEvidence`.
    """
    events: list[_OverviewCalendarEvent] = []
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
                _OverviewAeatSubmissionState.SUBMITTED_OBSERVED
                if _is_active_aeat_filing_status(declaration.estado)
                else None
            )
            events.append(
                _OverviewCalendarEvent(
                    event_type=_OverviewCalendarEventType.FILING,
                    post_filing_kind=_PostFilingEventKind.DECLARACION_PRESENTADA,
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
    calendar_range: _OverviewCalendarRange,
    *,
    as_of: date,
    expected_tax_id: str | None = None,
) -> tuple[_OverviewCalendarEvent, ...]:
    """Project persisted AEAT notifications into message events.

    Notifications become :class:`OverviewCalendarEventType.MESSAGE` rows only;
    they are additive calendar observations and never imply
    :class:`OverviewAeatSubmissionState` or filing evidence for an obligation.

    Each row also carries its :class:`~core.NotificacionEstadoServicio` service
    state, computed against ``as_of`` so a projection over stored snapshots is
    reproducible rather than dependent on when it happened to run.

    Args:
        snapshots: Persisted notification snapshots loaded by the caller.
        calendar_range: Inclusive window rows are filtered to.
        as_of: Date the Ley 39/2015 art. 43.2 window is evaluated against.
            Required and threaded from the caller, never defaulted to today.
        expected_tax_id: Taxpayer identity rows must match, when known.

    Returns:
        A tuple of :class:`OverviewCalendarEvent` message observations inside
        ``calendar_range``.
    """
    events: list[_OverviewCalendarEvent] = []
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
            post_filing_kind = _classify_post_filing_event_kind(concepto=row.concepto, tipo=row.tipo)
            estado_servicio = _resolve_notificacion_estado_servicio(
                fecha_notificacion=row.fecha_notificacion,
                leida=row.leida,
                as_of=as_of,
            )
            events.append(
                _OverviewCalendarEvent(
                    event_type=_OverviewCalendarEventType.MESSAGE,
                    post_filing_kind=post_filing_kind,
                    notificacion_estado_servicio=estado_servicio,
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
    calendar_range: _OverviewCalendarRange,
    *,
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[_OverviewCalendarEvent, ...]:
    """Project verified live justificante captures into calendar filing events.

    A :class:`~cadrumo.application.live.JustificanteCaptureSnapshot` becomes an
    :class:`OverviewCalendarEvent` only after loaded
    :class:`~cadrumo.domain.justificante.Justificante` metadata proves the same
    CSV/model/year/period/taxpayer tuple. The event therefore carries
    :attr:`OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED` without opening a
    new live read.
    """
    justificantes_by_csv = _justificantes_by_csv(justificantes)
    events: list[_OverviewCalendarEvent] = []
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
            _OverviewCalendarEvent(
                event_type=_OverviewCalendarEventType.FILING,
                post_filing_kind=_PostFilingEventKind.DECLARACION_PRESENTADA,
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
                aeat_submission_state=_OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
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
    expected = (expected_tax_id or "").strip()
    if not expected:
        return True
    row_tax_ids = {
        str(getattr(row, "titular_nif", "") or "").strip(),
        str(getattr(row, "destinatario_nif", "") or "").strip(),
    }
    row_tax_ids.discard("")
    if not row_tax_ids:
        return allow_missing_row_identity
    # Set membership over trim-and-uppercase values compared the printed
    # and stored spellings of one identifier as different bearers: it never
    # stripped the separators AEAT prints, so B-1234567-4 missed B12345674
    # and a matching row read as somebody else's.
    return any(same_tax_identifier(expected, row_tax_id) for row_tax_id in row_tax_ids)


def build_overview_calendar_events(
    *,
    calendar_range: _OverviewCalendarRange,
    as_of: date,
    expedientes_snapshots: tuple[PersistedExpedientesSnapshot, ...] = (),
    notification_snapshots: tuple[PersistedNotificationsSnapshot, ...] = (),
    justificante_capture_snapshots: tuple[JustificanteCaptureSnapshot, ...] = (),
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[_OverviewCalendarEvent, ...]:
    """Build observed events from persisted live-read snapshots.

    The snapshots are inputs loaded by the caller. This helper only
    fans out through :func:`calendar_events_from_expedientes_snapshots`,
    :func:`calendar_events_from_notification_snapshots`, and
    :func:`calendar_events_from_justificante_capture_snapshots`, then dedupes
    :class:`OverviewCalendarEvent` rows by their stable observation keys. It
    performs no storage or AEAT I/O.

    Args:
        calendar_range: Inclusive window rows are filtered to.
        as_of: Date the notification service-state window is evaluated against,
            threaded to :func:`calendar_events_from_notification_snapshots`.
        expedientes_snapshots: Persisted expedientes snapshots.
        notification_snapshots: Persisted notification snapshots.
        justificante_capture_snapshots: Persisted justificante captures.
        justificantes: Loaded justificante metadata for capture verification.
        expected_tax_id: Taxpayer identity rows must match, when known.
    """
    events = [
        *calendar_events_from_expedientes_snapshots(
            expedientes_snapshots,
            calendar_range,
            expected_tax_id=expected_tax_id,
        ),
        *calendar_events_from_notification_snapshots(
            notification_snapshots,
            calendar_range,
            as_of=as_of,
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


def _event_demands_attention(event: _OverviewCalendarEvent) -> bool:
    """Return whether one observed event demands operator attention.

    Two independent limbs, deliberately not collapsed into one: the procedural
    category the event was classified into, and the service state the art. 43.2
    window computed. Either alone is sufficient, because a deemed-served
    notification matters regardless of category and a requerimiento matters
    regardless of whether it was read.
    """
    if event.post_filing_kind is not None and _post_filing_event_is_actionable(event.post_filing_kind):
        return True
    return event.notificacion_estado_servicio is _NotificacionEstadoServicio.RECHAZO_TACITO


def actionable_post_filing_events(
    events: tuple[_OverviewCalendarEvent, ...],
) -> tuple[_OverviewCalendarEvent, ...]:
    """Return the observed :class:`OverviewCalendarEvent` rows that demand operator attention.

    An event is actionable when its
    :attr:`~cadrumo.application.overview.OverviewCalendarEvent.post_filing_kind`
    is a member of :data:`~cadrumo.core.ACTIONABLE_POST_FILING_EVENT_KINDS` — a
    requerimiento, a propuesta / acuerdo de liquidación, a procedimiento
    sancionador, or a recaudación enforcement act (providencia de apremio or
    diligencia de embargo). These are the post-filing events an operator must
    not miss; the overview surfaces them so a pulled requerimiento is not
    buried in an undifferentiated message list.

    An event is ALSO actionable, independent of its procedural category, when
    its :attr:`~cadrumo.application.overview.OverviewCalendarEvent.notificacion_estado_servicio`
    is :attr:`~cadrumo.core.NotificacionEstadoServicio.RECHAZO_TACITO`. A plain
    ``notificacion`` whose concepto matches no sharper pattern falls outside
    every actionable category, so before this second limb a formal notification
    that lapsed into deemed service under Ley 39/2015 art. 43.2 reached the
    operator on no day at all — while the taxpayer already bore its
    consequences. The limb is deliberately narrow: only the deemed-served state
    qualifies, so an ordinary read receipt or an in-window notification stays
    non-actionable and the surface does not regress to flagging every message.

    The result preserves the input order (the callers pass deduped,
    sort-stable event tuples).
    """
    return tuple(event for event in events if _event_demands_attention(event))


def calendar_events_from_modelo_records(
    filing_records: tuple[ModeloRecord, ...],
    calendar_range: _OverviewCalendarRange,
    *,
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[_OverviewCalendarEvent, ...]:
    """Project persisted Modelo filing records into calendar filing events.

    A :class:`~ModeloRecord` always contributes on the
    :class:`OverviewLocalFilingState` axis. It only contributes
    :class:`OverviewAeatSubmissionState` when its external evidence reference is
    corroborated by loaded :class:`~cadrumo.domain.justificante.Justificante`
    metadata for the same taxpayer and filing target.

    Args:
        filing_records: The persisted :class:`~ModeloRecord`
            filings to project.
        calendar_range: The window that bounds which records become events.
        justificantes: Optional AEAT justificantes corroborating the filings.
        expected_tax_id: The taxpayer NIF the justificantes must match.

    Returns:
        A tuple of :class:`OverviewCalendarEvent`, one per in-range record.
    """
    justificantes_by_csv = _justificantes_by_csv(justificantes)
    events: list[_OverviewCalendarEvent] = []
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
            _OverviewCalendarEvent(
                event_type=_OverviewCalendarEventType.FILING,
                post_filing_kind=_PostFilingEventKind.DECLARACION_PRESENTADA,
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


def _modelo_record_calendar_event_date(record: ModeloRecord, evidence: _OverviewCalendarFilingEvidence) -> date:
    """Return the event date for a local Modelo record's calendar projection."""
    if evidence.justificante_verified and evidence.aeat_submitted_at is not None:
        return evidence.aeat_submitted_at.date()
    return record.filed_at.date()


def _calendar_entry_from_obligation(
    obligation: _ModeloDeadline,
    *,
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
) -> _OverviewCalendarEntry:
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
    return _OverviewCalendarEntry(
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
        user_state=_user_state_for(obligation.status),
        recovery=obligation.recovery,
        recovery_action=(
            _declare_next_action(
                "operator.modelo.work.create",
                modelo=str(obligation.modelo),
                year=period.filing_year,
                period=period.registry_token,
            )
            if obligation.recovery is not None
            else None
        ),
        filing_year=period.filing_year,
        censo_enrolment_state=_calendar_censo_enrolment_state(
            modelo=obligation.modelo,
            live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        ),
        filing_evidence=_calendar_entry_filing_evidence(
            modelo=obligation.modelo,
            filing_year=period.filing_year,
            period=period,
            evidence=filing_evidence,
        ),
    )


def _schedules_for_calendar_range(
    profile: _TaxpayerProfile,
    calendar_range: _OverviewCalendarRange,
    *,
    today: date,
    engine: _ScheduleProducer | None,
) -> tuple[_ScheduleProducer, list[_Schedule]]:
    """Return the deadline engine and per-year schedules covering ``calendar_range``.

    A year inside the range with no registered deadline windows is a normal
    "no data yet" state (registry-track gap R1), not an error: the year
    contributes zero entries and every other covered year still resolves.
    This catch is deliberately the narrow ``_NoDeadlineWindowsError``
    subtype; a genuine registry-integrity fault (validation failure,
    profile-condition evaluation failure) raises the bare
    ``ScheduleComputationError`` and must propagate, mirroring the graceful
    degradation ``overview explain`` applies via the same narrow catch.
    """
    deadline_engine = engine if engine is not None else _DeadlineEngine()
    schedules: list[_Schedule] = []
    for year in calendar_range.covered_years():
        try:
            schedules.append(deadline_engine.compute(profile, year, today=today))
        except _NoDeadlineWindowsError as exc:
            _log.debug(
                "overview calendar ignored covered year with no registered deadline windows",
                extra={"year": year, "error_type": type(exc).__name__},
            )
            continue
    return deadline_engine, schedules


def _entries_and_suppressed_from_schedules(
    schedules: list[_Schedule],
    *,
    profile: _TaxpayerProfile,
    calendar_range: _OverviewCalendarRange,
    show_suppressed: bool,
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
) -> tuple[list[_OverviewCalendarEntry], list[_SuppressedCalendarEntry], set[str]]:
    """Project every schedule's obligations into applicable calendar entries.

    Each modelo's applicability is DERIVED from the taxpayer model. Only a
    positively ``APPLICABLE`` verdict earns a calendar row. An obligation the
    taxpayer model excludes (``NOT_APPLICABLE`` -- e.g. Modelo 130 for a pure
    landlord) is dropped; so is a cuota self-assessment routed to the
    attribution pass-through (``ATTRIBUTION_PASS_THROUGH`` -- a comunidad de
    bienes owes no IS / IRPF cuota of its own); so is a modelo the seed table
    cannot yet decide (``INCOMPLETE`` -- no seed rule). Surfacing any of
    these as a confident due row would diverge from ``explain`` and
    re-create the confident-wrong-obligation defect. The seed covers the
    core persona set; full per-modelo coverage is a deferred expansion (see
    ``_SEED_COVERAGE_NOTICE``).
    """
    entries: list[_OverviewCalendarEntry] = []
    suppressed: list[_SuppressedCalendarEntry] = []
    coverage_surface_modelos: set[str] = set()
    for schedule in schedules:
        for obligation in schedule.obligations:
            intersects_range = _entry_intersects_range(obligation, calendar_range)
            applicability = _derive_modelo_applicability(profile, obligation.modelo)
            if applicability.verdict is not _ApplicabilityVerdict.APPLICABLE:
                if show_suppressed and intersects_range:
                    suppressed.append(
                        _SuppressedCalendarEntry(
                            modelo=obligation.modelo,
                            period=obligation.period,
                            verdict=applicability.verdict,
                            reason=applicability.reason,
                        ),
                    )
                continue
            coverage_surface_modelos.add(obligation.modelo)
            if not intersects_range:
                continue
            entries.append(
                _calendar_entry_from_obligation(
                    obligation,
                    filing_evidence=filing_evidence,
                    live_censo_verified_profile_keys=live_censo_verified_profile_keys,
                ),
            )
    return entries, suppressed, coverage_surface_modelos


def build_overview_calendar(
    profile: _TaxpayerProfile,
    calendar_range: _OverviewCalendarRange,
    *,
    today: date,
    engine: _ScheduleProducer | None = None,
    raw_values: Mapping[str, object] | None = None,
    show_suppressed: bool = False,
    events: tuple[_OverviewCalendarEvent, ...] = (),
    filing_evidence: tuple[_OverviewCalendarFilingEvidence, ...] = (),
    work_units: tuple[_WorkUnit, ...] = (),
    live_censo_verified_profile_keys: tuple[str, ...] | None = None,
) -> _OverviewCalendar:
    """Build a typed calendar view for ``profile`` over ``calendar_range``.

    Composes the existing :class:`~cadrumo.domain.deadlines.DeadlineEngine`
    over each year the range spans, filters obligations to those whose
    filing window intersects the range, attaches the user-state
    mapping, merges already-loaded :class:`OverviewCalendarFilingEvidence`,
    enriches :class:`OverviewCalendarEvent` rows, and returns the typed
    :class:`OverviewCalendar`. The builder does not load repositories and does
    not contact AEAT.

    Args:
        profile: The operator's :class:`~cadrumo.domain.deadlines.TaxpayerProfile`.
        calendar_range: Inclusive date window to enumerate.
        today: Reference date for engine status classification.
        engine: Optional :class:`~cadrumo.domain.deadlines.ScheduleProducer` the caller wants to
            share across queries — a concrete
            :class:`~cadrumo.domain.deadlines.DeadlineEngine` or any object
            satisfying the schedule-producing protocol. When ``None``,
            a default :class:`~cadrumo.domain.deadlines.DeadlineEngine` is
            constructed.
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
        work_units: Optional active or audit-loaded Modelo work units. Active
            units are merged onto matching registry rows or projected as
            local-work-unit rows when registry windows do not cover the
            historical target.
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
        # engine does not fall back to the autónomo guess. Coverage is still
        # reconciled (nothing surfaced), so the report honestly shows the whole
        # obligation universe as advised/undetermined rather than empty — an
        # undeclared profile can under-scope the most, so it must not read as
        # "nothing to file".
        return _OverviewCalendar(
            range=calendar_range,
            entries=(),
            generated_at=now(),
            warnings=(),
            completeness=_CalendarCompleteness(),
            taxpayer_model_declared=False,
            incomplete_reason=_tr("cli.overview.taxpayer_model_undeclared"),
            events=_calendar_events_with_filing_evidence(events, filing_evidence),
            coverage=build_obligation_coverage(profile, frozenset(), today=today),
        )

    deadline_engine, schedules = _schedules_for_calendar_range(profile, calendar_range, today=today, engine=engine)
    entries, suppressed, coverage_surface_modelos = _entries_and_suppressed_from_schedules(
        schedules,
        profile=profile,
        calendar_range=calendar_range,
        show_suppressed=show_suppressed,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
    )
    entries.sort(
        key=lambda entry: (
            entry.closes_on,
            entry.modelo,
            entry.period.filing_year,
            entry.period.registry_token,
        ),
    )
    due_soon_days = getattr(deadline_engine, "due_soon_days", _DEFAULT_LOCAL_WORK_UNIT_DUE_SOON_DAYS)
    suppressed.sort(key=lambda s: (s.modelo, s.period.filing_year, s.period.registry_token))
    entries_tuple = _merge_work_units_into_entries(
        tuple(entries),
        work_units=work_units,
        calendar_range=calendar_range,
        today=today,
        due_soon_days=due_soon_days,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
    )
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
    regime_incompatibility_warnings = _calendar_regime_incompatibility_warnings(
        iva_regime=profile.iva_regime,
        entries=entries_tuple,
    )
    coverage = build_obligation_coverage(
        profile,
        coverage_surface_modelos | {entry.modelo for entry in entries_tuple},
        today=today,
    )
    return _OverviewCalendar(
        range=calendar_range,
        entries=entries_tuple,
        generated_at=now(),
        warnings=(
            warnings
            + censo_warnings
            + justificante_warnings
            + evidence_conflict_warnings
            + regime_incompatibility_warnings
        ),
        completeness=completeness,
        suppressed_entries=tuple(suppressed),
        events=enriched_events,
        coverage=coverage,
    )
