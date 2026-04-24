"""Unit tests for :func:`aeat.status._parsers.parse_notificaciones` (#170)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from .. import Notificacion, StatusParseError
from . import parse_notificaciones

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "aeat-pages" / "notificaciones"
_SOURCE_URL: AnyHttpUrl = TypeAdapter(AnyHttpUrl).validate_python(
    "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/NOT-L/Notificacion"
)
_FETCHED_AT = datetime(2026, 4, 21, 10, 0, tzinfo=UTC)


def _load(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


class TestParseNotificaciones:
    def test_fixture_dir_exists(self) -> None:
        assert _FIXTURE_DIR.is_dir(), f"missing fixture dir: {_FIXTURE_DIR}"

    def test_parses_sample(self) -> None:
        records = parse_notificaciones(
            _load("sample.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        assert len(records) == 3
        assert all(isinstance(r, Notificacion) for r in records)

    def test_first_row_fields(self) -> None:
        records = parse_notificaciones(
            _load("sample.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        first = records[0]
        assert first.notificacion_id == "NOT-2026-0001"
        assert first.kind == "Requerimiento"
        assert first.title.get("es") == "Requerimiento de subsanacion modelo 303 2025-4T"
        assert first.body_excerpt.get("es") == first.title.get("es")
        assert first.received_at.tzinfo == UTC
        assert first.due_at is not None

    def test_blank_plazo_is_none(self) -> None:
        records = parse_notificaciones(
            _load("sample.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        ack = records[1]
        assert ack.notificacion_id == "NOT-2026-0002"
        assert ack.due_at is None

    def test_missing_table_raises_parse_error(self) -> None:
        with pytest.raises(StatusParseError):
            parse_notificaciones(
                "<html><body><p>nothing here</p></body></html>",
                source_url=_SOURCE_URL,  # type: ignore[arg-type]
                fetched_at=_FETCHED_AT,
            )

    def test_spanish_locale_fixture(self) -> None:
        """AEAT renders dd/mm/yyyy HH:MM:SS and carries accented headers."""
        records = parse_notificaciones(
            _load("sample_spanish.html"),
            source_url=_SOURCE_URL,  # type: ignore[arg-type]
            fetched_at=_FETCHED_AT,
        )
        assert len(records) == 2  # totals row dropped
        madrid = ZoneInfo("Europe/Madrid")
        first = records[0]
        assert first.notificacion_id == "NOT-2026-0050"
        assert first.received_at.tzinfo == UTC
        first_local = first.received_at.astimezone(madrid)
        assert (first_local.year, first_local.month, first_local.day) == (2026, 2, 20)
        assert (first_local.hour, first_local.minute, first_local.second) == (14, 5, 12)

    def test_unparseable_timestamp_raises(self) -> None:
        html = """
        <table>
          <thead>
            <tr>
              <th>Identificador</th><th>Tipo</th><th>Asunto</th>
              <th>Fecha puesta a disposicion</th><th>Plazo</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>NOT-X</td><td>Test</td><td>subject</td>
              <td>not-a-date</td><td></td>
            </tr>
          </tbody>
        </table>
        """
        with pytest.raises(StatusParseError):
            parse_notificaciones(
                html,
                source_url=_SOURCE_URL,  # type: ignore[arg-type]
                fetched_at=_FETCHED_AT,
            )
