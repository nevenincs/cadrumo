"""Grounded 2025 inventory-variation projection tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.contribuyente.inventory import (
    InventoryAnexoDResult,
    InventoryLedger,
    InventoryLedgerError,
    InventoryValidationError,
    MovementKind,
    MovementRecord,
    ValuationMethod,
    compute_inventory_anexo_d_projection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _ledger(*, opening: str, purchase: str | None = None, closing: str | None = None) -> InventoryLedger:
    movements = ()
    if purchase is not None:
        movements = (
            MovementRecord(
                movement_id="purchase-1",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("1"),
                unit_cost=Decimal(purchase),
            ),
        )
    return InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal(opening),
        closing_stock=None if closing is None else Decimal(closing),
        period_movements=movements,
    )


def test_closing_over_opening_populates_only_casilla_0177() -> None:
    result = compute_inventory_anexo_d_projection(_ledger(opening="100.00", purchase="25.00"))

    assert result == InventoryAnexoDResult(
        actividad_id="retail",
        filing_year=2025,
        opening_value=Decimal("100.00"),
        closing_value=Decimal("125.00"),
        casilla_0177=Decimal("25.00"),
        casilla_0182=Decimal("0.00"),
    )


def test_opening_over_closing_populates_only_casilla_0182() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("100.00"),
        period_movements=(
            MovementRecord(
                movement_id="sale-1",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.COGS,
                quantity=Decimal("0.25"),
            ),
        ),
    )

    result = compute_inventory_anexo_d_projection(ledger)

    assert result.opening_value == Decimal("100.00")
    assert result.closing_value == Decimal("75.00")
    assert result.casilla_0177 == Decimal("0.00")
    assert result.casilla_0182 == Decimal("25.00")


def test_equal_opening_and_closing_produce_two_zeroes() -> None:
    result = compute_inventory_anexo_d_projection(_ledger(opening="100.00", closing="100.00"))

    assert result.casilla_0177 == Decimal("0.00")
    assert result.casilla_0182 == Decimal("0.00")


def test_projection_refuses_a_revision_outside_grounded_2025_scope() -> None:
    ledger = _ledger(opening="0.00").model_copy(update={"year": 2024})

    with pytest.raises(InventoryLedgerError, match="grounded only for filing year 2025"):
        compute_inventory_anexo_d_projection(ledger)


def test_projection_refuses_unadjudicated_explicit_closing_conflict() -> None:
    ledger = _ledger(opening="100.00", purchase="25.00", closing="130.00")

    with pytest.raises(InventoryLedgerError, match="explicit inventory closing conflicts"):
        compute_inventory_anexo_d_projection(ledger)


def test_result_refuses_a_split_that_does_not_match_its_audited_basis() -> None:
    with pytest.raises(ValidationError) as exc_info:
        InventoryAnexoDResult(
            actividad_id="retail",
            filing_year=2025,
            opening_value=Decimal("100.00"),
            closing_value=Decimal("125.00"),
            casilla_0177=Decimal("25.00"),
            casilla_0182=Decimal("1.00"),
        )

    assert isinstance(exc_info.value.errors()[0]["ctx"]["error"], InventoryValidationError)
