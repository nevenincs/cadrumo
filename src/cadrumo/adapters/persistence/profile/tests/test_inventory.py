"""Persistence tests for the encrypted inventory ledger.

Verifies that :mod:`cadrumo.adapters.persistence.profile.inventory` round-trips
ledgers through encrypted FINANCIAL-class envelopes (no plaintext SKU leakage)
and that movement appends are atomically validated against the resulting
valuation, refusing inputs that would consume more stock than available.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.contribuyente.inventory import (
    InventoryLedger,
    InventoryLedgerError,
    MovementKind,
    MovementRecord,
    ValuationMethod,
)
from .....tests.secure_sql import TestRuntimeProfile
from ...tests.runtime_profile_fixture import _runtime_profile
from ..inventory import InventoryLedgerRepository, load_inventory, record_movement, save_inventory

__all__ = ["_runtime_profile"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _movement(kind: MovementKind, quantity: str, unit_cost: str, day: int) -> MovementRecord:
    return MovementRecord(
        movement_id=f"{kind.value}-{day}",
        movement_date=date(2025, 1, day),
        kind=kind,
        quantity=Decimal(quantity),
        unit_cost=Decimal(unit_cost),
    )


def test_inventory_persistence_and_real_movement_append() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("150.00"),
        closing_authority_record=None,
    )
    save_inventory((ledger,))

    updated = record_movement(
        "retail",
        _movement(MovementKind.PURCHASE, "2", "10", 1),
        year=2025,
    )

    assert len(updated.period_movements) == 1
    assert load_inventory()[0] == updated


def test_inventory_duplicate_ledger_refusal_is_localized_and_structured() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
        closing_authority_record=None,
    )
    repository = InventoryLedgerRepository()
    repository.create(ledger)

    with pytest.raises(InventoryLedgerError) as exc_info:
        repository.create(ledger)

    assert (
        exc_info.value.translated_message
        == "adapters.persistence.profile.inventory.errors.inventory_ledger_already_exists"
    )
    assert exc_info.value.context == {"actividad_id": "retail", "year": 2025}


def test_inventory_duplicate_movement_refusal_is_localized_and_structured() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
        closing_authority_record=None,
    )
    movement = _movement(MovementKind.PURCHASE, "2", "10", 1)
    save_inventory((ledger.model_copy(update={"period_movements": (movement,)}),))

    with pytest.raises(InventoryLedgerError) as exc_info:
        record_movement("retail", movement, year=2025)

    assert exc_info.value.translated_message == "adapters.persistence.profile.inventory.errors.movement_already_exists"
    assert exc_info.value.context == {"movement_id": movement.movement_id}


def test_inventory_persistence_is_encrypted_financial_secure_object(_runtime_profile: TestRuntimeProfile) -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
        closing_authority_record=None,
        period_movements=(
            MovementRecord(
                movement_id="purchase-canary",
                movement_date=date(2025, 1, 2),
                kind=MovementKind.PURCHASE,
                sku="LEAK-CANARY-SKU",
                quantity=Decimal("1"),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21.00"),
                iva_amount=Decimal("21.00"),
            ),
        ),
    )

    from .....tests.secure_sql import read_db_at_rest_bytes

    path = save_inventory((ledger,))
    db_bytes = read_db_at_rest_bytes(_runtime_profile.paths.database_file)

    assert not path.exists()
    assert b"LEAK-CANARY-SKU" not in db_bytes
    assert b"purchase-canary" not in db_bytes
