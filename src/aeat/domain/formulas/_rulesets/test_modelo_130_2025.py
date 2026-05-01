"""Unit tests for the Modelo 130 2025 ruleset.

Wave 55 companion to test_modelo_130_2024.py. The 2025 ruleset
re-uses the 2024 casillas + citations (mid-year rule changes absent
for 2024→2025 per the research doc), so the 2025 tests exercise the
same formulas via the 2025 variant to confirm no drift.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_130_2025
from .modelo_130_2024 import compute_casilla_13_minoracion

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """Identical shape to the 2024 test: 20 000 € ingresos, 5 000 € gastos.

    If the 2025 ruleset drifted from 2024 (rate change, formula
    swap, casilla shuffle), this fixture would flag a discrepancy
    against the engine-derived values.
    """
    return {
        "01": Decimal("20000.00"),
        "02": Decimal("5000.00"),
        "03": Decimal("15000.00"),
        "04": Decimal("3000.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "07": Decimal("3000.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "10": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("3000.00"),
        "13": Decimal("0.00"),
        "14": Decimal("3000.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "17": Decimal("3000.00"),
        "18": Decimal("0.00"),
        "19": Decimal("3000.00"),
    }


class TestModelo130Ruleset2025:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_agraria_income_computes_2_percent(self) -> None:
        """Casilla 09 = 2% x 08. Agricultural autónomo fixture."""
        provided = _provided()
        # Set 08 = 5000 (agraria ingresos), expect 09 = 100.
        provided["08"] = Decimal("5000.00")
        provided["09"] = Decimal("100.00")
        provided["11"] = Decimal("100.00")  # 11 = 09 - 10 = 100
        provided["12"] = Decimal("3100.00")  # 07 + 11 = 3000 + 100
        provided["14"] = Decimal("3100.00")
        provided["17"] = Decimal("3100.00")
        provided["19"] = Decimal("3100.00")
        report = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2025_no_drift_from_2024(self) -> None:
        """Wave 55 regression: 2025 ruleset MUST produce identical audit
        to 2024 for any fixture where both rulesets would legally apply
        (i.e. no mid-year change). The casillas + formulas are shared
        module-level imports, so a drift would require an active change.
        """
        from . import MODELO_130_2024

        provided = _provided()
        report_2024 = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2025 = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        # Same number of ledger entries and same derived values.
        assert len(report_2024.ledger.entries) == len(report_2025.ledger.entries)
        derived_2024 = {e.casilla_id: e.value for e in report_2024.ledger.entries}
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        assert derived_2024 == derived_2025

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_130_2025.ruleset_id == "modelo_130.2025"
        assert MODELO_130_2025.effective_from == date(2025, 1, 1)
        assert MODELO_130_2025.effective_to == date(2025, 12, 31)

    def test_external_worked_example_rirpf_art_110(self) -> None:
        """External anchor per Reglamento del IRPF (RD 439/2007) art. 110.1.a.

        RIRPF art. 110.1.a fixes the pago fraccionado general at 20% of the
        rendimiento neto acumulado for actividades económicas en estimación
        directa. Sister subsections: art. 110.1.b covers estimación objetiva
        (módulos) at 4%/3%/2% depending on employee count; art. 110.1.c is
        the 2% rate on actividades agrícolas/ganaderas/forestales/pesqueras.
        The statute (BOE-A-2007-6820) — not the ruleset's ParameterTable —
        is the external source. This test asserts the arithmetic mandated
        by the statute using a scenario distinct from `_provided()` to
        avoid mirroring the 2024 drift-check fixture.

        Scenario: Kent (autónomo actividad económica no-agraria) Q3 2025.
          - Casilla 01 (ingresos acumulados): 48 000,00 EUR
          - Casilla 02 (gastos deducibles acumulados): 12 500,00 EUR
          - Casilla 03 (rendimiento neto): 48 000 - 12 500 = 35 500,00
          - Casilla 04 (pago fraccionado 20%): 35 500 x 0,20 = 7 100,00
          - Casillas 05/06 (minoraciones): 0,00 / 0,00
          - Casilla 07 (resultado apartado I): 7 100 - 0 - 0 = 7 100,00
          - Casillas 08-11 (actividades agrarias): all 0,00 (no agraria)
          - Casilla 12 (suma parciales): max(0, 7 100 + 0) = 7 100,00
          - Casilla 13 (minoracion art. 110.3.c): 0,00
          - Casilla 14 (neto tras minoracion): 7 100,00
          - Casilla 15 (pagos previos trimestres): 2 500,00
          - Casilla 16 (retenciones ingreso a cuenta): 450,00
          - Casilla 17 (diferencia): 7 100 - 2 500 - 450 = 4 150,00
          - Casilla 18 (resultado negativo previo): 0,00
          - Casilla 19 (resultado final): 4 150 - 0 = 4 150,00

        Every arithmetic step is traceable to RIRPF art. 110 subsections; the
        20% rate is the statutory rate, not a ruleset-internal constant.
        """
        provided = {
            "01": Decimal("48000.00"),
            "02": Decimal("12500.00"),
            "03": Decimal("35500.00"),
            "04": Decimal("7100.00"),
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
            "07": Decimal("7100.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("7100.00"),
            "13": Decimal("0.00"),
            "14": Decimal("7100.00"),
            "15": Decimal("2500.00"),
            "16": Decimal("450.00"),
            "17": Decimal("4150.00"),
            "18": Decimal("0.00"),
            "19": Decimal("4150.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


# Issue #321: external-anchored threshold-edge cases for the casilla-13
# minoración helper, in the 2025 ruleset's test file. The bracket
# boundaries (9 000 / 10 000 / 11 000 / 12 000 €) are stable across
# 2024 → 2025 → 2026 per the rule-delta manifest; the helper imports
# from `modelo_130_2024` and the test exercises it through the 2025
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
def test_casilla_13_minoracion_brackets_2025(
    previous_year_rn: Decimal,
    expected_minoracion: Decimal,
) -> None:
    """Threshold-edge cases for RIRPF art. 110.3.c minoración brackets (2025)."""
    assert compute_casilla_13_minoracion(previous_year_rn) == expected_minoracion
