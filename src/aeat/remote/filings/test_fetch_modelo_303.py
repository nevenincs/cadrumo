"""Unit tests for :mod:`aeat.remote.filings._fetch_modelo_303`.

Covers the Tier-1 VAT return projection: happy path, unknown-status
fallback, and complementaria linkage. All collaborators are real
Protocol-conforming Python classes; no mocks or patches are used.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest

from ...formulas import FiscalPeriod, Quarter
from .._schema import RemoteFiling
from .._status import RemoteFilingStatus
from ._fetch_modelo_303 import fetch, project_filing_detail_303
from ._filing_detail_303 import FilingDetail303
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
    """Happy-path Modelo 303: all six tracked casillas land in typed fields."""
    expediente = make_expediente(
        modelo="303",
        period="2025-1T",
        expediente_id="2025X1234567L0303A",
        status="Presentada",
        presented_at=utc(2025, 4, 20, 9, 0),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_303_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    detail = project_filing_detail_303(remote)
    assert isinstance(detail, FilingDetail303)
    assert detail.filing.status is RemoteFilingStatus.PRESENTADA
    assert detail.total_devengado == Decimal("4200.00")
    assert detail.total_deducir == Decimal("3150.00")
    assert detail.diferencia == Decimal("1050.00")
    assert detail.resultado_liquidacion == Decimal("1050.00")
    assert detail.a_ingresar == Decimal("1050.00")
    assert detail.a_devolver == Decimal("0.00")


@pytest.mark.asyncio
async def test_unknown_status_folds_to_unknown_and_logs_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An AEAT status the enum does not model folds to UNKNOWN with a warn log."""
    expediente = make_expediente(
        modelo="303",
        period="2025-2T",
        expediente_id="2025X1234567L0303B",
        status="Revision pendiente",
        presented_at=utc(2025, 7, 21, 8, 45),
    )
    with caplog.at_level(logging.WARNING, logger="aeat.remote._status"):
        _, remote = await parse_fixture_to_remote_filing(
            fixture_name="modelo_303_unknown_status.html",
            expediente=expediente,
            tmp_path=tmp_path,
        )
    detail = project_filing_detail_303(remote)
    assert detail.filing.status is RemoteFilingStatus.UNKNOWN
    assert detail.filing.raw_status == "Revision pendiente"
    # Warning preserves the raw string and surfaces modelo/period for triage.
    matching = [rec for rec in caplog.records if "Revision pendiente" in rec.getMessage()]
    assert matching, "expected a warning log for the unknown status"
    message = matching[0].getMessage()
    assert "modelo=303" in message
    assert "period=2025-2T" in message


@pytest.mark.asyncio
async def test_complementaria_links_back_to_prior_expediente(tmp_path: Path) -> None:
    """A complementaria filing preserves the ``complementaria_of`` linkage."""
    expediente = make_expediente(
        modelo="303",
        period="2025-1T",
        expediente_id="2025X1234567L0303C",
        status="Complementaria",
        presented_at=utc(2025, 5, 5, 14, 22),
    )
    _, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_303_complementaria.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    detail = project_filing_detail_303(remote)
    assert detail.filing.status is RemoteFilingStatus.COMPLEMENTARIA
    assert detail.filing.complementaria_of == "2025X1234567L0001"
    # The amended numbers still project into the typed fields.
    assert detail.total_devengado == Decimal("4350.00")
    assert detail.a_ingresar == Decimal("150.00")


@pytest.mark.asyncio
async def test_fetch_returns_tuple_ordered_by_fetcher(tmp_path: Path) -> None:
    """``fetch`` projects every RemoteFiling returned by the fetcher in order."""
    expediente = make_expediente(
        modelo="303",
        period="2025-1T",
        expediente_id="2025X1234567L0303A",
        status="Presentada",
        presented_at=utc(2025, 4, 20, 9, 0),
    )
    _, happy = await parse_fixture_to_remote_filing(
        fixture_name="modelo_303_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    complementaria_expediente = make_expediente(
        modelo="303",
        period="2025-1T",
        expediente_id="2025X1234567L0303C",
        status="Complementaria",
        presented_at=utc(2025, 5, 5, 14, 22),
    )
    _, comp = await parse_fixture_to_remote_filing(
        fixture_name="modelo_303_complementaria.html",
        expediente=complementaria_expediente,
        tmp_path=tmp_path,
    )
    fetcher = _StaticFetcher(payload=(happy, comp))

    result = await fetch(fetcher, period=FiscalPeriod(year=2025, quarter=Quarter.Q1))

    assert fetcher.calls == [("303", "2025-1T", True)]
    assert [d.filing.expediente_id for d in result] == [
        "2025X1234567L0303A",
        "2025X1234567L0303C",
    ]


@pytest.mark.asyncio
async def test_fetch_empty_result_returns_empty_tuple() -> None:
    """An empty AEAT result produces an empty tuple — the NOT_YET_FOUND signal."""
    fetcher = _StaticFetcher(payload=())
    result = await fetch(fetcher, period=FiscalPeriod(year=2025, quarter=Quarter.Q4))
    assert result == ()
    assert fetcher.calls == [("303", "2025-4T", True)]
