"""Lifecycle services for bucket-scoped manual ledger transactions.

Archive, stash, restore, remove, and reset operations mutate a loaded
:class:`TransactionCatalogue`, append bucket events, and return typed
application reports. Removal and reset paths can also update an
:class:`InvoiceCatalogue` through an
:class:`~cadrumo.domain.invoices.InvoiceCatalogueRepositoryProtocol` when
purchase-invoice evidence must be detached.

The public services return
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`,
:class:`~cadrumo.application.ledger.models.LedgerTransactionRemovalReport`, or
:class:`~cadrumo.application.ledger.models.LedgerCatalogueResetReport`.
"""

from __future__ import annotations

from datetime import datetime

from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepositoryProtocol
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction, TransactionCatalogue, TransactionLifecycleLineageEntry
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .actions_common import (
    blocking_modelo_references,
    build_ledger_bucket_event,
    build_manual_ledger_result,
    catalogue_modelo_source_ids,
    draft_revision_advisories,
    normalise_timestamp,
    raise_finalized_modelo_blocked,
    remove_transaction,
    replace_transaction,
    require_actor,
    require_source_command,
    require_transaction,
    resolve_bucket_event_repository,
    resolve_invoice_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
    save_transaction_catalogue_invoices_and_events,
    transaction_catalogue_object_id,
    transaction_modelo_source_ids,
)
from .models import (
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

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    reflecting the archived transaction state.
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

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    reflecting the stashed transaction state.
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

    The clean inverse of
    :func:`~cadrumo.application.ledger.actions_lifecycle.archive_manual_transaction` and
    :func:`~cadrumo.application.ledger.actions_lifecycle.stash_manual_transaction`. Moves ``STASHED -> ACTIVE`` and
    ``ARCHIVED -> ACTIVE`` through the single-writer
    :func:`_transition_manual_transaction_lifecycle` primitive, so it
    inherits that primitive's atomic catalogue-plus-event persistence, its
    lifecycle-lineage append, and the finalized-modelo guard: a row cited by a
    sealed (``VERIFICADO_COMPLETO`` / ``PRESENTADO`` /
    ``PRESENTADO_SUPERSEDIDO``) calculation revision is refused so a restore
    cannot silently change the input basis of an already-filed period. Split
    and merged lineage stays out of scope - only
    :func:`~cadrumo.application.ledger.actions_split_merge.split_transaction` /
    :func:`~cadrumo.application.ledger.actions_split_merge.merge_transactions` move those rows.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    reflecting the restored, now-active transaction state.

    Raises:
        TransactionValidationError: when the row is already active (with an
            instructive message), when the row is part of split lineage, or
            when a finalized-modelo reference blocks the restore.
        TransactionNotFoundError: when no transaction matches ``transaction_id``.
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    current = require_transaction(repository.load(), transaction_id)
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


def mark_transaction_reviewed_excluded(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    source_command: str = "aeat app ledger exclude",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Mark one active ledger transaction as reviewed and excluded from filing.

    Sets the transaction's ``business_classification`` to
    :attr:`~cadrumo.domain.transactions.BusinessClassification.REVIEWED_EXCLUDED` —
    the operator's assertion "I reviewed this, it is not filing-relevant, stop
    surfacing it." The row stays ``ACTIVE`` and visible in the ledger with review
    status ``excluded``, drops out of the review queue, and is omitted from every
    tax aggregation. The operator re-includes it by re-classifying the row
    (``aeat app ledger classify``).

    The finalized-modelo guard refuses the exclusion when the row is cited by a
    sealed (``VERIFICADO_COMPLETO`` / ``PRESENTADO`` / ``PRESENTADO_SUPERSEDIDO``)
    calculation revision, so an exclusion cannot silently change the input basis
    of an already-filed period.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    carrying the uniform mutation quintet.

    Raises:
        TransactionValidationError: when the row is not ``ACTIVE``, when it is
            already ``REVIEWED_EXCLUDED``, or when a finalized-modelo reference
            blocks the exclusion.
        TransactionNotFoundError: when no transaction matches ``transaction_id``.
    """
    now = normalise_timestamp(occurred_at)
    trimmed_actor = require_actor(actor, operation="ledger review exclusion")
    trimmed_source_command = require_source_command(source_command, operation="ledger review exclusion")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be reviewed-excluded; archived, stashed, "
            "and split-parent rows are already out of filing scope",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    if current.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        raise TransactionValidationError(
            "ledger transaction is already reviewed-excluded",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id},
        )
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        raise_finalized_modelo_blocked(
            operation="ledger transaction review exclusion",
            transaction_ids=transaction_modelo_source_ids(current),
            blockers=blockers,
        )
    event = build_ledger_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_REVIEWED_EXCLUDED,
        occurred_at=now,
        actor=trimmed_actor,
        object_id=current.transaction_id,
        payload={
            "source_command": trimmed_source_command,
            "previous_classification": current.business_classification.value,
            "business_classification": BusinessClassification.REVIEWED_EXCLUDED.value,
            "reason": reason.strip(),
        },
    )
    replacement = current.model_copy(
        update={
            "business_classification": BusinessClassification.REVIEWED_EXCLUDED,
            # business_pct is coupled to MIXED; a reviewed-excluded row carries no
            # proportion, so clear it or the persisted row fails validation on load.
            "business_pct": None,
            "classified_by": CLASSIFIED_BY_MANUAL,
            "modified_at": now,
        },
    )
    updated = replace_transaction(catalogue, old_transaction_id=current.transaction_id, replacement=replacement)
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=updated,
        events=(event,),
    )
    return build_manual_ledger_result(bucket_id, replacement, (event.event_id,))


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

    Returns a :class:`~cadrumo.application.ledger.models.LedgerTransactionRemovalReport`
    indicating whether the transaction was removed or blocked by a
    finalized-modelo reference.
    """
    now = normalise_timestamp(occurred_at)
    trimmed_actor = require_actor(actor, operation="ledger removal")
    trimmed_source_command = require_source_command(source_command, operation="ledger removal")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    guard_ids = transaction_modelo_source_ids(current)
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    draft_advisories = draft_revision_advisories(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    invoices = None
    purchase_evidence_ids: tuple[str, ...] = ()
    updated_invoice_catalogue: InvoiceCatalogue | None = None
    if invoice_repository is not None or current.purchase_invoice_evidence_id is not None:
        invoices = resolve_invoice_repository(bucket_id=bucket_id, repository=invoice_repository)
        purchase_evidence_ids, updated_invoice_catalogue = _detach_transaction_from_purchase_evidence(
            invoices.load(),
            bucket_id=bucket_id,
            transaction_id=current.transaction_id,
        )
    attachment_ids = tuple(sorted(current.attachment_ids))
    if blockers:
        if not dry_run:
            raise_finalized_modelo_blocked(
                operation="ledger transaction removal",
                transaction_ids=transaction_modelo_source_ids(current),
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
    updated_transaction_catalogue = remove_transaction(catalogue, transaction_id=current.transaction_id)
    if invoices is None or updated_invoice_catalogue is None:
        save_transaction_catalogue_and_events(
            transaction_repository=repository,
            event_repository=event_repository,
            catalogue=updated_transaction_catalogue,
            events=events,
        )
    else:
        save_transaction_catalogue_invoices_and_events(
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

    Returns a :class:`~cadrumo.application.ledger.models.LedgerCatalogueResetReport`.
    """
    now = normalise_timestamp(occurred_at)
    trimmed_actor = require_actor(actor, operation="ledger reset")
    trimmed_source_command = require_source_command(source_command, operation="ledger reset")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    removed_ids = tuple(sorted(catalogue.transactions))
    guard_ids = catalogue_modelo_source_ids(catalogue)
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    draft_advisories = draft_revision_advisories(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    invoices = None
    invoice_catalogue = InvoiceCatalogue()
    purchase_evidence_ids: tuple[str, ...] = ()
    updated_invoice_catalogue: InvoiceCatalogue | None = None
    if invoice_repository is not None or any(
        transaction.purchase_invoice_evidence_id is not None for transaction in catalogue.values()
    ):
        invoices = resolve_invoice_repository(bucket_id=bucket_id, repository=invoice_repository)
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
            raise_finalized_modelo_blocked(
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
    reset_event = build_ledger_bucket_event(
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
        save_transaction_catalogue_and_events(
            transaction_repository=repository,
            event_repository=event_repository,
            catalogue=TransactionCatalogue(),
            events=(*removal_events, reset_event),
        )
    else:
        save_transaction_catalogue_invoices_and_events(
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
    now = normalise_timestamp(occurred_at)
    trimmed_actor = require_actor(actor, operation="ledger lifecycle")
    trimmed_source_command = require_source_command(source_command, operation="ledger lifecycle")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
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
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        raise_finalized_modelo_blocked(
            operation="ledger transaction lifecycle transition",
            transaction_ids=transaction_modelo_source_ids(current),
            blockers=blockers,
        )
    event = build_ledger_bucket_event(
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
    updated = replace_transaction(catalogue, old_transaction_id=current.transaction_id, replacement=replacement)
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=updated,
        events=(event,),
    )
    return build_manual_ledger_result(bucket_id, replacement, (event.event_id,))


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
            build_ledger_bucket_event(
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
            build_ledger_bucket_event(
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
        build_ledger_bucket_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_TRANSACTION_REMOVED,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction.transaction_id,
            payload={
                "source_command": source_command,
                "reason": reason,
                # Counts, never the joined id lists. A payload value is capped at
                # 500 characters, and attachment ids are hex-64, so eight of them
                # joined on commas is 519 and the row could not construct the event
                # recording its own removal. Nothing is lost: each cascaded id is
                # already carried as the object_id of its own event in this same
                # batch, emitted above. Both counts are kept rather than only their
                # sum so the cascade stays decomposable by kind; a count cannot
                # outgrow the cap.
                "purchase_invoice_evidence_count": str(len(purchase_evidence_ids)),
                "attachment_count": str(len(attachment_ids)),
                "cascade_count": str(len(purchase_evidence_ids) + len(attachment_ids)),
            },
        ),
    )
    return tuple(events)


__all__ = [
    "archive_manual_transaction",
    "mark_transaction_reviewed_excluded",
    "remove_manual_transaction",
    "reset_ledger_catalogue",
    "restore_manual_transaction",
    "stash_manual_transaction",
]
