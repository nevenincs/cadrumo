"""Tests for actividad economica inventory ledgers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ....core.errors import get_registered_error_code
from ...formulas import ValuationMethod
from ..errors import InventoryLedgerError, LIFOForbiddenError
from . import (
    InventoryLedger,
    MovementKind,
    MovementRecord,
    StockLayer,
    compute_anexo_d_inventory_variation,
    compute_inventory_valuation,
    compute_inventory_variation,
    load_inventory,
    parse_valuation_method,
    record_movement,
    save_inventory,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _movement(kind: MovementKind, quantity: str, unit_cost: str, day: int) -> MovementRecord:
    return MovementRecord(
        movement_id=f"{kind.value}-{day}",
        movement_date=date(2025, 1, day),
        kind=kind,
        quantity=Decimal(quantity),
        unit_cost=Decimal(unit_cost),
    )


@pytest.fixture(autouse=True)
def _ephemeral_master_key() -> Iterator[None]:
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)


def test_lifo_is_refused_with_lis_art_17_citation() -> None:
    with pytest.raises(LIFOForbiddenError) as exc_info:
        parse_valuation_method("lifo")

    assert "LIS art. 17.1" in str(exc_info.value)
    assert get_registered_error_code(LIFOForbiddenError).code == "REFUSED_PROFILE_INVENTORY_LIFO"


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (ValuationMethod.FIFO, Decimal("450.00")),
        (ValuationMethod.PMP, Decimal("437.50")),
        (ValuationMethod.COSTE_MEDIO, Decimal("437.50")),
    ],
)
def test_inventory_variation_by_method(method: ValuationMethod, expected: Decimal) -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=method,
        opening_stock=Decimal("1000.00"),
        opening_layers=(
            StockLayer(
                sku="default",
                quantity=Decimal("100"),
                unit_cost=Decimal("10.00"),
                source_movement_id="opening",
            ),
        ),
        period_movements=(
            _movement(MovementKind.PURCHASE, "10", "20", 3),
            _movement(MovementKind.PURCHASE, "10", "30", 4),
            _movement(MovementKind.COGS, "5", "0", 5),
        ),
    )

    assert compute_inventory_variation(ledger, 2025) == expected


def test_explicit_closing_stock_wins_for_variation() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("1000.00"),
        closing_stock=Decimal("850.00"),
    )

    assert compute_inventory_variation(ledger, 2025) == Decimal("-150.00")


def test_inventory_persistence_and_real_movement_append(tmp_path) -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("150.00"),
    )
    save_inventory((ledger,), storage_dir=tmp_path)

    updated = record_movement(
        "retail",
        _movement(MovementKind.PURCHASE, "2", "10", 1),
        year=2025,
        storage_dir=tmp_path,
    )

    assert len(updated.period_movements) == 1
    assert load_inventory(storage_dir=tmp_path)[0] == updated


def test_inventory_persistence_is_encrypted_financial_envelope(tmp_path) -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
        period_movements=(
            MovementRecord(
                movement_id="purchase-canary",
                movement_date=date(2025, 1, 2),
                kind=MovementKind.PURCHASE,
                sku="LEAK-CANARY-SKU",
                quantity=Decimal("1"),
                taxable_base=Decimal("100.00"),
                vat_rate=Decimal("21.00"),
                vat_amount=Decimal("21.00"),
            ),
        ),
    )

    path = save_inventory((ledger,), storage_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert '"classification":"financial"' in text
    assert '"encryption":' in text
    assert "LEAK-CANARY-SKU" not in text


def test_fifo_consumes_oldest_layers() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("150.00"),
        opening_layers=(
            StockLayer(sku="ssd", quantity=Decimal("5"), unit_cost=Decimal("10.00"), source_movement_id="open-a"),
            StockLayer(sku="ssd", quantity=Decimal("5"), unit_cost=Decimal("20.00"), source_movement_id="open-b"),
        ),
        period_movements=(
            MovementRecord(
                movement_id="sale-1",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.COGS,
                sku="ssd",
                quantity=Decimal("7"),
            ),
        ),
    )

    result = compute_inventory_valuation(ledger)

    assert result.cogs_value == Decimal("90.00")
    assert result.closing_value == Decimal("60.00")
    assert compute_inventory_variation(ledger, 2025) == Decimal("-90.00")


def test_negative_stock_is_refused() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("10.00"),
        opening_layers=(
            StockLayer(sku="ssd", quantity=Decimal("1"), unit_cost=Decimal("10.00"), source_movement_id="open-a"),
        ),
        period_movements=(
            MovementRecord(
                movement_id="sale-too-many",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.COGS,
                sku="ssd",
                quantity=Decimal("2"),
            ),
        ),
    )

    with pytest.raises(InventoryLedgerError, match="consume more stock"):
        compute_inventory_valuation(ledger)


def test_weighted_average_keeps_sku_pools_separate() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.PMP,
        opening_stock=Decimal("300.00"),
        opening_layers=(
            StockLayer(sku="ssd", quantity=Decimal("10"), unit_cost=Decimal("10.00"), source_movement_id="open-ssd"),
            StockLayer(sku="ram", quantity=Decimal("10"), unit_cost=Decimal("20.00"), source_movement_id="open-ram"),
        ),
        period_movements=(
            MovementRecord(
                movement_id="sale-ssd",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.COGS,
                sku="ssd",
                quantity=Decimal("10"),
            ),
        ),
    )

    result = compute_inventory_valuation(ledger)

    assert result.cogs_value == Decimal("100.00")
    assert result.closing_value == Decimal("200.00")
    assert tuple(layer.sku for layer in result.closing_layers) == ("ram",)


def test_opening_stock_must_match_opening_layers() -> None:
    with pytest.raises(ValidationError, match="opening_stock"):
        InventoryLedger(
            actividad_id="retail",
            year=2025,
            valuation_method=ValuationMethod.FIFO,
            opening_stock=Decimal("100.00"),
            opening_layers=(
                StockLayer(
                    sku="ssd",
                    quantity=Decimal("10"),
                    unit_cost=Decimal("20.00"),
                    source_movement_id="open",
                ),
            ),
        )


def test_record_movement_refuses_invalid_negative_stock(tmp_path) -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("10.00"),
        opening_layers=(
            StockLayer(sku="ssd", quantity=Decimal("1"), unit_cost=Decimal("10.00"), source_movement_id="open-a"),
        ),
    )
    save_inventory((ledger,), storage_dir=tmp_path)

    with pytest.raises(InventoryLedgerError, match="consume more stock"):
        record_movement(
            "retail",
            MovementRecord(
                movement_id="sale-too-many",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.COGS,
                sku="ssd",
                quantity=Decimal("2"),
            ),
            year=2025,
            storage_dir=tmp_path,
        )


def test_multi_actividad_ledgers_are_separate() -> None:
    ledgers = (
        InventoryLedger(
            actividad_id="consulting",
            year=2025,
            valuation_method=ValuationMethod.FIFO,
            opening_stock=Decimal("0.00"),
            closing_stock=Decimal("0.00"),
        ),
        InventoryLedger(
            actividad_id="retail",
            year=2025,
            valuation_method=ValuationMethod.FIFO,
            opening_stock=Decimal("1000.00"),
            closing_stock=Decimal("1200.00"),
        ),
    )

    assert compute_anexo_d_inventory_variation(2025, "consulting", ledgers=ledgers) == Decimal("0.00")
    assert compute_anexo_d_inventory_variation(2025, "retail", ledgers=ledgers) == Decimal("200.00")
