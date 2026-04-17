"""Unit tests for :func:`aeat.status._parsers.parse_expedientes`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from aeat.status import Expediente, StatusParseError
from aeat.status._parsers import parse_expedientes

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "aeat-pages" / "expedientes"
_SOURCE_URL: AnyHttpUrl = TypeAdapter(AnyHttpUrl).validate_python(
    "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente?COPT=Y"
)
_FETCHED_AT = datetime(2026, 4, 12, 10, 0, tzinfo=UTC)


def _load(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


class TestParseExpedientes:
    def test_fixture_dir_exists(self) -> None:
        assert _FIXTURE_DIR.is_dir(), f"missing fixture dir: {_FIXTURE_DIR}"

    def test_parses_sample(self) -> None:
        records = parse_expedientes(
            _load("sample.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        assert len(records) == 3
        assert all(isinstance(r, Expediente) for r in records)

    def test_first_row_fields(self) -> None:
        records = parse_expedientes(
            _load("sample.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        first = records[0]
        assert first.expediente_id == "2025X1234567L0001"
        assert first.modelo == "130"
        assert first.period == "2025-1T"
        assert first.status == "Presentada"
        assert first.csv == "ABCD1234EFGH5678"
        assert first.justificante_url is not None
        assert str(first.justificante_url).startswith("https://sede.agenciatributaria.gob.es/wlpl/justificante")

    def test_blank_csv_and_justificante_are_none(self) -> None:
        records = parse_expedientes(
            _load("sample.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        rejected = records[2]
        assert rejected.status == "Rechazada"
        assert rejected.csv is None
        assert rejected.justificante_url is None

    def test_missing_table_raises_parse_error(self) -> None:
        with pytest.raises(StatusParseError):
            parse_expedientes(
                "<html><body><p>No table here</p></body></html>",
                source_url=_SOURCE_URL,  # type: ignore[arg-type]
                fetched_at=_FETCHED_AT,
            )

    def test_spanish_locale_fixture(self) -> None:
        """Real AEAT pages render ``dd/mm/yyyy HH:MM:SS`` and ship
        relative justificante links; the parser must accept both and
        must drop footer rows with colspan."""
        records = parse_expedientes(
            _load("sample_spanish.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        assert len(records) == 2  # totals row dropped
        madrid = ZoneInfo("Europe/Madrid")
        first = records[0]
        assert first.status == "Presentada - pendiente de compensacion"
        # Timestamps must be tz-aware UTC (AwareDatetime mandate).
        assert first.presented_at.tzinfo == UTC
        first_local = first.presented_at.astimezone(madrid)
        assert (first_local.year, first_local.month, first_local.day) == (2025, 7, 20)
        assert (first_local.hour, first_local.minute, first_local.second) == (12, 34, 56)
        assert first.justificante_url is not None
        assert str(first.justificante_url).startswith("https://sede.agenciatributaria.gob.es/wlpl/justificante"), (
            f"expected absolute url, got {first.justificante_url}"
        )
        second = records[1]
        assert second.presented_at.tzinfo == UTC
        second_local = second.presented_at.astimezone(madrid)
        assert (second_local.year, second_local.month, second_local.day) == (2025, 7, 15)
        assert second.csv is None
        assert second.justificante_url is None

    def test_unparseable_timestamp_raises_parse_error(self) -> None:
        html = """
        <table>
          <thead>
            <tr>
              <th>Expediente</th><th>Modelo</th><th>Periodo</th>
              <th>Estado</th><th>Fecha presentacion</th><th>CSV</th><th>Justificante</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>ID-1</td><td>130</td><td>2025-1T</td>
              <td>OK</td><td>not-a-date</td><td></td><td></td>
            </tr>
          </tbody>
        </table>
        """
        with pytest.raises(StatusParseError):
            parse_expedientes(
                html,
                source_url=_SOURCE_URL,  # type: ignore[arg-type]
                fetched_at=_FETCHED_AT,
            )
