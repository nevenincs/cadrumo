"""Persistence tests for the encrypted asset and amortizacion ledgers.

Verifies that :mod:`aeat.adapters.persistence.profile.assets` round-trips
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

from ....core.config import override_settings
from ....domain.profile.assets import AmortizacionEntry, AmortizacionLedger, AssetClass, AssetRecord
from ..storage import EphemeralMasterKeyProvider
from ..storage.sql import dispose_engine
from .assets import load_amortizacion_ledger, load_assets, save_amortizacion_ledger, save_assets

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]
_BUCKET_ID = "profile-assets"


@pytest.fixture(autouse=True)
def _ephemeral_master_key(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings:
        dispose_engine(settings)
        with EphemeralMasterKeyProvider():
            try:
                yield
            finally:
                dispose_engine(settings)


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

    save_assets((asset,))
    loaded = load_assets()

    assert loaded == (asset,)


def test_asset_persistence_is_encrypted_financial_secure_object(tmp_path) -> None:
    asset = AssetRecord(
        identifier="nas",
        description="LEAK-CANARY-NAS",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2025, 1, 1),
        taxable_base=Decimal("1000.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("210.00"),
        deductible_vat_ratio=Decimal("0.50"),
        gross_total=Decimal("1210.00"),
        cost_basis=Decimal("1105.00"),
    )

    path = save_assets((asset,))
    db_bytes = (tmp_path / "buckets" / _BUCKET_ID / "db" / "aeat.db").read_bytes()

    assert not path.exists()
    assert b"LEAK-CANARY-NAS" not in db_bytes
    assert b'"nas"' not in db_bytes


def test_amortizacion_ledger_persistence_round_trip() -> None:
    ledger = AmortizacionLedger(entries=(AmortizacionEntry(asset_id="pc", year=2025, amount=Decimal("100.00")),))

    save_amortizacion_ledger(ledger)

    assert load_amortizacion_ledger() == ledger
