"""Persistence tests for encrypted asset ledgers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....domain.formulas import AssetClass
from ....domain.profile.assets import AmortizationEntry, AssetRecord, LibertadAmortizacionElection
from ..storage import EphemeralMasterKeyProvider, override_master_key_provider
from .assets import load_amortization_ledger, load_assets, record_amortization, save_assets

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


@pytest.fixture(autouse=True)
def _ephemeral_master_key() -> Iterator[None]:
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)


def _asset(identifier: str, asset_class: AssetClass, cost_basis: str = "10000.00") -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=f"asset {identifier}",
        asset_class=asset_class,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal(cost_basis),
    )


def test_asset_persistence_round_trip(tmp_path) -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)

    save_assets((asset,), storage_dir=tmp_path)
    loaded = load_assets(storage_dir=tmp_path)

    assert loaded == (asset,)


def test_asset_persistence_is_encrypted_financial_envelope(tmp_path) -> None:
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

    path = save_assets((asset,), storage_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert '"classification":"financial"' in text
    assert '"encryption":' in text
    assert "LEAK-CANARY-NAS" not in text


def test_record_amortization_persists_real_ledger(tmp_path) -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)

    record_amortization(asset, 2025, storage_dir=tmp_path)
    ledger = load_amortization_ledger(storage_dir=tmp_path)

    assert ledger.entries == (AmortizationEntry(asset_id="pc", year=2025, amount=Decimal("2500.00")),)


def test_record_amortization_is_idempotent_for_existing_year(tmp_path) -> None:
    asset = AssetRecord(
        identifier="robot",
        description="robot",
        asset_class=AssetClass.MAQUINARIA_GENERAL,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal("12000.00"),
        libertad_amortizacion=LibertadAmortizacionElection(enabled=True, legal_basis="LIS art. 12.5"),
    )

    record_amortization(asset, 2025, storage_dir=tmp_path)
    record_amortization(asset, 2025, storage_dir=tmp_path)
    ledger = load_amortization_ledger(storage_dir=tmp_path)

    assert ledger.entries == (AmortizationEntry(asset_id="robot", year=2025, amount=Decimal("12000.00")),)
