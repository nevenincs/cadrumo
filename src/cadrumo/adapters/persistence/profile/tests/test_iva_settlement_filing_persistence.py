"""Encrypted persistence coverage for Modelo 303 settlement snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    IvaCreditSnapshot,
    IvaSettlementPaymentEvidence,
    IvaSettlementRefundState,
    IvaSettlementSnapshot,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record

from ...storage.tests.secure_sql import isolated_runtime_profile
from ..modelos_filing import ModeloRecordCatalogueRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "30330300-0000-4000-8000-000000000903"
_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "b" * 64
_AT = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)


def test_encrypted_filing_catalogue_roundtrips_an_iva_settlement_snapshot(tmp_path: Path) -> None:
    settlement = IvaSettlementSnapshot(
        calculation_revision_id=_REVISION_ID,
        declared_liability=Decimal("100.00"),
        payment_evidence=(
            IvaSettlementPaymentEvidence(
                reference=FilingEvidenceReference(reference="secure-payment-evidence-1"),
                amount=Decimal("100.00"),
                effective_at=_AT,
            ),
        ),
        refund_state=IvaSettlementRefundState.NOT_REQUESTED,
        refund_requested_amount=Decimal("0"),
        refund_approved_amount=Decimal("0"),
        refund_paid_amount=Decimal("0"),
        credit_snapshot=IvaCreditSnapshot(
            opening_amount=Decimal("30.00"),
            generated_amount=Decimal("20.00"),
            applied_amount=Decimal("10.00"),
            remaining_amount=Decimal("40.00"),
        ),
    )
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_REVISION_ID,
            filed_by="operator-A",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_REVISION_ID,
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=_AT,
        filed_by="operator-A",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        settlement=settlement,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = ModeloRecordCatalogueRepository(objects=profile.repository)
        repository.save(upsert_filing_record(ModeloRecordCatalogue(), record))
        restored = repository.load().get(record.filing_record_id)

    assert restored is not None
    assert restored.settlement == settlement
