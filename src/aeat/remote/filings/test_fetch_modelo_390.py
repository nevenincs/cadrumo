"""Unit tests for :mod:`aeat.remote.filings._fetch_modelo_390`.

Covers the Tier-1 annual VAT summary projection. The fixture
represents a full-year exercise; ``FiscalPeriod`` is constructed
without a quarter so the period formatter emits the bare year.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...formulas import FiscalPeriod
from .._schema import RemoteFiling
from .._status import RemoteFilingStatus
from ._fetch_modelo_390 import fetch, project_filing_detail_390
from ._filing_detail_390 import FilingDetail390
from ._fixture_helpers import make_expediente, parse_fixture_to_remote_filing, utc

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


class _StaticFetcher:
    """Protocol-conforming ``RemoteFilingFetcher`` returning a static payload."""

    def __init__(self, payload: tuple[RemoteFiling, ...]) -> None:
        self._payload = payload
        self.calls: list[tuple[str, str, bool]] = []

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[RemoteFiling, ...]:
        self.calls.append((modelo, period, use_cache))
        return self._payload


@pytest.mark.asyncio
async def test_project_happy_path_extracts_every_tracked_casilla(tmp_path: Path) -> None:
    """Happy-path Modelo 390: every tracked casilla lands in typed fields."""
    expediente = make_expediente(
        modelo="390",
        period="2024",
        expediente_id="2024X1234567L0390A",
        status="Presentada",
        presented_at=utc(2025, 1, 28, 17, 40),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_390_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    detail = project_filing_detail_390(remote)
    assert isinstance(detail, FilingDetail390)
    assert detail.filing.status is RemoteFilingStatus.PRESENTADA
    assert detail.filing.period == "2024"
    assert detail.total_bases_devengado == Decimal("80000.00")
    assert detail.total_cuotas_devengadas == Decimal("16800.00")
    assert detail.total_cuotas_deducibles == Decimal("12400.00")
    assert detail.resultado_liquidacion_anual == Decimal("4400.00")
    assert detail.volumen_operaciones == Decimal("82000.00")


@pytest.mark.asyncio
async def test_fetch_annual_period_emits_bare_year(tmp_path: Path) -> None:
    """Annual FiscalPeriod renders as the bare year on the wire."""
    expediente = make_expediente(
        modelo="390",
        period="2024",
        expediente_id="2024X1234567L0390A",
        status="Presentada",
        presented_at=utc(2025, 1, 28, 17, 40),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_390_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    fetcher = _StaticFetcher(payload=(remote,))

    result = await fetch(fetcher, period=FiscalPeriod(year=2024))

    assert fetcher.calls == [("390", "2024", True)]
    assert len(result) == 1
    assert isinstance(result[0], FilingDetail390)


@pytest.mark.asyncio
async def test_fetch_empty_result_returns_empty_tuple() -> None:
    """An empty AEAT result produces an empty tuple — the NOT_YET_FOUND signal."""
    fetcher = _StaticFetcher(payload=())
    result = await fetch(fetcher, period=FiscalPeriod(year=2023))
    assert result == ()
    assert fetcher.calls == [("390", "2023", True)]
