"""Ledger filing evidence: projection, fingerprint binding, and coverage.

Asserts the bundled fact basis for modelo export evidence parity:
- ``compute_ledger_filing_evidence`` projects the typed tax facts and binds each
  row to its fingerprint;
- the no-silent-omission guard refuses an evidence bundle that does not cover the
  fingerprint snapshot.

The encrypted ``CalculationRevision`` roundtrip is covered at the profile
persistence adapter seam.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.iva.schema import IvaCategory
from ....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..ledger_filing_snapshot import (
    assert_evidence_covers_snapshot,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    row_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
_MANUAL_FACT_CASILLA: CasillaId = validated_casilla_id("00501")
_REVISION_CASILLA: CasillaId = validated_casilla_id("01")
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-2025-form",)


def _txn() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="provider-row-evidence",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 11),
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
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "iva_category": IvaCategory("domestic_general"),
            "category_id": "material_oficina",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_capture_projects_tax_facts_and_binds_fingerprint() -> None:
    txn = _txn()
    catalogue = TransactionCatalogue.from_transactions((txn,))
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        captured_at=_NOW,
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_NOW,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        manual_entries=(
            ManualFactBasisEntry(
                casilla_id=_MANUAL_FACT_CASILLA,
                value="140000.00",
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
    )
    assert evidence.snapshot_fingerprint == snapshot.snapshot_fingerprint
    assert len(evidence.rows) == 1
    row = evidence.rows[0]
    # Facts are projected verbatim and the row binds to its fingerprint.
    assert row.transaction_id == txn.transaction_id
    assert row.fingerprint == row_fingerprint(txn)
    assert row.amount == Decimal("121.00")
    assert row.taxable_base == Decimal("100.00")
    assert row.iva_category == "domestic_general"
    assert row.direction == "OUTGOING"
    assert row.lifecycle_state == "ACTIVE"
    assert evidence.manual_entries[0].casilla_id == _MANUAL_FACT_CASILLA


def test_no_silent_omission_guard_refuses_uncovered_evidence() -> None:
    from ....domain.modelos.errors import ModeloError

    txn = _txn()
    catalogue = TransactionCatalogue.from_transactions((txn,))
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        captured_at=_NOW,
    )
    # Evidence that drops the contributor the snapshot fingerprints.
    empty_evidence = LedgerFilingEvidence(
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        rows=(),
        manual_entries=(),
        captured_at=_NOW,
    )
    with pytest.raises(ModeloError, match="does not cover"):
        assert_evidence_covers_snapshot(snapshot, empty_evidence)

    # A faithful capture passes the guard.
    good = compute_ledger_filing_evidence(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_NOW,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    assert_evidence_covers_snapshot(snapshot, good)  # no raise


def test_evidence_row_strict_json_roundtrip_all_fields() -> None:
    row = LedgerEvidenceRow(
        transaction_id="1" * 64,
        fingerprint="a" * 64,
        booked_date="2025-02-10",
        value_date="2025-02-11",
        amount=Decimal("121.00"),
        currency="EUR",
        direction="OUTGOING",
        business_classification="MIXED",
        business_pct=Decimal("0.5"),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        iva_category="domestic_general",
        category_id="material_oficina",
        irpf_category="actividad_economica",
        counterparty_country="DE",
        fx_rate=Decimal("1.08"),
        value_in_eur=Decimal("112.04"),
        lifecycle_state="ACTIVE",
        counterparty="Proveedor SL",
        description="Compra",
        attachment_ids=("att-1",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    back = LedgerEvidenceRow.model_validate_json(row.model_dump_json())
    assert back == row
