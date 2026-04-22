"""Unit tests for the Modelo 111 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_111_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo111Ruleset:
    def test_consistent_sum_and_resultado_is_clean(self) -> None:
        provided = {
            "03": Decimal("5000.00"),  # trabajo
            "06": Decimal("3000.00"),  # actividades
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("8000.00"),
            "29": Decimal("0.00"),
            "30": Decimal("8000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_sum_mismatch_surfaces_discrepancy(self) -> None:
        # Kent forgets to carry 5000 + 3000 → reports 7000.
        provided = {
            "03": Decimal("5000.00"),
            "06": Decimal("3000.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("7000.00"),  # bug: actual 8000
            "29": Decimal("0.00"),
            "30": Decimal("7000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "28" in offenders

    def test_resultado_subtracts_negative_carryover(self) -> None:
        provided = {
            "03": Decimal("2000.00"),
            "06": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("2000.00"),
            "29": Decimal("300.00"),
            "30": Decimal("1700.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_exposes_fixed_rate_formulas(self) -> None:
        # Wave 29 HIGH-2: fixed-rate retentions on premios (casilla 09) and
        # arrendamientos-ganancias (casilla 12) at 19% are now verified.
        assert len(MODELO_111_2025.casillas) == 11
        computed = {c.casilla_id for c in MODELO_111_2025.casillas if c.computed}
        assert computed == {"09", "12", "28", "30"}

    def test_premios_retention_at_19pct(self) -> None:
        # 8000 premios x 19% = 1520 retencion.
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("8000.00"),
            "09": Decimal("1520.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("1520.00"),
            "29": Decimal("0.00"),
            "30": Decimal("1520.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_external_worked_example_rirpf_105(self) -> None:
        """External-anchored worked example (wave 57b H5/H6 closure).

        Provenance: RD 439/2007 (RIRPF) art. 105.1 fixes the 19%
        retention rate on premios en metalico; art. 100.3.c fixes
        the 19% rate on ganancias patrimoniales de arrendamientos.
        This fixture derives expected retention values from those
        rates directly (NOT from the ruleset's `irpf.premios_rate`
        parameter).

        Scenario: Q2 2025 Kent with a 2 500 lottery prize
        (casilla 08) and 1 000 ganancias arrendamiento (casilla 11):
        - casilla 09 = 2 500 x 19% = 475.00 per RIRPF art. 105.1
        - casilla 12 = 1 000 x 19% = 190.00 per RIRPF art. 100.3.c
        - casilla 28 = 03 + 06 + 09 + 12 + 15 + 18 = 475 + 190 = 665.
        - casilla 30 = 28 - 29 = 665 - 0 = 665.

        Citations:
        - BOE-A-2007-6820 RD 439/2007 art. 105.1
        - BOE-A-2007-6820 RD 439/2007 art. 100.3.c
        """
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("2500.00"),
            "09": Decimal("475.00"),  # from RIRPF 105.1, NOT from ruleset
            "11": Decimal("1000.00"),
            "12": Decimal("190.00"),  # from RIRPF 100.3.c, NOT from ruleset
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("665.00"),
            "29": Decimal("0.00"),
            "30": Decimal("665.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        """Wave 57b M5: zero-quarter boundary (no retenciones)."""
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("0.00"),
            "29": Decimal("0.00"),
            "30": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_premios_retention_typo_detected(self) -> None:
        # Kent enters 1400 instead of 1520 — 120€ off the expected 19%.
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("8000.00"),
            "09": Decimal("1400.00"),  # should be 1520
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("1400.00"),
            "29": Decimal("0.00"),
            "30": Decimal("1400.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "09" in offenders
