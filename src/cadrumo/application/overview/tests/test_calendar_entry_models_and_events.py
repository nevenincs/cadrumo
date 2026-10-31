"""Overview calendar entry, range and period-state models, and the filing events projected from expedientes and notifications."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.deadlines.models import (
    ObligationStatus,
)
from ...live.expedientes import PersistedExpedientesSnapshot
from ...live.expedientes_ports import ExpedientesDeclaration
from ...live.notification_ports import RemoteNotification
from ...live.notifications import PersistedNotificationsSnapshot
from ..calendar_events import (
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_notification_snapshots,
)
from ..calendar_models import (
    OverviewCalendarEventType,
    OverviewCalendarRange,
    OverviewPeriodState,
    user_state_for,
)
from .calendar_support import _entry
from .calendar_test_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .calendar_test_support import (
    PERIOD_2025_1T as _PERIOD_2025_1T,
)
from .calendar_test_support import (
    SOURCE_URL as _SOURCE_URL,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------
# OverviewPeriodState mapping
# ---------------------------------------------------------------------


def test_period_state_enum_carries_cli_values() -> None:
    assert {item.value for item in OverviewPeriodState} == {
        "due",
        "late",
        "filed",
        "unknown",
    }


_USER_STATE_CASES: tuple[tuple[ObligationStatus, OverviewPeriodState], ...] = (
    (ObligationStatus.UPCOMING, OverviewPeriodState.DUE),
    (ObligationStatus.DUE_SOON, OverviewPeriodState.DUE),
    (ObligationStatus.DUE_TODAY, OverviewPeriodState.DUE),
    (ObligationStatus.OVERDUE, OverviewPeriodState.LATE),
    (ObligationStatus.FILED, OverviewPeriodState.FILED),
    (ObligationStatus.NOT_APPLICABLE, OverviewPeriodState.UNKNOWN),
)


@pytest.mark.parametrize(
    ("engine_status", "expected_user_state"),
    _USER_STATE_CASES,
    ids=("upcoming", "due-soon", "due-today", "overdue", "filed", "not-applicable"),
)
def test_user_state_maps_engine_status_to_cli_state(
    engine_status: ObligationStatus,
    expected_user_state: OverviewPeriodState,
) -> None:
    assert user_state_for(engine_status) is expected_user_state


def test_user_state_covers_every_engine_status() -> None:
    """Every ObligationStatus must map to a user state."""
    for status in ObligationStatus:
        assert isinstance(user_state_for(status), OverviewPeriodState)


# ---------------------------------------------------------------------
# OverviewCalendarRange
# ---------------------------------------------------------------------


def test_range_round_trips_canonical_window() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.from_date == date(2026, 1, 1)
    assert rng.to_date == date(2026, 4, 20)


def test_range_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match=r"from_date|to_date|window|range"):
        OverviewCalendarRange(from_date=date(2026, 4, 20), to_date=date(2026, 1, 1))


def test_range_accepts_single_day_window() -> None:
    # covered_years always includes the prior fiscal year so that annual
    # declarations (IS Modelo 200, IRPF Modelo 100) whose deadlines fall in
    # the following calendar year appear when querying that year.
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 1, 1))
    assert rng.covered_years() == (2025, 2026)


def test_range_covered_years_spans_year_boundary() -> None:
    rng = OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20))
    assert rng.covered_years() == (2024, 2025, 2026)


_RANGE_COVERAGE_CASES: tuple[tuple[date, bool], ...] = (
    (date(2026, 1, 1), True),
    (date(2026, 4, 20), True),
    (date(2026, 3, 15), True),
    (date(2025, 12, 31), False),
    (date(2026, 4, 21), False),
)


@pytest.mark.parametrize(
    ("probe", "expected"),
    _RANGE_COVERAGE_CASES,
    ids=("from-bound", "to-bound", "inside", "before", "after"),
)
def test_range_covers_returns_expected_inclusive_boundary_result(probe: date, expected: bool) -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.covers(probe) is expected


def test_range_is_frozen() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        rng.from_date = date(2025, 12, 31)


def test_entry_round_trips_canonical_fields() -> None:
    entry = _entry()
    assert entry.modelo == "130"
    assert entry.period == Period.from_year_and_code(2026, "1T")
    assert str(entry.period) == "2026 1T"
    assert entry.user_state is OverviewPeriodState.DUE


def test_entry_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match=r"opens_on|closes_on|window"):
        _entry(opens_on=date(2026, 4, 21), closes_on=date(2026, 4, 20))


def test_entry_rejects_payment_cutoff_after_closes_on() -> None:
    with pytest.raises(ValueError, match=r"payment_cutoff|closes_on"):
        _entry(payment_cutoff_on=date(2026, 4, 25))


def test_entry_rejects_user_state_inconsistent_with_engine_status() -> None:
    with pytest.raises(ValueError, match=r"user_state|status|inconsistent"):
        _entry(status=ObligationStatus.OVERDUE, user_state=OverviewPeriodState.DUE)


def test_entry_is_frozen() -> None:
    entry = _entry()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        entry.modelo = "303"


# ---------------------------------------------------------------------
# OverviewCalendarEvent
# ---------------------------------------------------------------------


def _expedientes_snapshot(authenticated_identity: str) -> PersistedExpedientesSnapshot:
    return PersistedExpedientesSnapshot(
        snapshot_id="e" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity=authenticated_identity,
        declarations=(
            ExpedientesDeclaration(
                modelo="303",
                ejercicio=2025,
                period=_PERIOD_2025_1T,
                expediente_id="12345678901234567890",
                estado="ALTA",
                presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
            ),
        ),
        persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
    )


def test_expedientes_snapshots_project_filing_events_inside_range() -> None:
    snapshot = _expedientes_snapshot("X1234567L")

    events = calendar_events_from_expedientes_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type is OverviewCalendarEventType.FILING
    assert event.event_date == date(2025, 4, 15)
    assert event.modelo == "303"
    assert event.filing_year == 2025
    assert event.period == Period.from_year_and_code(2025, "1T")
    assert event.reference_id == "12345678901234567890"
    assert event.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert event.authenticated_identity == "X1234567L"


def test_expedientes_snapshot_for_wrong_identity_does_not_project_filing_event() -> None:
    snapshot = _expedientes_snapshot("Y7654321G")

    events = calendar_events_from_expedientes_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        expected_tax_id="X1234567L",
    )

    assert events == ()


def test_notification_snapshots_project_message_events_on_notification_date() -> None:
    row = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=_SOURCE_URL,
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        rows=(row,),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 13),
    )

    assert len(events) == 1
    assert events[0].event_type is OverviewCalendarEventType.MESSAGE
    assert events[0].event_date == date(2025, 3, 12)
    assert events[0].reference_id == "2596230606502"
    assert events[0].status == "unread"
    assert events[0].modelo is None
    assert events[0].filing_year is None
    assert events[0].period is None
    assert events[0].aeat_submission_state is None
    assert events[0].aeat_submitted_at is None
    assert events[0].justificante_verified is None
    assert events[0].verified_justificante_csv is None


def test_notification_filing_like_text_stays_unlinked_and_replay_is_idempotent() -> None:
    """A message cannot become filing evidence through suggestive metadata."""
    row = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Modelo 303 1T 2025 pagado con justificante",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 4, 20),
        fecha_notificacion=date(2025, 4, 21),
        modo_notificacion="DEHú",
        leida=True,
        source_url=_SOURCE_URL,
    )
    first = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 4, 21, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="B12345674",
        rows=(row,),
        persisted_at=datetime(2025, 4, 21, 10, 5, tzinfo=UTC),
    )
    replay = first.model_copy(
        update={
            "snapshot_id": "b" * 64,
            "captured_at": datetime(2025, 4, 22, 10, 0, tzinfo=UTC),
            "persisted_at": datetime(2025, 4, 22, 10, 5, tzinfo=UTC),
        }
    )

    events = calendar_events_from_notification_snapshots(
        (first, replay),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        as_of=date(2025, 4, 22),
        expected_tax_id="B12345674",
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type is OverviewCalendarEventType.MESSAGE
    assert event.reference_id == row.certificado_id
    assert event.modelo is None
    assert event.filing_year is None
    assert event.period is None
    assert event.aeat_submission_state is None
    assert event.aeat_submitted_at is None
    assert event.justificante_verified is None
    assert event.verified_justificante_csv is None


def test_notification_snapshots_filter_message_events_by_expected_taxpayer() -> None:
    matching = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=_SOURCE_URL,
    )
    other_taxpayer = RemoteNotification(
        certificado_id="2699101808461",
        tipo="comunicacion",
        concepto="Comunicacion de otro contribuyente",
        titular_nif="C12345674",
        titular_nombre="Other S.L.",
        destinatario_nif="C12345674",
        destinatario_nombre="Other S.L.",
        fecha_emision=date(2025, 3, 11),
        fecha_notificacion=None,
        modo_notificacion="DEHú",
        leida=True,
        source_url=_SOURCE_URL,
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        rows=(matching, other_taxpayer),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 13),
        expected_tax_id="B12345674",
    )

    assert tuple(event.reference_id for event in events) == ("2596230606502",)


def test_notification_snapshots_filter_message_events_by_authenticated_snapshot_identity() -> None:
    matching = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=_SOURCE_URL,
    )
    explicit_other_taxpayer = RemoteNotification(
        certificado_id="2699101808461",
        tipo="comunicacion",
        concepto="Comunicacion de otro contribuyente",
        titular_nif="C12345674",
        titular_nombre="Other S.L.",
        destinatario_nif="C12345674",
        destinatario_nombre="Other S.L.",
        fecha_emision=date(2025, 3, 11),
        fecha_notificacion=None,
        modo_notificacion="DEHú",
        leida=True,
        source_url=_SOURCE_URL,
    )
    matching_snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="B12345674",
        rows=(matching, explicit_other_taxpayer),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )
    other_snapshot = PersistedNotificationsSnapshot(
        snapshot_id="b" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 14, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="C12345674",
        rows=(matching,),
        persisted_at=datetime(2025, 3, 14, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (matching_snapshot, other_snapshot),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 13),
        expected_tax_id="B12345674",
    )

    assert tuple(event.reference_id for event in events) == ("2596230606502",)
