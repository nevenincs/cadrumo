"""Application services for bucket-scoped manual ledger transactions.

Services operate over a :class:`TransactionCatalogueRepository` for ledger
state, a :class:`BucketEventHistoryRepository` for durable audit events, and
an optional :class:`InvoiceCatalogueRepository` for purchase-invoice evidence
cascade on removal. The inner functions accept a :class:`TransactionCatalogue`
or :class:`InvoiceCatalogue` directly when the caller supplies pre-loaded data.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
from ...domain.invoices._protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionLifecycleLineageEntry,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ._actions_common import (
    _blocking_modelo_references,
    _bucket_event_repository,
    _build_bucket_event,
    _catalogue_modelo_source_ids,
    _draft_revision_advisories,
    _invoice_repository,
    _normalise_timestamp,
    _raise_finalized_modelo_blocked,
    _remove_transaction,
    _replace_transaction,
    _require_actor,
    _require_source_command,
    _require_transaction,
    _result,
    _save_transaction_catalogue_and_events,
    _save_transaction_catalogue_invoices_and_events,
    _transaction_modelo_source_ids,
    _transaction_repository,
    transaction_catalogue_object_id,
)
from ._models import (
    LedgerCatalogueResetReport,
    LedgerTransactionRemovalReport,
    ManualLedgerTransactionResult,
)


def archive_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    source_command: str = "aeat app ledger archive",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Mark one bucket-scoped ledger transaction as archived.

    Returns a :class:`ManualLedgerTransactionResult` reflecting the
    archived transaction state.
    """
    return _transition_manual_transaction_lifecycle(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        state=TransactionLifecycleState.ARCHIVED,
        event_type=BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
        actor=actor,
        reason=reason,
        source_command=source_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def stash_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    source_command: str = "aeat app ledger stash",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Mark one active bucket-scoped ledger transaction as stashed.

    Returns a :class:`ManualLedgerTransactionResult` reflecting the
    stashed transaction state.
    """
    return _transition_manual_transaction_lifecycle(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        state=TransactionLifecycleState.STASHED,
        event_type=BucketEventType.LEDGER_TRANSACTION_STASHED,
        actor=actor,
        reason=reason,
        source_command=source_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def restore_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    source_command: str = "aeat app ledger restore",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Restore one stashed or archived ledger transaction to active.

    The clean inverse of :func:`archive_manual_transaction` and
    :func:`stash_manual_transaction`. Moves ``STASHED -> ACTIVE`` and
    ``ARCHIVED -> ACTIVE`` through the single-writer
    :func:`_transition_manual_transaction_lifecycle` primitive, so it
    inherits that primitive's atomic catalogue-plus-event persistence, its
    lifecycle-lineage append, and the finalized-modelo guard: a row cited by a
    sealed (``VERIFICADO_COMPLETO`` / ``PRESENTADO`` /
    ``PRESENTADO_SUPERSEDIDO``) calculation revision is refused so a restore
    cannot silently change the input basis of an already-filed period. Split
    and merged lineage stays out of scope — only
    :func:`split_transaction` / :func:`merge_transactions` move those rows.

    Returns a :class:`ManualLedgerTransactionResult` reflecting the
    restored, now-active transaction state.

    Raises:
        TransactionValidationError: when the row is already active (with an
            instructive message), when the row is part of split lineage, or
            when a finalized-modelo reference blocks the restore.
        TransactionNotFoundError: when no transaction matches ``transaction_id``.
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    current = _require_transaction(repository.load(), transaction_id)
    if current.lifecycle_state is TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "ledger transaction is already active; restore applies only to a stashed or archived row",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "state": current.lifecycle_state.value,
            },
        )
    if current.lifecycle_state is TransactionLifecycleState.SPLIT:
        raise TransactionValidationError(
            "split-parent ledger transactions cannot be restored; re-merge the split children instead",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "state": current.lifecycle_state.value,
            },
        )
    return _transition_manual_transaction_lifecycle(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        state=TransactionLifecycleState.ACTIVE,
        event_type=BucketEventType.LEDGER_TRANSACTION_RESTORED,
        actor=actor,
        reason=reason,
        source_command=source_command,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def remove_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    dry_run: bool = False,
    source_command: str = "aeat app ledger remove",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LedgerTransactionRemovalReport:
    """Remove one bucket-scoped ledger transaction after finalized-modelo checks.

    Returns a :class:`LedgerTransactionRemovalReport` indicating whether
    the transaction was removed or blocked by a finalized-modelo reference.
    """
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger removal")
    trimmed_source_command = _require_source_command(source_command, operation="ledger removal")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    guard_ids = _transaction_modelo_source_ids(current)
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    draft_advisories = _draft_revision_advisories(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    invoices: InvoiceCatalogueRepository | None = None
    purchase_evidence_ids: tuple[str, ...] = ()
    updated_invoice_catalogue: InvoiceCatalogue | None = None
    if invoice_repository is not None or current.purchase_invoice_evidence_id is not None:
        invoices = _invoice_repository(bucket_id=bucket_id, repository=invoice_repository)
        purchase_evidence_ids, updated_invoice_catalogue = _detach_transaction_from_purchase_evidence(
            invoices.load(),
            bucket_id=bucket_id,
            transaction_id=current.transaction_id,
        )
    attachment_ids = tuple(sorted(current.attachment_ids))
    if blockers:
        if not dry_run:
            _raise_finalized_modelo_blocked(
                operation="ledger transaction removal",
                transaction_ids=_transaction_modelo_source_ids(current),
                blockers=blockers,
            )
        return LedgerTransactionRemovalReport(
            bucket_id=bucket_id,
            transaction_id=current.transaction_id,
            dry_run=dry_run,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
            blocking_modelo_references=blockers,
            stale_draft_revision_references=draft_advisories,
        )
    if dry_run:
        return LedgerTransactionRemovalReport(
            bucket_id=bucket_id,
            transaction_id=current.transaction_id,
            dry_run=True,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
            stale_draft_revision_references=draft_advisories,
        )

    events = _removal_events(
        bucket_id=bucket_id,
        transaction=current,
        actor=trimmed_actor,
        reason=reason.strip(),
        source_command=trimmed_source_command,
        purchase_evidence_ids=purchase_evidence_ids,
        attachment_ids=attachment_ids,
        occurred_at=now,
    )
    updated_transaction_catalogue = _remove_transaction(catalogue, transaction_id=current.transaction_id)
    if invoices is None or updated_invoice_catalogue is None:
        _save_transaction_catalogue_and_events(
            transaction_repository=repository,
            event_repository=event_repository,
            catalogue=updated_transaction_catalogue,
            events=events,
        )
    else:
        _save_transaction_catalogue_invoices_and_events(
            transaction_repository=repository,
            invoice_repository=invoices,
            event_repository=event_repository,
            transaction_catalogue=updated_transaction_catalogue,
            invoice_catalogue=updated_invoice_catalogue,
            events=events,
        )
    return LedgerTransactionRemovalReport(
        bucket_id=bucket_id,
        transaction_id=current.transaction_id,
        removed=True,
        actor=trimmed_actor,
        reason=reason.strip(),
        cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
        cascaded_attachment_ids=attachment_ids,
        stale_draft_revision_references=draft_advisories,
        bucket_event_ids=tuple(event.event_id for event in events),
    )


def reset_ledger_catalogue(
    *,
    bucket_id: str,
    actor: str,
    reason: str = "",
    dry_run: bool = False,
    source_command: str = "aeat app ledger reset",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LedgerCatalogueResetReport:
    """Reset one bucket's ledger catalogue after finalized-modelo checks.

    Returns a :class:`LedgerCatalogueResetReport`.
    """
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger reset")
    trimmed_source_command = _require_source_command(source_command, operation="ledger reset")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    removed_ids = tuple(sorted(catalogue.transactions))
    guard_ids = _catalogue_modelo_source_ids(catalogue)
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    draft_advisories = _draft_revision_advisories(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    invoices: InvoiceCatalogueRepository | None = None
    invoice_catalogue = InvoiceCatalogue()
    purchase_evidence_ids: tuple[str, ...] = ()
    updated_invoice_catalogue: InvoiceCatalogue | None = None
    if invoice_repository is not None or any(
        transaction.purchase_invoice_evidence_id is not None for transaction in catalogue.values()
    ):
        invoices = _invoice_repository(bucket_id=bucket_id, repository=invoice_repository)
        invoice_catalogue = invoices.load()
        purchase_evidence_ids, updated_invoice_catalogue = _detach_transactions_from_purchase_evidence(
            invoice_catalogue,
            bucket_id=bucket_id,
            transaction_ids=removed_ids,
        )
    attachment_ids = tuple(
        sorted({attachment_id for transaction in catalogue.values() for attachment_id in transaction.attachment_ids}),
    )
    if blockers:
        if not dry_run:
            _raise_finalized_modelo_blocked(
                operation="ledger catalogue reset",
                transaction_ids=guard_ids,
                blockers=blockers,
            )
        return LedgerCatalogueResetReport(
            bucket_id=bucket_id,
            removed_transaction_ids=removed_ids,
            dry_run=dry_run,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
            blocking_modelo_references=blockers,
            stale_draft_revision_references=draft_advisories,
        )
    if dry_run:
        return LedgerCatalogueResetReport(
            bucket_id=bucket_id,
            removed_transaction_ids=removed_ids,
            dry_run=True,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
            stale_draft_revision_references=draft_advisories,
        )
    removal_events = tuple(
        event
        for transaction in sorted(catalogue.values(), key=lambda item: item.transaction_id)
        for event in _removal_events(
            bucket_id=bucket_id,
            transaction=transaction,
            actor=trimmed_actor,
            reason=reason.strip(),
            source_command=trimmed_source_command,
            purchase_evidence_ids=tuple(
                invoice_id
                for invoice_id, invoice in invoice_catalogue.invoices.items()
                if invoice.bucket_id == bucket_id and transaction.transaction_id in invoice.linked_transaction_ids
            ),
            attachment_ids=tuple(sorted(transaction.attachment_ids)),
            occurred_at=now,
        )
    )
    reset_event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_CATALOGUE_RESET,
        occurred_at=now,
        actor=trimmed_actor,
        object_type=BucketEventObjectType.LEDGER_CATALOGUE,
        object_id=transaction_catalogue_object_id(bucket_id),
        payload={
            "source_command": trimmed_source_command,
            "reason": reason.strip(),
            "removed_transaction_count": str(len(removed_ids)),
        },
    )
    if invoices is None or updated_invoice_catalogue is None:
        _save_transaction_catalogue_and_events(
            transaction_repository=repository,
            event_repository=event_repository,
            catalogue=TransactionCatalogue(),
            events=(*removal_events, reset_event),
        )
    else:
        _save_transaction_catalogue_invoices_and_events(
            transaction_repository=repository,
            invoice_repository=invoices,
            event_repository=event_repository,
            transaction_catalogue=TransactionCatalogue(),
            invoice_catalogue=updated_invoice_catalogue,
            events=(*removal_events, reset_event),
        )
    return LedgerCatalogueResetReport(
        bucket_id=bucket_id,
        removed_transaction_ids=removed_ids,
        reset=True,
        actor=trimmed_actor,
        reason=reason.strip(),
        cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
        cascaded_attachment_ids=attachment_ids,
        stale_draft_revision_references=draft_advisories,
        bucket_event_ids=tuple(event.event_id for event in (*removal_events, reset_event)),
    )


def _transition_manual_transaction_lifecycle(
    *,
    bucket_id: str,
    transaction_id: str,
    state: TransactionLifecycleState,
    event_type: BucketEventType,
    actor: str,
    reason: str,
    source_command: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
    occurred_at: datetime | None,
) -> ManualLedgerTransactionResult:
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger lifecycle")
    trimmed_source_command = _require_source_command(source_command, operation="ledger lifecycle")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    if current.lifecycle_state is state:
        raise TransactionValidationError(
            f"ledger transaction is already {state.value.lower()}",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id, "state": state.value},
        )
    if current.lifecycle_state is TransactionLifecycleState.ARCHIVED and state is TransactionLifecycleState.STASHED:
        raise TransactionValidationError(
            "archived ledger transactions cannot be stashed",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id},
        )
    if current.lifecycle_state is TransactionLifecycleState.SPLIT or state is TransactionLifecycleState.SPLIT:
        raise TransactionValidationError(
            "split-lineage transitions are only available through split_transaction / merge_transactions",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "current_state": current.lifecycle_state.value,
                "requested_state": state.value,
            },
        )
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=_transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger transaction lifecycle transition",
            transaction_ids=_transaction_modelo_source_ids(current),
            blockers=blockers,
        )
    event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=now,
        actor=trimmed_actor,
        object_id=current.transaction_id,
        payload={
            "source_command": trimmed_source_command,
            "previous_lifecycle_state": current.lifecycle_state.value,
            "lifecycle_state": state.value,
            "reason": reason.strip(),
        },
    )
    lifecycle_entry = TransactionLifecycleLineageEntry(
        previous_state=current.lifecycle_state,
        state=state,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        changed_at=now,
        reason=reason,
        bucket_event_id=event.event_id,
    )
    replacement = current.model_copy(
        update={
            "lifecycle_state": state,
            "lifecycle_lineage": (*current.lifecycle_lineage, lifecycle_entry),
            # D6: a lifecycle transition is a mutating edit; re-stamp modified_at.
            "modified_at": now,
        },
    )
    updated = _replace_transaction(catalogue, old_transaction_id=current.transaction_id, replacement=replacement)
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=updated,
        events=(event,),
    )
    return _result(bucket_id, replacement, (event.event_id,))


def _detach_transaction_from_purchase_evidence(
    catalogue: InvoiceCatalogue,
    *,
    bucket_id: str,
    transaction_id: str,
) -> tuple[tuple[str, ...], InvoiceCatalogue]:
    return _detach_transactions_from_purchase_evidence(
        catalogue,
        bucket_id=bucket_id,
        transaction_ids=(transaction_id,),
    )


def _detach_transactions_from_purchase_evidence(
    catalogue: InvoiceCatalogue,
    *,
    bucket_id: str,
    transaction_ids: tuple[str, ...],
) -> tuple[tuple[str, ...], InvoiceCatalogue]:
    detached_ids: list[str] = []
    wanted = set(transaction_ids)
    updated_invoices = dict(catalogue.invoices)
    for invoice_id, invoice in catalogue.invoices.items():
        if invoice.bucket_id != bucket_id or not wanted.intersection(invoice.linked_transaction_ids):
            continue
        remaining_links = tuple(item for item in invoice.linked_transaction_ids if item not in wanted)
        updated_invoices[invoice_id] = invoice.model_copy(update={"linked_transaction_ids": remaining_links})
        detached_ids.append(invoice_id)
    return tuple(sorted(detached_ids)), InvoiceCatalogue.model_validate({"invoices": updated_invoices})


def _removal_events(
    *,
    bucket_id: str,
    transaction: Transaction,
    actor: str,
    reason: str,
    source_command: str,
    purchase_evidence_ids: tuple[str, ...],
    attachment_ids: tuple[str, ...],
    occurred_at: datetime,
) -> tuple[BucketEvent, ...]:
    events: list[BucketEvent] = []
    for evidence_id in purchase_evidence_ids:
        events.append(
            _build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                object_id=evidence_id,
                payload={
                    "source_command": source_command,
                    "transaction_id": transaction.transaction_id,
                    "reason": reason,
                    "mutation_kind": "ledger_transaction_removed",
                },
            ),
        )
    for attachment_id in attachment_ids:
        events.append(
            _build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.ATTACHMENT_REMOVED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.ATTACHMENT,
                object_id=attachment_id,
                payload={
                    "source_command": source_command,
                    "transaction_id": transaction.transaction_id,
                    "reason": reason,
                    "mutation_kind": "ledger_transaction_removed",
                },
            ),
        )
    events.append(
        _build_bucket_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_TRANSACTION_REMOVED,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction.transaction_id,
            payload={
                "source_command": source_command,
                "reason": reason,
                "purchase_invoice_evidence_ids": ",".join(purchase_evidence_ids),
                "attachment_ids": ",".join(attachment_ids),
                "cascade_count": str(len(purchase_evidence_ids) + len(attachment_ids)),
            },
        ),
    )
    return tuple(events)
