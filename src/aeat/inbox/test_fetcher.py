"""Unit tests for :class:`aeat.inbox.InboxFetcher`.

The upstream :class:`NotificacionSource` is exercised with a **real**
Python class that structurally conforms to the Protocol — no mocks,
no patches, no fakes. See the CLAUDE.md mandate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from . import (
    InboxAcknowledgeError,
    InboxFetcher,
    NotificacionKind,
    NotificacionPriority,
    RawNotificacion,
)


class _InMemorySource:
    """Real concrete :class:`NotificacionSource` backed by a list.

    Not a mock — a plain Python class that structurally satisfies the
    :class:`aeat.inbox.NotificacionSource` Protocol.
    """

    def __init__(self, payloads: tuple[RawNotificacion, ...]) -> None:
        self.payloads = payloads
        self.calls: list[date | None] = []

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
    ) -> tuple[RawNotificacion, ...]:
        self.calls.append(since)
        if since is None:
            return self.payloads
        return tuple(p for p in self.payloads if p.received_at.date() >= since)


def _raw(
    notificacion_id: str,
    subject_es: str,
    *,
    received_at: datetime | None = None,
) -> RawNotificacion:
    ts = received_at or datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    return RawNotificacion(
        notificacion_id=notificacion_id,
        subject={"es": subject_es, "en": subject_es, "hu": subject_es},
        body_excerpt={"es": "...", "en": "...", "hu": "..."},
        received_at=ts,
        effective_at=ts,
        source_url=AnyHttpUrl(f"https://sede.agenciatributaria.gob.es/{notificacion_id}"),
    )


def _fetcher(tmp_path: Path, payloads: tuple[RawNotificacion, ...]) -> InboxFetcher:
    return InboxFetcher(
        source=_InMemorySource(payloads),
        inbox_file=tmp_path / "inbox.json",
        pdf_dir=tmp_path / "pdfs",
    )


@pytest.mark.unit
class TestInboxFetcher:
    @pytest.mark.asyncio
    async def test_fetch_classifies_and_persists(self, tmp_path: Path) -> None:
        payloads = (
            _raw("A", "Requerimiento de información"),
            _raw("B", "Acuerdo de liquidación provisional"),
            _raw("C", "Novedad desconocida inventada"),  # → OTRO/HIGH
        )
        fetcher = _fetcher(tmp_path, payloads)
        added = await fetcher.fetch_new()
        assert {r.notificacion_id for r in added} == {"A", "B", "C"}
        by_id = {r.notificacion_id: r for r in added}
        assert by_id["A"].kind is NotificacionKind.REQUERIMIENTO
        assert by_id["A"].priority is NotificacionPriority.CRITICAL
        assert by_id["A"].appeal_deadline is not None
        assert by_id["B"].kind is NotificacionKind.ACUERDO_LIQUIDACION
        assert by_id["C"].kind is NotificacionKind.OTRO
        assert by_id["C"].priority is NotificacionPriority.HIGH

        # Reload from disk to prove we actually persisted.
        reloaded = fetcher.load_inbox()
        assert set(reloaded.entries.keys()) == {"A", "B", "C"}

    @pytest.mark.asyncio
    async def test_fetch_is_idempotent(self, tmp_path: Path) -> None:
        payloads = (_raw("A", "Requerimiento"),)
        fetcher = _fetcher(tmp_path, payloads)
        first = await fetcher.fetch_new()
        second = await fetcher.fetch_new()
        assert len(first) == 1
        assert second == ()  # already known

    @pytest.mark.asyncio
    async def test_acknowledge_round_trip(self, tmp_path: Path) -> None:
        fetcher = _fetcher(tmp_path, (_raw("A", "Requerimiento"),))
        await fetcher.fetch_new()
        acked = await fetcher.acknowledge("A", by="gw")
        assert acked.acknowledged_by == "gw"
        assert acked.acknowledged_at is not None
        reloaded = fetcher.load_inbox().get("A")
        assert reloaded is not None
        assert reloaded.acknowledged_by == "gw"

    @pytest.mark.asyncio
    async def test_acknowledge_rejects_unknown(self, tmp_path: Path) -> None:
        fetcher = _fetcher(tmp_path, ())
        with pytest.raises(InboxAcknowledgeError):
            await fetcher.acknowledge("missing", by="gw")

    @pytest.mark.asyncio
    async def test_acknowledge_rejects_double(self, tmp_path: Path) -> None:
        fetcher = _fetcher(tmp_path, (_raw("A", "Requerimiento"),))
        await fetcher.fetch_new()
        await fetcher.acknowledge("A", by="gw")
        with pytest.raises(InboxAcknowledgeError):
            await fetcher.acknowledge("A", by="gw")

    @pytest.mark.asyncio
    async def test_acknowledge_rejects_empty_by(self, tmp_path: Path) -> None:
        fetcher = _fetcher(tmp_path, (_raw("A", "Requerimiento"),))
        await fetcher.fetch_new()
        with pytest.raises(InboxAcknowledgeError):
            await fetcher.acknowledge("A", by="")

    @pytest.mark.asyncio
    async def test_fetch_forwards_since(self, tmp_path: Path) -> None:
        payloads = (
            _raw("A", "Requerimiento", received_at=datetime(2026, 3, 1, tzinfo=UTC)),
            _raw("B", "Requerimiento", received_at=datetime(2026, 4, 5, tzinfo=UTC)),
        )
        source = _InMemorySource(payloads)
        fetcher = InboxFetcher(
            source=source,
            inbox_file=tmp_path / "inbox.json",
            pdf_dir=tmp_path / "pdfs",
        )
        added = await fetcher.fetch_new(since=datetime(2026, 4, 1, tzinfo=UTC))
        assert {r.notificacion_id for r in added} == {"B"}
        assert source.calls == [date(2026, 4, 1)]
