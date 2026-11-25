"""Regression test: M303 régimen simplificado bypasses ledger preflight gate.

Simplificado operators supply casillas 47-58 as manual inputs and have no
transaction ledger to satisfy the IVA aggregation preflight check. This test
pins that bypass so it cannot regress silently.

The test calls ``raise_if_ledger_preflight_blocks_calculation`` directly with:
- a real M303 revision (from the registry, so ledger_iva_aggregation bindings exist)
- an unclassified ACTIVE transaction held by an inward in-memory repository
  capability in the 2026-Q1 window (which blocks a GENERAL-regime calculation)

The encrypted repository and profile-capsule roundtrips are covered by the
profile-persistence adapter tests; this suite isolates the application policy.

Anti-tautology proof: the GENERAL-regime case with the same inputs MUST raise
``ModeloLedgerPreflightBlockedError``, confirming the bypass fires only for
``SIMPLIFICADO`` and not universally.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.action_errors import ModeloLedgerPreflightBlockedError
from cadrumo.application.modelo.calculation_preparation import raise_if_ledger_preflight_blocks_calculation
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.usage_ratios.model import UsageRatioProfile

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_serving_period
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ...aggregation.tests.ledger_source_mesh_support import InMemoryInvoiceCatalogueRepository
from ...tests.ledger_partition_support import CatalogueTransactionRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_REVISION = str(revision_serving_period("303", _YEAR, "1T").id)
_T0 = datetime(_YEAR, 1, 10, 10, 0, tzinfo=UTC)
_SIMPLIFICADO_PROFILE_ID = "30300000-0000-4000-8000-000000000303"
_GENERAL_PROFILE_ID = "30300000-0000-4000-8000-000000000304"


def _build_work_unit(bucket_id: str) -> WorkUnit:
    modelo = ModeloCode("303")
    period = Period.from_year_and_code(_YEAR, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=_YEAR,
            period=period,
            revision_id=_REVISION,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=_YEAR,
        period=period,
        revision_id=_REVISION,
        name=f"m303-{_YEAR}-1T",
        created_at=_T0,
        updated_at=_T0,
        state=WorkUnitState.BORRADOR,
    )


def _blocking_transaction() -> Transaction:
    """Return an ACTIVE unclassified transaction in Q1-2026 (NOT_YET_PROCESSED → blocks preflight)."""
    raw = RawTransaction(
        provider_transaction_id="tx-block-001",
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 10),
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


def _seed_blocking_transaction(bucket_id: str) -> TransactionCatalogueRepositoryProtocol:
    tx = _blocking_transaction()
    return CatalogueTransactionRepository(
        bucket_id=bucket_id,
        catalogue=TransactionCatalogue(transactions={tx.transaction_id: tx}),
    )


def _empty_usage_ratio_profile(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    del bucket_id, operation
    return UsageRatioProfile()


def test_simplificado_bypasses_ledger_preflight_when_transactions_are_unclassified(
    operation: PinnedAuthorityOperation,
) -> None:
    """SIMPLIFICADO work unit must not be blocked even when unclassified transactions exist.

    A simplificado client can have transaction data that was never classified
    for IVA (because simplificado clients do not use the ledger aggregation
    path). The preflight check must not block M303 manual casillas 47-58.
    """
    bucket_id = _SIMPLIFICADO_PROFILE_ID
    tx_repo = _seed_blocking_transaction(bucket_id)
    work_unit = _build_work_unit(bucket_id)
    snapshot = published_snapshot("303", filing_year=_YEAR, period="1T")

    # Must not raise for SIMPLIFICADO even with a blocking transaction.
    raise_if_ledger_preflight_blocks_calculation(
        work_unit=work_unit,
        revision=snapshot.revision,
        transaction_repository=tx_repo,
        invoice_reader=InMemoryInvoiceCatalogueRepository(),
        usage_ratio_profile_loader=_empty_usage_ratio_profile,
        operation=operation,
        profile_values={"iva.regime": "SIMPLIFICADO"},
    )


def test_general_profile_raises_preflight_error_when_transactions_are_unclassified(
    operation: PinnedAuthorityOperation,
) -> None:
    """Anti-tautology: GENERAL-regime work unit MUST be blocked by the same inputs.

    If this test ever stops raising, the bypass has widened beyond SIMPLIFICADO
    and the previous test becomes tautological.
    """
    bucket_id = _GENERAL_PROFILE_ID
    tx_repo = _seed_blocking_transaction(bucket_id)
    work_unit = _build_work_unit(bucket_id)
    snapshot = published_snapshot("303", filing_year=_YEAR, period="1T")

    with pytest.raises(ModeloLedgerPreflightBlockedError) as exc_info:
        raise_if_ledger_preflight_blocks_calculation(
            work_unit=work_unit,
            revision=snapshot.revision,
            transaction_repository=tx_repo,
            invoice_reader=InMemoryInvoiceCatalogueRepository(),
            usage_ratio_profile_loader=_empty_usage_ratio_profile,
            operation=operation,
            profile_values={"iva.regime": "GENERAL"},
        )
    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked_movement"
