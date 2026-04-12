"""Unit tests for :func:`aeat.inbox.next_appeal_deadline`."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import AnyHttpUrl

from aeat.inbox import (
    Inbox,
    Notificacion,
    NotificacionKind,
    NotificacionPriority,
    next_appeal_deadline,
)


def _make(
    nid: str,
    *,
    priority: NotificacionPriority,
    deadline: date | None,
    acked: bool = False,
) -> Notificacion:
    received = datetime(2026, 3, 15, tzinfo=UTC)
    return Notificacion(
        notificacion_id=nid,
        kind=NotificacionKind.REQUERIMIENTO if deadline else NotificacionKind.COMUNICACION_GENERAL,
        priority=priority,
        subject={"es": "Requerimiento", "en": "Request", "hu": "Kérelem"},
        body_excerpt={"es": "...", "en": "...", "hu": "..."},
        received_at=received,
        effective_at=received,
        appeal_deadline=deadline,
        source_url=AnyHttpUrl(f"https://sede.agenciatributaria.gob.es/{nid}"),
        acknowledged_at=datetime(2026, 4, 1, tzinfo=UTC) if acked else None,
        acknowledged_by="gw" if acked else None,
    )


def _inbox(*records: Notificacion) -> Inbox:
    return Inbox(entries={r.notificacion_id: r for r in records})


TODAY = date(2026, 4, 10)


@pytest.mark.unit
class TestNextAppealDeadline:
    def test_empty_inbox(self) -> None:
        assert next_appeal_deadline(_inbox(), today=TODAY) is None

    def test_picks_earliest_critical(self) -> None:
        a = _make("A", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 20))
        b = _make("B", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 15))
        result = next_appeal_deadline(_inbox(a, b), today=TODAY)
        assert result is not None
        assert result.notificacion_id == "B"

    def test_ignores_acknowledged(self) -> None:
        a = _make("A", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 15), acked=True)
        b = _make("B", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 20))
        result = next_appeal_deadline(_inbox(a, b), today=TODAY)
        assert result is not None
        assert result.notificacion_id == "B"

    def test_ignores_past(self) -> None:
        a = _make("A", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 1))
        b = _make("B", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 15))
        result = next_appeal_deadline(_inbox(a, b), today=TODAY)
        assert result is not None
        assert result.notificacion_id == "B"

    def test_ignores_normal_and_info(self) -> None:
        a = _make("A", priority=NotificacionPriority.NORMAL, deadline=date(2026, 4, 12))
        b = _make("B", priority=NotificacionPriority.INFO, deadline=date(2026, 4, 13))
        assert next_appeal_deadline(_inbox(a, b), today=TODAY) is None

    def test_includes_high(self) -> None:
        a = _make("A", priority=NotificacionPriority.HIGH, deadline=date(2026, 4, 15))
        result = next_appeal_deadline(_inbox(a), today=TODAY)
        assert result is not None
        assert result.notificacion_id == "A"

    def test_lead_window(self) -> None:
        a = _make("A", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 15))
        b = _make("B", priority=NotificacionPriority.CRITICAL, deadline=date(2026, 4, 25))
        # Lead window = 7 days → 4/15 is in, 4/25 is out.
        result = next_appeal_deadline(_inbox(a, b), today=TODAY, lead_days=7)
        assert result is not None
        assert result.notificacion_id == "A"
        # Lead window = 2 days → nothing qualifies.
        assert next_appeal_deadline(_inbox(a, b), today=TODAY, lead_days=2) is None
