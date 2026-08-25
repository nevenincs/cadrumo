"""Canonical ownership checks for overview calendar DTOs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from importlib import import_module

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import RemoteNotification
from ....tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from ...live.notifications import PersistedNotificationsSnapshot
from .. import OverviewCalendarEvent, OverviewCalendarRange, calendar_events_from_notification_snapshots
from .. import _calendar_models as _calendar_models

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLIC_CALENDAR_MODEL_NAMES = frozenset(
    {
        "CalendarCompleteness",
        "CalendarWarning",
        "OverviewAeatSubmissionState",
        "OverviewCalendar",
        "OverviewCalendarEntry",
        "OverviewCalendarEvent",
        "OverviewCalendarEventType",
        "OverviewCalendarFilingEvidence",
        "OverviewCalendarRange",
        "OverviewCensoEnrolmentState",
        "OverviewLocalFilingState",
        "OverviewPeriodState",
        "OverviewStatusReport",
        "SuppressedCalendarEntry",
        "user_state_for",
    },
)


def test_calendar_dtos_are_publicly_owned_by_models_not_builder_module() -> None:
    """The public DTO surface resolves directly to its defining module."""
    overview = import_module("cadrumo.application.overview")
    calendar_builder = import_module("cadrumo.application.overview._calendar")

    assert set(overview.__all__) >= _PUBLIC_CALENDAR_MODEL_NAMES
    assert set(_calendar_models.__all__) >= _PUBLIC_CALENDAR_MODEL_NAMES
    assert all(getattr(overview, name) is getattr(_calendar_models, name) for name in _PUBLIC_CALENDAR_MODEL_NAMES)
    assert _PUBLIC_CALENDAR_MODEL_NAMES.isdisjoint(vars(calendar_builder))


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
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEH",
        leida=False,
        source_url=AnyHttpUrl(source_url),
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="b" * 64,
        bucket_id="7390a6bb-5577-4e08-8518-16e6292f690f",
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=source_url,
        rows=(notification,),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 22),
        expected_tax_id="B12345678",
    )

    assert len(events) == 1
    assert type(events[0]) is _calendar_models.OverviewCalendarEvent
    assert isinstance(events[0], OverviewCalendarEvent)
