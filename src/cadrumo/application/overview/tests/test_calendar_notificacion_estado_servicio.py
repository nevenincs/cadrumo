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

from ....adapters.outbound.aeat.sede import RemoteNotification
from ....core import NotificacionEstadoServicio
from ...live import PersistedNotificationsSnapshot
from .. import OverviewCalendarRange, calendar_events_from_notification_snapshots
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


def test_the_projection_reads_as_of_and_not_an_ambient_clock() -> None:
    """The same stored snapshot yields different states for different ``as_of`` values.

    This is the property that makes the projection reproducible. If the builder
    read a clock instead of the argument, both calls would return the same state
    and this assertion would fail regardless of which state that was.
    """
    inside = _project_one(leida=False, as_of=date(2025, 3, 21))
    lapsed = _project_one(leida=False, as_of=date(2025, 3, 22))

    assert inside.notificacion_estado_servicio is not lapsed.notificacion_estado_servicio
