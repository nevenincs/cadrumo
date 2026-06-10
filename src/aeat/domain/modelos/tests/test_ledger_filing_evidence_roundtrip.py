"""Encrypted roundtrip coverage for ledger filing evidence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests.secure_sql import isolated_runtime_profile
from .._calculation_repository import CalculationRevisionCatalogueRepository
from .._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .._ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry
from .._work_unit import derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 6, 3, 14, 0, tzinfo=UTC)
_TX_ID = "c" * 64


@pytest.fixture
def objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile.repository


def _evidence() -> LedgerFilingEvidence:
    return LedgerFilingEvidence(
        snapshot_fingerprint="b" * 64,
        rows=(
            LedgerEvidenceRow(
                transaction_id=_TX_ID,
                fingerprint="a" * 64,
                booked_date="2026-01-31",
                value_date="2026-02-01",
                amount=Decimal("-121.00"),
                currency="EUR",
                direction="outgoing",
                business_classification="mixed",
                business_pct=Decimal("0.75"),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
                iva_category="domestic_general_21",
                category_id="office-supplies",
                irpf_category="professional-services",
                counterparty_eu_member_state="DE",
                fx_rate=Decimal("1.08"),
                value_in_eur=Decimal("-112.04"),
                lifecycle_state="active",
                counterparty="Proveedor SL",
                description="Compra material oficina",
                purchase_invoice_evidence_id="purchase-evidence-1",
                attachment_ids=("attachment-1",),
                document_link_ids=("drive-doc-1",),
                legal_refs=("liva-art-99",),
                source_refs=("boe-a-2026-1",),
            ),
        ),
        manual_entries=(
            ManualFactBasisEntry(
                casilla="00501",
                value="140000.00",
                kind="casilla_input",
                note="resultado contable",
            ),
        ),
        captured_at=_NOW,
    )


def _revision(evidence: LedgerFilingEvidence | None) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-a",
        modelo="303",
        filing_year=2026,
        period="1T",
        revision_id="2009-y-siguientes",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"00501": "140000.00"},
        binding_overrides={},
        casilla_values={"00501": Decimal("140000.00")},
        source_transaction_ids=(_TX_ID,),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot={"00501": "140000.00"},
        source_transaction_ids=(_TX_ID,),
        casilla_values={"00501": Decimal("140000.00")},
        ledger_filing_evidence=evidence,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
    )


def test_ledger_filing_evidence_roundtrips_through_encrypted_revision(objects: SecureObjectRepository) -> None:
    evidence = _evidence()
    original = _revision(evidence)
    repository = CalculationRevisionCatalogueRepository(objects=objects)

    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    loaded = CalculationRevisionCatalogueRepository(objects=objects).load().get(original.calculation_revision_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.ledger_filing_evidence == evidence
    # Narrow ledger_filing_evidence to non-None for safe attribute access.
    assert loaded.ledger_filing_evidence is not None
    assert loaded.ledger_filing_evidence.rows[0].document_link_ids == ("drive-doc-1",)
    assert loaded.ledger_filing_evidence.manual_entries[0].note == "resultado contable"

    stripped = original.model_copy(update={"ledger_filing_evidence": None})
    assert stripped != original
