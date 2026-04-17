"""Unit tests for the modelo-303 detail-page parser."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ...status import Expediente
from .._errors import HistoryParseError
from .modelo_303 import parse_modelo_303_detail

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "aeat-pages" / "filing-history"
_SOURCE_URL = AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/detail/303/0002")
_FETCHED = datetime(2025, 4, 20, 9, 5, 0, tzinfo=UTC)


def _expediente_303() -> Expediente:
    return Expediente(
        expediente_id="2025X1234567L0002",
        modelo="303",
        period="2025-1T",
        status="Presentada",
        presented_at=datetime(2025, 4, 20, 9, 0, 0, tzinfo=UTC),
        csv="ZZZZ9999YYYY0000",
        justificante_url=None,
        source_page_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/mis-expedientes"),
        fetched_at=_FETCHED,
    )


def _load_fixture() -> str:
    return (_FIXTURES / "modelo_303_detail.html").read_text(encoding="utf-8")


class TestParseModelo303Detail:
    def test_extracts_metadata(self) -> None:
        record = parse_modelo_303_detail(
            _load_fixture(),
            expediente=_expediente_303(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.metadata.modelo == "303"
        assert record.metadata.period == "2025-1T"
        assert record.metadata.tax_id == "X1234567L"

    def test_extracts_casillas(self) -> None:
        record = parse_modelo_303_detail(
            _load_fixture(),
            expediente=_expediente_303(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.calculations.casillas["01"] == "20.000,00"
        assert record.calculations.casillas["03"] == "4.200,00"
        assert record.calculations.casillas["29"] == "3.150,00"
        assert record.calculations.casillas["69"] == "1.050,00"

    def test_extracts_all_totals(self) -> None:
        record = parse_modelo_303_detail(
            _load_fixture(),
            expediente=_expediente_303(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.calculations.total_a_ingresar == Decimal("1050.00")
        assert record.calculations.total_a_devolver == Decimal("0.00")
        assert record.calculations.resultado_a_compensar == Decimal("0.00")

    def test_malformed_html_raises(self) -> None:
        with pytest.raises(HistoryParseError):
            parse_modelo_303_detail(
                "<html><body></body></html>",
                expediente=_expediente_303(),
                source_url=_SOURCE_URL,
                fetched_at=_FETCHED,
            )
