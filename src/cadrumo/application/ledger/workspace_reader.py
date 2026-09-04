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

from .actions_manual import ledger_transaction_payload, summarize_manual_transactions
from .models import LedgerReviewQuery
from .review_projection import project_ledger_review_query
from .workspace import LedgerWorkspaceProjectionV1, project_ledger_workspace

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnitCatalogue
    from ...domain.transactions.models import TransactionCatalogue
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol


def read_ledger_workspace_projection(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
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
    """
    catalogue = transactions if transactions is not None else transaction_repository.load()
    invoice_catalogue = invoices if invoices is not None else invoice_repository.load()
    return project_ledger_workspace(
        summary=summarize_manual_transactions(
            bucket_id=bucket_id,
            transaction_repository=transaction_repository,
            catalogue=catalogue,
        ),
        preflight=None,
        review=project_ledger_review_query(
            LedgerReviewQuery(bucket_id=bucket_id),
            catalogue=catalogue,
            bucket_event_repository=bucket_event_repository,
            transaction_payload_builder=ledger_transaction_payload,
        ),
        transactions=catalogue,
        invoices=invoice_catalogue,
        revisions=calculation_revisions,
        work_units=work_units,
    )


__all__ = ["read_ledger_workspace_projection"]
