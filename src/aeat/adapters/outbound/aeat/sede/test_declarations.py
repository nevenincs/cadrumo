"""Offline tests for :mod:`aeat.adapters.outbound.aeat.sede._declarations`.

The walker itself depends on Playwright + a live AEAT session, so
its end-to-end coverage is gated as a ``live`` test. The unit tests
here exercise the post-Buscar HTML parser against a redacted fixture
captured against a real account (Modelo 100 / 2022). The fixture's
PII (NIE, name, expediente id) is replaced with synthetic
shape-preserving values per the
:mod:`aeat.adapters.inbound.sanitizer` token-replace pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ._declarations import _extract_csv_from_url, _parse_listbox, _parse_presented_at
from ._errors import SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


_FIXTURE_ROOT = Path(__file__).resolve().parents[6] / "tests" / "fixtures" / "aeat-sede"


class TestParseListbox:
    """Verify :func:`_parse_listbox` extracts typed Declaration rows from the post-Buscar HTML."""

    def test_modelo_100_2022_parses_one_row(self) -> None:
        """Assert the Modelo 100 / 2022 fixture parses to a single fully-populated row."""
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
        """Assert the AEAT 'no results' listbox shape parses to the empty tuple."""
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
        """Assert HTML without a listbox raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError):
            _parse_listbox("<html><body>not a listbox</body></html>", modelo="100", ejercicio=2022)


class TestParsePresentedAt:
    """Verify the Spanish ``dd/mm/YYYY hh:mm:ss`` timestamp shape parses to UTC."""

    def test_canonical_shape(self) -> None:
        """Assert a well-formed Spanish timestamp parses to a UTC :class:`datetime`."""
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
        """Assert ISO-style timestamps are rejected."""
        with pytest.raises(ValueError):
            _parse_presented_at("2024-02-01 19:15:34")

    def test_partial_match_rejected(self) -> None:
        """Assert a date-only string (no time component) is rejected."""
        with pytest.raises(ValueError):
            _parse_presented_at("01/02/2024")


class TestExtractCsvFromUrl:
    """Verify cotejo-URL CSV extraction validates the AEAT shape strictly."""

    _COTEJO = "https://www6.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV="

    def test_canonical_csv(self) -> None:
        """Assert a canonical 16-character CSV extracts cleanly."""
        assert _extract_csv_from_url(f"{self._COTEJO}S3RASL6U73H49Y83") == "S3RASL6U73H49Y83"

    def test_missing_csv_param_raises(self) -> None:
        """Assert a URL without a CSV query parameter raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError, match="missing CSV"):
            _extract_csv_from_url("https://www6.agenciatributaria.gob.es/wlpl/foo")

    def test_lowercase_csv_rejected(self) -> None:
        """Assert a lowercase CSV value is rejected (AEAT only emits uppercase)."""
        # AEAT only emits uppercase CSV; lowercase indicates a
        # malformed response or attacker-crafted URL.
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}lowercaseinvalid")

    def test_too_short_csv_rejected(self) -> None:
        """Assert a CSV shorter than the AEAT minimum is rejected."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}AB12")

    def test_too_long_csv_rejected(self) -> None:
        """Assert a CSV longer than the AEAT maximum is rejected."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}{'A' * 32}")

    def test_csv_with_special_chars_rejected(self) -> None:
        """Assert a CSV containing path-traversal characters is rejected."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}AAAA1234../../etc")

    def test_multiple_csv_values_rejected(self) -> None:
        """Assert multiple CSV query parameter values are rejected."""
        # AEAT never repeats the CSV parameter; multiple values
        # indicate a malformed response or an attacker-crafted URL.
        with pytest.raises(SedeParseError, match="2 CSV values"):
            _extract_csv_from_url(f"{self._COTEJO}AAAA1234&CSV=BBBB5678")
