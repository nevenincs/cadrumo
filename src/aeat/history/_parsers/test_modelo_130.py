"""Unit tests for the modelo-130 detail-page parser."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ...status import Expediente
from .._errors import HistoryParseError
from .modelo_130 import parse_modelo_130_detail

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "aeat-pages" / "filing-history"
_SOURCE_URL = AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/detail/130/0001")
_FETCHED = datetime(2025, 4, 15, 10, 25, 0, tzinfo=UTC)


def _expediente_130() -> Expediente:
    return Expediente(
        expediente_id="2025X1234567L0001",
        modelo="130",
        period="2025-1T",
        status="Presentada",
        presented_at=datetime(2025, 4, 15, 10, 22, 31, tzinfo=UTC),
        csv="ABCD1234EFGH5678",
        justificante_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/justificante/0001"),
        source_page_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/mis-expedientes"),
        fetched_at=_FETCHED,
    )


def _load_fixture() -> str:
    return (_FIXTURES / "modelo_130_detail.html").read_text(encoding="utf-8")


class TestParseModelo130Detail:
    def test_extracts_metadata(self) -> None:
        record = parse_modelo_130_detail(
            _load_fixture(),
            expediente=_expediente_130(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.metadata.modelo == "130"
        assert record.metadata.period == "2025-1T"
        assert record.metadata.tax_id == "X1234567L"
        assert record.metadata.status == "Presentada"
        assert record.metadata.csv == "ABCD1234EFGH5678"

    def test_extracts_casillas(self) -> None:
        record = parse_modelo_130_detail(
            _load_fixture(),
            expediente=_expediente_130(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.calculations.casillas == {
            "01": "12.345,67",
            "02": "2.345,67",
            "03": "10.000,00",
            "04": "2.000,00",
            "05": "0,00",
            "06": "0,00",
            "07": "2.000,00",
        }

    def test_extracts_totals(self) -> None:
        record = parse_modelo_130_detail(
            _load_fixture(),
            expediente=_expediente_130(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.calculations.total_a_ingresar == Decimal("2000.00")
        assert record.calculations.total_a_devolver == Decimal("0.00")
        assert record.calculations.resultado_a_compensar is None

    def test_malformed_html_raises(self) -> None:
        with pytest.raises(HistoryParseError):
            parse_modelo_130_detail(
                "<html><body>no table here</body></html>",
                expediente=_expediente_130(),
                source_url=_SOURCE_URL,
                fetched_at=_FETCHED,
            )
