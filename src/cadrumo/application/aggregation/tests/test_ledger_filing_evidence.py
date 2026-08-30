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

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.iva.schema import IvaCategory
from ....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry
from ....domain.modelos.work_unit import derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from .. import assert_evidence_covers_snapshot
from .._ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    row_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
_BUCKET_ID = "13131313-1313-4313-8313-131313131313"


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
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
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


def _revision_with_evidence(*, evidence: LedgerFilingEvidence, tx_id: str) -> CalculationRevision:
    period = Period.from_year_and_code(2025, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=period,
        revision_id="2022",
    )
    filing_instance_evidence = general_m303_filing_evidence(period, reference="test:ledger-filing-evidence")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=(tx_id,),
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
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
            period=period.registry_token,
            casilla_values={_REVISION_CASILLA: Decimal("1")},
        ),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        ledger_filing_evidence=evidence,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def test_evidence_roundtrips_through_encrypted_revision(secure_objects: SecureObjectRepository) -> None:
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
                note="resultado contable",
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
    )
    original = _revision_with_evidence(evidence=evidence, tx_id=txn.transaction_id)
    repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repo.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    loaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load()
    loaded_revision = loaded.revisions[original.calculation_revision_id]
    # Strict equality across the encrypted boundary: the bundled evidence survives.
    assert loaded_revision == original
    assert loaded_revision.ledger_filing_evidence == evidence
    loaded_evidence = loaded_revision.ledger_filing_evidence
    assert loaded_evidence is not None
    assert loaded_evidence.rows[0].iva_category == "domestic_general"

    # Anti-tautology: a revision with evidence must NOT equal the same revision
    # with its evidence stripped — the field carries real state.
    stripped = original.model_copy(update={"ledger_filing_evidence": None})
    assert stripped != original


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
