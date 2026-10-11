"""Synthetic ledger rows and one driver for the suites that run one ledger act on each frontend.

Every row is stored through the ledger's own actions under a person's actor
label, so what a row records about who classified it and who linked its
evidence is what the product records, not what a test wrote into it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.ledger.actions_classification import (
    add_classification_rule,
    apply_classification_rule_match,
    plan_classification_rules,
)
from ...application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    update_manual_transaction_fields,
)
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...application.operations.execution_actor import OperationExecutionCaller
from ...application.operations.frontend_requests import OperationObservationSuccessV1
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import SessionKind
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction
from ..ledger_action_composition import compose_ledger_action_ports
from . import test_registered_executor_conformance as conformance

SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
AGENT_LABEL = f"agent:mcp.attended.{SESSION_CLIENT}"
PERSON_LABEL = "synthetic-person"
ROW_AMOUNT = Decimal("121.00")

_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


class SwitchableSessionHost:
    """A session host whose admitting frontend a test changes between invocations."""

    def __init__(self, frontend: OperationFrontendProjection) -> None:
        self.frontend = frontend

    def __call__(self, identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id.startswith("ledger.")
        return OperationExecutionCaller(
            frontend=self.frontend, session_kind=SessionKind.ATTENDED, client_id=SESSION_CLIENT
        )


def seed_row(
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    *,
    description: str,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> str:
    """Store one row as the person's own entry: unprocessed, or classified by hand."""
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(profile_id),
            booked_date=date(2025, 1, 21),
            amount=ROW_AMOUNT,
            direction=TransactionDirection.OUTGOING,
            description=description,
            business_classification=classification,
            actor=PERSON_LABEL,
        ),
        ports=compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation),
        occurred_at=now(),
    )
    return created.ref.transaction_id


def seed_row_a_rule_classified(profile_id: UUID, operation: PinnedAuthorityOperation, *, description: str) -> str:
    """Store an unprocessed row and let a stored rule classify it as business, as a rule run does."""
    bucket_id = str(profile_id)
    transaction_id = seed_row(profile_id, operation, description=description)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    add_classification_rule(
        bucket_id=bucket_id,
        description_pattern=description,
        classification=BusinessClassification.BUSINESS,
        actor=PERSON_LABEL,
    )
    (match,) = (
        row
        for row in plan_classification_rules(bucket_id=bucket_id, ports=ports).matches
        if row.transaction_id == transaction_id
    )
    applied = apply_classification_rule_match(
        bucket_id=bucket_id,
        row=match,
        actor=PERSON_LABEL,
        source_command="aeat app ledger rule apply",
        reaffirm=False,
        ports=ports,
    )
    assert applied.transaction.classified_by.startswith("rule:")
    return applied.ref.transaction_id


def seed_stored_attachment(profile_id: UUID, operation: PinnedAuthorityOperation, *, reference: str) -> str:
    """Store one attachment's bytes, linked to no row yet."""
    bucket_id = str(profile_id)
    attachment = add_attachment(
        compose_ledger_action_ports(bucket_id=bucket_id, operation=operation).attachment_store,
        content=AttachmentBytesContent(data=_PDF_BYTES + reference.encode("ascii")),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.INLINE,
            source_reference=reference,
            mime_type="application/pdf",
            captured_at=now(),
            bucket_id=bucket_id,
            captured_by=PERSON_LABEL,
            source_command="synthetic seed",
        ),
    )
    return attachment.attachment_id


def attach_as_the_person(
    profile_id: UUID, operation: PinnedAuthorityOperation, *, transaction_id: str, attachment_id: str
) -> None:
    """Link a stored attachment to a row the way the person's own frontend does."""
    bucket_id = str(profile_id)
    attach_manual_transaction_evidence(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        attachment_ids=(attachment_id,),
        actor=PERSON_LABEL,
        source_command="aeat app ledger attach",
        ports=compose_ledger_action_ports(bucket_id=bucket_id, operation=operation),
        occurred_at=now(),
    )


def classify_as_the_person(
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    *,
    transaction_id: str,
    classification: BusinessClassification,
) -> None:
    """Classify a row by hand through the writer the person's own classification reaches."""
    bucket_id = str(profile_id)
    update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=classification),
        actor=PERSON_LABEL,
        source_command="aeat app ledger classify",
        ports=compose_ledger_action_ports(bucket_id=bucket_id, operation=operation),
    )


def seed_invoice(profile_id: UUID, *, number: str) -> str:
    """Store one received invoice for the row's amount beside those already stored."""
    bucket_id = str(profile_id)
    invoice = Invoice.model_validate(
        dict(
            payment_status=PaymentStatus.PENDING,
            kind=InvoiceKind.RECEIVED,
            bucket_id=bucket_id,
            invoice_number=number,
            issued_at=date(2025, 1, 21),
            counterparty_name="Synthetic Supplier",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            base_total=Decimal("100.00"),
            iva_total=Decimal("21.00"),
            grand_total=ROW_AMOUNT,
            currency="EUR",
            lines=(
                InvoiceLine(
                    description="synthetic expense",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100"),
                    subtotal=Decimal("100"),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=Decimal("21"),
                ),
            ),
        )
    )
    repository = InvoiceCatalogueRepository(bucket_id=bucket_id)
    stored = dict(repository.load().invoices) if repository.exists() else {}
    repository.save(InvoiceCatalogue(invoices={**stored, invoice.invoice_id: invoice}))
    return invoice.invoice_id


def stored_row(profile_id: UUID, transaction_id: str, operation: PinnedAuthorityOperation) -> Transaction:
    stored = (
        compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
        .transaction_repository.load()
        .get(transaction_id)
    )
    assert stored is not None
    return stored


def stored_events(profile_id: UUID) -> dict[str, BucketEvent]:
    return dict(bucket_event_history_repository(bucket_id=str(profile_id)).load().events)


def stored_state(
    profile_id: UUID, operation: PinnedAuthorityOperation
) -> tuple[dict[str, Transaction], dict[str, BucketEvent]]:
    """Every stored row and every stored event: what an act that does not take effect leaves as it was."""
    ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
    return dict(ports.transaction_repository.load().transactions), stored_events(profile_id)


def submit(
    driver: conformance._ExecutionDriver, *, definition_id: str, profile_id: UUID, payload: BaseModel
) -> OperationObservationSuccessV1:
    """Run one operation through the real supervisor to where it settles or waits for its review."""

    async def run() -> OperationObservationSuccessV1:
        submitted, _observed = await driver.run(
            definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
        )
        return await driver.observe(submitted.receipt.operation_id)

    return asyncio.run(run())


def review_and_apply(
    driver: conformance._ExecutionDriver,
    *,
    definition_id: str,
    profile_id: UUID,
    payload: BaseModel,
    while_pending: Callable[[], None] = lambda: None,
) -> OperationObservationSuccessV1:
    """Run one review to its pending proposal, answer it with an apply, and return what it settled as.

    ``while_pending`` runs between the proposal and the answer, which is when another
    party can change the row the proposal was made for.
    """

    async def run() -> OperationObservationSuccessV1:
        submitted, waiting = await driver.run(
            definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
        )
        assert waiting.projection.pending_interaction is not None, waiting.projection
        while_pending()
        operation_id = await driver.respond_apply(submitted, waiting)
        # The commit runs on a worker thread, so its end is awaited rather than polled for.
        await driver.services.submission.settled(operation_id)
        return await driver.await_terminal(operation_id)

    return asyncio.run(run())


def succeeded(observed: OperationObservationSuccessV1) -> bool:
    terminal = observed.projection
    return (
        terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        and terminal.effect is OperationEffect.UPDATED
    )


def resolve_result[ResultT: BaseModel](
    driver: conformance._ExecutionDriver,
    registry: OperationRegistry,
    *,
    definition_id: str,
    observed: OperationObservationSuccessV1,
    result_type: type[ResultT],
) -> ResultT:
    return conformance._resolve_result_projection(
        driver,
        registry,
        definition_id=definition_id,
        operation_id=observed.projection.operation_id,
        terminal_revision=observed.projection.revision,
        projection_type=result_type,
    )
