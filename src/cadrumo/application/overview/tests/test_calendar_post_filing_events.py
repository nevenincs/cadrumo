"""Post-filing event classification and actionable-filtering on calendar events.

Asserts that pulled AEAT notification / expediente snapshots carry the
fine-grained :class:`~cadrumo.core.PostFilingEventKind` procedural category on
the projected :class:`~cadrumo.application.overview.OverviewCalendarEvent`, and
that :func:`~cadrumo.application.overview.actionable_post_filing_events` selects
exactly the demand / enforcement categories.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....adapters.outbound.aeat.sede.notifications import RemoteNotification
from ....core.period import Period
from ....core.post_filing_event import PostFilingEventKind
from ...live.expedientes import PersistedExpedientesSnapshot
from ...live.notifications import PersistedNotificationsSnapshot
from ..calendar import (
    actionable_post_filing_events,
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_notification_snapshots,
)
from ..calendar_models import OverviewCalendarRange
from .calendar_test_support import BUCKET_ID, SOURCE_URL

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RANGE = OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31))
_AS_OF = date(2025, 3, 13)
"""One day after every fixture's puesta a disposicion.

Inside the art. 43.2 window, so the service-state axis stays EN_PLAZO and
cannot influence the procedural-category assertions in this module.
"""


def _notification(
    *,
    certificado_id: str,
    concepto: str,
    tipo: Literal["notificacion", "comunicacion", "pendiente", "unknown"],
    leida: bool | None,
) -> RemoteNotification:
    return RemoteNotification(
        certificado_id=certificado_id,
        tipo=tipo,
        concepto=concepto,
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEH",
        leida=leida,
        source_url=AnyHttpUrl(SOURCE_URL),
    )


def _notifications_snapshot(rows: tuple[RemoteNotification, ...]) -> PersistedNotificationsSnapshot:
    return PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=SOURCE_URL,
        rows=rows,
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )


def test_notification_events_classify_requerimiento_kind() -> None:
    snapshot = _notifications_snapshot(
        (
            _notification(
                certificado_id="2596230606502",
                concepto="Requerimiento de documentación relativa al IVA",
                tipo="notificacion",
                leida=False,
            ),
        ),
    )

    events = calendar_events_from_notification_snapshots((snapshot,), _RANGE, as_of=_AS_OF)

    assert len(events) == 1
    assert events[0].post_filing_kind is PostFilingEventKind.REQUERIMIENTO


def test_notification_events_classify_informational_comunicacion_kind() -> None:
    snapshot = _notifications_snapshot(
        (
            _notification(
                certificado_id="2596230606503",
                concepto="Comunicación informativa del estado de su expediente",
                tipo="comunicacion",
                leida=True,
            ),
        ),
    )

    events = calendar_events_from_notification_snapshots((snapshot,), _RANGE, as_of=_AS_OF)

    assert len(events) == 1
    assert events[0].post_filing_kind is PostFilingEventKind.COMUNICACION


def test_expediente_filing_event_carries_declaracion_presentada_kind() -> None:
    snapshot = PersistedExpedientesSnapshot(
        snapshot_id="e" * 64,
        bucket_id=BUCKET_ID,
        captured_at=datetime(2025, 3, 16, 10, 0, tzinfo=UTC),
        source_url=SOURCE_URL,
        authenticated_identity="B12345678",
        declarations=(
            Declaracion(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "1T"),
                expediente_id="12345678901234567890",
                estado="ALTA",
                presented_at=datetime(2025, 3, 15, 9, 30, tzinfo=UTC),
            ),
        ),
        persisted_at=datetime(2025, 3, 16, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_expedientes_snapshots((snapshot,), _RANGE)

    assert len(events) == 1
    assert events[0].post_filing_kind is PostFilingEventKind.DECLARACION_PRESENTADA


def test_actionable_filter_selects_only_demand_and_enforcement_events() -> None:
    snapshot = _notifications_snapshot(
        (
            _notification(
                certificado_id="2596230606502",
                concepto="Requerimiento de documentación relativa al IVA",
                tipo="notificacion",
                leida=False,
            ),
            _notification(
                certificado_id="2596230606504",
                concepto="Diligencia de embargo de cuentas",
                tipo="notificacion",
                leida=False,
            ),
            _notification(
                certificado_id="2596230606503",
                concepto="Comunicación informativa del estado de su expediente",
                tipo="comunicacion",
                leida=True,
            ),
        ),
    )

    events = calendar_events_from_notification_snapshots((snapshot,), _RANGE, as_of=_AS_OF)
    actionable = actionable_post_filing_events(events)

    assert {event.post_filing_kind for event in actionable} == {
        PostFilingEventKind.REQUERIMIENTO,
        PostFilingEventKind.DILIGENCIA_EMBARGO,
    }
    assert {event.reference_id for event in actionable} == {"2596230606502", "2596230606504"}


def test_actionable_filter_is_empty_when_no_demand_events_present() -> None:
    snapshot = _notifications_snapshot(
        (
            _notification(
                certificado_id="2596230606503",
                concepto="Comunicación informativa",
                tipo="comunicacion",
                leida=True,
            ),
        ),
    )

    events = calendar_events_from_notification_snapshots((snapshot,), _RANGE, as_of=_AS_OF)

    assert actionable_post_filing_events(events) == ()
