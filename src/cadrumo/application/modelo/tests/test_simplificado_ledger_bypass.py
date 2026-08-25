"""Regression test: M303 régimen simplificado bypasses ledger preflight gate.

Simplificado operators supply casillas 47-58 as manual inputs and have no
transaction ledger to satisfy the IVA aggregation preflight check. This test
pins that bypass so it cannot regress silently.

The test calls ``_raise_if_ledger_preflight_blocks_calculation`` directly with:
- a real M303 revision (from the registry, so ledger_iva_aggregation bindings exist)
- an unclassified ACTIVE transaction saved to real per-bucket storage in the
  2026-Q1 window (which would block a GENERAL-regime calculate)

Anti-tautology proof: the GENERAL-regime case with the same inputs MUST raise
``ModeloAggregationBindingError``, confirming the bypass fires only for
``SIMPLIFICADO`` and not universally.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import Period
from ....core.resources import resources
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    WorkUnitState,
    derive_work_unit_id,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import ModeloAggregationBindingError
from .._calculation_preparation import _raise_if_ledger_preflight_blocks_calculation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_SIMPLIFICADO_PROFILE_ID = "30300000-0000-4000-8000-000000000303"
_GENERAL_PROFILE_ID = "30300000-0000-4000-8000-000000000304"


def _build_work_unit(bucket_id: str) -> WorkUnit:
    modelo: ModeloCode = cast(ModeloCode, "303")
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=2026,
            period=period,
            revision_id="2022",
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id="2022",
        name="m303-2026-1T",
        created_at=_T0,
        updated_at=_T0,
        state=WorkUnitState.BORRADOR,
    )


def _blocking_transaction() -> Transaction:
    """Return an ACTIVE unclassified transaction in Q1-2026 (NOT_YET_PROCESSED → blocks preflight)."""
    raw = RawTransaction(
        provider_transaction_id="tx-block-001",
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor",
        description="compra material",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            # BusinessClassification.NOT_YET_PROCESSED → not in _CLASSIFIED_TAX_STATES →
            # preflight raises MISSING_BUSINESS_CLASSIFICATION for this bucket.
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        },
    )


def _seed_profile(bucket_id: str, *, iva_regime: str, m303_regime_composition: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="iva.regime", value=iva_regime),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value=m303_regime_composition),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _seed_blocking_transaction(bucket_id: str) -> TransactionCatalogueRepository:
    tx = _blocking_transaction()
    repo = TransactionCatalogueRepository(bucket_id=bucket_id)
    repo.save(TransactionCatalogue(transactions={tx.transaction_id: tx}))
    return repo


def test_simplificado_bypasses_ledger_preflight_when_transactions_are_unclassified(tmp_path: Path) -> None:
    """SIMPLIFICADO work unit must not be blocked even when unclassified transactions exist.

    This is the real production scenario: a simplificado client has transaction
    data in the ledger that was never classified for IVA (because simplificado
    clients do not use the ledger aggregation path). The preflight check must
    not block them from calculating M303 via the manual casillas 47-58 path.
    """
    bucket_id = _SIMPLIFICADO_PROFILE_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        _seed_profile(bucket_id, iva_regime="SIMPLIFICADO", m303_regime_composition="simplified")
        tx_repo = _seed_blocking_transaction(bucket_id)
        work_unit = _build_work_unit(bucket_id)
        snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")

        # Must not raise for SIMPLIFICADO even with a blocking transaction.
        _raise_if_ledger_preflight_blocks_calculation(
            work_unit=work_unit,
            revision=snapshot.revision,
            transaction_repository=tx_repo,
        )


def test_general_profile_raises_preflight_error_when_transactions_are_unclassified(tmp_path: Path) -> None:
    """Anti-tautology: GENERAL-regime work unit MUST be blocked by the same inputs.

    If this test ever stops raising, the bypass has widened beyond SIMPLIFICADO
    and the previous test becomes tautological.
    """
    bucket_id = _GENERAL_PROFILE_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        _seed_profile(bucket_id, iva_regime="GENERAL", m303_regime_composition="general")
        tx_repo = _seed_blocking_transaction(bucket_id)
        work_unit = _build_work_unit(bucket_id)
        snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")

        with pytest.raises(ModeloAggregationBindingError) as exc_info:
            _raise_if_ledger_preflight_blocks_calculation(
                work_unit=work_unit,
                revision=snapshot.revision,
                transaction_repository=tx_repo,
            )
        assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked"
