"""Unit tests for the Modelo 180 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_180_2025
from ._modelo_180_cumulation import (
    Modelo180QuarterlyRetention,
    aggregate_modelo_180_from_quarters,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


class TestModelo180Ruleset:
    def test_consistent_annual_is_clean(self) -> None:
        # 02 = 60_000, 03 = 19% = 11_400, 04 ingresos especie = 0.
        provided = {
            "01": Decimal("5"),
            "02": Decimal("60000.00"),
            "03": Decimal("11400.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_180_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_retention_rate_mismatch(self) -> None:
        # User enters 18% retention by mistake.
        provided = {
            "01": Decimal("5"),
            "02": Decimal("60000.00"),
            "03": Decimal("10800.00"),  # 18% — wrong
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_180_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "03" in {d.casilla_id for d in report.discrepancies}

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_180_2025.casillas if c.computed}
        assert computed == {"03"}
        assert len(MODELO_180_2025.formulas) == 1

    def test_ingresos_especie_preserves_04(self) -> None:
        """Casilla 04 is user-input and preserved by the four-casilla summary."""
        provided = {
            "01": Decimal("3"),
            "02": Decimal("30000.00"),
            "03": Decimal("5700.00"),  # 30000 * 0.19
            "04": Decimal("250.00"),  # in-kind payments on account
        }
        report = Engine().audit_against(ruleset=MODELO_180_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()

    def test_zero_base_yields_zero_retencion(self) -> None:
        """Boundary: 0€ base ⇒ 0€ retención."""
        provided = {
            "01": Decimal("0"),
            "02": Decimal("0.00"),
            "03": Decimal("0.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()

    def test_external_worked_example_rirpf_100_1(self) -> None:
        """External-anchored worked example for RIRPF art. 100.1.

        Modelo 180 is the annual rollup of Modelo 115 quarterly filings;
        RIRPF art. 100.1 fixes the 19% rate on arrendamientos urbanos.
        Fixture values derived from that rate, NOT from the ruleset's
        `irpf.arrendamientos_rate` parameter. BOE-A-2007-6820
        consolidated retrieval 2026-04-22.

        Scenario: Kent's 2025 annual summary with 3 landlords, total
        base 90 000:
        - 01 perceptores = 3.
        - 02 base = 90 000.
        - 03 retención = 90 000 x 19% = 17 100 per RIRPF 100.1.
        """
        provided = {
            "01": Decimal("3"),
            "02": Decimal("90000.00"),
            "03": Decimal("17100.00"),  # 19% per RIRPF 100.1
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()


def test_cumulation_from_four_quarterly_modelo_115_sources() -> None:
    """Approach A: M180 annual summary equals four Modelo 115-style quarters."""
    quarters = (
        Modelo180QuarterlyRetention.from_m115_casillas(
            {
                "01": Decimal("1"),
                "02": Decimal("10000.00"),
                "03": Decimal("1900.00"),
                "04": Decimal("0.00"),
            },
            recipient_ids=("landlord-a",),
        ),
        Modelo180QuarterlyRetention.from_m115_casillas(
            {
                "01": Decimal("1"),
                "02": Decimal("12000.00"),
                "03": Decimal("2280.00"),
                "04": Decimal("0.00"),
            },
            recipient_ids=("landlord-b",),
        ),
        Modelo180QuarterlyRetention.from_m115_casillas(
            {
                "01": Decimal("2"),
                "02": Decimal("14000.00"),
                "03": Decimal("2660.00"),
                "04": Decimal("25.00"),
            },
            recipient_ids=("landlord-c", "landlord-d"),
        ),
        Modelo180QuarterlyRetention.from_m115_casillas(
            {
                "01": Decimal("1"),
                "02": Decimal("12000.00"),
                "03": Decimal("2280.00"),
                "04": Decimal("0.00"),
            },
            recipient_ids=("landlord-e",),
        ),
    )
    annual = aggregate_modelo_180_from_quarters(quarters).as_casillas()

    assert annual == {
        "01": Decimal("5"),
        "02": Decimal("48000.00"),
        "03": Decimal("9120.00"),
        "04": Decimal("25.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_180_2025, provided=annual, tolerance=Decimal("0.01"))
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


def test_cumulation_rejects_missing_quarter() -> None:
    """Cumulation catches the omitted-quarter shape before formula verification."""
    quarters = (
        Modelo180QuarterlyRetention(
            recipients=Decimal("1"),
            recipient_ids=("landlord-a",),
            base_retencion=Decimal("10000.00"),
            retenciones=Decimal("1900.00"),
            ingresos_especie=Decimal("0.00"),
        ),
    )
    with pytest.raises(ValueError, match="exactly 4 quarters"):
        aggregate_modelo_180_from_quarters(quarters)


def test_cumulation_uses_annual_rounding_for_retenciones() -> None:
    """Annual M180 rounding derives 03 from annual base, not rounded quarters."""
    quarters = tuple(
        Modelo180QuarterlyRetention(
            recipients=Decimal("1"),
            recipient_ids=("landlord-a",),
            base_retencion=Decimal("0.02"),
            retenciones=Decimal("0.00"),
            ingresos_especie=Decimal("0.00"),
        )
        for _ in range(4)
    )
    annual = aggregate_modelo_180_from_quarters(quarters).as_casillas()
    assert annual == {
        "01": Decimal("1"),
        "02": Decimal("0.08"),
        "03": Decimal("0.02"),
        "04": Decimal("0.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_180_2025, provided=annual, tolerance=Decimal("0.01"))
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


def test_cumulation_counts_unique_recipients_across_quarters() -> None:
    """Recurring landlords count once in annual Modelo 180 casilla 01."""
    quarters = tuple(
        Modelo180QuarterlyRetention(
            recipients=Decimal("1"),
            recipient_ids=("landlord-a",),
            base_retencion=Decimal("100.00"),
            retenciones=Decimal("19.00"),
            ingresos_especie=Decimal("0.00"),
        )
        for _ in range(4)
    )
    annual = aggregate_modelo_180_from_quarters(quarters).as_casillas()
    assert annual["01"] == Decimal("1")
    assert annual["02"] == Decimal("400.00")
    assert annual["03"] == Decimal("76.00")


def test_quarterly_recipient_count_must_match_ids() -> None:
    """Synthetic cumulation fixtures must include per-recipient identities."""
    with pytest.raises(ValueError, match="recipient count must match"):
        Modelo180QuarterlyRetention(
            recipients=Decimal("2"),
            recipient_ids=("landlord-a",),
            base_retencion=Decimal("100.00"),
            retenciones=Decimal("19.00"),
            ingresos_especie=Decimal("0.00"),
        )
