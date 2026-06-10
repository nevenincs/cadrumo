"""Ledger→modelo staleness + finalized-modelo edit blocking (ratchet history).

A modelo revision verified from the ledger captures an immutable content
fingerprint over its contributing rows (the modelo-filing ledger snapshot contract).
When a contributing row's tax facts later drift, the staleness evaluator surfaces
it — a filed revision is never silently stale (behavior contract). Conversely, once a
revision is finalized, the blocking guard refuses destructive edits to its source
rows (behavior contract). These two mechanisms are complementary: the block protects finalized
filings, the staleness sweep is the defense-in-depth that catches any drift that
reaches a snapshot-backed revision.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ..adapters.persistence.storage.sql import SecureObjectRepository
from ..application.aggregation._ledger_filing_snapshot import (
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    stale_filed_revisions,
)
from ..application.ledger import ManualLedgerTransactionPatch, update_manual_transaction_fields
from ..domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ..domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ..domain.modelos._codes import ModeloCode
from ..domain.modelos._repository import WorkUnitCatalogueRepository
from ..domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ..tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _txn(*, taxable_base: Decimal) -> Transaction:
    raw = RawTransaction(
        transaction_id="provider-row-stale",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="Compra material oficina",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Compra material oficina"},
    )
    # The bank gross (the raw amount, 121.00) is fixed so the content-addressed
    # transaction id stays stable across the drift; re-split that gross so any
    # taxable_base yields a valid row (taxable_base + iva_amount == gross).
    iva_amount = Decimal("121.00") - taxable_base
    iva_rate = (iva_amount / taxable_base).quantize(Decimal("0.0001"))
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": "domestic_general_21",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        }
    )


def _verified_revision(snapshot, tx_id: str) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-a", modelo="303", filing_year=2025, period="1T", revision_id="2009-y-siguientes"
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"01": "1"},
        binding_overrides={},
        casilla_values={"01": Decimal("1")},
        source_transaction_ids=(tx_id,),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot={"01": "1"},
        binding_overrides={},
        source_transaction_ids=(tx_id,),
        casilla_values={"01": Decimal("1")},
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        ledger_filing_snapshot=snapshot,
    )


# --- behavior contract: modify a contributing row → drift is surfaced, never silent ----
def test_modifying_contributing_row_surfaces_staleness_not_silent() -> None:
    original = _txn(taxable_base=Decimal("100.00"))
    tx_id = original.transaction_id
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(tx_id,),
        catalogue=TransactionCatalogue.from_transactions((original,)),
        captured_at=_NOW,
    )
    revision = _verified_revision(snapshot, tx_id)

    # Unchanged ledger: the filed revision is NOT stale (no false positive).
    clean = evaluate_ledger_filing_staleness(snapshot, TransactionCatalogue.from_transactions((original,)))
    assert clean.is_stale is False
    assert clean.unchanged == (tx_id,)

    # A contributing row's tax facts drift (base 100 -> 80): the evaluator must
    # surface the drift — a filed revision is never silently stale.
    modified = _txn(taxable_base=Decimal("80.00"))
    assert modified.transaction_id == tx_id  # id is content-addressed on raw, not tax facts
    drifted = TransactionCatalogue.from_transactions((modified,))
    verdict = evaluate_ledger_filing_staleness(snapshot, drifted)
    assert verdict.is_stale is True
    assert verdict.changed == (tx_id,)

    # The system-level sweep names the stale revision + the contributors a
    # recalculation must re-consume (the recompute trigger signal).
    findings = stale_filed_revisions(revisions={revision.calculation_revision_id: revision}, catalogue=drifted)
    assert len(findings) == 1
    found_revision, found_verdict = findings[0]
    assert found_revision.calculation_revision_id == revision.calculation_revision_id
    assert found_verdict.changed == (tx_id,)


def test_removing_contributing_row_surfaces_staleness() -> None:
    original = _txn(taxable_base=Decimal("100.00"))
    tx_id = original.transaction_id
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(tx_id,),
        catalogue=TransactionCatalogue.from_transactions((original,)),
        captured_at=_NOW,
    )
    # The contributing row is gone from the live ledger entirely.
    verdict = evaluate_ledger_filing_staleness(snapshot, TransactionCatalogue.from_transactions(()))
    assert verdict.is_stale is True
    assert verdict.removed == (tx_id,)


# --- behavior contract: a finalized modelo blocks destructive edits to its source rows -----
@pytest.fixture
def _profile(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile.repository


def test_finalized_modelo_blocks_destructive_ledger_edit(_profile: SecureObjectRepository) -> None:
    objects = _profile
    tx = _txn(taxable_base=Decimal("100.00"))
    TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects).save(
        TransactionCatalogue.from_transactions((tx,))
    )
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(tx.transaction_id,),
        catalogue=TransactionCatalogue.from_transactions((tx,)),
        captured_at=_NOW,
    )
    revision = _verified_revision(snapshot, tx.transaction_id)
    work_unit = WorkUnit(
        work_unit_id=revision.work_unit_id,
        bucket_id="bucket-a",
        modelo=ModeloCode("303"),
        filing_year=2025,
        period="1T",
        revision_id="2009-y-siguientes",
        name="303-2025-1T",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=revision.calculation_revision_id,
    )
    WorkUnitCatalogueRepository(objects=objects).save(WorkUnitCatalogue.from_work_units((work_unit,)))
    CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions={revision.calculation_revision_id: revision})
    )

    # The row now feeds a VERIFICADO_COMPLETO revision: editing it is refused.
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        update_manual_transaction_fields(
            bucket_id="bucket-a",
            transaction_id=tx.transaction_id,
            patch=ManualLedgerTransactionPatch(notes="tweak"),
            actor="operator",
            source_command="aeat app ledger update",
            transaction_repository=TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects),
        )
