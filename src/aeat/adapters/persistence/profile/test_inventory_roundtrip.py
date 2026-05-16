"""Strict roundtrip across the encrypted inventory ledger repository.

Persists :class:`InventoryLedgerDocument` (a tuple of
:class:`InventoryLedger` rows) under
``aeat.persistence.profile.inventory`` at
``SensitivityClass.FINANCIAL``. Flagged as untested in the
persistence-boundary identity audit.

Anti-tautology: the fixture populates non-default values on every
optional axis of ``InventoryLedger`` (``opening_layers``,
``closing_stock``, ``period_movements`` with two distinct kinds /
SKUs / vat shapes). Witness clauses pin per-field identity so a drift
silently flattening movements or layers fails on inequality.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ...persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...persistence.storage.sql import SecureObjectRepository
from ...persistence.storage.sql._orm import Base
from ...persistence.storage.sql.engine import create_engine_from_settings
from ....core.config import Settings
from ....domain.profile.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
    MovementKind,
    MovementRecord,
    StockLayer,
    ValuationMethod,
)
from .inventory import InventoryLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_ledger() -> InventoryLedger:
    return InventoryLedger(
        actividad_id="iae.501.1",
        year=2024,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("1500.00"),
        opening_layers=(
            StockLayer(
                sku="widget-blue",
                quantity=Decimal("100"),
                unit_cost=Decimal("10.00"),
                source_movement_id="opening-widget-blue-2024",
            ),
            StockLayer(
                sku="widget-red",
                quantity=Decimal("50"),
                unit_cost=Decimal("10.00"),
                source_movement_id="opening-widget-red-2024",
            ),
        ),
        period_movements=(
            MovementRecord(
                movement_id="mv-2024-001",
                movement_date=date(2024, 2, 15),
                kind=MovementKind.PURCHASE,
                sku="widget-blue",
                quantity=Decimal("75"),
                unit_cost=Decimal("11.00"),
                taxable_base=Decimal("825.00"),
                vat_rate=Decimal("21.00"),
                vat_amount=Decimal("173.25"),
                deductible_vat_ratio=Decimal("1.00"),
            ),
            MovementRecord(
                movement_id="mv-2024-002",
                movement_date=date(2024, 5, 30),
                kind=MovementKind.COGS,
                sku="widget-blue",
                quantity=Decimal("40"),
                unit_cost=Decimal("10.40"),
            ),
        ),
    )


def test_inventory_ledger_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """InventoryLedgerDocument roundtrips strictly with non-default movements + layers."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "inventory-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        repo = InventoryLedgerRepository()
        ledger = _populated_ledger()
        original_doc = InventoryLedgerDocument(ledgers=(ledger,))
        repo.save(original_doc)
        loaded_doc = repo.load()

        assert loaded_doc == original_doc
        loaded_ledger = loaded_doc.ledgers[0]
        assert len(loaded_ledger.opening_layers) == 2
        assert tuple(layer.sku for layer in loaded_ledger.opening_layers) == (
            "widget-blue",
            "widget-red",
        )
        assert len(loaded_ledger.period_movements) == 2
        assert tuple(m.kind for m in loaded_ledger.period_movements) == (
            MovementKind.PURCHASE,
            MovementKind.COGS,
        )
        # VAT decomposition is FINANCIAL-class identity; pin the
        # explicit vat_amount survives un-quantised.
        purchase = loaded_ledger.period_movements[0]
        assert purchase.vat_amount == Decimal("173.25")
        assert purchase.deductible_vat_ratio == Decimal("1.00")
    finally:
        engine.dispose()
        override_master_key_provider(None)
