"""The projected calendar event carries its art. 43.2 service state.

Asserts that a persisted DEHu notification snapshot projects onto an
:class:`~cadrumo.application.overview.OverviewCalendarEvent` carrying the typed
:class:`~cadrumo.core.NotificacionEstadoServicio` service state, computed against
the caller-supplied ``as_of`` rather than an ambient clock, so a stored snapshot
reprojects identically on any day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede.notifications import RemoteNotification
from ....core.post_filing_event import ACTIONABLE_POST_FILING_EVENT_KINDS, PostFilingEventKind
from ....core.notificacion_estado_servicio import NotificacionEstadoServicio
from ...live.notifications import PersistedNotificationsSnapshot
from ..calendar import actionable_post_filing_events, calendar_events_from_notification_snapshots
from ..calendar_models import OverviewCalendarRange
from .calendar_test_support import BUCKET_ID, SOURCE_URL

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

PUESTA_A_DISPOSICION = date(2025, 3, 12)
_RANGE = OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31))


def _snapshot(*, leida: bool | None, fecha_notificacion: date | None = PUESTA_A_DISPOSICION):
    row = RemoteNotification(
        certificado_id="2596230606601",
        tipo="notificacion" if fecha_notificacion is not None else "pendiente",
        concepto="Notificación cuyo concepto no coincide con ninguna categoría más precisa",
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=fecha_notificacion,
        modo_notificacion="DEH" if fecha_notificacion is not None else None,
        leida=leida,
        source_url=AnyHttpUrl(SOURCE_URL),
    )
    return PersistedNotificationsSnapshot(
        snapshot_id="b" * 64,
        bucket_id=BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=SOURCE_URL,
        rows=(row,),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )


def _project_one(*, leida: bool | None, as_of: date, fecha_notificacion: date | None = PUESTA_A_DISPOSICION):
    events = calendar_events_from_notification_snapshots(
        (_snapshot(leida=leida, fecha_notificacion=fecha_notificacion),),
        _RANGE,
        as_of=as_of,
    )
    assert len(events) == 1
    return events[0]


def test_a_ten_day_lapsed_row_projects_as_deemed_rejected() -> None:
    """Ten dias naturales without access reaches the calendar as RECHAZO_TACITO."""
    event = _project_one(leida=False, as_of=date(2025, 3, 22))

    assert event.notificacion_estado_servicio is NotificacionEstadoServicio.RECHAZO_TACITO


def test_a_nine_day_row_projects_as_still_inside_the_window() -> None:
    """One day earlier the same row is still EN_PLAZO, so the projection is not constant."""
    event = _project_one(leida=False, as_of=date(2025, 3, 21))

    assert event.notificacion_estado_servicio is NotificacionEstadoServicio.EN_PLAZO


def test_an_accessed_row_projects_as_accedida_past_the_window() -> None:
    """Access serves the notification, so a long-elapsed read row is never deemed rejected."""
    event = _project_one(leida=True, as_of=date(2025, 3, 31))

    assert event.notificacion_estado_servicio is NotificacionEstadoServicio.ACCEDIDA


def test_an_undelivered_row_projects_as_no_entregada() -> None:
    """A pendiente row has no puesta a disposicion, so no window has started.

    The row still projects (it falls back to ``fecha_emision`` for its event
    date), which is why the state must be NO_ENTREGADA rather than absent: an
    absent state would be indistinguishable from a non-notification event.
    """
    event = _project_one(leida=None, as_of=date(2025, 3, 31), fecha_notificacion=None)

    assert event.notificacion_estado_servicio is NotificacionEstadoServicio.NO_ENTREGADA


def test_a_deemed_served_plain_notificacion_reaches_the_actionable_set() -> None:
    """The gap this feature closes: a plain NOTIFICACION was actionable on no day.

    The fixture's concepto matches no sharper procedural pattern, so the row
    classifies as the generic ``NOTIFICACION`` fallback, which is NOT a member of
    ACTIONABLE_POST_FILING_EVENT_KINDS. Before the service-state limb such a row
    never reached the operator -- not on day 1, not on day 30 -- while art. 43.2
    had already deemed it served.
    """
    event = _project_one(leida=False, as_of=date(2025, 3, 22))

    assert event.post_filing_kind is PostFilingEventKind.NOTIFICACION
    assert event.post_filing_kind not in ACTIONABLE_POST_FILING_EVENT_KINDS
    assert event.notificacion_estado_servicio is NotificacionEstadoServicio.RECHAZO_TACITO
    assert actionable_post_filing_events((event,)) == (event,)


def test_an_in_window_plain_notificacion_stays_non_actionable() -> None:
    """The widening must not regress the surface to flagging every notification.

    Same row, one day earlier. If the limb keyed on the field being POPULATED
    rather than on the RECHAZO_TACITO value, every projected notification would
    become actionable and this assertion would fail.
    """
    event = _project_one(leida=False, as_of=date(2025, 3, 21))

    assert event.notificacion_estado_servicio is NotificacionEstadoServicio.EN_PLAZO
    assert actionable_post_filing_events((event,)) == ()


def test_an_accessed_plain_notificacion_stays_non_actionable() -> None:
    """An ordinary read receipt is not a demand for action."""
    event = _project_one(leida=True, as_of=date(2025, 3, 31))

    assert actionable_post_filing_events((event,)) == ()


def test_the_widening_is_not_satisfiable_by_the_kind_limb_alone() -> None:
    """Anti-tautology proof: reverting to a bare kind-membership check fails.

    Reproduces the pre-widening predicate exactly -- a bare frozenset membership
    test on ``post_filing_kind`` -- and proves it and the shipped predicate
    DISAGREE on the deemed-served row. Without this, the test above could pass
    against a predicate that never consulted the service state at all, so long
    as some other limb admitted the row.

    It also proves the disagreement is confined to the deemed-served case: on the
    in-window row the two predicates agree, so the widening added exactly one
    behaviour rather than broadening the surface generally.
    """

    def pre_widening_predicate(event) -> bool:
        return event.post_filing_kind is not None and event.post_filing_kind in ACTIONABLE_POST_FILING_EVENT_KINDS

    deemed_served = _project_one(leida=False, as_of=date(2025, 3, 22))
    in_window = _project_one(leida=False, as_of=date(2025, 3, 21))

    assert actionable_post_filing_events((deemed_served,)) == (deemed_served,)
    assert pre_widening_predicate(deemed_served) is False
    assert actionable_post_filing_events((in_window,)) == ()
    assert pre_widening_predicate(in_window) is False


def test_an_actionable_kind_stays_actionable_regardless_of_service_state() -> None:
    """The kind limb survives the widening.

    A requerimiento is actionable on the strength of its category alone, so a
    read requerimiento inside its window must still reach the operator. This
    guards against a rewrite that replaced the kind limb rather than adding to it.
    """
    snapshot = _snapshot(leida=True)
    row = snapshot.rows[0].model_copy(update={"concepto": "Requerimiento de documentación relativa al IVA"})
    events = calendar_events_from_notification_snapshots(
        (snapshot.model_copy(update={"rows": (row,)}),),
        _RANGE,
        as_of=date(2025, 3, 13),
    )

    assert len(events) == 1
    assert events[0].post_filing_kind is PostFilingEventKind.REQUERIMIENTO
    assert events[0].notificacion_estado_servicio is NotificacionEstadoServicio.ACCEDIDA
    assert actionable_post_filing_events(events) == events


def test_the_projection_reads_as_of_and_not_an_ambient_clock() -> None:
    """The same stored snapshot yields different states for different ``as_of`` values.

    This is the property that makes the projection reproducible. If the builder
    read a clock instead of the argument, both calls would return the same state
    and this assertion would fail regardless of which state that was.
    """
    inside = _project_one(leida=False, as_of=date(2025, 3, 21))
    lapsed = _project_one(leida=False, as_of=date(2025, 3, 22))

    assert inside.notificacion_estado_servicio is not lapsed.notificacion_estado_servicio
