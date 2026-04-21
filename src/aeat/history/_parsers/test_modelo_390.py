"""Unit tests for the modelo-390 detail-page parser."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ...status import Expediente
from .._errors import HistoryParseError
from .modelo_390 import parse_modelo_390_detail

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "aeat-pages" / "filing-history"
_SOURCE_URL = AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/detail/390/0003")
_FETCHED = datetime(2026, 1, 30, 18, 50, 0, tzinfo=UTC)


def _expediente_390() -> Expediente:
    return Expediente(
        expediente_id="2025X1234567L0003",
        modelo="390",
        period="2025",
        status="Presentada",
        presented_at=datetime(2026, 1, 30, 18, 45, 12, tzinfo=UTC),
        csv=None,
        justificante_url=None,
        source_page_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/mis-expedientes"),
        fetched_at=_FETCHED,
    )


def _load_fixture() -> str:
    return (_FIXTURES / "modelo_390_detail.html").read_text(encoding="utf-8")


class TestParseModelo390Detail:
    def test_extracts_metadata(self) -> None:
        record = parse_modelo_390_detail(
            _load_fixture(),
            expediente=_expediente_390(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.metadata.modelo == "390"
        assert record.metadata.period == "2025"
        assert record.metadata.tax_id == "X1234567L"

    def test_extracts_casillas(self) -> None:
        record = parse_modelo_390_detail(
            _load_fixture(),
            expediente=_expediente_390(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.calculations.casillas["03"] == "80.000,00"
        assert record.calculations.casillas["84"] == "4.200,00"
        assert record.calculations.casillas["97"] == "4.200,00"

    def test_extracts_compensar(self) -> None:
        record = parse_modelo_390_detail(
            _load_fixture(),
            expediente=_expediente_390(),
            source_url=_SOURCE_URL,
            fetched_at=_FETCHED,
        )
        assert record.calculations.resultado_a_compensar == Decimal("0.00")
        # Modelo 390 does not always print total_a_ingresar/total_a_devolver;
        # expect a corresponding parse warning.
        assert any("total_a_ingresar" in w for w in record.parse_warnings)

    def test_malformed_html_raises(self) -> None:
        with pytest.raises(HistoryParseError):
            parse_modelo_390_detail(
                "<html><body></body></html>",
                expediente=_expediente_390(),
                source_url=_SOURCE_URL,
                fetched_at=_FETCHED,
            )
