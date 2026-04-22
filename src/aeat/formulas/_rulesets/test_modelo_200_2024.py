"""Unit tests for the Modelo 200 (ejercicio 2024) ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_200_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """A simple ejercicio-2024 filing with base 500_000, tipo 25%."""
    return {
        "00547": Decimal("0.00"),  # no BIN compensation
        "00550": Decimal("500000.00"),  # base pre-reserva
        "00552": Decimal("500000.00"),  # base imponible
        "00558": Decimal("25.00"),  # 25% tipo (whole-percent)
        "00560": Decimal("125000.00"),  # cuota pre
        "00562": Decimal("125000.00"),  # cuota integra = 500_000 x 25%
        "00582": Decimal("125000.00"),  # cuota ajustada positiva
        "00592": Decimal("125000.00"),  # cuota liquida (no deducciones en este fixture)
        "00599": Decimal("5000.00"),  # retenciones
        "00601": Decimal("30000.00"),  # 1P
        "00603": Decimal("30000.00"),  # 2P
        "00605": Decimal("30000.00"),  # 3P
        "00615": Decimal("0.00"),  # abono
        "00619": Decimal("0.00"),  # incremento
        # 00611 = 125000 - 5000 - 30000 - 30000 - 30000 = 30000
        "00611": Decimal("30000.00"),
        # 00621 = 00611 + 00619 - 00615 = 30000 + 0 - 0 = 30000
        "00621": Decimal("30000.00"),
    }


class TestModelo200Ruleset2024:
    def test_consistent_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_200_2024,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_cuota_integra_from_whole_percent_tipo(self) -> None:
        """Casilla 00558 is whole-percent; 00562 = 00552 * (00558/100)."""
        provided = _provided()
        provided["00562"] = Decimal("130000.00")  # should be 125_000
        report = Engine().audit_against(
            ruleset=MODELO_200_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "00562" in {d.casilla_id for d in report.discrepancies}

    def test_cuota_diferencial_subtracts_all_payments(self) -> None:
        provided = _provided()
        provided["00611"] = Decimal("35000.00")  # forgot one 5000 subtraction
        report = Engine().audit_against(
            ruleset=MODELO_200_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "00611" in {d.casilla_id for d in report.discrepancies}

    def test_liquido_applies_incremento_and_abono(self) -> None:
        """00621 = 00611 + 00619 - 00615 (art. 125 LIS)."""
        provided = _provided()
        provided["00615"] = Decimal("1000.00")  # abono
        provided["00619"] = Decimal("500.00")  # incremento
        # 00621 = 30000 + 500 - 1000 = 29500
        provided["00621"] = Decimal("29500.00")
        report = Engine().audit_against(
            ruleset=MODELO_200_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_200_2024.casillas if c.computed}
        assert computed == {"00562", "00611", "00621"}
        assert len(MODELO_200_2024.formulas) == 3

    def test_external_worked_example_lis_art_29(self) -> None:
        """External-anchored worked example (wave 59c H3 closure).

        Provenance: Ley 27/2014 (LIS) art. 29.1 fixes the general tipo
        de gravamen at 25%. Art. 125 defines liquido = cuota diferencial
        + incremento - abono.

        Scenario: 2024 IS filing, base 1 000 000 at 25%.
        Citation: BOE-A-2014-12328 arts. 29.1 + 125.
        """
        provided = {
            "00547": Decimal("0.00"),
            "00550": Decimal("1000000.00"),
            "00552": Decimal("1000000.00"),
            "00558": Decimal("25.00"),  # 25% per LIS art. 29.1
            "00560": Decimal("250000.00"),
            "00562": Decimal("250000.00"),
            "00582": Decimal("0.00"),
            "00592": Decimal("250000.00"),
            "00599": Decimal("5000.00"),
            "00601": Decimal("60000.00"),
            "00603": Decimal("60000.00"),
            "00605": Decimal("60000.00"),
            "00615": Decimal("0.00"),
            "00619": Decimal("0.00"),
            "00611": Decimal("65000.00"),
            "00621": Decimal("65000.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_200_2024, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
