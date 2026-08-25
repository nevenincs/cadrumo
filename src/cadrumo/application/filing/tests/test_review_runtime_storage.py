"""Runtime-storage coverage for filing approval review helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.errors import StorageValidationError
from ....core import CasillaId, Period, validated_casilla_id
from ....core.config import override_settings
from ....core.hashing import content_hash_hex
from ....domain.filing import ModeloDraft
from ....domain.submission import ModeloDraftStatus
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.filing import build_registry_filing_draft_from_decimals
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.secure_sql import isolated_storage_root as _isolated_storage  # noqa: F401 - autouse fixture
from .. import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    build_runtime_schema_provider,
    compute_current_approval_basis,
)
from .._review import _transaction_catalogue_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cf394ec1-128f-4d57-b66d-2d57f35aaf35"
_Q1_2026 = Period.from_year_and_code(2026, "1T")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_MODELO_130_CASILLA_INPUTS: dict[CasillaId, str] = {
    _M130_INGRESOS_CASILLA: "12500.00",
    _M130_GASTOS_CASILLA: "3500.00",
    _M130_PAGOS_PREVIOS_CASILLA: "250.00",
    _M130_RETENCIONES_CASILLA: "100.00",
    _M130_AGRARIAN_VOLUME_CASILLA: "2000.00",
    _M130_AGRARIAN_WITHHELD_CASILLA: "10.00",
    _M130_HOME_DEDUCTION_CASILLA: "0.00",
    _M130_PRIOR_RETURN_CASILLA: "0.00",
}
_MODELO_130_BINDING_INPUTS = {
    "irpf.previous_year_economic_activity_net_income": "13000.00",
    "modelo-130-pagos-fraccionados-anteriores": "250.00",
    "modelo-130-resultados-negativos-anteriores": "0.00",
}


def test_compute_current_approval_basis_refuses_missing_runtime_session(tmp_path: Path) -> None:
    schema_provider = build_runtime_schema_provider(modelos=("130",), filing_year=_Q1_2026.filing_year, period=_Q1_2026)
    draft = _ready_modelo_130_draft()

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID),
        pytest.raises(StorageValidationError, match=r"no active bucket session|route does not match"),
    ):
        compute_current_approval_basis(
            draft,
            bucket_id=_BUCKET_ID,
            schema_provider=schema_provider,
        )


def test_approval_stale_reasons_reloads_transaction_catalogue_from_runtime_default(tmp_path: Path) -> None:
    schema_provider = build_runtime_schema_provider(modelos=("130",), filing_year=_Q1_2026.filing_year, period=_Q1_2026)
    draft = _ready_modelo_130_draft()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions((_transaction("initial"),)),
        )
        approved = approve_draft(
            draft,
            bucket_id=profile.bucket_id,
            approved_by="operator",
            schema_provider=schema_provider,
        )

        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions((_transaction("changed"),)),
        )
        reasons = approval_stale_reasons(
            approved,
            bucket_id=profile.bucket_id,
            schema_provider=schema_provider,
        )

    assert ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED in reasons


def test_transaction_catalogue_fingerprint_has_core_canonical_digest_parity() -> None:
    transaction = _transaction("canonical")
    catalogue = TransactionCatalogue.from_transactions((transaction,))
    payload = [
        {
            "business_classification": transaction.business_classification.value,
            "business_pct": None,
            "category_id": None,
            "direction": transaction.direction.value,
            "invoice_id": None,
            "transaction_id": transaction.transaction_id,
        },
    ]

    assert _transaction_catalogue_fingerprint(catalogue) == content_hash_hex(payload)


def _ready_modelo_130_draft() -> ModeloDraft:
    return build_registry_filing_draft_from_decimals(
        modelo="130",
        period=_Q1_2026,
        casilla_decimals=_MODELO_130_CASILLA_INPUTS,
        binding_decimals=_MODELO_130_BINDING_INPUTS,
        status=ModeloDraftStatus.LISTO_PARA_PRESENTAR,
    )


def _transaction(label: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=f"tx-{label}",
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
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
