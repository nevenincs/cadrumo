"""Registered-executor conformance scenarios for ledger export and invoice linkage."""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from decimal import Decimal
from io import StringIO

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...application.export.tabular import ExportSerializationFormat
from ...application.ledger.actions_common import build_manual_ledger_result
from ...application.ledger.actions_lifecycle import archive_manual_transaction
from ...application.ledger.actions_manual import ledger_transaction_result_payload
from ...application.ledger.export_operation import (
    LEDGER_EXPORT_OPERATION_DEFINITION_ID,
    LedgerExportProjection,
    LedgerExportRequest,
    LedgerExportRowProjection,
)
from ...application.ledger.link_operation import (
    LEDGER_LINK_OPERATION_DEFINITION_ID,
    LedgerLinkOperationResult,
    LedgerLinkProjection,
    LedgerLinkRequest,
)
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...application.operations.public_period import PublicPeriod
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .conformance_ledger_seed_support import SEED_ACTOR, ledger_action_ports, seed_manual_transaction

_FIRST_QUARTER = Period.from_year_and_code(2025, "1T")
_CSV_MEDIA_TYPE = "text/csv"


def _new_events(context: ConformanceFamilyContext, before_ids: frozenset[str]) -> tuple[BucketEvent, ...]:
    events = ledger_action_ports(context).bucket_event_repository.load().events
    return tuple(event for event_id, event in events.items() if event_id not in before_ids)


def _prepare_export(context: ConformanceFamilyContext) -> ConformancePreparation:
    early = seed_manual_transaction(
        context, booked_date=date(2025, 1, 15), amount=Decimal("12.50"), description="export row early in period"
    )
    late = seed_manual_transaction(
        context, booked_date=date(2025, 3, 20), amount=Decimal("30.00"), description="export row late in period"
    )
    # Neither of these may reach the artifact: one is booked after the period
    # and the other is inside it but no longer active.
    seed_manual_transaction(
        context, booked_date=date(2025, 4, 10), amount=Decimal("44.00"), description="export row after period"
    )
    archived = seed_manual_transaction(
        context, booked_date=date(2025, 2, 1), amount=Decimal("55.00"), description="export row archived in period"
    )
    ports = ledger_action_ports(context)
    archive_manual_transaction(
        bucket_id=str(context.profile_id),
        transaction_id=archived,
        actor=SEED_ACTOR,
        reason="excluded from the export by lifecycle state",
        ports=ports,
    )
    events_before = frozenset(ports.bucket_event_repository.load().events)
    output_path = context.input_root / "ledger-export.csv"
    expected_rows = ((early, "export row early in period", "12.50"), (late, "export row late in period", "30.00"))

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(LedgerExportProjection)
        assert projection.profile_id == context.profile_id
        assert projection.bucket_id == str(context.profile_id)
        assert projection.export_format is ExportSerializationFormat.CSV
        assert projection.media_type == _CSV_MEDIA_TYPE
        assert projection.output_path == str(output_path)
        # Active rows inside the period, ordered by effective date then id.
        # actions_export.py `_ledger_export_rows`.
        assert [row.transaction_id for row in projection.rows] == [row[0] for row in expected_rows]
        assert projection.row_count == len(expected_rows)
        assert projection.fieldnames == tuple(LedgerExportRowProjection.model_fields)

        payload = output_path.read_bytes()
        assert projection.byte_size == len(payload)
        assert projection.sha256 == hashlib.sha256(payload).hexdigest()
        table = list(csv.DictReader(StringIO(payload.decode("utf-8"), newline="")))
        assert [row["transaction_id"] for row in table] == [row[0] for row in expected_rows]
        assert [row["description"] for row in table] == [row[1] for row in expected_rows]
        assert [Decimal(row["amount"]) for row in table] == [Decimal(row[2]) for row in expected_rows]
        assert all(row["lifecycle_state"] == "ACTIVE" for row in table)

        new_events = _new_events(context, events_before)
        assert len(new_events) == 1
        event = new_events[0]
        assert event.event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
        assert event.object_type is BucketEventObjectType.LEDGER_EXPORT
        assert event.object_id == projection.export_id
        assert projection.bucket_event_ids == (event.event_id,)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=LedgerExportRequest(
            profile_id=context.profile_id,
            output_path=str(output_path),
            period=PublicPeriod.from_period(_FIRST_QUARTER),
        ),
        verify=verify,
    )


def _seed_invoice(context: ConformanceFamilyContext) -> Invoice:
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": str(context.profile_id),
            "invoice_number": "LINK-2025-001",
            "issued_at": date(2025, 5, 1),
            "counterparty_name": "Conformance Supplier",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine(
                    description="Conformance linked invoice",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("100.00"),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=Decimal("21.00"),
                ),
            ),
        }
    )
    InvoiceCatalogueRepository(bucket_id=str(context.profile_id)).save(
        InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
    )
    return invoice


def _prepare_link(context: ConformanceFamilyContext) -> ConformancePreparation:
    bucket_id = str(context.profile_id)
    transaction_id = seed_manual_transaction(
        context, booked_date=date(2025, 5, 1), amount=Decimal("121.00"), description="link row"
    )
    invoice = _seed_invoice(context)
    ports = ledger_action_ports(context)
    events_before = frozenset(ports.bucket_event_repository.load().events)
    requested_prefix = transaction_id[:12]

    def verify(outcome: ConformanceOutcome) -> None:
        after = ledger_action_ports(context)
        # Linkage is reciprocal: the row cites the invoice and the invoice cites the row.
        # actions_manual.py `link_manual_transaction_invoice`.
        transaction = after.transaction_repository.load().get(transaction_id)
        assert transaction is not None
        assert transaction.invoice_id == invoice.invoice_id
        linked_invoice = after.invoice_repository.load().get(invoice.invoice_id)
        assert linked_invoice is not None
        assert linked_invoice.linked_transaction_ids == (transaction_id,)

        new_events = _new_events(context, events_before)
        assert len(new_events) == 1
        event = new_events[0]
        assert event.event_type is BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED
        assert event.object_id == transaction_id
        assert event.payload["invoice_id"] == invoice.invoice_id

        canonical = ledger_transaction_result_payload(
            build_manual_ledger_result(bucket_id, transaction, (event.event_id,))
        )
        expected = LedgerLinkOperationResult(
            profile_id=context.profile_id,
            transaction_id=requested_prefix,
            invoice_id=invoice.invoice_id,
            outcome="linked",
            projection=LedgerLinkProjection(
                profile_id=context.profile_id,
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                invoice_id=invoice.invoice_id,
                # No actor in the request: link_operation.py `_apply_link` defaults to "operator".
                actor="operator",
                bucket_event_ids=(event.event_id,),
                review_status=canonical.review_status,
                transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
            ),
        )
        assert outcome.resolve_result(LedgerLinkOperationResult) == expected

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerLinkRequest(
            profile_id=context.profile_id, transaction_id=requested_prefix, invoice_id=invoice.invoice_id
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == LEDGER_EXPORT_OPERATION_DEFINITION_ID:
        return _prepare_export(context)
    if definition_id == LEDGER_LINK_OPERATION_DEFINITION_ID:
        return _prepare_link(context)
    raise AssertionError(f"no ledger export/link conformance scenario for {definition_id}")


LEDGER_EXPORT_LINK_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # Both publish the single phase named after the definition and persist a
        # bucket event, so each settles UPDATED. export_operation.py, link_operation.py.
        RegisteredExecutorConformanceCase(
            LEDGER_EXPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_EXPORT_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_LINK_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_LINK_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
