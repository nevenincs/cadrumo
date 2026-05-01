"""Unit tests for the Modelo 130 2026 ruleset.

Issue #321 (Tier-L per-modelo calc-verify-roundtrip): the 2026
ruleset is a structural clone of the 2024 / 2025 rulesets because
RIRPF art. 110 was not amended for 2025 or 2026 (see the rule-delta
manifest at ``.vault/reference/2026-130-rule-delta.md``). These
tests assert the no-drift invariant against the 2025 ruleset and
ship an external-anchored worked example whose expected values come
from RIRPF art. 110 verbatim — not from the 2026 ruleset's stored
parameters. A typo in either the ruleset's parameters or the
helper's bracket boundaries would therefore fail one of the cases
below.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_130_2026
from .modelo_130_2024 import compute_casilla_13_minoracion

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """Worked-example fixture for a Q2 2026 estimación-directa autónomo.

    Distinct numerical scenario from the 2024 / 2025 fixtures (which
    use 20 000 € / 5 000 € and 48 000 € / 12 500 € respectively) to
    avoid mirror-fixture coupling: a Q2 autónomo with both an
    estimación-directa slice (Apartado I) and a small agraria slice
    (Apartado II) plus a non-zero minoración.

    Inputs (RIRPF art. 110.1.a + 110.1.c + 110.3.c):
      - Casilla 01 (ingresos acumulados): 24 000,00 EUR
      - Casilla 02 (gastos deducibles acumulados): 9 000,00 EUR
      - Casilla 03 (rendimiento neto): 24 000 - 9 000 = 15 000,00
      - Casilla 04 (pago fraccionado 20 %): 15 000 x 0,20 = 3 000,00
      - Casilla 05 (pagos previos trimestres): 1 200,00
      - Casilla 06 (retenciones a cuenta Apartado I): 100,00
      - Casilla 07 (resultado parcial Apartado I): 3 000 - 1 200 - 100 = 1 700,00
      - Casilla 08 (volumen ingresos agraria del trimestre): 4 500,00
      - Casilla 09 (pago fraccionado agraria 2 %): 4 500 x 0,02 = 90,00
      - Casilla 10 (retenciones agraria): 20,00
      - Casilla 11 (resultado parcial Apartado II): 90 - 20 = 70,00
      - Casilla 12 (suma parciales, ≥ 0): max(0, 1 700 + 70) = 1 770,00
      - Casilla 13 (minoración art. 110.3.c): 75,00
        (the prior-year RN bracket the caller resolves; here = 75)
      - Casilla 14 (neto tras minoración): 1 770 - 75 = 1 695,00
      - Casilla 15 (arrastre de negativos): 0,00
      - Casilla 16 (deducción vivienda habitual): 0,00
      - Casilla 17 (diferencia): 1 695 - 0 - 0 = 1 695,00
      - Casilla 18 (resultado complementaria previa): 0,00
      - Casilla 19 (resultado final): 1 695 - 0 = 1 695,00

    Every arithmetic step is traceable to RIRPF art. 110; the rates
    come from the statute, not from the ruleset's ``ParameterTable``.
    """
    return {
        "01": Decimal("24000.00"),
        "02": Decimal("9000.00"),
        "03": Decimal("15000.00"),
        "04": Decimal("3000.00"),
        "05": Decimal("1200.00"),
        "06": Decimal("100.00"),
        "07": Decimal("1700.00"),
        "08": Decimal("4500.00"),
        "09": Decimal("90.00"),
        "10": Decimal("20.00"),
        "11": Decimal("70.00"),
        "12": Decimal("1770.00"),
        "13": Decimal("75.00"),
        "14": Decimal("1695.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "17": Decimal("1695.00"),
        "18": Decimal("0.00"),
        "19": Decimal("1695.00"),
    }


class TestModelo130Ruleset2026:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2026_no_drift_from_2025(self) -> None:
        """Issue #321 invariant: 2026 audit must equal 2025 audit on identical inputs.

        RIRPF art. 110 is unchanged across 2025 → 2026 per the rule-
        delta manifest. The casillas + citations are shared module-
        level imports from 2024; only the formula-id namespace differs
        (``modelo_130.2025.<reason>`` vs ``modelo_130.2026.<reason>``).
        Derived values must therefore be identical.
        """
        from . import MODELO_130_2025

        provided = _provided()
        report_2025 = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2026 = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert len(report_2025.ledger.entries) == len(report_2026.ledger.entries)
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        derived_2026 = {e.casilla_id: e.value for e in report_2026.ledger.entries}
        assert derived_2025 == derived_2026

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_130_2026.ruleset_id == "modelo_130.2026"
        assert MODELO_130_2026.effective_from == date(2026, 1, 1)
        assert MODELO_130_2026.effective_to == date(2026, 12, 31)

    def test_external_worked_example_rirpf_art_110_2026(self) -> None:
        """External-anchored worked example for the 2026 ruleset.

        Provenance: RD 439/2007 (RIRPF) art. 110.1.a fixes the 20 %
        rate on actividades en estimación directa; art. 110.1.c fixes
        the 2 % rate on actividades agrícolas / ganaderas / forestales /
        pesqueras. Fixture values derived from those rates, NOT from
        the ruleset's ``ParameterTable``.

        Citation: BOE-A-2007-6820 RD 439/2007 art. 110 (consolidated
        text last update 2026-02-28; no 2025 / 2026 amendment to art.
        110).

        Scenario distinct from ``_provided()`` to avoid coupling: a 4T
        2026 autónomo with no agraria activity, no minoración, and a
        small retención-a-cuenta carry from earlier quarters.
          - Casilla 01: 60 000,00 EUR
          - Casilla 02: 18 000,00 EUR
          - Casilla 03: 60 000 - 18 000 = 42 000,00
          - Casilla 04: 42 000 x 0,20 = 8 400,00 (RIRPF 110.1.a)
          - Casilla 05: 6 300,00 (sum of 1T+2T+3T pagos)
          - Casilla 06: 850,00 (retenciones acumuladas)
          - Casilla 07: 8 400 - 6 300 - 850 = 1 250,00
          - Casillas 08-11: 0,00 (no agraria)
          - Casilla 12: max(0, 1 250 + 0) = 1 250,00
          - Casilla 13: 0,00 (no art. 110.3.c minoración this year)
          - Casilla 14: 1 250 - 0 = 1 250,00
          - Casilla 15-16: 0,00
          - Casilla 17: 1 250,00
          - Casilla 18: 0,00 (no complementaria)
          - Casilla 19: 1 250,00
        """
        provided = {
            "01": Decimal("60000.00"),
            "02": Decimal("18000.00"),
            "03": Decimal("42000.00"),
            "04": Decimal("8400.00"),  # 20 % per RIRPF 110.1.a
            "05": Decimal("6300.00"),
            "06": Decimal("850.00"),
            "07": Decimal("1250.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("1250.00"),
            "13": Decimal("0.00"),
            "14": Decimal("1250.00"),
            "15": Decimal("0.00"),
            "16": Decimal("0.00"),
            "17": Decimal("1250.00"),
            "18": Decimal("0.00"),
            "19": Decimal("1250.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_agraria_income_computes_2_percent(self) -> None:
        """Casilla 09 = 2 % x 08 (RIRPF art. 110.1.c). Pure agraria fixture."""
        provided = {
            "01": Decimal("0.00"),
            "02": Decimal("0.00"),
            "03": Decimal("0.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
            "07": Decimal("0.00"),
            "08": Decimal("12500.00"),
            "09": Decimal("250.00"),  # 2 % per RIRPF 110.1.c
            "10": Decimal("0.00"),
            "11": Decimal("250.00"),
            "12": Decimal("250.00"),
            "13": Decimal("0.00"),
            "14": Decimal("250.00"),
            "15": Decimal("0.00"),
            "16": Decimal("0.00"),
            "17": Decimal("250.00"),
            "18": Decimal("0.00"),
            "19": Decimal("250.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        """Zero-boundary case: no ingresos, no pago."""
        provided = {
            k: Decimal("0.00")
            for k in [
                "01",
                "02",
                "03",
                "04",
                "05",
                "06",
                "07",
                "08",
                "09",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
            ]
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_suma_parciales_clamps_negative_to_zero(self) -> None:
        """Casilla 12 = max(0, 07 + 11) — clamp on negative parcial.

        Threshold-edge case for the ``max_op(lit("0"), ...)`` clamp:
        small rendimiento + large prior-quarter pool ⇒ negative
        Apartado I parcial that the engine must clamp to zero before
        propagating downstream.
        """
        provided = {
            "01": Decimal("3000.00"),
            "02": Decimal("1500.00"),
            "03": Decimal("1500.00"),
            "04": Decimal("300.00"),  # 20 % x 1500
            "05": Decimal("700.00"),
            "06": Decimal("0.00"),
            "07": Decimal("-400.00"),  # 300 - 700 - 0
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),  # clamp fires
            "13": Decimal("0.00"),
            "14": Decimal("0.00"),
            "15": Decimal("0.00"),
            "16": Decimal("0.00"),
            "17": Decimal("0.00"),
            "18": Decimal("0.00"),
            "19": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_pago_fraccionado_rate_mismatch_raises(self) -> None:
        """Casilla 04 = 20 % x 03. Kent applies 18 % (1 800 short).

        Negative-path test: confirm the 2026 audit surfaces a casilla-04
        discrepancy when the user-supplied value departs from the
        engine's re-derivation by more than the audit tolerance.
        """
        provided = _provided()
        provided["04"] = Decimal("2700.00")  # should be 3 000 (20 % x 15 000)
        report = Engine().audit_against(
            ruleset=MODELO_130_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "04" in {d.casilla_id for d in report.discrepancies}


# Issue #321: external-anchored threshold-edge cases for the casilla-13
# minoración helper exercised through the 2026 path. The bracket
# boundaries (9 000 / 10 000 / 11 000 / 12 000 €) are stable across
# 2024 → 2025 → 2026 per the rule-delta manifest; the helper imports
# from `modelo_130_2024` and the test exercises it through the 2026
# import path to confirm no drift.
@pytest.mark.parametrize(
    ("previous_year_rn", "expected_minoracion"),
    [
        (Decimal("0.00"), Decimal("100")),
        (Decimal("8999.99"), Decimal("100")),
        (Decimal("9000.00"), Decimal("100")),
        (Decimal("9000.01"), Decimal("75")),
        (Decimal("10000.00"), Decimal("75")),
        (Decimal("10000.01"), Decimal("50")),
        (Decimal("11000.00"), Decimal("50")),
        (Decimal("11000.01"), Decimal("25")),
        (Decimal("12000.00"), Decimal("25")),
        (Decimal("12000.01"), Decimal("0")),
        (Decimal("50000.00"), Decimal("0")),
    ],
)
def test_casilla_13_minoracion_brackets_2026(
    previous_year_rn: Decimal,
    expected_minoracion: Decimal,
) -> None:
    """Threshold-edge cases for RIRPF art. 110.3.c minoración brackets (2026)."""
    assert compute_casilla_13_minoracion(previous_year_rn) == expected_minoracion
