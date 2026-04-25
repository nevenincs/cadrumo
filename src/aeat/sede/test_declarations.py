"""Offline tests for :mod:`aeat.sede._declarations`.

The walker itself depends on Playwright + a live AEAT session, so
its end-to-end coverage is a `live` test. These offline tests
exercise the post-Buscar HTML parser against a redacted fixture
captured 2026-04-25 against Kent's account (Modelo 100 / 2022).
The fixture's PII (NIE, name, expediente id) is replaced with
synthetic shape-preserving values per the
:mod:`aeat.sanitizer` token-replace pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ._declarations import _parse_listbox, _parse_presented_at
from ._errors import SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-sede"


class TestParseListbox:
    """The post-Buscar HTML lands a typed Declaration row."""

    def test_modelo_100_2022_parses_one_row(self) -> None:
        html = (_FIXTURE_ROOT / "declaraciones-modelo-100-2022.html").read_text(encoding="utf-8")
        rows = _parse_listbox(html, modelo="100", ejercicio=2022)
        assert len(rows) == 1
        row = rows[0]
        assert row.modelo == "100"
        assert row.ejercicio == 2022
        assert row.expediente_id == "202210013522222A"
        assert row.period == "0A"
        assert row.estado == "ALTA"
        assert row.presented_at == datetime(
            year=2024,
            month=2,
            day=1,
            hour=19,
            minute=15,
            second=34,
            tzinfo=UTC,
        )
        assert row.justificante_link_text == "Ver"
        assert row.archive_link_text == "Ver"
        assert row.mode == "read"

    def test_no_results_returns_empty_tuple(self) -> None:
        # Synthesise the no-results listbox shape inline.
        html = """
            <div class="z-listbox">
              <table class="z-listbox-body">
                <tr class="z-listitem">
                  <td class="z-listcell">
                    <div class="z-listcell-content">
                      No se han encontrado resultados para la consulta realizada.
                    </div>
                  </td>
                </tr>
              </table>
            </div>
        """
        rows = _parse_listbox(html, modelo="130", ejercicio=2024)
        assert rows == ()

    def test_missing_listbox_raises_parse_error(self) -> None:
        with pytest.raises(SedeParseError):
            _parse_listbox("<html><body>not a listbox</body></html>", modelo="100", ejercicio=2022)


class TestParsePresentedAt:
    """The Spanish dd/mm/YYYY hh:mm:ss timestamp shape parses to UTC."""

    def test_canonical_shape(self) -> None:
        result = _parse_presented_at("01/02/2024 19:15:34")
        assert result == datetime(
            year=2024,
            month=2,
            day=1,
            hour=19,
            minute=15,
            second=34,
            tzinfo=UTC,
        )

    def test_invalid_shape_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _parse_presented_at("2024-02-01 19:15:34")

    def test_partial_match_rejected(self) -> None:
        with pytest.raises(ValueError):
            _parse_presented_at("01/02/2024")
