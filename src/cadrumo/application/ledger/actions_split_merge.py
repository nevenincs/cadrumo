"""Split and merge services for manual ledger transaction lineage.

Split operations load a :class:`TransactionCatalogue` through a
:class:`TransactionCatalogueRepositoryProtocol`, mark parent and child rows with
:class:`~cadrumo.domain.transactions.SplitLineage`, append audit events through a
:class:`BucketEventHistoryRepositoryProtocol`, and return
:class:`~cadrumo.application.ledger.models.SplitTransactionResult`. Merge operations
verify the complete child cohort and return
:class:`~cadrumo.application.ledger.models.MergeTransactionsResult`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.hashing import sha256_hex
from ...domain.buckets import BucketEvent, BucketEventHistoryRepositoryProtocol, BucketEventType
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    SplitLineage,
    SplitRole,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepositoryProtocol,
    TransactionLifecycleLineageEntry,
    TransactionLifecycleState,
    TransactionValidationError,
    derive_split_group_id,
)
from .actions_common import (
    _bucket_event_repository,
    _build_bucket_event,
    _invoice_repository,
    _normalise_timestamp,
    _raise_finalized_modelo_blocked,
    _require_actor,
    _require_source_command,
    _require_transaction,
    _save_transaction_catalogue_and_events,
    _transaction_modelo_source_ids,
    _transaction_repository,
    blocking_modelo_references,
)
from .actions_manual import (
    command_from_patch as _command_from_patch,
)
from .actions_manual import (
    prepare_manual_transaction_update as _prepare_manual_transaction_update,
)
from .models import (
    ManualLedgerTransactionPatch,
    MergeTransactionsResult,
    SplitChildCommand,
    SplitTransactionResult,
)

if TYPE_CHECKING:
    from ...domain.attachments import AttachmentStoreProtocol
    from ...domain.invoices import InvoiceCatalogueRepositoryProtocol


def split_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    children: tuple[SplitChildCommand, ...],
    actor: str,
    source_command: str = "aeat app ledger split",
    reason: str = "",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> SplitTransactionResult:
    """Redistribute one parent transaction into N child transactions.

    Pre-conditions:

    - Parent must be in ACTIVE lifecycle state.
    - Parent must not be referenced by a finalized modelo calculation.
    - At least two children must be supplied.
    - Sum of child amounts equals the parent amount exactly (no rounding).
    - Child amounts are non-negative magnitudes; direction is inherited
      from the parent (the builder copies ``parent.direction``).

    Effect:

    - Parent transitions ACTIVE -> SPLIT and gains
      ``split_lineage`` with role=PARENT and the child ids as siblings.
    - Each child is persisted as ACTIVE with
      ``split_lineage`` role=CHILD and (parent + other-child) ids as siblings.
    - Children inherit currency, direction, and (by default)
      counterparty / booked_date / value_date from the parent.
    - Children default to ``BusinessClassification.NOT_YET_PROCESSED``
      to force conscious tax treatment per row; classification, evidence,
      and attachment links are NOT auto-cloned.
    - A single ``LEDGER_TRANSACTION_SPLIT`` event is emitted, anchored on
      the parent transaction id so ``for_object(parent_id)`` returns the
      whole lineage chain in chronological order.
    - Catalogue + event are persisted atomically.

    Returns a :class:`~cadrumo.application.ledger.models.SplitTransactionResult`.
    """
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger split")
    trimmed_source_command = _require_source_command(source_command, operation="ledger split")
    if len(children) < 2:
        raise TransactionValidationError(
            "ledger split requires at least two children",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id, "child_count": len(children)},
        )
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    parent_after, final_children, event, split_group_id, child_ids = _build_split_state(
        catalogue=catalogue,
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        children=children,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        reason=reason,
        now=now,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )

    updated_transactions = dict(catalogue.transactions)
    updated_transactions[parent_after.transaction_id] = parent_after
    for child_transaction in final_children:
        updated_transactions[child_transaction.transaction_id] = child_transaction
    new_catalogue = TransactionCatalogue.model_validate({"transactions": updated_transactions})

    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=new_catalogue,
        events=(event,),
    )

    return SplitTransactionResult(
        bucket_id=bucket_id,
        parent_transaction_id=parent_after.transaction_id,
        split_group_id=split_group_id,
        child_transaction_ids=child_ids,
        parent_transaction=parent_after,
        child_transactions=final_children,
        bucket_event_id=event.event_id,
    )


def _build_split_state(
    *,
    catalogue: TransactionCatalogue,
    bucket_id: str,
    transaction_id: str,
    children: tuple[SplitChildCommand, ...],
    actor: str,
    source_command: str,
    reason: str,
    now: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> tuple[Transaction, tuple[Transaction, ...], BucketEvent, str, tuple[str, ...]]:
    """Build the parent transition, child rows, and split event in memory.

    Resolves and guards the parent, validates the child amounts, and returns the
    ``(parent_after, final_children, split_event, split_group_id, child_ids)``
    tuple without persisting anything. Both :func:`split_transaction` and the
    atomic evidence-driven classified split reuse this builder so the split shape
    is defined once.
    """
    parent = _resolve_active_split_parent(catalogue, bucket_id=bucket_id, transaction_id=transaction_id)
    _reject_split_with_finalized_modelo_blockers(
        parent=parent,
        bucket_id=bucket_id,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    _validate_split_child_amounts(parent_amount=parent.raw.amount, children=children)

    child_amounts = tuple(child.amount for child in children)
    child_narratives = tuple(child.description for child in children)
    split_group_id = derive_split_group_id(
        parent_transaction_id=parent.transaction_id,
        child_amounts=child_amounts,
        child_narratives=child_narratives,
    )

    child_transactions_initial = tuple(
        _build_split_child_transaction(
            parent=parent,
            child=child,
            index=index,
            occurred_at=now,
            actor=actor,
            source_command=source_command,
        )
        for index, child in enumerate(children)
    )
    child_ids = tuple(transaction.transaction_id for transaction in child_transactions_initial)
    if len(set(child_ids)) != len(child_ids):
        raise TransactionValidationError(
            "ledger split produced duplicate child transaction ids; "
            "vary amount, description, value_date, or counterparty between siblings",
            context={"child_ids": child_ids},
        )

    parent_lineage = SplitLineage(
        split_group_id=split_group_id,
        role=SplitRole.PARENT,
        sibling_transaction_ids=child_ids,
    )
    parent_transition = TransactionLifecycleLineageEntry(
        previous_state=parent.lifecycle_state,
        state=TransactionLifecycleState.SPLIT,
        actor=actor,
        source_command=source_command,
        changed_at=now,
        reason=reason.strip() or "split",
    )
    parent_after = parent.model_copy(
        update={
            "lifecycle_state": TransactionLifecycleState.SPLIT,
            "lifecycle_lineage": (*parent.lifecycle_lineage, parent_transition),
            "split_lineage": parent_lineage,
            # D6: splitting the parent is a mutating edit; re-stamp modified_at.
            "modified_at": now,
        },
    )

    final_children = tuple(
        transaction.model_copy(
            update={
                "split_lineage": SplitLineage(
                    split_group_id=split_group_id,
                    role=SplitRole.CHILD,
                    sibling_transaction_ids=(
                        parent.transaction_id,
                        *(other for other in child_ids if other != transaction.transaction_id),
                    ),
                ),
            },
        )
        for transaction in child_transactions_initial
    )

    event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_SPLIT,
        occurred_at=now,
        actor=actor,
        object_id=parent.transaction_id,
        payload={
            "source_command": source_command,
            "reason": reason.strip(),
            "split_group_id": split_group_id,
            "parent_transaction_id": parent.transaction_id,
            # A count, never the joined child ids. A payload value is capped at
            # 500 characters and a transaction id is a 64-char SHA-256 digest,
            # so eight children joined on commas is 519 and a split into eight
            # or more could not construct the event recording it — the same
            # arithmetic that broke transaction removal at eight attachments.
            # Nothing is lost: every child carries this split_group_id as a
            # required field, and the group id is in this payload, so the cohort
            # is recoverable from the transaction catalogue.
            "child_count": str(len(child_ids)),
        },
    )
    return parent_after, final_children, event, split_group_id, child_ids


def split_transaction_with_classified_children(
    *,
    bucket_id: str,
    transaction_id: str,
    children: tuple[SplitChildCommand, ...],
    child_classifications: tuple[ManualLedgerTransactionPatch, ...],
    classified_by: str,
    actor: str,
    source_command: str,
    reason: str = "",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: AttachmentStoreProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> SplitTransactionResult:
    """Split a parent and persist fully-classified children in ONE transaction.

    This is the atomic evidence-driven split writer. It builds the parent
    transition, every child, each child's inherited validated evidence link and
    provenance, its classification and registry-derived IVA substrate, and every
    audit event entirely in memory, then persists the whole set with a single
    catalogue-and-events save. No generic field patch is issued after the split,
    so there is no intermediate state in which a child exists split but
    unclassified or evidence-less. Any child evidence-validation or build failure
    raises before the save, leaving the parent ACTIVE and no child, catalogue
    entry, or event persisted.

    ``child_classifications`` is one
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionPatch` per child (in
    the same order as ``children``) carrying the classification, IVA substrate, and
    inherited evidence to stamp on that child. ``classified_by`` is the shared
    provenance stamp (e.g. an ``llm:<model>`` label).

    Returns a :class:`~cadrumo.application.ledger.models.SplitTransactionResult` whose
    ``child_transactions`` are the classified, evidence-bearing children.
    """
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger classified split")
    trimmed_source_command = _require_source_command(source_command, operation="ledger classified split")
    if len(children) < 2:
        raise TransactionValidationError(
            "ledger split requires at least two children",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id, "child_count": len(children)},
        )
    if len(children) != len(child_classifications):
        raise TransactionValidationError(
            "each split child must carry exactly one classification patch",
            context={"children": len(children), "classifications": len(child_classifications)},
        )
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    invoices_repo = _invoice_repository(bucket_id=bucket_id, repository=invoice_repository)
    catalogue = repository.load()

    parent_after, bare_children, split_event, split_group_id, child_ids = _build_split_state(
        catalogue=catalogue,
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        children=children,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        reason=reason,
        now=now,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )

    classified_children: list[Transaction] = []
    child_events: list[BucketEvent] = []
    for bare_child, patch in zip(bare_children, child_classifications, strict=True):
        command = _command_from_patch(
            bucket_id=bucket_id,
            current=bare_child,
            patch=patch,
            actor=trimmed_actor,
            source_command=trimmed_source_command,
            classified_by_override=classified_by,
        )
        prepared = _prepare_manual_transaction_update(
            current=bare_child,
            command=command,
            previous_transaction_id=bare_child.transaction_id,
            now=now,
            invoice_repository=invoices_repo,
            attachment_store=attachment_store,
        )
        if prepared is None:
            classified_children.append(bare_child)
            continue
        replacement, events = prepared
        # A child's transaction_id is content-addressed over its RAW movement only.
        # A classification patch must therefore never change it; if a caller ever
        # passes a raw field (amount/date/counterparty), the replacement would land
        # under a new id while siblings, lineage, and the result still name the
        # stale id — a silently corrupted split group. Refuse rather than persist it.
        if replacement.transaction_id != bare_child.transaction_id:
            raise TransactionValidationError(
                "split child classification changed its transaction id; a per-child "
                "classification patch must not alter raw movement fields "
                "(amount, currency, dates, counterparty, description)",
                context={
                    "expected_transaction_id": bare_child.transaction_id,
                    "produced_transaction_id": replacement.transaction_id,
                },
            )
        # _prepare_manual_transaction_update rebuilds the row from the command and
        # does not carry split_lineage; restore the child's lineage so the split
        # group linkage survives the classification in the same atomic write.
        classified_children.append(replacement.model_copy(update={"split_lineage": bare_child.split_lineage}))
        child_events.extend(events)

    updated_transactions = dict(catalogue.transactions)
    updated_transactions[parent_after.transaction_id] = parent_after
    for classified_child in classified_children:
        updated_transactions[classified_child.transaction_id] = classified_child
    new_catalogue = TransactionCatalogue.model_validate({"transactions": updated_transactions})

    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=new_catalogue,
        events=(split_event, *child_events),
    )

    return SplitTransactionResult(
        bucket_id=bucket_id,
        parent_transaction_id=parent_after.transaction_id,
        split_group_id=split_group_id,
        child_transaction_ids=child_ids,
        parent_transaction=parent_after,
        child_transactions=tuple(classified_children),
        bucket_event_id=split_event.event_id,
    )


def _resolve_active_split_parent(
    catalogue: TransactionCatalogue,
    *,
    bucket_id: str,
    transaction_id: str,
) -> Transaction:
    """Load the split-parent transaction and assert it is currently ACTIVE.

    Only ACTIVE transactions can be split - splitting a SPLIT or
    ARCHIVED row would corrupt the lifecycle chain. The state
    refusal carries the actual lifecycle state in its context so an
    operator can diagnose why the split is blocked.
    """
    parent = _require_transaction(catalogue, transaction_id)
    if parent.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be split",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "lifecycle_state": parent.lifecycle_state.value,
            },
        )
    return parent


def _reject_split_with_finalized_modelo_blockers(
    *,
    parent: Transaction,
    bucket_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> None:
    """Refuse the split if any finalized modelo calculation references the parent.

    The blocking-references probe walks the work-unit + calculation
    catalogues for any verified-complete or filed revision whose
    source-transaction set contains the parent (or any synthetic
    successor). A non-empty blocker list maps directly to the
    operator-facing "transaction frozen by filed modelo" error.
    """
    transaction_ids = _transaction_modelo_source_ids(parent)
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=transaction_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger split",
            transaction_ids=transaction_ids,
            blockers=blockers,
        )


def _validate_split_child_amounts(
    *,
    parent_amount: Decimal,
    children: tuple[SplitChildCommand, ...],
) -> None:
    """Verify split-child magnitudes sum to the parent exactly.

    Two contracts enforced in order (amounts are non-negative magnitudes;
    flow is carried by ``direction``, which every child inherits from the
    parent in the split builder, so there is no sign to reconcile):

    * ``sum(child.amount) == parent_amount`` exactly - no rounding
      slack; bank ledgers carry exact cents.
    * Every child amount is non-zero; a zero-amount child is a
      modelling error, not a legitimate split.
    """
    child_sum = sum((child.amount for child in children), start=Decimal("0"))
    if child_sum != parent_amount:
        raise TransactionValidationError(
            "ledger split child amounts must sum to the parent amount exactly",
            context={
                "parent_amount": str(parent_amount),
                "child_sum": str(child_sum),
                "child_amounts": tuple(str(child.amount) for child in children),
            },
        )
    for index, child in enumerate(children):
        if child.amount < Decimal("0"):
            raise TransactionValidationError(
                "ledger split child amount must be a non-negative magnitude; children inherit the parent's direction",
                context={"child_index": index, "child_amount": str(child.amount)},
            )
        if child.amount == Decimal("0"):
            raise TransactionValidationError(
                "ledger split child amount must not be zero",
                context={"child_index": index},
            )


def _build_split_child_transaction(
    *,
    parent: Transaction,
    child: SplitChildCommand,
    index: int,
    occurred_at: datetime,
    actor: str,
    source_command: str,
) -> Transaction:
    """Build one child Transaction.

    ``split_lineage`` is filled in by the caller once all child ids are
    known so siblings can reference each other.
    """
    parent_raw = parent.raw
    provider_transaction_id = f"split:{parent.transaction_id}:{index:04d}"
    raw_child = RawTransaction(
        provider_transaction_id=provider_transaction_id,
        booked_date=child.booked_date or parent_raw.booked_date,
        value_date=child.value_date if child.value_date is not None else parent_raw.value_date,
        amount=child.amount,
        currency=parent_raw.currency,
        counterparty=child.counterparty if child.counterparty is not None else parent_raw.counterparty,
        description=child.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".cadrumo-ledger-split",
            source_sha256=sha256_hex(f"split:{parent.transaction_id}:{index}".encode()),
            source_row_index=index + 1,
            source_format=SourceFormat.MANUAL,
            ingested_at=occurred_at,
            provider_name="ledger-split",
        ),
        raw_fields={"parent_transaction_id": parent.transaction_id, "split_index": str(index)},
    )
    return Transaction.model_validate(
        {
            "raw": raw_child,
            "direction": parent.direction,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": parent.source_jurisdiction,
            "group_label": parent.group_label,
            "created_by": actor,
            "source_command": source_command,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "notes": "",
            # D6: a split child is a freshly-created row.
            "created_at": occurred_at,
            "modified_at": occurred_at,
        },
    )


def merge_transactions(
    *,
    bucket_id: str,
    child_transaction_ids: tuple[str, ...],
    actor: str,
    source_command: str = "aeat app ledger merge",
    reason: str = "",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> MergeTransactionsResult:
    """Re-merge a complete cohort of split children into a fresh transaction.

    Returns a :class:`~cadrumo.application.ledger.models.MergeTransactionsResult`.

    Pre-conditions:

    - At least two child ids supplied.
    - All children exist in the catalogue.
    - All children share the same ``split_group_id``.
    - All children are currently ACTIVE.
    - The parent recorded in each child's lineage is in SPLIT state.
    - The cohort is complete - the children supplied must equal the
      parent's recorded sibling set (no partial re-merge).
    - Neither the parent nor any child is referenced by a finalized
      modelo calculation.

    Effect:

    - Children transition ACTIVE -> ARCHIVED with a lifecycle lineage
      entry recording the merge.
    - Parent transitions SPLIT -> ARCHIVED with its lifecycle lineage
      extended; the parent's split_lineage role=PARENT is preserved
      for audit so the chain is reconstructable.
    - A fresh transaction is persisted with a content-addressed id
      derived from a synthesized ``merged:{split_group_id}`` provider
      key plus the parent's amount / narrative / value_date, and
      ``split_lineage`` role=MERGED carrying the merged child ids.
    - One ``LEDGER_TRANSACTION_MERGED`` event is emitted, anchored on
      the parent transaction id so ``for_object(parent_id)`` returns
      the entire split + merge chain in chronological order.
    - Catalogue + event are persisted atomically.
    """
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger merge")
    trimmed_source_command = _require_source_command(source_command, operation="ledger merge")
    if len(child_transaction_ids) < 2:
        raise TransactionValidationError(
            "ledger merge requires at least two child transactions",
            context={"bucket_id": bucket_id, "child_count": len(child_transaction_ids)},
        )
    if len(set(child_transaction_ids)) != len(child_transaction_ids):
        raise TransactionValidationError(
            "ledger merge child ids must be unique",
            context={"bucket_id": bucket_id, "child_transaction_ids": tuple(child_transaction_ids)},
        )

    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()

    children = tuple(_require_transaction(catalogue, child_id) for child_id in child_transaction_ids)
    split_group_id = _resolve_merge_split_group(
        children=children,
        bucket_id=bucket_id,
        child_transaction_ids=child_transaction_ids,
    )
    parent = _resolve_merge_parent(
        catalogue=catalogue,
        bucket_id=bucket_id,
        split_group_id=split_group_id,
        child_transaction_ids=child_transaction_ids,
    )

    _reject_merge_with_finalized_modelo_blockers(
        bucket_id=bucket_id,
        catalogue=catalogue,
        parent=parent,
        child_transaction_ids=child_transaction_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )

    sorted_child_ids = tuple(sorted(child_transaction_ids))
    merged_transaction = _build_merged_transaction(
        parent=parent,
        split_group_id=split_group_id,
        sorted_child_ids=sorted_child_ids,
        occurred_at=now,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
    )
    if merged_transaction.transaction_id in catalogue.transactions:
        raise TransactionValidationError(
            "ledger merge produced an id that already exists in the catalogue",
            context={"merged_transaction_id": merged_transaction.transaction_id},
        )

    parent_after, archived_children = _archive_merge_members(
        parent=parent,
        children=children,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        changed_at=now,
        reason=reason,
    )

    event = _build_merge_event(
        bucket_id=bucket_id,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        occurred_at=now,
        reason=reason,
        split_group_id=split_group_id,
        parent=parent,
        merged_transaction=merged_transaction,
        sorted_child_ids=sorted_child_ids,
    )

    updated_transactions = dict(catalogue.transactions)
    updated_transactions[parent_after.transaction_id] = parent_after
    for archived_child in archived_children:
        updated_transactions[archived_child.transaction_id] = archived_child
    updated_transactions[merged_transaction.transaction_id] = merged_transaction
    new_catalogue = TransactionCatalogue.model_validate({"transactions": updated_transactions})

    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=new_catalogue,
        events=(event,),
    )

    return MergeTransactionsResult(
        bucket_id=bucket_id,
        split_group_id=split_group_id,
        parent_transaction_id=parent.transaction_id,
        merged_transaction_id=merged_transaction.transaction_id,
        source_child_ids=sorted_child_ids,
        merged_transaction=merged_transaction,
        parent_transaction=parent_after,
        bucket_event_id=event.event_id,
    )


def _reject_merge_with_finalized_modelo_blockers(
    *,
    bucket_id: str,
    catalogue: TransactionCatalogue,
    parent: Transaction,
    child_transaction_ids: tuple[str, ...],
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> None:
    transaction_ids_under_check = (parent.transaction_id, *child_transaction_ids)
    blocking_pool: list[str] = []
    for member_id in transaction_ids_under_check:
        member = _require_transaction(catalogue, member_id)
        blocking_pool.extend(_transaction_modelo_source_ids(member))
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=tuple(blocking_pool),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger merge",
            transaction_ids=tuple(blocking_pool),
            blockers=blockers,
        )


def _build_merged_transaction(
    *,
    parent: Transaction,
    split_group_id: str,
    sorted_child_ids: tuple[str, ...],
    occurred_at: datetime,
    actor: str,
    source_command: str,
) -> Transaction:
    # Its content-addressed id varies from the parent's because the
    # synthesized provider_id is unique.
    parent_raw = parent.raw
    merged_provider_id = f"merged:{split_group_id}"
    merged_raw = RawTransaction(
        provider_transaction_id=merged_provider_id,
        booked_date=parent_raw.booked_date,
        value_date=parent_raw.value_date,
        amount=parent_raw.amount,
        currency=parent_raw.currency,
        counterparty=parent_raw.counterparty,
        description=parent_raw.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".cadrumo-ledger-merge",
            source_sha256=sha256_hex(merged_provider_id.encode("utf-8")),
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=occurred_at,
            provider_name="ledger-merge",
        ),
        raw_fields={
            "parent_transaction_id": parent.transaction_id,
            "split_group_id": split_group_id,
            "merged_child_count": str(len(sorted_child_ids)),
        },
    )
    return Transaction.model_validate(
        {
            "raw": merged_raw,
            "direction": parent.direction,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": parent.source_jurisdiction,
            "group_label": parent.group_label,
            "created_by": actor,
            "source_command": source_command,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "split_lineage": SplitLineage(
                split_group_id=split_group_id,
                role=SplitRole.MERGED,
                sibling_transaction_ids=sorted_child_ids,
            ),
            "notes": "",
            # D6: the merged transaction is a freshly-created row.
            "created_at": occurred_at,
            "modified_at": occurred_at,
        },
    )


def _archive_merge_members(
    *,
    parent: Transaction,
    children: tuple[Transaction, ...],
    actor: str,
    source_command: str,
    changed_at: datetime,
    reason: str,
) -> tuple[Transaction, tuple[Transaction, ...]]:
    transition_reason = reason.strip() or "merge"
    archived_children: list[Transaction] = []
    for child in children:
        transition = TransactionLifecycleLineageEntry(
            previous_state=child.lifecycle_state,
            state=TransactionLifecycleState.ARCHIVED,
            actor=actor,
            source_command=source_command,
            changed_at=changed_at,
            reason=transition_reason,
        )
        archived_children.append(
            child.model_copy(
                update={
                    "lifecycle_state": TransactionLifecycleState.ARCHIVED,
                    "lifecycle_lineage": (*child.lifecycle_lineage, transition),
                    # D6: archiving a child on merge is a mutating edit.
                    "modified_at": changed_at,
                },
            ),
        )

    parent_transition = TransactionLifecycleLineageEntry(
        previous_state=parent.lifecycle_state,
        state=TransactionLifecycleState.ARCHIVED,
        actor=actor,
        source_command=source_command,
        changed_at=changed_at,
        reason=transition_reason,
    )
    parent_after = parent.model_copy(
        update={
            "lifecycle_state": TransactionLifecycleState.ARCHIVED,
            "lifecycle_lineage": (*parent.lifecycle_lineage, parent_transition),
            # D6: archiving the parent on merge is a mutating edit.
            "modified_at": changed_at,
        },
    )
    return parent_after, tuple(archived_children)


def _build_merge_event(
    *,
    bucket_id: str,
    actor: str,
    source_command: str,
    occurred_at: datetime,
    reason: str,
    split_group_id: str,
    parent: Transaction,
    merged_transaction: Transaction,
    sorted_child_ids: tuple[str, ...],
) -> BucketEvent:
    return _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_MERGED,
        occurred_at=occurred_at,
        actor=actor,
        object_id=parent.transaction_id,
        payload={
            "source_command": source_command,
            "reason": reason.strip(),
            "split_group_id": split_group_id,
            "parent_transaction_id": parent.transaction_id,
            "merged_transaction_id": merged_transaction.transaction_id,
            # A count, never the joined source ids, for the reason given on the
            # split event above: eight 64-char ids joined is 519 characters
            # against a 500-character payload slot, so merging eight or more
            # children could not record its own event. The cohort stays
            # recoverable through the split_group_id carried here.
            "child_count": str(len(sorted_child_ids)),
        },
    )


def _resolve_merge_split_group(
    *,
    children: tuple[Transaction, ...],
    bucket_id: str,
    child_transaction_ids: tuple[str, ...],
) -> str:
    """Validate child shape and return the shared ``split_group_id``.

    Rejects: any child without a split_lineage, any disagreement on
    split_group_id across the cohort, any child not in ACTIVE state,
    and any child not carrying split_lineage role=CHILD.
    """
    split_group_ids = {
        child.split_lineage.split_group_id if child.split_lineage is not None else None for child in children
    }
    if None in split_group_ids or len(split_group_ids) != 1:
        raise TransactionValidationError(
            "ledger merge children must all share one split_group_id",
            context={"bucket_id": bucket_id, "child_transaction_ids": tuple(child_transaction_ids)},
        )
    split_group_id = next(iter(split_group_ids))
    assert split_group_id is not None  # narrowed: None excluded by the guard above
    for child in children:
        _require_child_active_and_role(child)
    return split_group_id


def _require_child_active_and_role(child: Transaction) -> None:
    if child.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "ledger merge children must all be active",
            context={
                "child_transaction_id": child.transaction_id,
                "lifecycle_state": child.lifecycle_state.value,
            },
        )
    if child.split_lineage is None or child.split_lineage.role is not SplitRole.CHILD:
        raise TransactionValidationError(
            "ledger merge children must carry split_lineage role=CHILD",
            context={"child_transaction_id": child.transaction_id},
        )


def _resolve_merge_parent(
    *,
    catalogue: TransactionCatalogue,
    bucket_id: str,
    split_group_id: str,
    child_transaction_ids: tuple[str, ...],
) -> Transaction:
    """Find the unique split-parent for ``split_group_id`` and verify the cohort.

    Rejects: zero / multiple parent candidates, parent not in SPLIT
    state, parent not carrying split_lineage role=PARENT, or supplied
    children not matching the parent's recorded sibling set.
    """
    parent_candidates = tuple(
        transaction
        for transaction in catalogue.transactions.values()
        if transaction.split_lineage is not None
        and transaction.split_lineage.role is SplitRole.PARENT
        and transaction.split_lineage.split_group_id == split_group_id
    )
    if len(parent_candidates) != 1:
        raise TransactionValidationError(
            "ledger merge could not resolve a unique parent for the split_group_id",
            context={
                "bucket_id": bucket_id,
                "split_group_id": split_group_id,
                "candidate_count": len(parent_candidates),
            },
        )
    parent = parent_candidates[0]
    if parent.lifecycle_state is not TransactionLifecycleState.SPLIT:
        raise TransactionValidationError(
            "ledger merge parent must be in SPLIT state",
            context={"parent_transaction_id": parent.transaction_id, "lifecycle_state": parent.lifecycle_state.value},
        )
    if parent.split_lineage is None or parent.split_lineage.role is not SplitRole.PARENT:
        raise TransactionValidationError(
            "ledger merge parent must carry split_lineage role=PARENT",
            context={"parent_transaction_id": parent.transaction_id},
        )
    expected_children = set(parent.split_lineage.sibling_transaction_ids)
    if expected_children != set(child_transaction_ids):
        raise TransactionValidationError(
            "ledger merge cohort is incomplete; every child of the split_group must be supplied",
            context={
                "parent_transaction_id": parent.transaction_id,
                "expected_children": tuple(sorted(expected_children)),
                "supplied": tuple(sorted(child_transaction_ids)),
            },
        )
    return parent


__all__ = [
    "merge_transactions",
    "split_transaction",
    "split_transaction_with_classified_children",
]
