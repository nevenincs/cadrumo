"""Strict roundtrip across the assets + amortizacion ledger repos.

Persists :class:`AssetsLedgerDocument` under
``cadrumo.persistence.profile.assets`` and :class:`AmortizacionLedger`
under ``cadrumo.persistence.profile.assets.amortization``, both at
``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates every defaultable field on
``AssetRecord`` with non-default values (taxable_base / iva_amount /
gross_total / deductible_iva_ratio < 1 / useful_life_years /
allocation_ratio / actividad_id / a non-empty
LibertadAmortizacionElection). The IVA-decomposition invariant on
``AssetRecord`` is satisfied so the fixture rejects only on real
identity drift, not on the model_validator's structural check.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pydantic
import pytest

from .....domain.contribuyente.assets.records import (
    AmortizacionEntry,
    AmortizacionLedger,
    AssetClass,
    AssetRecord,
    AssetsLedgerDocument,
    LibertadAmortizacionElection,
)
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ....persistence.storage.sql.engine import get_engine
from ..assets import (
    AmortizacionLedgerRepository,
    AssetsLedgerRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _populated_asset() -> AssetRecord:
    # taxable_base 10 000.00 + 21% IVA = 12 100.00 gross; 50%
    # deductible -> 1 050 non-deductible IVA rolls into cost_basis,
    # producing 11 050.00.
    return AssetRecord(
        identifier="asset-2024-laptop-pro",
        description="MacBook Pro 16 M3 Max - development workstation",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2024, 3, 15),
        cost_basis=Decimal("11050.00"),
        taxable_base=Decimal("10000.00"),
        iva_rate=Decimal("21.00"),
        iva_amount=Decimal("2100.00"),
        deductible_iva_ratio=Decimal("0.50"),
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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="0611f8c1-ff10-4ebf-8bbc-6f6cdebece7a"):
        assets_repo = AssetsLedgerRepository()
        amortizacion_repo = AmortizacionLedgerRepository()

        asset = _populated_asset()
        original_doc = AssetsLedgerDocument(assets=(asset,))
        assets_repo.save(original_doc)
        loaded_doc = assets_repo.load()

        assert loaded_doc == original_doc
        loaded_asset = loaded_doc.assets[0]
        # Per-field witnesses on the optional IVA / allocation axes.
        assert loaded_asset.taxable_base == Decimal("10000.00")
        assert loaded_asset.deductible_iva_ratio == Decimal("0.50")
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


def test_assets_ledger_dropped_cost_basis_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: corrupting the IVA decomposition must surface.

    :class:`AssetRecord` carries a model_validator that cross-checks
    ``cost_basis == taxable_base + non-deductible IVA``. The
    persistence boundary serialises every component; if the wire shape
    silently strips one, the rehydrated record's invariant will fail
    at load time (or, if it doesn't, the strict-equality witness will
    flag the drift). Persists a populated ledger, reaches into the
    encrypted SecureObjectRow via ``session_scope``, surgically
    halves the persisted ``cost_basis`` (breaking the
    ``cost_basis == taxable_base + non-deductible IVA`` cross-check),
    and asserts the load path catches the drift.

    If this test passes silently with a corrupted cost_basis, the
    assets ledger boundary is tautological and every ledger
    roundtrip in the suite is suspect.
    """

    from sqlalchemy import select

    from ...storage.secure_object_namespaces import PROFILE_ASSETS_LEDGER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="196b0b56-31ec-4598-a910-9c4ae58ff804") as profile:
        engine = get_engine(profile.settings)
        assets_repo = AssetsLedgerRepository()
        asset = _populated_asset()
        assets_repo.save(AssetsLedgerDocument(assets=(asset,)))

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_ASSETS_LEDGER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_ASSETS_LEDGER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            asset_dict = document["assets"][0]
            assert asset_dict.get("cost_basis"), (
                "fixture must serialise cost_basis onto the asset for this proof test to be meaningful"
            )
            # Halve the cost_basis so the IVA decomposition cross-
            # check fails ("cost_basis must equal taxable_base plus
            # non-deductible IVA").
            asset_dict["cost_basis"] = "5525.00"

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(
            pydantic.ValidationError,
            match="cost_basis must equal taxable_base plus non-deductible IVA",
        ):
            assets_repo.load()


def test_assets_ledger_missing_cost_basis_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: a *deleted* cost_basis must surface at load.

    The sibling test corrupts ``cost_basis`` to a wrong value; this one
    deletes the key entirely from the encrypted JSON payload. A
    save-drops-field / load-re-defaults-field regression is invisible
    to a mutation test — only an absent-field probe catches it. The
    load path must raise ``ValidationError`` (``cost_basis`` is
    required, or a re-defaulted value fails the IVA decomposition
    cross-check), never silently rehydrate an asset with no cost basis.
    """

    from sqlalchemy import select

    from ...storage.secure_object_namespaces import PROFILE_ASSETS_LEDGER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="131dcb94-9624-4ef4-8837-36e1f0212b5a") as profile:
        engine = get_engine(profile.settings)
        assets_repo = AssetsLedgerRepository()
        assets_repo.save(AssetsLedgerDocument(assets=(_populated_asset(),)))

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_ASSETS_LEDGER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_ASSETS_LEDGER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            asset_dict = document["assets"][0]
            assert "cost_basis" in asset_dict
            del asset_dict["cost_basis"]

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="cost_basis"):
            assets_repo.load()
