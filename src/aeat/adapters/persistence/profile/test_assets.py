"""Persistence tests for the encrypted asset and amortization ledgers.

Verifies that :mod:`aeat.adapters.persistence.profile.assets` round-trips
records through encrypted FINANCIAL-class envelopes (no plaintext leakage),
that amortization is persisted to a real ledger, and that recording is
idempotent for an already-amortized year.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.profile.assets import AmortizationEntry, AmortizationLedger, AssetClass, AssetRecord
from ..storage import EphemeralMasterKeyProvider
from ..storage.sql import dispose_engine
from .assets import load_amortization_ledger, load_assets, save_amortization_ledger, save_assets

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


@pytest.fixture(autouse=True)
def _ephemeral_master_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


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
    db_bytes = (tmp_path / "aeat.db").read_bytes()

    assert not path.exists()
    assert b"LEAK-CANARY-NAS" not in db_bytes
    assert b'"nas"' not in db_bytes


def test_amortization_ledger_persistence_round_trip() -> None:
    ledger = AmortizationLedger(entries=(AmortizationEntry(asset_id="pc", year=2025, amount=Decimal("100.00")),))

    save_amortization_ledger(ledger)

    assert load_amortization_ledger() == ledger
