"""Strict roundtrip across the assets + amortization ledger repos.

Persists :class:`AssetsLedgerDocument` under
``aeat.persistence.profile.assets`` and :class:`AmortizationLedger`
under ``aeat.persistence.profile.assets.amortization``, both at
``SensitivityClass.FINANCIAL``. Flagged as untested in the
persistence-boundary identity audit.

Anti-tautology: the fixture populates every defaultable field on
``AssetRecord`` with non-default values (taxable_base / vat_amount /
gross_total / deductible_vat_ratio < 1 / useful_life_years /
allocation_ratio / actividad_id / a non-empty
LibertadAmortizacionElection). The VAT-decomposition invariant on
``AssetRecord`` is satisfied so the fixture rejects only on real
identity drift, not on the model_validator's structural check.
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
from ....domain.profile.assets import (
    AmortizationEntry,
    AmortizationLedger,
    AssetClass,
    AssetRecord,
    AssetsLedgerDocument,
    LibertadAmortizacionElection,
)
from .assets import (
    AmortizationLedgerRepository,
    AssetsLedgerRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_asset() -> AssetRecord:
    # taxable_base 10 000.00 + 21% VAT = 12 100.00 gross; 50%
    # deductible -> 1 050 non-deductible VAT rolls into cost_basis,
    # producing 11 050.00.
    return AssetRecord(
        identifier="asset-2024-laptop-pro",
        description="MacBook Pro 16 M3 Max - development workstation",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2024, 3, 15),
        cost_basis=Decimal("11050.00"),
        taxable_base=Decimal("10000.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("2100.00"),
        deductible_vat_ratio=Decimal("0.50"),
        gross_total=Decimal("12100.00"),
        useful_life_years=4,
        libertad_amortizacion=LibertadAmortizacionElection(
            enabled=True,
            legal_basis="LIS art. 12.1.e - DT 13a",
            amount_limit=Decimal("5000.00"),
        ),
        actividad_id="iae.844",
        allocation_ratio=Decimal("0.75"),
    )


def test_assets_ledger_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AssetsLedgerDocument + AmortizationLedger roundtrip through encrypted SQL."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "assets-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        assets_repo = AssetsLedgerRepository()
        amortization_repo = AmortizationLedgerRepository()

        asset = _populated_asset()
        original_doc = AssetsLedgerDocument(assets=(asset,))
        assets_repo.save(original_doc)
        loaded_doc = assets_repo.load()

        assert loaded_doc == original_doc
        loaded_asset = loaded_doc.assets[0]
        # Per-field witnesses on the optional VAT / allocation axes.
        assert loaded_asset.taxable_base == Decimal("10000.00")
        assert loaded_asset.deductible_vat_ratio == Decimal("0.50")
        assert loaded_asset.allocation_ratio == Decimal("0.75")
        assert loaded_asset.useful_life_years == 4
        assert loaded_asset.actividad_id == "iae.844"
        assert loaded_asset.libertad_amortizacion.enabled is True
        assert loaded_asset.libertad_amortizacion.amount_limit == Decimal("5000.00")

        original_ledger = AmortizationLedger(
            entries=(
                AmortizationEntry(asset_id=asset.identifier, year=2024, amount=Decimal("2762.50")),
                AmortizationEntry(asset_id=asset.identifier, year=2025, amount=Decimal("2762.50")),
            ),
        )
        amortization_repo.save(original_ledger)
        loaded_ledger = amortization_repo.load()

        assert loaded_ledger == original_ledger
        assert len(loaded_ledger.entries) == 2
        assert loaded_ledger.entries[0].amount == Decimal("2762.50")
    finally:
        engine.dispose()
        override_master_key_provider(None)
