"""Ledger filing evidence: capture, fingerprint binding, encrypted roundtrip.

Asserts the bundled fact basis for modelo export evidence parity:
- ``compute_ledger_filing_evidence`` projects the typed tax facts and binds each
  row to its fingerprint;
- the evidence rides inside the encrypted ``CalculationRevision`` envelope and
  reconstitutes byte-for-byte (every defaultable field populated non-default);
- the no-silent-omission guard refuses an evidence bundle that does not cover the
  fingerprint snapshot.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry
from ....domain.modelos._work_unit import derive_work_unit_id
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
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo._actions import _assert_evidence_covers_snapshot
from .._ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    row_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _txn() -> Transaction:
    raw = RawTransaction(
        transaction_id="provider-row-evidence",
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
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "iva_category": "domestic_general_21",
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
        source_transaction_ids=(txn.transaction_id,), catalogue=catalogue, captured_at=_NOW,
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_NOW,
        manual_entries=(ManualFactBasisEntry(casilla="00501", value="140000.00"),),
    )
    assert evidence.snapshot_fingerprint == snapshot.snapshot_fingerprint
    assert len(evidence.rows) == 1
    row = evidence.rows[0]
    # Facts are projected verbatim and the row binds to its fingerprint.
    assert row.transaction_id == txn.transaction_id
    assert row.fingerprint == row_fingerprint(txn)
    assert row.amount == Decimal("121.00")
    assert row.taxable_base == Decimal("100.00")
    assert row.iva_category == "domestic_general_21"
    assert row.direction == "OUTGOING"
    assert row.lifecycle_state == "ACTIVE"
    assert evidence.manual_entries[0].casilla == "00501"


@pytest.fixture
def _objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile.repository


def _revision_with_evidence(*, evidence: LedgerFilingEvidence, tx_id: str) -> CalculationRevision:
    period = Period.from_year_and_code(2025, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-a",
        modelo="303",
        filing_year=2025,
        period=period,
        revision_id="2009-y-siguientes",
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
        ledger_filing_evidence=evidence,
    )


def test_evidence_roundtrips_through_encrypted_revision(_objects: SecureObjectRepository) -> None:
    txn = _txn()
    catalogue = TransactionCatalogue.from_transactions((txn,))
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(txn.transaction_id,), catalogue=catalogue, captured_at=_NOW,
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_NOW,
        manual_entries=(ManualFactBasisEntry(casilla="00501", value="140000.00", note="resultado contable"),),
    )
    original = _revision_with_evidence(evidence=evidence, tx_id=txn.transaction_id)
    repo = CalculationRevisionCatalogueRepository(objects=_objects)
    repo.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    loaded = CalculationRevisionCatalogueRepository(objects=_objects).load()
    loaded_revision = loaded.revisions[original.calculation_revision_id]
    # Strict equality across the encrypted boundary: the bundled evidence survives.
    assert loaded_revision == original
    assert loaded_revision.ledger_filing_evidence == evidence
    loaded_evidence = loaded_revision.ledger_filing_evidence
    assert loaded_evidence is not None
    assert loaded_evidence.rows[0].iva_category == "domestic_general_21"

    # Anti-tautology: a revision with evidence must NOT equal the same revision
    # with its evidence stripped — the field carries real state.
    stripped = original.model_copy(update={"ledger_filing_evidence": None})
    assert stripped != original


def test_no_silent_omission_guard_refuses_uncovered_evidence() -> None:
    from ...modelo._actions import ModeloError

    txn = _txn()
    catalogue = TransactionCatalogue.from_transactions((txn,))
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(txn.transaction_id,), catalogue=catalogue, captured_at=_NOW,
    )
    # Evidence that drops the contributor the snapshot fingerprints.
    empty_evidence = LedgerFilingEvidence(
        snapshot_fingerprint=snapshot.snapshot_fingerprint, rows=(), manual_entries=(), captured_at=_NOW,
    )
    with pytest.raises(ModeloError, match="does not cover"):
        _assert_evidence_covers_snapshot(snapshot, empty_evidence)

    # A faithful capture passes the guard.
    good = compute_ledger_filing_evidence(
        source_transaction_ids=(txn.transaction_id,),
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_NOW,
    )
    _assert_evidence_covers_snapshot(snapshot, good)  # no raise


def test_evidence_row_strict_json_roundtrip_all_fields() -> None:
    row = LedgerEvidenceRow(
        transaction_id="t1",
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
        iva_category="domestic_general_21",
        category_id="material_oficina",
        irpf_category="actividad_economica",
        counterparty_eu_member_state="de",
        fx_rate=Decimal("1.08"),
        value_in_eur=Decimal("112.04"),
        lifecycle_state="ACTIVE",
        counterparty="Proveedor SL",
        description="Compra",
        attachment_ids=("att-1",),
        legal_refs=("lis-art-1",),
        source_refs=("boe-1",),
    )
    back = LedgerEvidenceRow.model_validate_json(row.model_dump_json())
    assert back == row
