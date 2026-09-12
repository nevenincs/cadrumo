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

from .....domain.contribuyente.inventory.records import (
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    MovementKind,
    MovementRecord,
    ValuationMethod,
)
from .....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from ...tests.runtime_profile_fixture import default_bucket_runtime_profile_fixture
from ..inventory import InventoryLedgerRepository, record_movement
from ._inventory_acquisition_fixture import (
    acquisition_for as _acquisition_for,
)

_runtime_profile = default_bucket_runtime_profile_fixture()

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _movement(kind: MovementKind, quantity: str, unit_cost: str, day: int) -> MovementRecord:
    value = Decimal(quantity) * Decimal(unit_cost)
    return MovementRecord(
        movement_id=f"{kind.value}-{day}",
        movement_date=date(2025, 1, day),
        kind=kind,
        quantity=Decimal(quantity),
        unit_cost=Decimal(unit_cost),
        acquisition_cost=(
            _acquisition_for(value, iva_rate=Decimal("21.00"), ratio=Decimal("1.00"))
            if kind is MovementKind.PURCHASE
            else None
        ),
    )


def test_inventory_persistence_and_real_movement_append() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("150.00"),
        closing_authority_record=None,
    )
    repository = InventoryLedgerRepository()
    repository.save(InventoryLedgerDocument(ledgers=(ledger,)))

    updated = record_movement(
        "retail",
        _movement(MovementKind.PURCHASE, "2", "10", 1),
        year=2025,
    )

    assert len(updated.period_movements) == 1
    assert repository.load().ledgers[0] == updated


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
    InventoryLedgerRepository().save(
        InventoryLedgerDocument(ledgers=(ledger.model_copy(update={"period_movements": (movement,)}),)),
    )

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
                acquisition_cost=_acquisition_for(Decimal("100.00"), iva_rate=Decimal("21.00"), ratio=Decimal("1.00")),
            ),
        ),
    )

    from .....adapters.persistence.storage.tests.secure_sql import read_db_at_rest_bytes

    repository = InventoryLedgerRepository()
    repository.save(InventoryLedgerDocument(ledgers=(ledger,)))
    path = repository.envelope_path
    db_bytes = read_db_at_rest_bytes(_runtime_profile.paths.database_file)

    assert not path.exists()
    assert b"LEAK-CANARY-SKU" not in db_bytes
    assert b"purchase-canary" not in db_bytes
