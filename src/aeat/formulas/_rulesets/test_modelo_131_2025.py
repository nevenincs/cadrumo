"""Unit tests for the Modelo 131 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_131_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


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
