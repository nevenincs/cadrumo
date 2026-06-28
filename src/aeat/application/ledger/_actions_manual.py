"""Application services for bucket-scoped manual ledger transactions.

Services operate over a :class:`TransactionCatalogueRepository` for ledger
state, a :class:`BucketEventHistoryRepository` for durable audit events, and
an optional :class:`InvoiceCatalogueRepository` for purchase-invoice evidence
cascade on removal. The inner functions accept a :class:`TransactionCatalogue`
or :class:`InvoiceCatalogue` directly when the caller supplies pre-loaded data.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ...core.hashing import content_hash_hex

if TYPE_CHECKING:
    pass

from ...core import BindingSourceKind, Period
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.attachments._protocols import AttachmentStoreProtocol as _AttachmentStoreProtocol
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices._protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ...domain.usage_ratios import (
    UsageRatioProfile,
)
from ..review import LedgerReviewStatus
from ._actions_common import (
    _blocking_modelo_references,
    _bucket_event_repository,
    _build_bucket_event,
    _command_matches_current,
    _decimal_to_string,
    _display_decimal,
    _EventSpec,
    _evidence_event_ids,
    _merge_identifier_tuple,
    _mutation_signature,
    _normalise_attachment_patch_ids,
    _normalise_timestamp,
    _optional_decimal,
    _optional_patched,
    _primary_lineage_event_id,
    _raise_finalized_modelo_blocked,
    _replace_transaction,
    _require_actor,
    _require_source_command,
    _require_transaction,
    _required_patched,
    _result,
    _save_transaction_catalogue_and_events,
    _transaction_modelo_source_ids,
    _transaction_repository,
    _upsert_transaction,
    _verify_evidence_references,
    _verify_usage_ratio_reference,
)
from ._models import (
    LedgerReviewQuery,
    LedgerReviewQueryResult,
    LedgerStatusReport,
    LedgerTransactionPayload,
    LedgerTransactionResultPayload,
    LedgerTransactionReviewPayload,
    LedgerTransactionTrackingPayload,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ._preflight import preflight_ledger_tax_readiness
from ._review_projection import ledger_transaction_review_status, project_ledger_review_query

_MANUAL_PROVIDER_NAME = "manual-ledger"


def create_manual_transaction(
    command: ManualLedgerTransactionCommand,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Persist one manual ledger transaction in the command's bucket.

    Returns a :class:`ManualLedgerTransactionResult` with the created
    transaction and associated bucket event.
    """
    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
    transaction_base = _transaction_from_command(command, occurred_at=now)
    _verify_evidence_references(
        command,
        transaction_id=transaction_base.transaction_id,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
    )
    _verify_usage_ratio_reference(command, usage_ratio_profile=usage_ratio_profile)
    event = _build_bucket_event(
        bucket_id=command.bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_CREATED,
        occurred_at=now,
        actor=command.actor,
        object_id=transaction_base.transaction_id,
        payload=_event_payload(command),
    )
    transaction = _transaction_from_command(command, occurred_at=now, bucket_event_id=event.event_id)
    catalogue = repository.load()
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=_upsert_transaction(catalogue, transaction),
        events=(event,),
    )
    return _result(command.bucket_id, transaction, (event.event_id,))


def attach_manual_transaction_evidence(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    source_command: str = "aeat app ledger attach",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Attach purchase evidence or supplementary attachments to one ledger transaction.

    Returns a :class:`ManualLedgerTransactionResult`.
    """
    trimmed_actor = _require_actor(actor, operation="ledger evidence attachment")
    trimmed_source_command = _require_source_command(source_command, operation="ledger evidence attachment")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    normalized_purchase_evidence_id = purchase_invoice_evidence_id.strip() if purchase_invoice_evidence_id else None
    normalized_attachment_ids = _normalise_attachment_patch_ids(attachment_ids)
    if normalized_purchase_evidence_id is None and not normalized_attachment_ids:
        raise TransactionValidationError(
            "ledger evidence attachment requires purchase evidence or attachment ids",
            translated_message="application.ledger.errors.evidence_attachment_requires_ids",
        )
    if (
        normalized_purchase_evidence_id is not None
        and current.purchase_invoice_evidence_id is not None
        and current.purchase_invoice_evidence_id != normalized_purchase_evidence_id
    ):
        raise TransactionValidationError(
            "ledger transaction already has purchase_invoice_evidence_id; "
            "remove or replace through attachments workflow",
            translated_message="application.ledger.errors.purchase_evidence_already_set",
        )
    patch_values: dict[str, object] = {}
    if normalized_purchase_evidence_id is not None:
        patch_values["purchase_invoice_evidence_id"] = normalized_purchase_evidence_id
    if normalized_attachment_ids:
        patch_values["attachment_ids"] = _merge_identifier_tuple(current.attachment_ids, normalized_attachment_ids)
    return update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate(patch_values),
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
        usage_ratio_profile=usage_ratio_profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
        _preloaded_catalogue=catalogue,
    )


def get_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> ManualLedgerTransactionResult:
    """Return one :class:`ManualLedgerTransactionResult` from a bucket-scoped catalogue."""
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = _require_transaction(repository.load(), transaction_id)
    return _result(bucket_id, transaction, ())


def list_manual_transactions(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Return every transaction in a bucket, sorted by effective date and id.

    Each element is a :class:`ManualLedgerTransactionResult` for one
    stored transaction.
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transactions = sorted(
        repository.load().values(),
        key=lambda transaction: (
            transaction.raw.value_date or transaction.raw.booked_date,
            transaction.transaction_id,
        ),
    )
    return tuple(_result(bucket_id, transaction, ()) for transaction in transactions)


def query_ledger_review_rows(
    query: LedgerReviewQuery,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> LedgerReviewQueryResult:
    """Return review rows for bucket-local ledger transactions.

    Returns a :class:`LedgerReviewQueryResult`.
    """
    repository = _transaction_repository(bucket_id=query.bucket_id, repository=transaction_repository)
    catalogue = repository.load()
    return project_ledger_review_query(
        query=query,
        catalogue=catalogue,
        bucket_event_repository=bucket_event_repository,
        transaction_payload_builder=ledger_transaction_payload,
    )


def ledger_transaction_payload(transaction: Transaction) -> LedgerTransactionPayload:
    """Return the :class:`LedgerTransactionPayload` for one ledger transaction."""
    raw = transaction.raw
    return LedgerTransactionPayload(
        transaction_id=transaction.transaction_id,
        date=(raw.value_date or raw.booked_date).isoformat(),
        booked_date=raw.booked_date.isoformat(),
        value_date=raw.value_date.isoformat() if raw.value_date else None,
        amount=_display_decimal(raw.amount),
        currency=raw.currency,
        direction=transaction.direction.value,
        counterparty=raw.display_counterparty,
        description=raw.description,
        business_classification=transaction.business_classification.value,
        business_pct=_display_decimal(transaction.business_pct) if transaction.business_pct is not None else None,
        category_id=transaction.category_id,
        taxable_base=_display_decimal(transaction.taxable_base) if transaction.taxable_base is not None else None,
        iva_rate=_display_decimal(transaction.iva_rate) if transaction.iva_rate is not None else None,
        iva_amount=_display_decimal(transaction.iva_amount) if transaction.iva_amount is not None else None,
        iva_category=transaction.iva_category.value if transaction.iva_category is not None else None,
        counterparty_eu_member_state=(
            transaction.counterparty_eu_member_state.value
            if transaction.counterparty_eu_member_state is not None
            else None
        ),
        irpf_category=transaction.irpf_category,
        usage_ratio_id=transaction.usage_ratio_id,
        prorrata_reference=transaction.prorrata_reference,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        attachment_ids=transaction.attachment_ids,
        notes=transaction.notes,
        lifecycle_state=transaction.lifecycle_state.value,
        classified_by=transaction.classified_by,
        source_jurisdiction=transaction.source_jurisdiction,
        value_in_eur=_display_decimal(transaction.value_in_eur) if transaction.value_in_eur is not None else None,
        fx_rate=_display_decimal(transaction.fx_rate) if transaction.fx_rate is not None else None,
        created_at=transaction.created_at.isoformat(),
        modified_at=transaction.modified_at.isoformat(),
    )


def ledger_transaction_review_payload(transaction: Transaction) -> LedgerTransactionReviewPayload:
    """Return one ledger transaction projection plus derived operator review status.

    Returns a :class:`LedgerTransactionReviewPayload` with all operator-facing
    fields populated from the transaction record.
    """
    base = ledger_transaction_payload(transaction)
    return LedgerTransactionReviewPayload(
        **base.model_dump(),
        review_status=ledger_transaction_review_status(transaction),
    )


def ledger_transaction_result_payload(result: ManualLedgerTransactionResult) -> LedgerTransactionResultPayload:
    """Return the canonical :class:`LedgerTransactionResultPayload` for a single ledger mutation/read result."""
    return LedgerTransactionResultPayload(
        bucket_id=result.ref.bucket_id,
        transaction_id=result.ref.transaction_id,
        review_status=ledger_transaction_review_status(result.transaction),
        transaction=ledger_transaction_payload(result.transaction),
    )


def ledger_transaction_tracking_payload(transaction: Transaction) -> LedgerTransactionTrackingPayload:
    """Return durable event lineage fields as a :class:`LedgerTransactionTrackingPayload` for one ledger transaction."""
    return LedgerTransactionTrackingPayload(
        transaction_id=transaction.transaction_id,
        created_event_id=transaction.created_event_id,
        evidence_provenance=transaction.evidence_provenance,
        edit_lineage=transaction.edit_lineage,
        lifecycle_state=transaction.lifecycle_state.value,
        lifecycle_lineage=transaction.lifecycle_lineage,
    )


def summarize_manual_transactions(
    *,
    bucket_id: str,
    period: Period | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> LedgerStatusReport:
    """Return a read-only :class:`LedgerStatusReport` for one bucket's ledger transactions."""
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transactions = tuple(repository.load().values())
    status_counts: dict[LedgerReviewStatus, int] = {
        LedgerReviewStatus.PENDING: 0,
        LedgerReviewStatus.REVIEWED: 0,
        LedgerReviewStatus.SKIPPED: 0,
    }
    for transaction in transactions:
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        status_counts[ledger_transaction_review_status(transaction)] += 1
    checked = 0
    issue_count = 0
    ready: bool | None = None
    if period is not None:
        preflight = preflight_ledger_tax_readiness(
            bucket_id=bucket_id,
            period=period,
            transaction_repository=repository,
        )
        checked = preflight.checked_transaction_count
        issue_count = len(preflight.issues)
        ready = preflight.ready
    # Money roll-up over active business/mixed rows (period-filtered when given):
    # the year-end / readiness money picture the personas asked for. Gross EUR
    # (value_in_eur for foreign rows), not a registry calculation.
    money_period = period
    income_total = Decimal("0")
    expense_total = Decimal("0")
    for item in transactions:
        if item.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if item.business_classification not in {BusinessClassification.BUSINESS, BusinessClassification.MIXED}:
            continue
        if money_period is not None and not money_period.contains(item.raw.value_date or item.raw.booked_date):
            continue
        eur = abs(item.value_in_eur) if item.value_in_eur is not None else abs(item.raw.amount)
        if item.direction is TransactionDirection.INCOMING:
            income_total += eur
        elif item.direction is TransactionDirection.OUTGOING:
            expense_total += eur
    return LedgerStatusReport(
        bucket_id=bucket_id,
        income_total=_display_decimal(income_total),
        expense_total=_display_decimal(expense_total),
        net_total=_display_decimal(income_total - expense_total),
        total_count=len(transactions),
        active_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.ACTIVE),
        archived_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.ARCHIVED),
        stashed_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.STASHED),
        split_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.SPLIT),
        pending_review_count=status_counts[LedgerReviewStatus.PENDING],
        reviewed_count=status_counts[LedgerReviewStatus.REVIEWED],
        skipped_count=status_counts[LedgerReviewStatus.SKIPPED],
        period=period,
        checked_transaction_count=checked,
        readiness_issue_count=issue_count,
        ready=ready,
    )


def update_manual_transaction(
    *,
    transaction_id: str,
    command: ManualLedgerTransactionCommand,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Replace one manual ledger transaction with a validated command payload.

    Returns a :class:`ManualLedgerTransactionResult`.
    """
    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    blockers = _blocking_modelo_references(
        bucket_id=command.bucket_id,
        transaction_ids=_transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger transaction update",
            transaction_ids=_transaction_modelo_source_ids(current),
            blockers=blockers,
        )
    prepared = _prepare_manual_transaction_update(
        current=current,
        command=command,
        previous_transaction_id=transaction_id,
        now=now,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
        usage_ratio_profile=usage_ratio_profile,
    )
    if prepared is None:
        raise TransactionValidationError(
            "manual ledger update must change at least one ledger field",
            context={"transaction_id": transaction_id},
        )
    replacement, events = prepared
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=_replace_transaction(catalogue, old_transaction_id=transaction_id, replacement=replacement),
        events=events,
    )
    return _result(command.bucket_id, replacement, tuple(event.event_id for event in events))


def _prepare_manual_transaction_update(
    *,
    current: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
    now: datetime,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
) -> tuple[Transaction, tuple[BucketEvent, ...]] | None:
    """Build the replacement transaction + bucket events for one in-memory edit.

    Returns ``None`` when the command is a field-for-field no-op (the caller
    decides whether that is an error or a skip). Verifies evidence and usage-ratio
    references but performs **no** persistence and **no** catalogue load â€” the
    caller owns a single load/save so a batch re-encrypts the catalogue once
    rather than per row (the ``bulk_classify_from_csv`` load-once/save-once
    contract). Lifecycle and blocking-modelo guards remain the caller's
    responsibility before invoking this builder.
    """
    replacement = _transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.transaction_id if command.idempotency_key is None else None,
        created_by=current.created_by,
        created_source_command=current.source_command,
        created_event_id=current.created_event_id,
        existing_evidence_provenance=current.evidence_provenance,
        existing_edit_lineage=current.edit_lineage,
        lifecycle_state=current.lifecycle_state,
        lifecycle_lineage=current.lifecycle_lineage,
        import_fingerprint=current.import_fingerprint,
        created_at=current.created_at,
        modified_at=now,
    )
    if _mutation_signature(current) == _mutation_signature(replacement):
        return None
    _verify_evidence_references(
        command,
        transaction_id=replacement.transaction_id,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
    )
    _verify_usage_ratio_reference(command, usage_ratio_profile=usage_ratio_profile)
    event_specs = _update_event_specs(
        current=current,
        replacement=replacement,
        command=command,
        previous_transaction_id=previous_transaction_id,
    )
    events = tuple(
        _build_bucket_event(
            bucket_id=command.bucket_id,
            event_type=event_type,
            occurred_at=now,
            actor=command.actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        )
        for event_type, object_type, object_id, payload in event_specs
    )
    primary_event_id = _primary_lineage_event_id(events)
    evidence_event_ids = _evidence_event_ids(events)
    replacement = _transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.transaction_id if command.idempotency_key is None else None,
        created_by=current.created_by,
        created_source_command=current.source_command,
        created_event_id=current.created_event_id,
        existing_evidence_provenance=current.evidence_provenance,
        existing_edit_lineage=current.edit_lineage,
        lifecycle_state=current.lifecycle_state,
        lifecycle_lineage=current.lifecycle_lineage,
        edit_lineage_entry=TransactionEditLineageEntry(
            previous_transaction_id=previous_transaction_id,
            actor=command.actor,
            source_command=command.source_command,
            edited_at=now,
            bucket_event_id=primary_event_id,
        ),
        bucket_event_id=primary_event_id,
        evidence_event_ids=evidence_event_ids,
        import_fingerprint=current.import_fingerprint,
        created_at=current.created_at,
        modified_at=now,
    )
    return replacement, events


def update_manual_transaction_fields(
    *,
    bucket_id: str,
    transaction_id: str,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    source_command: str,
    classified_by_override: str | None = None,
    reaffirm: bool = False,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
    _preloaded_catalogue: TransactionCatalogue | None = None,
) -> ManualLedgerTransactionResult:
    """Apply a typed field patch to one active bucket-scoped ledger transaction.

    When ``reaffirm`` is :data:`True` the automatic re-affirmation no-op guard
    is bypassed and the command is forced through even if the patched fields are
    field-for-field identical to the stored transaction. This is the explicit
    operator-driven counterpart to the automatic silent no-op (S14).

    ``_preloaded_catalogue`` is an internal optimisation: a caller that has
    already decrypted the bucket :class:`TransactionCatalogue` (e.g.
    :func:`attach_manual_transaction_evidence`) passes it through so this function
    does not decrypt the whole catalogue a second time. There is no write between
    the caller's load and this one, so the preloaded view is current.

    Returns a :class:`ManualLedgerTransactionResult` reflecting the updated
    transaction state after the patch is applied.
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue = _preloaded_catalogue if _preloaded_catalogue is not None else repository.load()
    current = _require_transaction(catalogue, transaction_id)
    command = _command_from_patch(
        bucket_id=bucket_id,
        current=current,
        patch=patch,
        actor=actor,
        source_command=source_command,
        classified_by_override=classified_by_override,
    )
    # Re-affirmation: operator supplied the same ``business_classification`` the record already
    # carries.  ``_command_from_patch`` produces a command identical to the stored transaction,
    # which would trigger the mutation-required guard in ``update_manual_transaction``.  Treat
    # field-for-field-identical commands originating from a ``business_classification`` patch as
    # confirmed no-ops rather than errors (option b from the S14 architecture verdict).
    # When ``reaffirm`` is True the operator explicitly requests re-application; skip the guard.
    if (
        not reaffirm
        and "business_classification" in patch.model_fields_set
        and _command_matches_current(command, current)
    ):
        return _result(bucket_id, current, ())
    return update_manual_transaction(
        transaction_id=transaction_id,
        command=command,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
        usage_ratio_profile=usage_ratio_profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def _command_from_patch(
    *,
    bucket_id: str,
    current: Transaction,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    source_command: str,
    classified_by_override: str | None = None,
) -> ManualLedgerTransactionCommand:
    raw = current.raw
    patch_fields = patch.model_fields_set
    booked_date = _required_patched(patch, patch_fields, "booked_date", raw.booked_date)
    amount = _required_patched(patch, patch_fields, "amount", raw.amount)
    currency = _required_patched(patch, patch_fields, "currency", raw.currency)
    direction = _required_patched(patch, patch_fields, "direction", current.direction)
    description = _required_patched(patch, patch_fields, "description", raw.description)
    business_classification = _required_patched(
        patch,
        patch_fields,
        "business_classification",
        current.business_classification,
    )
    business_pct = _optional_patched(patch, patch_fields, "business_pct", current.business_pct)
    category_id = _optional_patched(patch, patch_fields, "category_id", current.category_id)
    taxable_base = _optional_patched(patch, patch_fields, "taxable_base", current.taxable_base)
    iva_rate = _optional_patched(patch, patch_fields, "iva_rate", current.iva_rate)
    iva_amount = _optional_patched(patch, patch_fields, "iva_amount", current.iva_amount)
    recargo_amount = _optional_patched(patch, patch_fields, "recargo_amount", current.recargo_amount)
    irpf_category = _optional_patched(patch, patch_fields, "irpf_category", current.irpf_category)
    usage_ratio_id = _optional_patched(patch, patch_fields, "usage_ratio_id", current.usage_ratio_id)
    prorrata_reference = _optional_patched(patch, patch_fields, "prorrata_reference", current.prorrata_reference)
    if "business_classification" in patch_fields and business_classification is not BusinessClassification.MIXED:
        business_pct = None
        usage_ratio_id = None
    if "business_classification" in patch_fields and business_classification not in {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    }:
        category_id = None
        taxable_base = None
        iva_rate = None
        iva_amount = None
        recargo_amount = None
        irpf_category = None
        prorrata_reference = None
    notes = _required_patched(patch, patch_fields, "notes", current.notes)
    attachment_ids = _required_patched(patch, patch_fields, "attachment_ids", current.attachment_ids)
    iva_category = _optional_patched(patch, patch_fields, "iva_category", current.iva_category)
    counterparty_eu_member_state = _optional_patched(
        patch,
        patch_fields,
        "counterparty_eu_member_state",
        current.counterparty_eu_member_state,
    )
    group_label = _optional_patched(patch, patch_fields, "group_label", current.group_label)
    return ManualLedgerTransactionCommand(
        bucket_id=bucket_id,
        booked_date=booked_date,
        value_date=patch.value_date if "value_date" in patch_fields else raw.value_date,
        amount=amount,
        currency=currency,
        direction=direction,
        counterparty=patch.counterparty if "counterparty" in patch_fields else raw.counterparty,
        description=description,
        business_classification=business_classification,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        irpf_category=irpf_category,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        purchase_invoice_evidence_id=(
            patch.purchase_invoice_evidence_id
            if "purchase_invoice_evidence_id" in patch_fields
            else current.purchase_invoice_evidence_id
        ),
        attachment_ids=attachment_ids,
        notes=notes,
        iva_category=iva_category,
        counterparty_eu_member_state=counterparty_eu_member_state,
        group_label=group_label,
        actor=actor,
        source_command=source_command,
        classified_by_override=classified_by_override,
    )


def _event_payload(command: ManualLedgerTransactionCommand) -> dict[str, str]:
    payload = {
        "source_command": command.source_command,
        "direction": command.direction.value,
        "amount": _decimal_to_string(command.amount),
        "currency": command.currency,
    }
    if command.business_pct is not None:
        payload["business_pct"] = _decimal_to_string(command.business_pct)
    if command.usage_ratio_id is not None:
        payload["usage_ratio_id"] = command.usage_ratio_id
    return payload


def _update_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
) -> tuple[_EventSpec, ...]:
    common_payload = {
        **_event_payload(command),
        "previous_transaction_id": previous_transaction_id,
    }
    specs: list[_EventSpec] = []
    if _core_edit_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_UPDATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {**common_payload, "mutation_kind": "edit"},
            ),
        )
    if _classification_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {
                    **common_payload,
                    "classification": replacement.business_classification.value,
                    "category_id": replacement.category_id or "",
                    "mutation_kind": "classification",
                },
            ),
        )
    if _allocation_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {
                    **common_payload,
                    "business_pct": _optional_decimal(replacement.business_pct),
                    "usage_ratio_id": replacement.usage_ratio_id or "",
                    "prorrata_reference": replacement.prorrata_reference or "",
                    "mutation_kind": "allocation",
                },
            ),
        )
    specs.extend(_evidence_event_specs(current=current, replacement=replacement, common_payload=common_payload))
    if not specs:
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_UPDATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {**common_payload, "mutation_kind": "correction"},
            ),
        )
    return tuple(specs)


def _core_edit_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current.raw, field) != getattr(replacement.raw, field)
        for field in ("booked_date", "value_date", "amount", "currency", "counterparty", "description")
    ) or any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("direction", "taxable_base", "iva_rate", "iva_amount", "irpf_category", "notes")
    )


def _classification_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("business_classification", "category_id", "classification_reason")
    )


def _allocation_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("business_pct", "usage_ratio_id", "prorrata_reference")
    )


def _evidence_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    common_payload: Mapping[str, str],
) -> tuple[_EventSpec, ...]:
    specs: list[_EventSpec] = []
    if current.purchase_invoice_evidence_id != replacement.purchase_invoice_evidence_id:
        if current.purchase_invoice_evidence_id is not None:
            specs.append(
                (
                    BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                    BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    current.purchase_invoice_evidence_id,
                    {
                        **common_payload,
                        "transaction_id": replacement.transaction_id,
                        "mutation_kind": "purchase_invoice_evidence_detached",
                    },
                ),
            )
        if replacement.purchase_invoice_evidence_id is not None:
            specs.append(
                (
                    (
                        BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
                        if current.purchase_invoice_evidence_id is not None
                        else BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
                    ),
                    BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    replacement.purchase_invoice_evidence_id,
                    {
                        **common_payload,
                        "transaction_id": replacement.transaction_id,
                        "mutation_kind": "purchase_invoice_evidence_attached",
                    },
                ),
            )
    current_attachments = set(current.attachment_ids)
    replacement_attachments = set(replacement.attachment_ids)
    for attachment_id in sorted(replacement_attachments - current_attachments):
        specs.append(
            (
                BucketEventType.ATTACHMENT_LINKED,
                BucketEventObjectType.ATTACHMENT,
                attachment_id,
                {
                    **common_payload,
                    "transaction_id": replacement.transaction_id,
                    "linked": "true",
                    "mutation_kind": "attachment_linked",
                },
            ),
        )
    for attachment_id in sorted(current_attachments - replacement_attachments):
        specs.append(
            (
                BucketEventType.ATTACHMENT_REMOVED,
                BucketEventObjectType.ATTACHMENT,
                attachment_id,
                {
                    **common_payload,
                    "transaction_id": replacement.transaction_id,
                    "linked": "false",
                    "mutation_kind": "attachment_removed",
                },
            ),
        )
    return tuple(specs)


def _transaction_from_command(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    provider_transaction_id: str | None = None,
    bucket_event_id: str | None = None,
    created_by: str | None = None,
    created_source_command: str | None = None,
    created_event_id: str | None = None,
    existing_evidence_provenance: tuple[TransactionEvidenceProvenanceEntry, ...] = (),
    existing_edit_lineage: tuple[TransactionEditLineageEntry, ...] = (),
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    lifecycle_lineage: tuple[TransactionLifecycleLineageEntry, ...] = (),
    edit_lineage_entry: TransactionEditLineageEntry | None = None,
    evidence_event_ids: Mapping[tuple[str, str], str] | None = None,
    import_fingerprint: str | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_transaction_id or _provider_transaction_id(command, occurred_at=occurred_at),
        booked_date=command.booked_date,
        value_date=command.value_date,
        amount=command.amount,
        currency=command.currency,
        counterparty=command.counterparty,
        description=command.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".aeat-manual-ledger",
            source_sha256=_source_sha256(command, occurred_at=occurred_at),
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=occurred_at,
            provider_name=_MANUAL_PROVIDER_NAME,
        ),
        raw_fields=_raw_fields(command),
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": command.direction,
        "business_classification": command.business_classification,
        "business_pct": command.business_pct,
        "category_id": command.category_id,
        "taxable_base": command.taxable_base,
        "iva_rate": command.iva_rate,
        "iva_amount": command.iva_amount,
        "recargo_amount": command.recargo_amount,
        "irpf_category": command.irpf_category,
        "usage_ratio_id": command.usage_ratio_id,
        "prorrata_reference": command.prorrata_reference,
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
        "attachment_ids": command.attachment_ids,
        "created_by": created_by or command.actor,
        "source_command": created_source_command or command.source_command,
        "created_event_id": created_event_id or bucket_event_id,
        "lifecycle_state": lifecycle_state,
        "lifecycle_lineage": lifecycle_lineage,
        "evidence_provenance": _evidence_provenance(
            command,
            occurred_at=occurred_at,
            bucket_event_id=bucket_event_id,
            existing=existing_evidence_provenance,
            evidence_event_ids=evidence_event_ids or {},
        ),
        "edit_lineage": (
            (*existing_edit_lineage, edit_lineage_entry) if edit_lineage_entry is not None else existing_edit_lineage
        ),
        "import_fingerprint": import_fingerprint,
        "notes": command.notes,
        "iva_category": command.iva_category,
        "counterparty_eu_member_state": command.counterparty_eu_member_state,
        "source_jurisdiction": command.source_jurisdiction,
        "group_label": command.group_label,
        # D6: created_at is stamped once (defaults to occurred_at on first
        # construction) and carried verbatim through edits; modified_at
        # re-stamps to occurred_at on every mutating construction.
        "created_at": created_at if created_at is not None else occurred_at,
        "modified_at": modified_at if modified_at is not None else occurred_at,
    }
    if command.business_classification is not BusinessClassification.NOT_YET_PROCESSED:
        payload.update(
            {
                "classified_at": occurred_at,
                "classified_by": command.classified_by_override or CLASSIFIED_BY_MANUAL,
                "classification_reason": command.source_command,
                "classification_confidence": Decimal("1"),
            },
        )
    return Transaction.model_validate(payload)


def _evidence_provenance(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    bucket_event_id: str | None,
    existing: tuple[TransactionEvidenceProvenanceEntry, ...],
    evidence_event_ids: Mapping[tuple[str, str], str],
) -> tuple[TransactionEvidenceProvenanceEntry, ...]:
    wanted = (
        {("purchase_invoice_evidence", command.purchase_invoice_evidence_id)}
        if command.purchase_invoice_evidence_id is not None
        else set()
    ) | {("attachment", attachment_id) for attachment_id in command.attachment_ids}
    retained = tuple(entry for entry in existing if (entry.evidence_kind, entry.evidence_id) in wanted)
    seen = {(entry.evidence_kind, entry.evidence_id) for entry in retained}
    created: list[TransactionEvidenceProvenanceEntry] = []
    for evidence_kind, evidence_id in sorted(wanted - seen):
        typed_kind: Literal["purchase_invoice_evidence", "attachment"] = (
            "purchase_invoice_evidence" if evidence_kind == "purchase_invoice_evidence" else "attachment"
        )
        evidence_event_id = evidence_event_ids.get((typed_kind, evidence_id), bucket_event_id)
        created.append(
            TransactionEvidenceProvenanceEntry(
                evidence_kind=typed_kind,
                evidence_id=evidence_id,
                actor=command.actor,
                source_command=command.source_command,
                linked_at=occurred_at,
                bucket_event_id=evidence_event_id,
            ),
        )
    return (*retained, *created)


def _provider_transaction_id(command: ManualLedgerTransactionCommand, *, occurred_at: datetime) -> str:
    if command.idempotency_key is not None:
        return f"manual:{command.bucket_id}:{command.idempotency_key}"
    return f"manual:{command.bucket_id}:{occurred_at.isoformat()}:{_source_sha256(command, occurred_at=occurred_at)}"


def _source_sha256(command: ManualLedgerTransactionCommand, *, occurred_at: datetime) -> str:
    payload = command.model_dump(mode="json")
    payload["occurred_at"] = occurred_at.isoformat()
    return content_hash_hex(payload)


def _raw_fields(command: ManualLedgerTransactionCommand) -> Mapping[str, str]:
    values = {
        "source_kind": BindingSourceKind.LEDGER_TRANSACTION,
        "source_command": command.source_command,
        "actor": command.actor,
        "business_classification": command.business_classification.value,
        "direction": command.direction.value,
        "taxable_base": _optional_decimal(command.taxable_base),
        "iva_rate": _optional_decimal(command.iva_rate),
        "iva_amount": _optional_decimal(command.iva_amount),
        "recargo_amount": _optional_decimal(command.recargo_amount),
        "irpf_category": command.irpf_category or "",
        "usage_ratio_id": command.usage_ratio_id or "",
        "prorrata_reference": command.prorrata_reference or "",
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id or "",
        "attachment_ids": ",".join(command.attachment_ids),
    }
    if command.business_pct is not None:
        values["business_pct"] = _decimal_to_string(command.business_pct)
    if command.category_id is not None:
        values["category_id"] = command.category_id
    if command.idempotency_key is not None:
        values["idempotency_key"] = command.idempotency_key
    return values
