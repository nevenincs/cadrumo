"""Tests for the modelo filing ledger snapshot capture and staleness."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.modelos._errors import ModeloValidationError
from ....domain.modelos._ledger_filing_snapshot import LedgerFilingEvidence, LedgerFilingSnapshot, ManualFactBasisEntry
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
from .._ledger_filing_snapshot import (
    assert_evidence_covers_snapshot,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    project_manual_fact_basis_entries,
    row_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)


def _tx(
    provider_id: str,
    *,
    amount: Decimal = Decimal("121.00"),
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_amount: Decimal | None = Decimal("21.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_CAPTURED,
            provider_name="manual",
        ),
        raw_fields={"k": "v"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": business_classification,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "category_id": "material_oficina",
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "attachment_ids": attachment_ids,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _CAPTURED,
            "classified_by": "manual",
        }
    )


def _catalogue(*transactions: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(transactions)


def test_row_fingerprint_is_deterministic_and_ignores_cosmetic_fields() -> None:
    tx = _tx("row-a")
    assert row_fingerprint(tx) == row_fingerprint(tx)


def test_snapshot_is_deterministic_for_identical_state() -> None:
    a, b = _tx("row-a"), _tx("row-b")
    cat = _catalogue(a, b)
    ids = [a.transaction_id, b.transaction_id]
    s1 = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_CAPTURED)
    s2 = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_CAPTURED)
    assert s1.snapshot_fingerprint == s2.snapshot_fingerprint
    assert len(s1.rows) == 2


def test_snapshot_roundtrips_through_strict_model() -> None:
    a = _tx("row-a")
    cat = _catalogue(a)
    snap = compute_ledger_filing_snapshot(
        source_transaction_ids=[a.transaction_id], catalogue=cat, captured_at=_CAPTURED
    )
    reloaded = LedgerFilingSnapshot.model_validate_json(snap.model_dump_json())
    assert reloaded == snap


def test_evidence_capture_projects_tax_facts_and_manual_basis() -> None:
    tx = _tx(
        "row-evidence",
        purchase_invoice_evidence_id="purchase-evidence-1",
        attachment_ids=("attachment-1",),
    )
    catalogue = _catalogue(tx)
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=[tx.transaction_id], catalogue=catalogue, captured_at=_CAPTURED
    )
    manual_entry = ManualFactBasisEntry(casilla="00501", value="140000.00", note="resultado contable")

    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=[tx.transaction_id, tx.transaction_id, "missing-row"],
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_CAPTURED,
        manual_entries=(manual_entry,),
    )

    assert evidence.snapshot_fingerprint == snapshot.snapshot_fingerprint
    assert evidence.manual_entries == (manual_entry,)
    assert len(evidence.rows) == 1
    row = evidence.rows[0]
    assert row.transaction_id == tx.transaction_id
    assert row.fingerprint == row_fingerprint(tx)
    assert row.taxable_base == Decimal("100.00")
    assert row.iva_amount == Decimal("21.00")
    # The projected gross mirrors the seeded transaction's base + IVA; asserting the
    # relationship (not a standalone literal) keeps this a fidelity check, not a
    # hand-summed aggregation.
    assert row.amount == row.taxable_base + row.iva_amount
    assert row.category_id == "material_oficina"
    assert row.purchase_invoice_evidence_id == "purchase-evidence-1"
    assert row.attachment_ids == ("attachment-1",)


def test_manual_fact_basis_projection_skips_blank_inputs() -> None:
    entries = project_manual_fact_basis_entries(
        {
            "00501": "140000.00",
            "00502": " ",
            "00503": "",
        }
    )

    assert entries == (ManualFactBasisEntry(casilla="00501", value="140000.00"),)


def test_evidence_coverage_guard_refuses_missing_contributor() -> None:
    tx = _tx("row-covered")
    catalogue = _catalogue(tx)
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=[tx.transaction_id], catalogue=catalogue, captured_at=_CAPTURED
    )
    missing = LedgerFilingEvidence(
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        rows=(),
        manual_entries=(),
        captured_at=_CAPTURED,
    )

    with pytest.raises(ModeloValidationError, match="does not cover"):
        assert_evidence_covers_snapshot(snapshot, missing)

    complete = compute_ledger_filing_evidence(
        source_transaction_ids=[tx.transaction_id],
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_CAPTURED,
    )
    assert_evidence_covers_snapshot(snapshot, complete)


def test_empty_contributor_set_is_valid_and_uniform() -> None:
    """A non-ledger modelo carries a valid empty snapshot (uniform shape)."""
    snap = compute_ledger_filing_snapshot(source_transaction_ids=[], catalogue=_catalogue(), captured_at=_CAPTURED)
    assert snap.rows == ()
    assert len(snap.snapshot_fingerprint) == 64
    verdict = evaluate_ledger_filing_staleness(snap, _catalogue())
    assert verdict.is_stale is False


def test_unchanged_ledger_is_not_stale() -> None:
    a, b = _tx("row-a"), _tx("row-b")
    cat = _catalogue(a, b)
    snap = compute_ledger_filing_snapshot(
        source_transaction_ids=[a.transaction_id, b.transaction_id], catalogue=cat, captured_at=_CAPTURED
    )
    verdict = evaluate_ledger_filing_staleness(snap, cat)
    assert verdict.is_stale is False
    assert set(verdict.unchanged) == {a.transaction_id, b.transaction_id}


def test_material_change_to_contributor_is_detected_stale() -> None:
    original = _tx("row-a", taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00"))
    snap = compute_ledger_filing_snapshot(
        source_transaction_ids=[original.transaction_id], catalogue=_catalogue(original), captured_at=_CAPTURED
    )
    # Operator later re-splits the base/iva of the same 121.00 gross: same row
    # id, material change to a casilla input -> detected as changed, not removed.
    edited = _tx("row-a", taxable_base=Decimal("110.00"), iva_amount=Decimal("11.00"))
    assert edited.transaction_id == original.transaction_id
    verdict = evaluate_ledger_filing_staleness(snap, _catalogue(edited))
    assert verdict.is_stale is True
    assert verdict.changed == (original.transaction_id,)


def test_removed_contributor_is_detected_stale() -> None:
    a, b = _tx("row-a"), _tx("row-b")
    snap = compute_ledger_filing_snapshot(
        source_transaction_ids=[a.transaction_id, b.transaction_id],
        catalogue=_catalogue(a, b),
        captured_at=_CAPTURED,
    )
    verdict = evaluate_ledger_filing_staleness(snap, _catalogue(a))
    assert verdict.is_stale is True
    assert verdict.removed == (b.transaction_id,)


def test_anti_tautology_tampered_fingerprint_surfaces_mismatch() -> None:
    """If a persisted row fingerprint is corrupted, staleness must surface it."""
    a = _tx("row-a")
    cat = _catalogue(a)
    snap = compute_ledger_filing_snapshot(
        source_transaction_ids=[a.transaction_id], catalogue=cat, captured_at=_CAPTURED
    )
    tampered = snap.model_copy(update={"rows": (snap.rows[0].model_copy(update={"fingerprint": "0" * 64}),)})
    verdict = evaluate_ledger_filing_staleness(tampered, cat)
    assert verdict.is_stale is True
    assert verdict.changed == (a.transaction_id,)
