"""Unit tests for the Modelo 131 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_131_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _provided() -> dict[str, Decimal]:
    """Consistent Q1 2025 fixture for estimación objetiva autónomo."""
    # 01: modules income (input, informativa).
    # 02: pago fraccionado del trimestre (input, user-computed).
    # 03: volumen ventas 10_000 ⇒ 04 = 200 (2%).
    # 05: volumen ingresos agrícolas 5_000 ⇒ 06 = 100 (2%).
    # 07 = 02 + 04 + 06 = 500 + 200 + 100 = 800.
    # 08 retenciones 50, 09 minoración 0 ⇒ 10 = 800 - 50 - 0 = 750.
    # 11 negativos 100, 12 vivienda 0 ⇒ 13 = 750 - 100 - 0 = 650.
    # 14 a deducir 0 ⇒ 15 = 650.
    return {
        "01": Decimal("3000.00"),
        "02": Decimal("500.00"),
        "03": Decimal("10000.00"),
        "04": Decimal("200.00"),
        "05": Decimal("5000.00"),
        "06": Decimal("100.00"),
        "07": Decimal("800.00"),
        "08": Decimal("50.00"),
        "09": Decimal("0.00"),
        "10": Decimal("750.00"),
        "11": Decimal("100.00"),
        "12": Decimal("0.00"),
        "13": Decimal("650.00"),
        "14": Decimal("0.00"),
        "15": Decimal("650.00"),
    }


class TestModelo131Ruleset:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_131_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_two_percent_ventas(self) -> None:
        """Casilla 04 must be exactly 2% of 03.

        The engine derives computed casillas from NON-computed inputs
        and uses the derived values downstream. When only 04 is
        corrupted, 07 is recomputed from user_02 + derived_04 +
        derived_06 = 500 + 200 + 100 = 800, matching the user's 800;
        downstream checks stay clean. Only 04 itself flags
        (user=150 vs. derived=200). Wave 37 L1.
        """
        provided = _provided()
        provided["04"] = Decimal("150.00")  # wrong: engine derives 200 from 03=10000
        report = Engine().audit_against(
            ruleset=MODELO_131_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert offenders == {"04"}

    def test_total_previo_sum_detection(self) -> None:
        """Casilla 07 = 02 + 04 + 06; an off-by-50 typo surfaces."""
        provided = _provided()
        provided["07"] = Decimal("750.00")  # should be 800
        report = Engine().audit_against(
            ruleset=MODELO_131_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "07" in {d.casilla_id for d in report.discrepancies}

    def test_resultado_a_ingresar_subtracts_prior_complementaria(self) -> None:
        provided = _provided()
        provided["14"] = Decimal("200.00")
        provided["15"] = Decimal("450.00")  # 650 - 200 = 450
        report = Engine().audit_against(
            ruleset=MODELO_131_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_131_2025.casillas if c.computed}
        assert computed == {"04", "06", "07", "10", "13", "15"}
        assert len(MODELO_131_2025.formulas) == 6

    def test_external_worked_example_rirpf_110(self) -> None:
        """External-anchored worked example (wave 57b H5/H6 closure).

        Provenance: RD 439/2007 (RIRPF) art. 110.1.c fixes the 2%
        rate on volumen ingresos agricolas/ganaderas/forestales/
        pesqueras; art. 110.1.b fixes the 4%/3%/2% rate (scaled by
        employee count, 2% without employees) on the rendimiento
        neto resultante for modulos activities — both rates apply
        to the volumen-ventas proxy used in Modelo 131 per Orden
        EHA/672/2007 instrucciones.

        Scenario: Q3 2025 autonomo on modulos with 25 000 volumen
        ventas (03) and 10 000 volumen ingresos agricolas (05):
        - casilla 04 = 25 000 x 2% = 500.00 per RIRPF art. 110.1.b
        - casilla 06 = 10 000 x 2% = 200.00 per RIRPF art. 110.1.c
        - casilla 07 = 02 + 04 + 06 = 150 + 500 + 200 = 850.
        - casilla 10 = 07 - 08 - 09 = 850 - 20 - 0 = 830.
        - casilla 13 = 10 - 11 - 12 = 830 - 0 - 0 = 830.
        - casilla 15 = 13 - 14 = 830 - 0 = 830.

        Citation: BOE-A-2007-6820 RD 439/2007 art. 110.
        """
        provided = {
            "01": Decimal("1500.00"),
            "02": Decimal("150.00"),
            "03": Decimal("25000.00"),
            "04": Decimal("500.00"),  # 2% per RIRPF art. 110.1.b
            "05": Decimal("10000.00"),
            "06": Decimal("200.00"),  # 2% per RIRPF art. 110.1.c
            "07": Decimal("850.00"),
            "08": Decimal("20.00"),
            "09": Decimal("0.00"),
            "10": Decimal("830.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "13": Decimal("830.00"),
            "14": Decimal("0.00"),
            "15": Decimal("830.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_131_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
