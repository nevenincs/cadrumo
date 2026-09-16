"""Persistence-backed ledger filing evidence roundtrip.

The encrypted CalculationRevision boundary is exercised at the profile
persistence adapter. Pure evidence projection and coverage policy remain in
the inward application aggregation tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.ledger_filing_snapshot import LedgerFilingEvidence, ManualFactBasisEntry
from cadrumo.domain.modelos.work_unit import derive_work_unit_id
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

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
            "iva_category": IvaCategory("domestic_general"),
            "category_id": "material_oficina",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _revision_with_evidence(
    *, evidence: LedgerFilingEvidence, tx_id: str, operation: PinnedAuthorityOperation
) -> CalculationRevision:
    period = Period.from_year_and_code(2025, "1T")
    registry_snapshot_ref = published_authority_operation().snapshot("303", filing_year=2025, period="1T").snapshot_ref
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=period,
        revision_id=registry_snapshot_ref.revision_id,
    )
    filing_instance_evidence = general_m303_filing_evidence(
        period, reference="test:ledger-filing-evidence", operation=operation
    )
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
        registry_snapshot_ref=registry_snapshot_ref,
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


def test_evidence_roundtrips_through_encrypted_revision(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
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
    original = _revision_with_evidence(evidence=evidence, tx_id=txn.transaction_id, operation=operation)
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
