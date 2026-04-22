"""Unit tests for the Modelo 130 2024 ruleset.

Wave 48 stream 4 H4 / wave 53 stream 3 H3: close the coverage gap
where Modelos 130_2024 and 130_2025 had no colocated test file
(only referenced via smoke tests in test_engine.py /
test_ruleset.py / test_registry.py).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_130_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """Worked example: simple Q1 2024 estimación directa autónomo.

    Inputs + outputs are arithmetic-only (no rate mirroring from the
    ruleset) — the 20% IRPF trimestral rate is applied once and the
    result cross-checked against the expected cuota. A formula bug
    in the ruleset would require the fixture to be edited in
    lockstep.

    Scenario: ingresos 20 000 €, gastos 5 000 €, rendimiento
    15 000 €; no agraria income; no prior-quarter negatives;
    no vivienda deduction; no retenciones.

    - 03 rendimiento neto = 01 - 02 = 20 000 - 5 000 = 15 000.
    - 04 pago fraccionado = max(0, 20% x 15 000) = 3 000.
    - 07 apartado I = 04 - 05 - 06 = 3 000 - 0 - 0 = 3 000.
    - 09 agraria = 2% x 0 = 0.
    - 11 apartado II = 09 - 10 = 0.
    - 12 suma parciales = max(0, 07 + 11) = 3 000.
    - 14 neto tras minoración = 12 - 13 = 3 000 - 0 = 3 000.
    - 17 diferencia = 14 - 15 - 16 = 3 000 - 0 - 0 = 3 000.
    - 19 resultado final = 17 - 18 = 3 000 - 0 = 3 000.
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


class TestModelo130Ruleset2024:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_rendimiento_neto_mismatch(self) -> None:
        """Casilla 03 = 01 - 02. Kent off by 100€."""
        provided = _provided()
        provided["03"] = Decimal("14900.00")  # should be 15000
        report = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "03" in {d.casilla_id for d in report.discrepancies}

    def test_pago_fraccionado_rate_mismatch(self) -> None:
        """Casilla 04 = 20% x 03. Kent applies 18% (1800 short)."""
        provided = _provided()
        provided["04"] = Decimal("2700.00")  # should be 3000
        report = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "04" in {d.casilla_id for d in report.discrepancies}

    def test_suma_parciales_clamps_negative_to_zero(self) -> None:
        """12 = max(0, 07 + 11). Small rendimiento + big carryover ⇒ 12 clamps.

        03 = 1 000 ⇒ 04 = 200 (derived 20%). 05 = 500 (carryover).
        07 = 200 - 500 - 0 = -300.
        11 = 0 (no agraria).
        12 = max(0, -300 + 0) = 0 (clamp fires).
        14 = 12 - 13 = 0 - 0 = 0.
        17 = 14 - 15 - 16 = 0.
        19 = 17 - 18 = 0.
        """
        provided = {
            "01": Decimal("2000.00"),
            "02": Decimal("1000.00"),
            "03": Decimal("1000.00"),
            "04": Decimal("200.00"),
            "05": Decimal("500.00"),
            "06": Decimal("0.00"),
            "07": Decimal("-300.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),  # clamp result
            "13": Decimal("0.00"),
            "14": Decimal("0.00"),
            "15": Decimal("0.00"),
            "16": Decimal("0.00"),
            "17": Decimal("0.00"),
            "18": Decimal("0.00"),
            "19": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_ruleset_id_and_effective_range(self) -> None:
        from datetime import date

        assert MODELO_130_2024.ruleset_id == "modelo_130.2024"
        assert MODELO_130_2024.effective_from == date(2024, 1, 1)
        assert MODELO_130_2024.effective_to == date(2024, 12, 31)

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_130_2024.casillas if c.computed}
        # Full 130 ruleset: 04/07/09/11/12/14/17/19 are derived; 03 too.
        assert "03" in computed
        assert "04" in computed
        assert "19" in computed
        assert len(MODELO_130_2024.formulas) >= 8

    def test_external_worked_example_rirpf_110(self) -> None:
        """External-anchored worked example (wave 57b H5/H6 closure).

        Provenance: RD 439/2007 (RIRPF) art. 110.1.a fixes the 20%
        rate on IRPF pagos fraccionados (estimacion directa);
        art. 110.1.c fixes the 2% rate on agricola/ganadera/forestal/
        pesquera. Fixture values derived from those rates, NOT from
        the ruleset parameters.

        Citation: BOE-A-2007-6820 RD 439/2007 art. 110.
        """
        provided = {
            "01": Decimal("30000.00"),
            "02": Decimal("10000.00"),
            "03": Decimal("20000.00"),
            "04": Decimal("4000.00"),  # 20% per RIRPF 110.1.a
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
            "07": Decimal("4000.00"),
            "08": Decimal("2000.00"),
            "09": Decimal("40.00"),  # 2% per RIRPF 110.1.c
            "10": Decimal("0.00"),
            "11": Decimal("40.00"),
            "12": Decimal("4040.00"),
            "13": Decimal("0.00"),
            "14": Decimal("4040.00"),
            "15": Decimal("0.00"),
            "16": Decimal("0.00"),
            "17": Decimal("4040.00"),
            "18": Decimal("0.00"),
            "19": Decimal("4040.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        """Wave 57b M5: zero-quarter boundary — no ingresos, no pago."""
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
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()
