"""Strict roundtrip across the assets + amortization ledger repos.

Persists :class:`AssetsLedgerDocument` under
``aeat.persistence.profile.assets`` and :class:`AmortizationLedger`
under ``aeat.persistence.profile.assets.amortization``, both at
``SensitivityClass.FINANCIAL``.

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

from ...persistence.storage import EphemeralMasterKeyProvider
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
    with provider:
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


def test_assets_ledger_dropped_cost_basis_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: corrupting the VAT decomposition must surface.

    :class:`AssetRecord` carries a model_validator that cross-checks
    ``cost_basis == taxable_base + non-deductible VAT``. The
    persistence boundary serialises every component; if the wire shape
    silently strips one, the rehydrated record's invariant will fail
    at load time (or, if it doesn't, the strict-equality witness will
    flag the drift). Persists a populated ledger, reaches into the
    encrypted SecureObjectRow via ``session_scope``, surgically
    halves the persisted ``cost_basis`` (breaking the
    ``cost_basis == taxable_base + non-deductible VAT`` cross-check),
    and asserts the load path catches the drift.

    If this test passes silently with a corrupted cost_basis, the
    assets ledger boundary is tautological and every ledger
    roundtrip in the suite is suspect.
    """

    import json as _json

    from sqlalchemy import select

    from ...persistence.storage.sql._orm import SecureObjectRow
    from ...persistence.storage.sql.session import session_scope
    from .assets import _ASSETS_NAMESPACE, _LEDGER_OBJECT_KEY

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "assets-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)
            assets_repo = AssetsLedgerRepository()
            asset = _populated_asset()
            assets_repo.save(AssetsLedgerDocument(assets=(asset,)))

            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _ASSETS_NAMESPACE,
                    SecureObjectRow.object_key == _LEDGER_OBJECT_KEY,
                )
                row = session.execute(stmt).scalar_one()
                document = _json.loads(row.payload.decode("utf-8"))
                asset_dict = document["assets"][0]
                assert asset_dict.get("cost_basis"), (
                    "fixture must serialise cost_basis onto the asset "
                    "for this proof test to be meaningful"
                )
                # Halve the cost_basis so the VAT decomposition cross-
                # check fails ("cost_basis must equal taxable_base plus
                # non-deductible VAT").
                asset_dict["cost_basis"] = "5525.00"
                row.payload = _json.dumps(document).encode("utf-8")

            regression_caught = False
            try:
                assets_repo.load()
            except Exception:  # noqa: BLE001 - boundary may raise different types
                regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: corrupting cost_basis to "
                "break the VAT-decomposition cross-check did NOT surface "
                "on load. The assets ledger boundary is tautological and "
                "every ledger roundtrip in the suite is suspect."
            )
        finally:
            engine.dispose()
