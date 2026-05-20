"""Strict roundtrip across the encrypted inventory ledger repository.

Persists :class:`InventoryLedgerDocument` (a tuple of
:class:`InventoryLedger` rows) under
``aeat.persistence.profile.inventory`` at
``SensitivityClass.FINANCIAL``.

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

import pydantic
import pytest

from ....core.config import Settings
from ....domain.profile.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
    MovementKind,
    MovementRecord,
    StockLayer,
    ValuationMethod,
)
from ...persistence.storage import EphemeralMasterKeyProvider
from ...persistence.storage.sql import SecureObjectRepository
from ...persistence.storage.sql._orm import Base
from ...persistence.storage.sql.engine import create_engine_from_settings
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
    with provider:
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


def test_inventory_ledger_dropped_layer_balance_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: corrupting the opening-layer balance must surface.

    :class:`InventoryLedger` carries a model_validator that enforces
    the sum of ``opening_layers`` (quantity * unit_cost) value-
    balances with ``opening_stock``. The persistence boundary
    serialises both components; if the wire shape silently strips a
    layer or skews a unit_cost, the rehydrated ledger's invariant
    must trip.

    Persists a populated ledger, reaches into SecureObjectRow via
    ``session_scope``, surgically halves the persisted
    ``opening_stock`` (breaking the value-balance), and asserts the
    load path catches the drift via the model_validator.

    If this test ever passes silently with a corrupted
    opening_stock, the inventory ledger boundary is tautological and
    every ledger roundtrip in the suite is suspect.
    """

    import json as _json

    from sqlalchemy import select

    from ...persistence.storage.sql._orm import SecureObjectRow
    from ...persistence.storage.sql.session import session_scope
    from .inventory import _INVENTORY_NAMESPACE, _LEDGER_OBJECT_KEY

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "inventory-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)
            repo = InventoryLedgerRepository()
            ledger = _populated_ledger()
            repo.save(InventoryLedgerDocument(ledgers=(ledger,)))

            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _INVENTORY_NAMESPACE,
                    SecureObjectRow.object_key == _LEDGER_OBJECT_KEY,
                )
                row = session.execute(stmt).scalar_one()
                document = _json.loads(row.payload.decode("utf-8"))
                ledger_dict = document["ledgers"][0]
                assert ledger_dict.get("opening_stock"), (
                    "fixture must serialise opening_stock onto the ledger "
                    "for this proof test to be meaningful"
                )
                # Halve the opening_stock so the layer-balance check fails
                # (sum of layers no longer matches the declared aggregate).
                ledger_dict["opening_stock"] = "750.00"
                row.payload = _json.dumps(document).encode("utf-8")

            with pytest.raises(pydantic.ValidationError, match="opening_stock must equal the value of opening_layers"):
                repo.load()
        finally:
            engine.dispose()
