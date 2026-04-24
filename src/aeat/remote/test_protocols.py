"""Unit tests for :mod:`aeat.remote._protocols`.

Protocol conformance is asserted against Protocol-conforming Python
classes declared inline in the tests — never ``unittest.mock`` — per
the project mandate against mocks/stubs in protocol-shape tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ..schema import CasillaDataType
from ._protocols import NotificationReader, RemoteFilingFetcher
from ._schema import RemoteCasilla, RemoteFiling, RemoteNotification
from ._status import RemoteFilingStatus

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def _make_filing() -> RemoteFiling:
    return RemoteFiling(
        modelo="303",
        period="2025-1T",
        expediente_id="EXP-001",
        status=RemoteFilingStatus.PRESENTADA,
        raw_status="Presentada",
        submitted_at=datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
        casillas=(
            RemoteCasilla(
                casilla_id="46",
                raw_value="1234.56",
                data_type=CasillaDataType.CURRENCY_EUR,
                coerced_value=Decimal("1234.56"),
            ),
        ),
    )


class _InMemoryFilingFetcher:
    """Protocol-conforming fetcher used only by the Protocol tests."""

    def __init__(self, filings: tuple[RemoteFiling, ...]) -> None:
        self._filings = filings
        self.calls: list[tuple[str, str, bool]] = []

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[RemoteFiling, ...]:
        self.calls.append((modelo, period, use_cache))
        return self._filings


class _InMemoryNotificationReader:
    """Protocol-conforming reader used only by the Protocol tests."""

    def __init__(self, notifications: tuple[RemoteNotification, ...]) -> None:
        self._notifications = notifications

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
        use_cache: bool = True,
    ) -> tuple[RemoteNotification, ...]:
        del since, use_cache
        return self._notifications


def test_in_memory_fetcher_satisfies_remote_filing_fetcher() -> None:
    fetcher = _InMemoryFilingFetcher(filings=(_make_filing(),))
    assert isinstance(fetcher, RemoteFilingFetcher)


def test_in_memory_reader_satisfies_notification_reader() -> None:
    reader = _InMemoryNotificationReader(notifications=())
    assert isinstance(reader, NotificationReader)


def test_unrelated_object_does_not_satisfy_remote_filing_fetcher() -> None:
    class _NoOp:
        pass

    assert not isinstance(_NoOp(), RemoteFilingFetcher)


@pytest.mark.asyncio
async def test_in_memory_fetcher_returns_typed_filings() -> None:
    expected = _make_filing()
    fetcher = _InMemoryFilingFetcher(filings=(expected,))
    result = await fetcher.fetch_filing_detail("303", "2025-1T", use_cache=False)
    assert result == (expected,)
    assert fetcher.calls == [("303", "2025-1T", False)]


@pytest.mark.asyncio
async def test_in_memory_reader_returns_typed_notifications() -> None:
    notification = RemoteNotification(
        notification_id="NOT-1",
        subject="Requerimiento",
        issued_at=datetime(2025, 4, 21, 8, 0, tzinfo=UTC),
    )
    reader = _InMemoryNotificationReader(notifications=(notification,))
    result = await reader.fetch_notificaciones(since=None)
    assert result == (notification,)
