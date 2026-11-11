"""Canonical ownership checks for overview calendar DTOs."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from ...live.notification_ports import RemoteNotification
from ...live.notifications import PersistedNotificationsSnapshot
from .. import calendar_models
from ..calendar_events import calendar_events_from_notification_snapshots
from ..calendar_models import OverviewCalendarEvent, OverviewCalendarRange

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def test_calendar_event_projection_materialises_models_from_their_canonical_owner() -> None:
    """The real persisted-notification projection materialises the canonical event DTO."""
    source_url = SEDE_ROOT_URL_FIXTURE
    notification = RemoteNotification(
        certificado_id="2596230606601",
        tipo="notificacion",
        concepto="Notificacion de prueba",
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(_YEAR, 3, 10),
        fecha_notificacion=date(_YEAR, 3, 12),
        modo_notificacion="DEH",
        leida=False,
        source_url=source_url,
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="b" * 64,
        bucket_id="7390a6bb-5577-4e08-8518-16e6292f690f",
        captured_at=datetime(_YEAR, 3, 13, 10, 0, tzinfo=UTC),
        source_url=source_url,
        rows=(notification,),
        persisted_at=datetime(_YEAR, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(_YEAR, 3, 1), to_date=date(_YEAR, 3, 31)),
        as_of=date(_YEAR, 3, 22),
        expected_tax_id="B12345678",
    )

    assert len(events) == 1
    assert type(events[0]) is calendar_models.OverviewCalendarEvent
    assert isinstance(events[0], OverviewCalendarEvent)
