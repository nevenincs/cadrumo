"""Real encrypted-SQL regression for the profile bare-model persistence kernel."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument, ValuationMethod
from ...storage.secure_object_namespaces import PROFILE_INVENTORY_LEDGER_NAMESPACE
from ...storage.tests.secure_sql import (
    interleave_write_after_first_singleton_select,
    isolated_runtime_profile,
    read_db_at_rest_bytes,
    secure_object_select_log,
)
from ..inventory import InventoryLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _document(identifier: str) -> InventoryLedgerDocument:
    """Build a non-default bare singleton payload for one observation test."""
    return InventoryLedgerDocument(
        ledgers=(
            InventoryLedger(
                actividad_id=f"KERNEL-SECRET-{identifier}",
                year=date.today().year,
                valuation_method=ValuationMethod.FIFO,
                opening_stock=Decimal("100.00"),
                closing_authority_record=None,
            ),
        ),
    )


def test_inventory_repository_roundtrips_a_strict_document_as_encrypted_registry_governed_bytes(
    tmp_path: Path,
) -> None:
    """The public inventory repository never creates plaintext or an ungoverned row."""
    document = _document("kernel-canary")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a0e10fc6-03c5-4290-832a-fcb4c7654fe4") as profile:
        repository = InventoryLedgerRepository(
            objects=profile.repository,
        )

        repository.save(document)

        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert repository.load() == document
        record = profile.repository.load(
            PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace,
            PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
            expected_class=PROFILE_INVENTORY_LEDGER_NAMESPACE.sensitivity,
            max_supported_version=PROFILE_INVENTORY_LEDGER_NAMESPACE.schema_version,
        )
        assert record is not None

    assert record.namespace == PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace
    assert record.classification is PROFILE_INVENTORY_LEDGER_NAMESPACE.sensitivity
    assert record.schema_version == PROFILE_INVENTORY_LEDGER_NAMESPACE.schema_version
    assert b"KERNEL-SECRET-ASSET" not in at_rest
    assert b"kernel-canary" not in at_rest


def test_inventory_repository_load_returns_one_document_across_an_interleaving(
    tmp_path: Path,
) -> None:
    """One live SQL SELECT cannot pair a first payload with a later revision."""
    first = _document("first")
    second = _document("second")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="ae1c1f6a-dde4-4dda-a3d5-4ef005b70129") as profile:
        repository = InventoryLedgerRepository(objects=profile.repository)
        repository.save(first)
        writer = InventoryLedgerRepository(objects=profile.repository)
        with interleave_write_after_first_singleton_select(
            profile.repository.engine, lambda: writer.save(second)
        ) as interleave:
            observed = repository.load()

    assert interleave.fired
    assert len(interleave.selects) == 1
    assert observed == first


def test_inventory_repository_load_observes_an_absent_singleton_with_one_select(
    tmp_path: Path,
) -> None:
    """The absent singleton outcome also comes from exactly one encrypted-SQL read."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="04ff919d-3023-4ea3-b177-1b4e9fca0f40") as profile:
        repository = InventoryLedgerRepository(objects=profile.repository)
        with secure_object_select_log(profile.repository.engine) as selects:
            observed = repository.load()

    assert len(selects) == 1
    assert observed == InventoryLedgerDocument()
