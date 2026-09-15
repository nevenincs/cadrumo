"""Regression test: M303 régimen simplificado bypasses ledger preflight gate.

Simplificado operators supply casillas 47-58 as manual inputs and have no
transaction ledger to satisfy the IVA aggregation preflight check. This test
pins that bypass so it cannot regress silently.

The test calls ``_raise_if_ledger_preflight_blocks_calculation`` directly with:
- a real M303 revision (from the registry, so ledger_iva_aggregation bindings exist)
- an unclassified ACTIVE transaction held by an inward in-memory repository
  capability in the 2026-Q1 window (which blocks a GENERAL-regime calculation)

The encrypted repository and profile-capsule roundtrips are covered by the
profile-persistence adapter tests; this suite isolates the application policy.

Anti-tautology proof: the GENERAL-regime case with the same inputs MUST raise
``ModeloAggregationBindingError``, confirming the bypass fires only for
``SIMPLIFICADO`` and not universally.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo import _calculation_preparation
from cadrumo.application.modelo._calculation_preparation import _raise_if_ledger_preflight_blocks_calculation
from cadrumo.application.modelo.action_errors import ModeloAggregationBindingError
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.deadlines.models import IVARegime
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from cadrumo.domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.usage_ratios.model import UsageRatioProfile

from ....domain.calculations.registry.tests.published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_SIMPLIFICADO_PROFILE_ID = "30300000-0000-4000-8000-000000000303"
_GENERAL_PROFILE_ID = "30300000-0000-4000-8000-000000000304"


def _build_work_unit(bucket_id: str) -> WorkUnit:
    modelo = ModeloCode("303")
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


class _InMemoryTransactionRepository:
    """Minimal in-memory implementation of the application transaction port."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


def _seed_blocking_transaction(bucket_id: str) -> TransactionCatalogueRepositoryProtocol:
    tx = _blocking_transaction()
    return _InMemoryTransactionRepository(
        bucket_id=bucket_id,
        catalogue=TransactionCatalogue(transactions={tx.transaction_id: tx}),
    )


def _empty_usage_ratio_profile(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    del bucket_id, operation
    return UsageRatioProfile()


def _set_iva_regime(monkeypatch: pytest.MonkeyPatch, regime: IVARegime) -> None:
    def resolve(_bucket_id: str, *, operation: PinnedAuthorityOperation) -> IVARegime:
        del operation
        return regime

    monkeypatch.setattr(_calculation_preparation, "_iva_regime_for_bucket", resolve)


def test_simplificado_bypasses_ledger_preflight_when_transactions_are_unclassified(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """SIMPLIFICADO work unit must not be blocked even when unclassified transactions exist.

    A simplificado client can have transaction data that was never classified
    for IVA (because simplificado clients do not use the ledger aggregation
    path). The preflight check must not block M303 manual casillas 47-58.
    """
    bucket_id = _SIMPLIFICADO_PROFILE_ID
    _set_iva_regime(monkeypatch, IVARegime("SIMPLIFICADO"))
    tx_repo = _seed_blocking_transaction(bucket_id)
    work_unit = _build_work_unit(bucket_id)
    snapshot = published_snapshot("303", filing_year=2026, period="1T")

    # Must not raise for SIMPLIFICADO even with a blocking transaction.
    _raise_if_ledger_preflight_blocks_calculation(
        work_unit=work_unit,
        revision=snapshot.revision,
        transaction_repository=tx_repo,
        usage_ratio_profile_loader=_empty_usage_ratio_profile,
        operation=operation,
    )


def test_general_profile_raises_preflight_error_when_transactions_are_unclassified(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """Anti-tautology: GENERAL-regime work unit MUST be blocked by the same inputs.

    If this test ever stops raising, the bypass has widened beyond SIMPLIFICADO
    and the previous test becomes tautological.
    """
    bucket_id = _GENERAL_PROFILE_ID
    _set_iva_regime(monkeypatch, IVARegime("GENERAL"))
    tx_repo = _seed_blocking_transaction(bucket_id)
    work_unit = _build_work_unit(bucket_id)
    snapshot = published_snapshot("303", filing_year=2026, period="1T")

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        _raise_if_ledger_preflight_blocks_calculation(
            work_unit=work_unit,
            revision=snapshot.revision,
            transaction_repository=tx_repo,
            usage_ratio_profile_loader=_empty_usage_ratio_profile,
            operation=operation,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked"
