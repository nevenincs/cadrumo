"""Unit tests for :mod:`aeat.remote.filings._fetch_modelo_130`.

Every test runs entirely offline against synthetic HTML fixtures under
``tests/fixtures/remote_filings/``. Collaborators are real Protocol-
conforming Python classes; no ``unittest.mock`` / ``patch`` /
``Mock`` is ever used.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...formulas import FiscalPeriod, Quarter
from .._schema import RemoteFiling
from .._status import RemoteFilingStatus
from ._fetch_modelo_130 import fetch, project_filing_detail_130
from ._filing_detail_130 import FilingDetail130
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
    """Happy-path Modelo 130: every tracked casilla is populated."""
    expediente = make_expediente(
        modelo="130",
        period="2025-1T",
        expediente_id="2025X1234567L0130A",
        status="Presentada",
        presented_at=utc(2025, 4, 18, 11, 30),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_130_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    detail = project_filing_detail_130(remote)
    assert isinstance(detail, FilingDetail130)
    assert detail.filing.modelo == "130"
    assert detail.filing.period == "2025-1T"
    assert detail.filing.status is RemoteFilingStatus.PRESENTADA
    assert detail.ingresos_computables == Decimal("12500.00")
    assert detail.gastos_deducibles == Decimal("4250.00")
    assert detail.rendimiento_neto == Decimal("8250.00")
    assert detail.pagos_fraccionados_anteriores == Decimal("0.00")
    assert detail.retenciones_soportadas == Decimal("500.00")
    assert detail.resultado == Decimal("1145.00")


@pytest.mark.asyncio
async def test_project_missing_casilla_falls_back_to_zero(tmp_path: Path) -> None:
    """Missing casillas default to Decimal('0') without raising."""
    expediente = make_expediente(
        modelo="130",
        period="2025-2T",
        expediente_id="2025X1234567L0130B",
        status="En tramitacion",
        presented_at=utc(2025, 7, 19, 10, 15),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_130_missing_casilla.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    detail = project_filing_detail_130(remote)
    # Casilla 02 and 06 are absent from the fixture table.
    assert detail.gastos_deducibles == Decimal("0")
    assert detail.pagos_fraccionados_anteriores == Decimal("0")
    # Populated casillas round-trip unchanged.
    assert detail.ingresos_computables == Decimal("9000.00")
    assert detail.rendimiento_neto == Decimal("9000.00")
    assert detail.retenciones_soportadas == Decimal("250.00")
    assert detail.resultado == Decimal("1100.00")
    # Status string is a known Spanish label, accent-tolerant.
    assert detail.filing.status is RemoteFilingStatus.EN_TRAMITACION


@pytest.mark.asyncio
async def test_fetch_formats_period_and_passes_through_use_cache(tmp_path: Path) -> None:
    """``fetch`` converts the FiscalPeriod to AEAT's wire string and forwards flags."""
    expediente = make_expediente(
        modelo="130",
        period="2025-1T",
        expediente_id="2025X1234567L0130A",
        status="Presentada",
        presented_at=utc(2025, 4, 18, 11, 30),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_130_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    fetcher = _StaticFetcher(payload=(remote,))

    result = await fetch(
        fetcher,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q1),
        use_cache=False,
    )

    assert len(result) == 1
    assert isinstance(result[0], FilingDetail130)
    assert fetcher.calls == [("130", "2025-1T", False)]


@pytest.mark.asyncio
async def test_fetch_empty_result_returns_empty_tuple() -> None:
    """An empty AEAT result produces an empty tuple — the NOT_YET_FOUND signal."""
    fetcher = _StaticFetcher(payload=())
    result = await fetch(fetcher, period=FiscalPeriod(year=2025, quarter=Quarter.Q3))
    assert result == ()
    assert fetcher.calls == [("130", "2025-3T", True)]
