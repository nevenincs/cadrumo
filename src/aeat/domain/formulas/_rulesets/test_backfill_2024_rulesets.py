"""Unit tests for the 2024 backfill rulesets (EPIC #305 wave 52).

Wave 48 stream 4 H4 coverage gap: six 2024 backfill rulesets shipped
with zero dedicated unit tests. The backfills are structural clones
of their 2025 siblings (same casillas + formulas + citations; only
the ParameterTable effective range narrows to 2024), so the test
surface is intentionally compact:

1. Registration + ruleset_id + effective range shape.
2. Happy-path audit against a canonical fixture (mirrors the 2025
   sibling's happy path to confirm the backfill did not drift).
3. One mutation per ruleset proves the formulas actually enforce.

Avoids tautology by recomputing expected values independently of
the ruleset — arithmetic is done inline in the fixture so a
formula-author bug surfaces as a mismatch.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import (
    MODELO_111_2024,
    MODELO_115_2024,
    MODELO_123_2024,
    MODELO_131_2024,
    MODELO_180_2024,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_EXPECTED_RANGE = (date(2024, 1, 1), date(2024, 12, 31))


class TestBackfillShape:
    """Every 2024 backfill must bind to the 2024 calendar year."""

    @pytest.mark.parametrize(
        ("ruleset", "expected_id"),
        [
            (MODELO_111_2024, "modelo_111.2024"),
            (MODELO_115_2024, "modelo_115.2024"),
            (MODELO_123_2024, "modelo_123.2024"),
            (MODELO_131_2024, "modelo_131.2024"),
            (MODELO_180_2024, "modelo_180.2024"),
        ],
        ids=["111", "115", "123", "131", "180"],
    )
    def test_ruleset_id_and_effective_range(self, ruleset, expected_id: str) -> None:
        assert ruleset.ruleset_id == expected_id
        assert ruleset.effective_from == _EXPECTED_RANGE[0]
        assert ruleset.effective_to == _EXPECTED_RANGE[1]


class TestModelo1152024:
    """19% retención on arrendamientos, fixed since 2016."""

    def test_clean_audit(self) -> None:
        # 02 base 12000 ⇒ 03 retenciones 2280 (= 12000 * 0.19).
        # 06 resultado = 03 + 04 - 05 = 2280 + 100 - 50 = 2330.
        provided = {
            "01": Decimal("2"),
            "02": Decimal("12000.00"),
            "03": Decimal("2280.00"),
            "04": Decimal("100.00"),
            "05": Decimal("50.00"),
            "06": Decimal("2330.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_115_2024, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_wrong_rate_flagged(self) -> None:
        # 02 = 10000; correct retención at 19% = 1900. Kent enters 1800 (18%).
        provided = {
            "01": Decimal("1"),
            "02": Decimal("10000.00"),
            "03": Decimal("1800.00"),  # wrong
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("1800.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_115_2024, provided=provided, tolerance=Decimal("0.01"))
        assert not report.is_clean()
        assert "03" in {d.casilla_id for d in report.discrepancies}


class TestModelo1802024:
    """Annual resumen of 115 quarterly filings; same 19% rate."""

    def test_clean_audit(self) -> None:
        # 02 = 48000 (annual base); 03 = 48000 * 0.19 = 9120.
        provided = {
            "01": Decimal("4"),
            "02": Decimal("48000.00"),
            "03": Decimal("9120.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2024, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()

    def test_wrong_retencion_flagged(self) -> None:
        provided = {
            "01": Decimal("4"),
            "02": Decimal("48000.00"),
            "03": Decimal("9000.00"),  # wrong — should be 9120
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2024, provided=provided, tolerance=Decimal("0.01"))
        assert "03" in {d.casilla_id for d in report.discrepancies}


class TestModelo1112024:
    """IRPF retenciones trabajo/premios/ganancias. 19% fixed rates."""

    def test_clean_audit(self) -> None:
        # Premios 08 = 5000 ⇒ 09 = 950 (19%).
        # Ganancias arrendamiento 11 = 2000 ⇒ 12 = 380 (19%).
        # 28 = 03 + 06 + 09 + 12 + 15 + 18 = 100 + 200 + 950 + 380 + 0 + 0 = 1630.
        # 30 = 28 - 29 = 1630 - 0 = 1630.
        provided = {
            "03": Decimal("100.00"),
            "06": Decimal("200.00"),
            "08": Decimal("5000.00"),
            "09": Decimal("950.00"),
            "11": Decimal("2000.00"),
            "12": Decimal("380.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("1630.00"),
            "29": Decimal("0.00"),
            "30": Decimal("1630.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_111_2024, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_premios_rate_mismatch_flagged(self) -> None:
        # 08 = 5000; correct 09 = 950 at 19%. Kent enters 900.
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("5000.00"),
            "09": Decimal("900.00"),  # wrong
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("900.00"),
            "29": Decimal("0.00"),
            "30": Decimal("900.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_111_2024, provided=provided, tolerance=Decimal("0.01"))
        assert "09" in {d.casilla_id for d in report.discrepancies}


class TestModelo1232024:
    """Retenciones capital mobiliario aggregation."""

    def test_clean_audit(self) -> None:
        # 03 = 01 + 02 = 3; 06 = 04 + 05 = 12500; 09 = 07 + 08 = 2375; 11 = 09 - 10 = 2375.
        provided = {
            "01": Decimal("1"),
            "02": Decimal("2"),
            "03": Decimal("3"),
            "04": Decimal("2500.00"),
            "05": Decimal("10000.00"),
            "06": Decimal("12500.00"),
            "07": Decimal("475.00"),
            "08": Decimal("1900.00"),
            "09": Decimal("2375.00"),
            "10": Decimal("0.00"),
            "11": Decimal("2375.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_123_2024, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()

    def test_sum_mismatch_flagged(self) -> None:
        # 03 should be 01+02 = 3, Kent enters 5.
        provided = {
            "01": Decimal("1"),
            "02": Decimal("2"),
            "03": Decimal("5"),  # wrong
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
            "07": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_123_2024, provided=provided, tolerance=Decimal("0.01"))
        assert "03" in {d.casilla_id for d in report.discrepancies}


class TestModelo1312024:
    """IRPF modulos 2% rate, unchanged 2024 ⇒ 2025."""

    def test_clean_audit(self) -> None:
        # 03 = 20000 ⇒ 04 = 400 (2%). 05 = 10000 ⇒ 06 = 200.
        # 07 = 02 + 04 + 06 = 300 + 400 + 200 = 900.
        # 10 = 07 - 08 - 09 = 900 - 50 - 0 = 850.
        # 13 = 10 - 11 - 12 = 850 - 0 - 0 = 850.
        # 15 = 13 - 14 = 850 - 0 = 850.
        provided = {
            "01": Decimal("5000.00"),
            "02": Decimal("300.00"),
            "03": Decimal("20000.00"),
            "04": Decimal("400.00"),
            "05": Decimal("10000.00"),
            "06": Decimal("200.00"),
            "07": Decimal("900.00"),
            "08": Decimal("50.00"),
            "09": Decimal("0.00"),
            "10": Decimal("850.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "13": Decimal("850.00"),
            "14": Decimal("0.00"),
            "15": Decimal("850.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_131_2024, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_two_percent_rate_mismatch(self) -> None:
        # 03 = 20000, correct 04 = 400. Kent enters 500 (2.5%).
        provided = {
            "01": Decimal("0.00"),
            "02": Decimal("0.00"),
            "03": Decimal("20000.00"),
            "04": Decimal("500.00"),  # wrong
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
            "07": Decimal("500.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("500.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "13": Decimal("500.00"),
            "14": Decimal("0.00"),
            "15": Decimal("500.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_131_2024, provided=provided, tolerance=Decimal("0.01"))
        assert "04" in {d.casilla_id for d in report.discrepancies}
