"""Unit tests for the LIS art. 12.1.a) amortization table + LIS art. 17 inventory model.

Closes the claude vaultspec-code-review M1 finding: the foundational
types `AmortizationCategory` and `InventoryRecord` were "exported but
uncalled". This test file exercises the construction surface, verifies
the LIS-table data integrity, and confirms LIFO is rejected by Pydantic
construction (LIS art. 17.6 enforced structurally rather than
runtime-checked).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ._amortization import (
    LIS_ART_12_LINEAL_TABLE,
    AmortizationCategory,
    AssetClass,
)
from ._inventario import InventoryRecord, ValuationMethod

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestAmortizationCategory:
    """LIS art. 12.1.a) tabla lineal — Pydantic v2 strict frozen extra=forbid."""

    def test_construct_obra_civil_general(self) -> None:
        """LIS art. 12.1.a) row 1: obra civil general 2 % / 100 años."""
        category = AmortizationCategory(
            asset_class=AssetClass.OBRA_CIVIL_GENERAL,
            coef_max_pct=Decimal("2.00"),
            period_max_years=100,
        )
        assert category.asset_class is AssetClass.OBRA_CIVIL_GENERAL
        assert category.coef_max_pct == Decimal("2.00")
        assert category.period_max_years == 100

    def test_extra_field_rejected(self) -> None:
        """ConfigDict(extra='forbid') must reject unknown fields."""
        with pytest.raises(ValidationError):
            AmortizationCategory.model_validate(
                {
                    "asset_class": AssetClass.MAQUINARIA_GENERAL,
                    "coef_max_pct": Decimal("12.00"),
                    "period_max_years": 18,
                    "unknown_field": "bogus",
                }
            )

    def test_frozen_assignment_rejected(self) -> None:
        """ConfigDict(frozen=True) must reject post-construction mutation."""
        category = AmortizationCategory(
            asset_class=AssetClass.MAQUINARIA_GENERAL,
            coef_max_pct=Decimal("12.00"),
            period_max_years=18,
        )
        with pytest.raises(ValidationError):
            category.coef_max_pct = Decimal("20.00")  # type: ignore[misc]


class TestLISArt12LinealTable:
    """The LIS art. 12.1.a) lineal amortization table is the load-bearing
    data structure for Anexo D normal's caller-supplied amortizacion
    (casilla 0173). Verify the BOE-published values are encoded verbatim.
    """

    def test_table_has_33_categories(self) -> None:
        """LIS art. 12.1.a) publishes exactly 33 asset categories
        (verified against BOE-A-2014-12328 consolidated text).
        """
        assert len(LIS_ART_12_LINEAL_TABLE) == 33

    def test_each_category_unique(self) -> None:
        """No duplicate asset classes in the table."""
        asset_classes = [c.asset_class for c in LIS_ART_12_LINEAL_TABLE]
        assert len(asset_classes) == len(set(asset_classes))

    @pytest.mark.parametrize(
        ("asset_class", "expected_coef", "expected_years"),
        [
            # Spot-checks across the table — high-frequency assets used
            # by autonomos para LIS art. 12 amortizacion.
            (AssetClass.OBRA_CIVIL_GENERAL, Decimal("2.00"), 100),
            (AssetClass.EDIFICIOS_INDUSTRIALES, Decimal("3.00"), 68),
            (AssetClass.EDIFICIOS_COMERCIALES, Decimal("2.00"), 100),
            (AssetClass.MAQUINARIA_GENERAL, Decimal("12.00"), 18),
            (AssetClass.TRANSPORTE_AUTOCAMIONES, Decimal("20.00"), 10),
            (AssetClass.MOBILIARIO_GENERAL, Decimal("10.00"), 20),
            (AssetClass.ELECTRONICA_INFORMATICA, Decimal("25.00"), 8),
            (AssetClass.ELECTRONICA_SOFTWARE, Decimal("33.00"), 6),
            (AssetClass.OTROS_ELEMENTOS, Decimal("10.00"), 20),
        ],
    )
    def test_spot_check_table_values(
        self,
        asset_class: AssetClass,
        expected_coef: Decimal,
        expected_years: int,
    ) -> None:
        """Verify selected high-traffic categories match BOE values."""
        match = next((c for c in LIS_ART_12_LINEAL_TABLE if c.asset_class is asset_class), None)
        assert match is not None, f"AssetClass.{asset_class.name} missing from table"
        assert match.coef_max_pct == expected_coef
        assert match.period_max_years == expected_years


class TestValuationMethod:
    """LIS art. 17.6: LIFO is forbidden for tax purposes. The closed enum
    excludes LIFO so any attempt to construct an InventoryRecord with
    LIFO as its method fails at the Pydantic field level.
    """

    def test_only_three_valuation_methods(self) -> None:
        assert {m.value for m in ValuationMethod} == {"fifo", "pmp", "coste_medio"}

    def test_lifo_not_in_enum(self) -> None:
        """LIFO is not a member of the closed StrEnum — cannot be
        instantiated even via string lookup."""
        assert "lifo" not in {m.value for m in ValuationMethod}
        with pytest.raises(ValueError):
            ValuationMethod("lifo")


class TestInventoryRecord:
    """LIS art. 17 inventory snapshot — Pydantic v2 strict frozen extra=forbid."""

    def test_construct_fifo_record(self) -> None:
        record = InventoryRecord(
            method=ValuationMethod.FIFO,
            initial_value=Decimal("10000.00"),
            final_value=Decimal("12000.00"),
        )
        assert record.method is ValuationMethod.FIFO
        assert record.final_value - record.initial_value == Decimal("2000.00")

    def test_construct_pmp_record(self) -> None:
        record = InventoryRecord(
            method=ValuationMethod.PMP,
            initial_value=Decimal("5500.00"),
            final_value=Decimal("4750.00"),
        )
        # Variación negativa = ingredientes consumidos > comprados durante el año.
        assert record.final_value - record.initial_value == Decimal("-750.00")

    def test_construct_coste_medio_record(self) -> None:
        record = InventoryRecord(
            method=ValuationMethod.COSTE_MEDIO,
            initial_value=Decimal("0.00"),
            final_value=Decimal("3500.00"),
        )
        assert record.method is ValuationMethod.COSTE_MEDIO

    def test_lifo_rejected_at_construction(self) -> None:
        """Direct attempt to construct with LIFO string fails — the
        StrEnum doesn't accept "lifo" as a member."""
        with pytest.raises(ValidationError):
            InventoryRecord.model_validate(
                {
                    "method": "lifo",  # not a member of ValuationMethod
                    "initial_value": Decimal("1000.00"),
                    "final_value": Decimal("1500.00"),
                }
            )

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InventoryRecord.model_validate(
                {
                    "method": ValuationMethod.FIFO,
                    "initial_value": Decimal("100.00"),
                    "final_value": Decimal("150.00"),
                    "method_v2": "lifo_workaround",  # would-be smuggle attempt
                }
            )

    def test_frozen_assignment_rejected(self) -> None:
        record = InventoryRecord(
            method=ValuationMethod.FIFO,
            initial_value=Decimal("100.00"),
            final_value=Decimal("150.00"),
        )
        with pytest.raises(ValidationError):
            record.initial_value = Decimal("200.00")  # type: ignore[misc]


class TestAmortizationWorkedExample:
    """Demonstrates how a caller would use AmortizationCategory + the
    LIS table to derive Anexo D normal's casilla 0173 (amortización del
    inmovilizado) before supplying it to the engine.
    """

    def test_caller_derives_0173_amortizacion_from_table(self) -> None:
        """Worked example: caller has a 30.000 EUR computer (LIS asset
        class ELECTRONICA_INFORMATICA, max coef 25 % / 8 years) and a
        50.000 EUR delivery van (TRANSPORTE_AUTOCAMIONES, 20 % / 10 years).

        Year-1 amortizacion at max coefficient:
            30.000 * 0.25 = 7.500  (computer)
          + 50.000 * 0.20 = 10.000 (van)
          = 17.500 EUR  -> casilla 0173
        """
        # Look up max coefs from the table.
        computer_cat = next(c for c in LIS_ART_12_LINEAL_TABLE if c.asset_class is AssetClass.ELECTRONICA_INFORMATICA)
        van_cat = next(c for c in LIS_ART_12_LINEAL_TABLE if c.asset_class is AssetClass.TRANSPORTE_AUTOCAMIONES)

        computer_amortizacion = Decimal("30000.00") * (computer_cat.coef_max_pct / Decimal("100"))
        van_amortizacion = Decimal("50000.00") * (van_cat.coef_max_pct / Decimal("100"))
        casilla_0173 = computer_amortizacion + van_amortizacion

        assert casilla_0173 == Decimal("17500.00")
