"""Unit tests for :mod:`aeat.remote.filings._adapters`."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._schema import RemoteFiling
from .._status import RemoteFilingStatus
from ._adapters import _coerce_currency, remote_casilla_from_raw
from ._fixture_helpers import make_expediente, parse_fixture_to_remote_filing, utc

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_coerce_currency_handles_spanish_number_format() -> None:
    """Thousand dots and decimal commas round-trip to :class:`Decimal`."""
    assert _coerce_currency("1.050,00") == Decimal("1050.00")
    assert _coerce_currency("80.000,00") == Decimal("80000.00")
    assert _coerce_currency("0,00") == Decimal("0.00")


def test_coerce_currency_returns_none_for_blank() -> None:
    """Blank raw values coerce to ``None`` rather than raising."""
    assert _coerce_currency("") is None
    assert _coerce_currency("   ") is None


def test_remote_casilla_from_raw_preserves_raw_value() -> None:
    """The raw Spanish string is preserved verbatim alongside the coerced value."""
    casilla = remote_casilla_from_raw("46", "1.050,00")
    assert casilla.casilla_id == "46"
    assert casilla.raw_value == "1.050,00"
    assert casilla.coerced_value == Decimal("1050.00")


def test_remote_casilla_from_raw_handles_blank_value() -> None:
    """Blank raw values produce a :class:`RemoteCasilla` with ``coerced_value=None``."""
    casilla = remote_casilla_from_raw("99", "")
    assert casilla.raw_value == ""
    assert casilla.coerced_value is None


@pytest.mark.asyncio
async def test_remote_filing_from_history_sorts_casillas_by_id(tmp_path: Path) -> None:
    """Casillas are ordered by identifier for deterministic repeat fetches."""
    expediente = make_expediente(
        modelo="303",
        period="2025-1T",
        expediente_id="2025X1234567L0303A",
        status="Presentada",
        presented_at=utc(2025, 4, 20, 9, 0),
    )
    filed, remote = await parse_fixture_to_remote_filing(
        fixture_name="modelo_303_happy.html",
        expediente=expediente,
        tmp_path=tmp_path,
    )
    assert isinstance(remote, RemoteFiling)
    ids = [c.casilla_id for c in remote.casillas]
    assert ids == sorted(ids)
    # Every casilla from the fixture survives the projection.
    assert set(ids) == set(filed.calculations.casillas)


@pytest.mark.asyncio
async def test_remote_filing_from_history_classifies_status(tmp_path: Path) -> None:
    """Status strings fold through :func:`classify_status`."""
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
    assert remote.status is RemoteFilingStatus.EN_TRAMITACION
    assert remote.raw_status == "En tramitacion"
