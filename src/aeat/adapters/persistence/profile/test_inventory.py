"""Persistence tests for the encrypted inventory ledger.

Verifies that :mod:`aeat.adapters.persistence.profile.inventory` round-trips
ledgers through encrypted FINANCIAL-class envelopes (no plaintext SKU leakage)
and that movement appends are atomically validated against the resulting
valuation, refusing inputs that would consume more stock than available.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....domain.profile.errors import InventoryLedgerError
from ....domain.profile.inventory import InventoryLedger, MovementKind, MovementRecord, StockLayer, ValuationMethod
from ..storage import EphemeralMasterKeyProvider
from ..storage.sql import dispose_engine
from .inventory import load_inventory, record_movement, save_inventory

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]
_BUCKET_ID = "profile-inventory"


@pytest.fixture(autouse=True)
def _ephemeral_master_key(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings:
        dispose_engine(settings)
        with EphemeralMasterKeyProvider():
            try:
                yield
            finally:
                dispose_engine(settings)


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
    )
    save_inventory((ledger,))

    updated = record_movement(
        "retail",
        _movement(MovementKind.PURCHASE, "2", "10", 1),
        year=2025,
    )

    assert len(updated.period_movements) == 1
    assert load_inventory()[0] == updated


def test_inventory_persistence_is_encrypted_financial_secure_object(tmp_path) -> None:
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

    path = save_inventory((ledger,))
    db_bytes = (tmp_path / "buckets" / _BUCKET_ID / "db" / "aeat.db").read_bytes()

    assert not path.exists()
    assert b"LEAK-CANARY-SKU" not in db_bytes
    assert b"purchase-canary" not in db_bytes


def test_record_movement_refuses_invalid_negative_stock() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("10.00"),
        opening_layers=(
            StockLayer(sku="ssd", quantity=Decimal("1"), unit_cost=Decimal("10.00"), source_movement_id="open-a"),
        ),
    )
    save_inventory((ledger,))

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
        )
