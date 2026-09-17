"""Read one Ledger workspace projection from an authenticated profile's stores.

:mod:`cadrumo.application.ledger.workspace` is deliberately pure: it joins
already-loaded canonical facts. Something still has to LOAD those facts for an
installed session, and doing it inside the projector would put persistence
inside a pure join. This module is that reader, and it is the only one — the
installed workbench and any other host resolve the same door rather than each
assembling the fact set their own way.

The reader performs local reads only. It opens no network client, starts no
operation, and never widens the caller's bucket: every fact is read through
the repositories the caller already bound to one authenticated profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors.hierarchy import InternalInvariantError
from ...domain.buckets.event import BucketEventType, bucket_event_order_key
from .action_ports import LedgerActionPorts
from .actions_manual import ledger_transaction_payload, summarize_manual_transactions
from .attachment_review import list_attachment_review_queue
from .confirmation_record import load_confirmation_records
from .models import LedgerReviewQuery
from .review_projection import project_ledger_review_query
from .workspace import LedgerWorkspaceProjectionV1, project_ledger_workspace

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.buckets.event import BucketEventHistoryCatalogue
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnitCatalogue
    from ...domain.transactions.models import TransactionCatalogue


def read_ledger_workspace_projection(
    *,
    bucket_id: str,
    ports: LedgerActionPorts,
    calculation_revisions: Mapping[str, CalculationRevision],
    work_units: WorkUnitCatalogue,
    transactions: TransactionCatalogue | None = None,
    invoices: InvoiceCatalogue | None = None,
) -> LedgerWorkspaceProjectionV1:
    """Load one profile's ledger facts once and project the workspace snapshot.

    ``transactions`` and ``invoices`` let a caller that has already read this
    bucket hand those exact catalogues in, so the snapshot it later re-reads to
    check for a mid-capture write is the same one the projection was built
    from. Omitted, they are read here.

    The preflight report is left to the projector's own period-free default:
    tax readiness is a period-bound question, and the landing view is not
    scoped to a period, so asserting readiness here would answer a question
    the operator has not yet asked.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
    :class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`,
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    catalogue = transactions if transactions is not None else ports.transaction_repository.load()
    invoice_catalogue = invoices if invoices is not None else ports.invoice_repository.load()
    events = ports.bucket_event_repository.load()
    return project_ledger_workspace(
        summary=summarize_manual_transactions(
            bucket_id=bucket_id,
            ports=ports,
            catalogue=catalogue,
        ),
        preflight=None,
        review=project_ledger_review_query(
            LedgerReviewQuery(bucket_id=bucket_id),
            catalogue=catalogue,
            bucket_event_repository=ports.bucket_event_repository,
            transaction_payload_builder=ledger_transaction_payload,
        ),
        transactions=catalogue,
        invoices=invoice_catalogue,
        revisions=calculation_revisions,
        work_units=work_units,
        evidence_pending_review=_evidence_pending_review(bucket_id=bucket_id, ports=ports, events=events),
        last_import_count=_last_import_count(events),
    )


def _evidence_pending_review(
    *, bucket_id: str, ports: LedgerActionPorts, events: BucketEventHistoryCatalogue
) -> int | None:
    """Count evidence the operator still has to act on.

    Two queues feed the area: attachments awaiting review in the bucket's
    attachment store, and locally added invoice evidence that has been neither
    confirmed as an invoice nor declined. The confirmation store is composed
    per invocation; where it is not, the count is unmeasured rather than
    guessed.
    """
    queued = len(list_attachment_review_queue(ports.attachment_store))
    records = ports.purchase_invoice_evidence_records
    if not records:
        return queued
    try:
        confirmations = load_confirmation_records(bucket_id)
    except InternalInvariantError:
        return None
    settled = {record.evidence_reference for record in confirmations.records}
    settled.update(
        event.object_id
        for event in events.events.values()
        if event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_DRAFT_DECLINED
    )
    return queued + sum(1 for record in records if record.evidence_id not in settled)


def _last_import_count(events: BucketEventHistoryCatalogue) -> int:
    """Return how many rows the most recent ledger import added, or zero."""
    imported = sorted(
        (event for event in events.events.values() if event.event_type is BucketEventType.LEDGER_TRANSACTION_IMPORTED),
        key=bucket_event_order_key,
    )
    if not imported:
        return 0
    last_batch = imported[-1].payload.get("import_batch_id")
    return sum(1 for event in imported if event.payload.get("import_batch_id") == last_batch)


__all__ = ["read_ledger_workspace_projection"]
