"""Runtime-storage coverage for filing approval review helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage import EphemeralMasterKeyProvider
from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....domain.filing import ModeloDraft
from ....domain.submission import ModeloDraftStatus
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from .. import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    build_runtime_schema_provider,
    compute_current_approval_basis,
)
from ..testing import build_registry_filing_draft_from_decimals

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MASTER_KEY = b"m" * 32
_MODELO_130_INPUTS = {
    "01": "12500.00",
    "02": "3500.00",
    "05": "250.00",
    "06": "100.00",
    "08": "2000.00",
    "10": "10.00",
    "irpf.previous_year_economic_activity_net_income": "13000.00",
    "modelo-130-resultados-negativos-anteriores": "0.00",
    "16": "0.00",
    "18": "0.00",
}


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path):
    with override_settings(aeat_local_storage_root=tmp_path) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


def test_compute_current_approval_basis_refuses_missing_runtime_session(tmp_path: Path) -> None:
    schema_provider = build_runtime_schema_provider(modelos=("130",), filing_year=2026, period="1T")
    draft = _ready_modelo_130_draft()

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        pytest.raises(StorageValidationError, match=r"no active bucket session|route does not match"),
    ):
        compute_current_approval_basis(
            draft,
            bucket_id="bucket-a",
            schema_provider=schema_provider,
        )


def test_approval_stale_reasons_reloads_transaction_catalogue_from_runtime_default(tmp_path: Path) -> None:
    schema_provider = build_runtime_schema_provider(modelos=("130",), filing_year=2026, period="1T")
    draft = _ready_modelo_130_draft()

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="ephemeral"),
        EphemeralMasterKeyProvider(key=_MASTER_KEY),
    ):
        TransactionCatalogueRepository(bucket_id="ephemeral").save(
            TransactionCatalogue.from_transactions((_transaction("initial"),)),
        )
        approved = approve_draft(
            draft,
            bucket_id="ephemeral",
            approved_by="operator",
            schema_provider=schema_provider,
        )

        TransactionCatalogueRepository(bucket_id="ephemeral").save(
            TransactionCatalogue.from_transactions((_transaction("changed"),)),
        )
        reasons = approval_stale_reasons(
            approved,
            bucket_id="ephemeral",
            schema_provider=schema_provider,
        )

    assert ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED in reasons


def _ready_modelo_130_draft() -> ModeloDraft:
    return build_registry_filing_draft_from_decimals(
        modelo="130",
        period="1T",
        casilla_decimals=_MODELO_130_INPUTS,
        status=ModeloDraftStatus.LISTO_PARA_PRESENTAR,
    )


def _transaction(label: str) -> Transaction:
    raw = RawTransaction(
        transaction_id=f"tx-{label}",
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"filing review runtime storage {label}",
        provenance=RawProvenance(
            source_path=Path(f"/bank/{label}.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": f"filing review runtime storage {label}"},
    )
    return Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})
