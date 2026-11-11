"""GUI-style attach then classify retains canonical purchase authority on readback.

All repositories are in memory. The real attachment action, registered classify
executor, domain provenance builder and normal read projections are exercised.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ...operations import profile_guard
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ..action_ports import LedgerActionPorts
from ..classify_operation import LedgerClassifyExecutor
from ..classify_requests import LedgerClassifyPatch, LedgerClassifyRequest
from ..evidence import MediaKind, PurchaseInvoiceEvidence
from ..manual_read import ledger_transaction_payload
from ..manual_update import attach_manual_transaction_evidence
from ..transaction_projection import LedgerTransactionProjection
from .action_port_fakes import (
    EmptyCalculationRepository,
    EmptyInvoiceRepository,
    EmptyWorkUnitRepository,
    InMemoryAttachmentStore,
    InMemoryEventRepository,
    empty_usage_ratio_profile,
)
from .in_memory_transaction_repository import InMemoryTransactionRepository
from .recording_executor_context_support import RecordingEvents, RecordingOperands
from .transaction_row_support import outgoing_manual_row

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "22222222-2222-4222-8222-222222222222"
_AT = datetime(_YEAR, 3, 1, 12, tzinfo=UTC)


@pytest.mark.asyncio
async def test_attach_then_classify_projects_deduction_and_preserves_invoice_authority(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = outgoing_manual_row(
        "purchase-evidence-readback",
        amount=Decimal("121"),
        currency="EUR",
        counterparty="Synthetic supplier",
        description="Synthetic purchase",
        classification=BusinessClassification.BUSINESS,
    )
    row = Transaction.model_validate(
        {
            **row.model_dump(),
            "category_id": "office-supplies",
            "iva_category": "domestic_general",
            "taxable_base": Decimal("100"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21"),
        }
    )
    attachments = InMemoryAttachmentStore()
    digest = attachments.put_bytes(b"synthetic purchase invoice bytes")
    evidence = PurchaseInvoiceEvidence(
        evidence_id="e" * 64,
        bucket_id=_BUCKET,
        source_path="synthetic-purchase.pdf",
        source_sha256=digest,
        attachment_id=digest,
        media_kind=MediaKind.PDF,
        supplier="Synthetic supplier",
        invoice_number="SYNTHETIC-001",
        invoice_date=date(_YEAR, 3, 1).isoformat(),
        taxable_base=Decimal("100"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21"),
        created_at=_AT,
        updated_at=_AT,
    )
    repository = InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions((row,)),
        permit_secure_object_writes=True,
    )
    ports = LedgerActionPorts(
        operation=operation,
        transaction_repository=repository,
        bucket_event_repository=InMemoryEventRepository(),
        invoice_repository=EmptyInvoiceRepository(bucket_id=_BUCKET),
        attachment_store=attachments,
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=empty_usage_ratio_profile,
        work_unit_repository=EmptyWorkUnitRepository(bucket_id=_BUCKET),
        calculation_repository=EmptyCalculationRepository(bucket_id=_BUCKET),
        purchase_invoice_evidence_records=(evidence,),
    )
    attached = attach_manual_transaction_evidence(
        bucket_id=_BUCKET,
        transaction_id=row.transaction_id,
        actor="operator",
        purchase_invoice_evidence_id=evidence.evidence_id,
        ports=ports,
        occurred_at=_AT,
    )
    assert attached.transaction.purchase_invoice_evidence_id == evidence.evidence_id
    assert attached.transaction.attachment_ids == (), "purchase reference is independent of supplementary blobs"

    @asynccontextmanager
    async def irreversible_section():
        yield

    events, operands = RecordingEvents(), RecordingOperands()
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(
                definition_id="ledger.classify.single", subject_ref=profile_operation_subject(_BUCKET)
            ),
            authority_operation=operation,
            cancellation=SimpleNamespace(irreversible_section=irreversible_section),
            events=events,
            operands=operands,
        ),
    )
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: _BUCKET)
    executor = LedgerClassifyExecutor(lambda **_kwargs: ports)
    await executor.execute(
        OperationRequest[LedgerClassifyRequest](
            definition_id="ledger.classify.single",
            subject_ref=profile_operation_subject(_BUCKET),
            payload=LedgerClassifyRequest(
                profile_id=UUID(_BUCKET),
                transaction_id=attached.transaction.transaction_id,
                patch=LedgerClassifyPatch(business_classification="BUSINESS", deduction_fact_kind="domestic_current"),
                patch_fields=("business_classification", "deduction_fact_kind"),
            ),
        ),
        context,
    )

    stored = repository.load().transactions[attached.transaction.transaction_id]
    assert stored.deduction_fact_kind is not None
    assert stored.deduction_fact_kind.value == "domestic_current"
    assert stored.purchase_invoice_evidence_id == evidence.evidence_id
    assert stored.attachment_ids == ()
    assert stored.taxable_base == Decimal("100")
    assert stored.iva_rate == Decimal("0.21")
    assert stored.iva_amount == Decimal("21")
    assert stored.deduction_provenance is not None
    assert stored.deduction_provenance.authority.value == "invoice_evidence"
    assert stored.deduction_provenance.source_locator == evidence.evidence_id
    assert stored.deduction_provenance.evidence_digest == digest
    read = LedgerTransactionProjection.from_payload(ledger_transaction_payload(stored))
    assert read.deduction_fact_kind == "domestic_current"
    assert read.investment_asset_id is None
    assert read.purchase_invoice_evidence_id == evidence.evidence_id
    assert read.attachment_ids == ()


@pytest.mark.parametrize("deduction_kind, asset_id", [(None, None), ("domestic_current", "synthetic-existing-asset")])
def test_normal_read_preserves_nullable_deduction_and_asset_facts(
    deduction_kind: str | None, asset_id: str | None
) -> None:
    row = outgoing_manual_row(
        "read-fiscal-facts",
        amount=Decimal("121"),
        currency="EUR",
        counterparty="Synthetic supplier",
        description="Synthetic purchase",
    )
    stored = Transaction.model_validate(
        {
            **row.model_dump(),
            "deduction_fact_kind": deduction_kind,
            "investment_asset_id": asset_id,
        }
    )
    payload = ledger_transaction_payload(stored)
    projected = LedgerTransactionProjection.from_payload(payload)
    assert payload.deduction_fact_kind == deduction_kind
    assert projected.deduction_fact_kind == deduction_kind
    assert projected.investment_asset_id == asset_id
