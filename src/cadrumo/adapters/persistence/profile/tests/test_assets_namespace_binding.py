"""Registry-definition binding proof for the dual-namespace assets repos.

``assets.py`` persists two distinct secure-object families — the assets ledger
(``PROFILE_ASSETS_LEDGER_NAMESPACE``) and the amortization ledger
(``PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE``). Each family's
``classification`` and envelope ``schema_version`` MUST be single-sourced from
its OWN registry
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`, not a
shared ``SensitivityClass`` literal — so a cross-namespace metadata swap between
the two ledgers cannot slip through.

This is a write-path proof: it drives the real ``AssetsLedgerRepository.save``
and ``AmortizacionLedgerRepository.save`` against a genuine encrypted bucket,
then reads the raw :class:`SecureObjectRow` back for each namespace and asserts
the persisted classification and schema_version equal exactly what that
namespace's registry def declares.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from .....domain.contribuyente.assets.records import (
    AmortizacionEntry,
    AmortizacionLedger,
    AssetClass,
    AssetRecord,
    AssetsLedgerDocument,
    LibertadAmortizacionElection,
)
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage.sql import SecureObjectRow
from ....persistence.storage.sql.session import session_scope
from ...storage.secure_object_namespaces import (
    PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
    PROFILE_ASSETS_LEDGER_NAMESPACE,
)
from ..assets import AmortizacionLedgerRepository, AssetsLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _asset() -> AssetRecord:
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


def test_assets_and_amortizacion_rows_carry_registry_declared_metadata(tmp_path: Path) -> None:
    """Each assets ledger row persists the metadata its OWN registry def declares."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="07ad11f2-1869-491d-b4d4-9a86bc7e450a") as profile:
        asset = _asset()
        AssetsLedgerRepository().save(AssetsLedgerDocument(assets=(asset,)))
        AmortizacionLedgerRepository().save(
            AmortizacionLedger(
                entries=(AmortizacionEntry(asset_id=asset.identifier, year=2024, amount=Decimal("2762.50")),),
            ),
        )

        with session_scope(profile.repository._engine) as session:
            rows = {row.namespace: row for row in session.execute(select(SecureObjectRow)).scalars().all()}

    for definition in (PROFILE_ASSETS_LEDGER_NAMESPACE, PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE):
        assert definition.namespace in rows, f"expected a persisted row under {definition.namespace!r}"
        row = rows[definition.namespace]
        assert row.classification == definition.sensitivity.value, (
            f"persisted classification {row.classification!r} for {definition.namespace!r} diverges from "
            f"registry def {definition.sensitivity.value!r}"
        )
        assert row.schema_version == definition.schema_version
