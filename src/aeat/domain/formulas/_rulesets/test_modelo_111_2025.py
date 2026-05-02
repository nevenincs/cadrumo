"""Unit tests for the Modelo 111 2025 ruleset.

Exercises the formula-engine derivations and the externally-anchored worked
example for :data:`aeat.domain.formulas._rulesets.MODELO_111_2025`. Covers
the fixed-rate retentions on premios (casilla 09) and ganancias /
arrendamientos (casilla 12), plus the resultado-a-ingresar chain.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_111_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo111Ruleset:
    """Formula-engine assertions for the 2025 Modelo 111 ruleset."""

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
        # fixed-rate retentions on premios (casilla 09) and
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

    def test_external_worked_example_rirpf_99(self) -> None:
        """Externally-anchored worked example for the 19 % pago-a-cuenta rate.

        Provenance (BOE-A-2007-6820 RD 439/2007): RIRPF art. 99
        ("Obligación de practicar pagos a cuenta") carries the 19 %
        pago-a-cuenta rate on both premios en metálico (LIRPF art.
        101.7 rate, implemented at RIRPF art. 99 + threshold at
        art. 75.2.c / 75.3.f) and rendimientos del capital mobiliario /
        arrendamientos (implemented at RIRPF art. 100). The fixture
        derives the retention amounts from the 19 % statutory rate
        directly, NOT from the ruleset's ``ParameterTable``.

        Scenario: Q2 2025 with a 2 500 € premio en metálico
        (casilla 08) and 1 000 € in rendimientos capital mobiliario
        reported here as casilla 11 (Modelo 111 casilla 12 captures
        ingresos a cuenta de retribuciones en especie per Orden
        EHA/586/2011 — the test scenario simplifies):
        - casilla 09 = 2 500 x 19% = 475.00 per LIRPF art. 101.7
          via RIRPF art. 99.
        - casilla 12 = 1 000 x 19% = 190.00 per RIRPF art. 100 +
          LIRPF art. 101.2.
        - casilla 28 = 03 + 06 + 09 + 12 + 15 + 18 = 475 + 190 = 665.
        - casilla 30 = 28 - 29 = 665 - 0 = 665.

        Citations:
        - BOE-A-2006-20764 Ley 35/2006 (LIRPF) arts. 99, 101.2, 101.7
        - BOE-A-2007-6820 RD 439/2007 (RIRPF) arts. 99, 100
        """
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("2500.00"),
            "09": Decimal("475.00"),  # 19% per LIRPF art. 101.7 + RIRPF art. 99
            "11": Decimal("1000.00"),
            "12": Decimal("190.00"),  # 19% per LIRPF art. 101.2 + RIRPF art. 100
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
        """Zero-quarter boundary case with no retenciones."""
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
