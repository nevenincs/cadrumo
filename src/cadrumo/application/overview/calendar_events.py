"""Project observed filing and notification events for the overview calendar.

These pure builders reconcile already-loaded snapshots and records without
performing network or storage I/O.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol

from ...core.identity.tax_id import same_tax_identifier
from ...core.notificacion_estado_servicio import NotificacionEstadoServicio as _NotificacionEstadoServicio
from ...core.notificacion_estado_servicio import (
    resolve_notificacion_estado_servicio as _resolve_notificacion_estado_servicio,
)
from ...core.post_filing_event import PostFilingEventKind as _PostFilingEventKind
from ...core.post_filing_event import classify_post_filing_event_kind as _classify_post_filing_event_kind
from ...core.post_filing_event import post_filing_event_is_actionable as _post_filing_event_is_actionable
from ...domain.deadlines.fact_context import DeadlineFactResolutionContext as _DeadlineFactResolutionContext
from ._calendar_evidence_sources import (
    authenticated_identity_matches_expected as _authenticated_identity_matches_expected,
)
from ._calendar_evidence_sources import (
    filing_axes_from_modelo_record as _filing_axes_from_modelo_record,
)
from ._calendar_evidence_sources import (
    filing_evidence_from_justificante_capture_snapshot as _filing_evidence_from_justificante_capture_snapshot,
)
from ._calendar_evidence_sources import (
    is_active_aeat_filing_status as _is_active_aeat_filing_status,
)
from ._calendar_evidence_sources import (
    justificantes_by_csv as _justificantes_by_csv,
)
from .calendar_evidence import (
    dedupe_calendar_events as _dedupe_calendar_events,
)
from .calendar_models import (
    OverviewAeatSubmissionState as _OverviewAeatSubmissionState,
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

if TYPE_CHECKING:
    from ...domain.justificante.schema import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ..live.expedientes import PersistedExpedientesSnapshot
    from ..live.justificante import JustificanteCaptureSnapshot
    from ..live.notifications import PersistedNotificationsSnapshot


class _RemoteNotification(Protocol):
    """Minimum notification-row surface consumed by the calendar projection."""

    @property
    def certificado_id(self) -> str:
        """Notification certificate identifier."""
        ...

    @property
    def tipo(self) -> str:
        """Notification type token."""
        ...

    @property
    def concepto(self) -> str:
        """Notification subject or concept."""
        ...

    @property
    def titular_nif(self) -> str:
        """Tax identity associated with the notification."""
        ...

    @property
    def destinatario_nif(self) -> str:
        """Recipient tax identity associated with the notification."""
        ...

    @property
    def fecha_emision(self) -> date:
        """Notification issue date."""
        ...

    @property
    def fecha_notificacion(self) -> date | None:
        """Notification delivery date, when delivered."""
        ...

    @property
    def leida(self) -> bool | None:
        """Whether the notification has been read, when known."""
        ...

    @property
    def source_url(self) -> object:
        """Source URL carried by the notification, when present."""
        ...


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

    Each row also carries its :class:`~core.notificacion_estado_servicio.NotificacionEstadoServicio` service
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
            event = _calendar_event_from_notification(snapshot, row, calendar_range=calendar_range, as_of=as_of)
            if event is not None:
                events.append(event)
    return _dedupe_calendar_events(events)


def _calendar_event_from_notification(
    snapshot: PersistedNotificationsSnapshot,
    row: _RemoteNotification,
    *,
    calendar_range: _OverviewCalendarRange,
    as_of: date,
) -> _OverviewCalendarEvent | None:
    """Assemble one in-range notification row into its message observation."""
    event_date = row.fecha_notificacion or row.fecha_emision
    if not calendar_range.covers(event_date):
        return None
    read_state = "read" if row.leida is True else "unread" if row.leida is False else None
    status = read_state or row.tipo
    summary = row.concepto.strip() or row.tipo
    post_filing_kind = _classify_post_filing_event_kind(concepto=row.concepto, tipo=row.tipo)
    # Notification service is calculated in core, while the governed legal
    # parameter is selected at this outer application composition boundary.
    # An undelivered row has no submission coordinate, so ``as_of`` is the
    # explicit projection coordinate for the state that does not consume it.
    from ...domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        facts = _DeadlineFactResolutionContext(
            authority=operation,
            filing_period=as_of,
            submission_date=row.fecha_notificacion or as_of,
        )
        estado_servicio = _resolve_notificacion_estado_servicio(
            fecha_notificacion=row.fecha_notificacion,
            leida=row.leida,
            as_of=as_of,
            tacit_rejection_natural_days=facts.integer("dehu-tacit-rejection-natural-days"),
        )
    return _OverviewCalendarEvent(
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
    )


def calendar_events_from_justificante_capture_snapshots(
    snapshots: tuple[JustificanteCaptureSnapshot, ...],
    calendar_range: _OverviewCalendarRange,
    *,
    justificantes: tuple[Justificante, ...] = (),
    expected_tax_id: str | None = None,
) -> tuple[_OverviewCalendarEvent, ...]:
    """Project verified live justificante captures into calendar filing events.

    A :class:`~cadrumo.application.live.justificante.JustificanteCaptureSnapshot` becomes an
    :class:`OverviewCalendarEvent` only after loaded
    :class:`~cadrumo.domain.justificante.schema.Justificante` metadata proves the same
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
    :attr:`~cadrumo.application.overview.calendar_models.OverviewCalendarEvent.post_filing_kind`
    is a member of :data:`~cadrumo.core.post_filing_event.ACTIONABLE_POST_FILING_EVENT_KINDS` — a
    requerimiento, a propuesta / acuerdo de liquidación, a procedimiento
    sancionador, or a recaudación enforcement act (providencia de apremio or
    diligencia de embargo). These are the post-filing events an operator must
    not miss; the overview surfaces them so a pulled requerimiento is not
    buried in an undifferentiated message list.

    An event is ALSO actionable, independent of its procedural category, when
    its :attr:`~cadrumo.application.overview.calendar_models.OverviewCalendarEvent.notificacion_estado_servicio`
    is :attr:`~cadrumo.core.notificacion_estado_servicio.NotificacionEstadoServicio.RECHAZO_TACITO`. A plain
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
    corroborated by loaded :class:`~cadrumo.domain.justificante.schema.Justificante`
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
                filing_year=record.filing_year,
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
