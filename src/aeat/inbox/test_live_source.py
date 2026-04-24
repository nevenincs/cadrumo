"""Unit tests for :class:`aeat.inbox.LiveAeatNotificacionSource` (#170)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ..status import Notificacion as StatusNotificacion
from . import LiveAeatNotificacionSource, RawNotificacion

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
_URL: AnyHttpUrl = _URL_ADAPTER.validate_python("https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/NOT-L/Notificacion")


class _StubReader:
    """Real Protocol-conforming double — no mocks, patches, or fakes."""

    def __init__(self, rows: tuple[StatusNotificacion, ...]) -> None:
        self.rows = rows
        self.calls: list[date | None] = []

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
        use_cache: bool = True,
    ) -> tuple[StatusNotificacion, ...]:
        del use_cache
        self.calls.append(since)
        return self.rows


def _status_notificacion(nid: str, received: datetime) -> StatusNotificacion:
    return StatusNotificacion(
        notificacion_id=nid,
        kind="Requerimiento",
        title={"es": "Requerimiento de subsanacion"},
        body_excerpt={"es": "Requerimiento de subsanacion"},
        received_at=received,
        due_at=None,
        source_page_url=_URL,
        fetched_at=received,
    )


@pytest.mark.asyncio
class TestLiveAeatNotificacionSource:
    async def test_translates_rows(self) -> None:
        received = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
        reader = _StubReader(rows=(_status_notificacion("NOT-A", received),))
        source = LiveAeatNotificacionSource(reader)
        raws = await source.fetch_notificaciones(since=None)
        assert len(raws) == 1
        assert isinstance(raws[0], RawNotificacion)
        assert raws[0].notificacion_id == "NOT-A"
        assert raws[0].subject == {"es": "Requerimiento de subsanacion"}
        assert raws[0].received_at == received
        # v1 conservative default: effective_at mirrors received_at.
        assert raws[0].effective_at == received

    async def test_since_passes_through(self) -> None:
        reader = _StubReader(rows=())
        source = LiveAeatNotificacionSource(reader)
        cutoff = date(2026, 4, 1)
        await source.fetch_notificaciones(since=cutoff)
        assert reader.calls == [cutoff]

    async def test_empty_tuple(self) -> None:
        reader = _StubReader(rows=())
        source = LiveAeatNotificacionSource(reader)
        raws = await source.fetch_notificaciones(since=None)
        assert raws == ()
