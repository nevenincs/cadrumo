"""Ledger→modelo staleness + finalized-modelo edit blocking (ratchet history).

A modelo revision verified from the ledger captures an immutable content
fingerprint over its contributing rows (the modelo-filing ledger snapshot contract).
When a contributing row's tax facts later drift, the staleness evaluator surfaces
it — a filed revision is never silently stale (behavior contract). Conversely, once a
revision is finalized, the blocking guard refuses destructive edits to its source
rows (behavior contract). These two mechanisms are complementary: the block protects finalized
filings, the staleness sweep is the defense-in-depth that catches any drift that
reaches a snapshot-backed revision.

See Also:
    :func:`~application.aggregation.compute_ledger_filing_snapshot`
        Transaction-aware capture of contributor fingerprints for a revision.
    :func:`~application.aggregation.evaluate_ledger_filing_staleness`
        Runtime comparison between a stored snapshot and the live ledger
        catalogue.
    :func:`~application.aggregation.stale_filed_revisions`
        System-level sweep that reports finalized snapshot-backed revisions whose
        ledger contributors drifted.
    :func:`~application.ledger.update_manual_transaction_fields`
        Ledger mutation path whose finalized-modelo write guard is exercised.
    :class:`~domain.modelos.CalculationRevision`
        Revision record that carries the optional ledger filing snapshot.
    :class:`~domain.transactions.TransactionCatalogue`
        Live ledger catalogue used to recompute contributor fingerprints.

Filing snapshots must stay immutable once captured, and the inverse
transaction-to-modelo reference index must remain derived and rebuildable,
never a second source of truth.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ..adapters.persistence.storage.sql import SecureObjectRepository
from ..application.aggregation import (
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    stale_filed_revisions,
)
from ..application.ledger import ManualLedgerTransactionPatch, update_manual_transaction_fields
from ..core import CasillaId, Period, validated_casilla_id
from ..domain.iva import IvaCategory
from ..domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ..domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from .filing_evidence import general_m303_filing_evidence
from .registry_observations import registry_grounded_observations
from .secure_objects_fixture import secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
_FILING_PERIOD = Period.from_year_and_code(2025, "1T")
_BUCKET_ID = "16161616-1616-4616-8616-161616161616"


_REVISION_CASILLA: CasillaId = validated_casilla_id("01")


def _txn(*, taxable_base: Decimal) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="provider-row-stale",
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
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _verified_revision(snapshot, tx_id: str) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=_FILING_PERIOD,
        revision_id="2009-2022",
    )
    filing_instance_evidence = general_m303_filing_evidence(_FILING_PERIOD, reference="test:ledger-modelo-staleness")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=(tx_id,),
        filing_instance_evidence=filing_instance_evidence,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        source_transaction_ids=(tx_id,),
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=2025,
            period=_FILING_PERIOD.registry_token,
            casilla_values={_REVISION_CASILLA: Decimal("1")},
        ),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        ledger_filing_snapshot=snapshot,
        filing_instance_evidence=filing_instance_evidence,
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
__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def test_finalized_modelo_blocks_destructive_ledger_edit(secure_objects: SecureObjectRepository) -> None:
    objects = secure_objects
    tx = _txn(taxable_base=Decimal("100.00"))
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions((tx,)),
    )
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(tx.transaction_id,),
        catalogue=TransactionCatalogue.from_transactions((tx,)),
        captured_at=_NOW,
    )
    revision = _verified_revision(snapshot, tx.transaction_id)
    work_unit = WorkUnit(
        work_unit_id=revision.work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=_FILING_PERIOD,
        revision_id="2009-2022",
        name="303-2025-1T",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=revision.calculation_revision_id,
    )
    WorkUnitCatalogueRepository(objects=objects).save(WorkUnitCatalogue.from_work_units((work_unit,)))
    CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions={revision.calculation_revision_id: revision}),
    )

    # The row now feeds a VERIFICADO_COMPLETO revision: editing it is refused.
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=tx.transaction_id,
            patch=ManualLedgerTransactionPatch(notes="tweak"),
            actor="operator",
            source_command="aeat app ledger update",
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        )
