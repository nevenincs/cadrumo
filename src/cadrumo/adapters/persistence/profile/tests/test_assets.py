"""Persistence tests for the encrypted asset and amortizacion ledgers.

Verifies that :mod:`cadrumo.adapters.persistence.profile.assets` round-trips
records through encrypted FINANCIAL-class envelopes (no plaintext leakage),
that amortizacion is persisted to a real ledger, and that recording is
idempotent for an already-amortized year.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....domain.contribuyente.assets.records import (
    AmortizacionEntry,
    AmortizacionLedger,
    AssetClass,
    AssetRecord,
    AssetRecordError,
    AssetsLedgerDocument,
)
from .....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..assets import (
    AmortizacionLedgerRepository,
    AssetsLedgerRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    # Distinct bucket_id (not the shared default) so the bucket-scoped master-key
    # session does not collide with other assets test modules sharing a bucket in
    # the same run — a previously-observed cross-module empty-load flake.
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="eab5682c-b62e-4dd7-9480-b7761fdb62af") as profile:
        yield profile


def _asset(identifier: str, asset_class: AssetClass, cost_basis: str = "10000.00") -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=f"asset {identifier}",
        asset_class=asset_class,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal(cost_basis),
    )


def test_asset_persistence_round_trip() -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)
    repository = AssetsLedgerRepository()

    repository.save(AssetsLedgerDocument(assets=(asset,)))
    loaded = repository.load().assets

    assert loaded == (asset,)


def test_asset_duplicate_refusal_is_localized_and_structured() -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)
    repository = AssetsLedgerRepository()
    repository.add(asset)

    with pytest.raises(AssetRecordError) as exc_info:
        repository.add(asset)

    assert exc_info.value.translated_message == "adapters.persistence.profile.assets.errors.asset_already_exists"
    assert exc_info.value.context == {"asset_id": "pc"}


def test_asset_persistence_is_encrypted_financial_secure_object(_runtime_profile: TestRuntimeProfile) -> None:
    asset = AssetRecord(
        identifier="nas",
        description="LEAK-CANARY-NAS",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2025, 1, 1),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21.00"),
        iva_amount=Decimal("210.00"),
        deductible_iva_ratio=Decimal("0.50"),
        gross_total=Decimal("1210.00"),
        cost_basis=Decimal("1105.00"),
    )

    from .....tests.secure_sql import read_db_at_rest_bytes

    repository = AssetsLedgerRepository()
    repository.save(AssetsLedgerDocument(assets=(asset,)))
    path = repository.envelope_path
    db_bytes = read_db_at_rest_bytes(_runtime_profile.paths.database_file)

    assert not path.exists()
    assert b"LEAK-CANARY-NAS" not in db_bytes
    assert b'"nas"' not in db_bytes


def test_amortizacion_ledger_persistence_round_trip() -> None:
    ledger = AmortizacionLedger(entries=(AmortizacionEntry(asset_id="pc", year=2025, amount=Decimal("100.00")),))
    repository = AmortizacionLedgerRepository()

    repository.save(ledger)

    assert repository.load() == ledger
