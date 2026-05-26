"""Strict roundtrip across the assets + amortizacion ledger repos.

Persists :class:`AssetsLedgerDocument` under
``aeat.persistence.profile.assets`` and :class:`AmortizacionLedger`
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

import pydantic
import pytest

from ....core.config import override_settings
from ....domain.profile.assets import (
    AmortizacionEntry,
    AmortizacionLedger,
    AssetClass,
    AssetRecord,
    AssetsLedgerDocument,
    LibertadAmortizacionElection,
)
from ...persistence.storage import EphemeralMasterKeyProvider
from ...persistence.storage.sql import SecureObjectRepository
from ...persistence.storage.sql.engine import create_engine_from_settings, dispose_engine
from .assets import (
    AmortizacionLedgerRepository,
    AssetsLedgerRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]
_BUCKET_ID = "profile-assets-roundtrip"


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
) -> None:
    """AssetsLedgerDocument + AmortizacionLedger roundtrip through encrypted SQL."""

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings,
        EphemeralMasterKeyProvider(),
    ):
        engine = create_engine_from_settings(settings)
        try:
            objects = SecureObjectRepository(engine=engine)

            assets_repo = AssetsLedgerRepository(objects=objects)
            amortizacion_repo = AmortizacionLedgerRepository(objects=objects)

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

            original_ledger = AmortizacionLedger(
                entries=(
                    AmortizacionEntry(asset_id=asset.identifier, year=2024, amount=Decimal("2762.50")),
                    AmortizacionEntry(asset_id=asset.identifier, year=2025, amount=Decimal("2762.50")),
                ),
            )
            amortizacion_repo.save(original_ledger)
            loaded_ledger = amortizacion_repo.load()

            assert loaded_ledger == original_ledger
            assert len(loaded_ledger.entries) == 2
            assert loaded_ledger.entries[0].amount == Decimal("2762.50")
        finally:
            engine.dispose()
            dispose_engine(settings)


def test_assets_ledger_dropped_cost_basis_surfaces_at_load(
    tmp_path: Path,
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

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings,
        EphemeralMasterKeyProvider(),
    ):
        engine = create_engine_from_settings(settings)
        try:
            objects = SecureObjectRepository(engine=engine)
            assets_repo = AssetsLedgerRepository(objects=objects)
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

            with pytest.raises(
                pydantic.ValidationError,
                match="cost_basis must equal taxable_base plus non-deductible VAT",
            ):
                assets_repo.load()
        finally:
            engine.dispose()
            dispose_engine(settings)


def test_assets_ledger_missing_cost_basis_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: a *deleted* cost_basis must surface at load.

    The sibling test corrupts ``cost_basis`` to a wrong value; this one
    deletes the key entirely from the encrypted JSON payload. A
    save-drops-field / load-re-defaults-field regression is invisible
    to a mutation test — only an absent-field probe catches it. The
    load path must raise ``ValidationError`` (``cost_basis`` is
    required, or a re-defaulted value fails the VAT decomposition
    cross-check), never silently rehydrate an asset with no cost basis.
    """

    import json as _json

    from sqlalchemy import select

    from ...persistence.storage.sql._orm import SecureObjectRow
    from ...persistence.storage.sql.session import session_scope
    from .assets import _ASSETS_NAMESPACE, _LEDGER_OBJECT_KEY

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings,
        EphemeralMasterKeyProvider(),
    ):
        engine = create_engine_from_settings(settings)
        try:
            objects = SecureObjectRepository(engine=engine)
            assets_repo = AssetsLedgerRepository(objects=objects)
            assets_repo.save(AssetsLedgerDocument(assets=(_populated_asset(),)))

            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _ASSETS_NAMESPACE,
                    SecureObjectRow.object_key == _LEDGER_OBJECT_KEY,
                )
                row = session.execute(stmt).scalar_one()
                document = _json.loads(row.payload.decode("utf-8"))
                asset_dict = document["assets"][0]
                assert "cost_basis" in asset_dict
                del asset_dict["cost_basis"]
                row.payload = _json.dumps(document).encode("utf-8")

            with pytest.raises(pydantic.ValidationError, match="cost_basis"):
                assets_repo.load()
        finally:
            engine.dispose()
            dispose_engine(settings)
