"""Manual ledger transaction services and read projections.

The services build :class:`~cadrumo.domain.transactions.Transaction` records from
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand`, persist them
in a loaded :class:`TransactionCatalogue`, append bucket events, and return
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` values.
Evidence paths validate purchase-invoice, attachment, and
:class:`~cadrumo.domain.usage_ratios.UsageRatioProfile` references before
persistence.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ...core.hashing import content_hash_hex

if TYPE_CHECKING:
    from ..invoices import InvoiceTransactionLinkResult

from ...core import BindingSourceKind, IvaDeductionEvidenceAuthority, Period
from ...core.decimal import format_decimal
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.attachments.protocols import AttachmentStoreProtocol as _AttachmentStoreProtocol
from ...domain.attachments.service import link_attachment_transaction
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.currency.service import CurrencyNormalizationService
from ...domain.invoices.errors import InvoiceLinkError
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.deduction_facts import IvaDeductionClassificationProvenance, required_deduction_evidence_authority
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction, TransactionCatalogue, TransactionEditLineageEntry, TransactionEvidenceProvenanceEntry, TransactionLifecycleLineageEntry, derive_import_fingerprint
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...domain.usage_ratios import (
    UsageRatioProfile,
)
from ..review.filter import LedgerReviewStatus
from .actions_common import (
    EventSpec,
    blocking_modelo_references,
    build_ledger_bucket_event,
    build_manual_ledger_result,
    command_matches_current,
    derive_evidence_event_ids,
    display_decimal,
    is_evidence_only_command,
    merge_identifier_tuple,
    mutation_signature,
    normalise_attachment_patch_ids,
    normalise_timestamp,
    optional_decimal,
    optional_patched,
    primary_lineage_event_id,
    purchase_invoice_evidence_records,
    raise_finalized_modelo_blocked,
    replace_transaction,
    require_actor,
    require_source_command,
    require_transaction,
    required_patched,
    resolve_attachment_store,
    resolve_bucket_event_repository,
    resolve_invoice_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
    transaction_modelo_source_ids,
    upsert_transaction,
    verify_evidence_references,
    verify_usage_ratio_reference,
)
from .actions_import import apply_fx_conversion as _apply_fx_conversion
from .models import (
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
from .preflight import preflight_ledger_tax_readiness
from .review_projection import ledger_transaction_review_status, project_ledger_review_query

_MANUAL_PROVIDER_NAME = "manual-ledger"

# Evidence catalogue and provenance are mutated ONLY through the attach authority
# (`attach_manual_transaction_evidence`). The generic manual-field update door
# refuses any patch/command that touches these fields; internal evidence-authority
# callers thread the private `_evidence_authority=True` flag to pass the guard.
_EVIDENCE_PATCH_FIELDS = frozenset({"purchase_invoice_evidence_id", "attachment_ids"})


def create_manual_transaction(
    command: ManualLedgerTransactionCommand,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    occurred_at: datetime | None = None,
    currency_normalizer: CurrencyNormalizationService | None = None,
) -> ManualLedgerTransactionResult:
    """Persist one manual ledger transaction in the command's bucket.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    with the created transaction and associated bucket event.
    """
    now = normalise_timestamp(occurred_at)
    repository = resolve_transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    if command.idempotency_key is not None:
        # The idempotency key is authoritative for row identity: a keyed row
        # carries the clock-free provider id `manual:{bucket}:{key}` on
        # raw.provider_transaction_id. Scan by that provider id (NOT the
        # content-folding catalogue id from derive_transaction_id) so the same
        # key always names the same logical add regardless of which content
        # fields it carries.
        provider_id = _provider_transaction_id(command, occurred_at=now)
        existing = next(
            (row for row in catalogue.values() if row.raw.provider_transaction_id == provider_id),
            None,
        )
        if existing is not None:
            if command_matches_current(command, existing):
                # Guarded idempotent retry: same idempotency key, identical content.
                # Return the stored row unchanged with no new event (an empty
                # bucket_event_ids tuple is the structural no-op signal), mirroring
                # the create_work_unit existing-record contract.
                return build_manual_ledger_result(command.bucket_id, existing, ())
            raise TransactionValidationError(
                f"ledger add idempotency-key {command.idempotency_key!r} already names a stored "
                "transaction with different content; use a new idempotency key for a different "
                "movement, or omit --idempotency-key to append a deliberate duplicate",
                translated_message="application.ledger.errors.idempotency_key_conflict",
            )
    transaction_base = _transaction_from_command(command, occurred_at=now, currency_normalizer=currency_normalizer)
    verify_evidence_references(
        command,
        transaction_id=transaction_base.transaction_id,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
    )
    verify_usage_ratio_reference(command, usage_ratio_profile=usage_ratio_profile)
    event = build_ledger_bucket_event(
        bucket_id=command.bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_CREATED,
        occurred_at=now,
        actor=command.actor,
        object_id=transaction_base.transaction_id,
        payload=_event_payload(command),
    )
    transaction = _transaction_from_command(
        command,
        occurred_at=now,
        bucket_event_id=event.event_id,
        currency_normalizer=currency_normalizer,
    )
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=upsert_transaction(catalogue, transaction),
        events=(event,),
    )
    _record_attachment_back_references(transaction, attachment_store=attachment_store)
    return build_manual_ledger_result(command.bucket_id, transaction, (event.event_id,))


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

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`.
    """
    trimmed_actor = require_actor(actor, operation="ledger evidence attachment")
    trimmed_source_command = require_source_command(source_command, operation="ledger evidence attachment")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    normalized_purchase_evidence_id = purchase_invoice_evidence_id.strip() if purchase_invoice_evidence_id else None
    normalized_attachment_ids = normalise_attachment_patch_ids(attachment_ids)
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
            "ledger transaction already has purchase_invoice_evidence_id and it cannot be "
            "replaced in place; detaching evidence is not implemented, so remove the "
            "transaction and re-add it with the correct evidence",
            translated_message="application.ledger.errors.purchase_evidence_already_set",
        )
    patch_values: dict[str, object] = {}
    if normalized_purchase_evidence_id is not None:
        patch_values["purchase_invoice_evidence_id"] = normalized_purchase_evidence_id
    if normalized_attachment_ids:
        patch_values["attachment_ids"] = merge_identifier_tuple(current.attachment_ids, normalized_attachment_ids)
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
        _evidence_authority=True,
    )


def detach_manual_transaction_attachments(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    attachment_ids: tuple[str, ...],
    source_command: str = "aeat app ledger detach",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Detach named supplementary attachments from one ledger transaction.

    The inverse of :func:`attach_manual_transaction_evidence` for the axis that
    can express it. ``attachment_ids`` is a whole-tuple patch, so the remaining
    ids are computed here and written as the new set -- the attach path merges
    into the same field, and both go through the one
    :func:`update_manual_transaction_fields` writer rather than editing the
    catalogue directly.

    PURCHASE EVIDENCE IS DELIBERATELY OUT OF SCOPE and refuses in
    :func:`attach_manual_transaction_evidence` instead of being cleared here.
    ``ManualLedgerTransactionPatch`` cannot express the difference between
    "clear this field" and "leave it unchanged": ``purchase_invoice_evidence_id``
    is an optional text field whose validator normalises an empty string to
    ``None``, which is also the patch's own "no change" value. Clearing it needs
    a sentinel the patch model does not have, and inventing one here -- rather
    than deciding it once for every optional field on that model -- would put a
    second clearing convention into the ledger command shape.

    Detaching does NOT delete the attachment's bytes. The attachment is a
    content-addressed secure object that other transactions and finalized
    revisions may reference; this removes one transaction's reference to it, and
    the stale-revision notices the caller already surfaces report where a
    finalized revision used what is now detached.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`.
    """
    trimmed_actor = require_actor(actor, operation="ledger evidence detachment")
    trimmed_source_command = require_source_command(source_command, operation="ledger evidence detachment")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    requested = normalise_attachment_patch_ids(attachment_ids)
    if not requested:
        raise TransactionValidationError(
            "ledger evidence detachment requires at least one attachment id",
            translated_message="application.ledger.errors.evidence_detachment_requires_ids",
        )
    attached = tuple(current.attachment_ids)
    unknown = tuple(identifier for identifier in requested if identifier not in attached)
    if unknown:
        raise TransactionValidationError(
            f"ledger transaction does not carry attachment(s) {unknown!r}",
            translated_message="application.ledger.errors.evidence_detachment_unknown_attachment",
            context={"attachment_ids": ", ".join(unknown)},
        )
    remaining = tuple(identifier for identifier in attached if identifier not in set(requested))
    return update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate({"attachment_ids": remaining}),
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
        _evidence_authority=True,
    )


def link_manual_transaction_invoice(
    *,
    bucket_id: str,
    transaction_id: str,
    invoice_id: str,
    actor: str = "operator",
    source_command: str = "aeat app ledger link",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> InvoiceTransactionLinkResult:
    """Establish an atomic invoice-only relationship for one ledger transaction.

    This is the sole invoice-linkage writer. It resolves the transaction,
    enforces the invoice's missing and cross-bucket policy up front, then
    delegates the bidirectional catalogue mutation and persistence to
    :func:`~cadrumo.application.invoices.link_invoice_transaction_repositories`.
    It never touches purchase evidence or attachments: evidence mutation is
    reserved for :func:`attach_manual_transaction_evidence`. Every rejection
    fires before any catalogue write, so a refused link leaves the transaction,
    invoice catalogue, and event history unchanged. The accepted path is
    equally all-or-nothing: the two catalogues and the
    :attr:`~cadrumo.domain.buckets.BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED`
    audit event are co-committed in one secure-object batch, so no failure can
    leave one side citing the other without being cited back, and no event can
    record a link that did not land.

    Returns an
    :class:`~cadrumo.application.invoices.InvoiceTransactionLinkResult`.
    """
    from ..invoices import link_invoice_transaction_repositories

    trimmed_actor = require_actor(actor, operation="ledger invoice linkage")
    trimmed_source_command = require_source_command(source_command, operation="ledger invoice linkage")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    current = require_transaction(repository.load(), transaction_id)
    invoices_repo = resolve_invoice_repository(bucket_id=bucket_id, repository=invoice_repository)
    invoice_record = invoices_repo.load().get(invoice_id)
    if invoice_record is None:
        raise InvoiceLinkError(
            "invoice_id not found in the active profile invoice catalogue",
            context={"invoice_id": invoice_id, "bucket_id": bucket_id},
        )
    if invoice_record.bucket_id not in (None, bucket_id):
        raise InvoiceLinkError(
            "invoice belongs to a different bucket than the active profile",
            context={
                "invoice_id": invoice_id,
                "command_bucket_id": bucket_id,
                "invoice_bucket_id": invoice_record.bucket_id or "",
            },
        )
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    event = build_ledger_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED,
        occurred_at=normalise_timestamp(occurred_at),
        actor=trimmed_actor,
        object_id=current.transaction_id,
        # Identifiers and the operator's verb only: invoice content (counterparty,
        # totals, tax id) never enters the event history.
        payload={
            "invoice_id": invoice_id,
            "source_command": trimmed_source_command,
            "mutation_kind": "invoice_linkage",
        },
    )
    # The event write rides the SAME batch as the two catalogues, so a crash
    # cannot record a linkage that did not land, nor land one silently.
    return link_invoice_transaction_repositories(
        bucket_id=bucket_id,
        invoice_id=invoice_id,
        transaction_id=current.transaction_id,
        invoice_repository=invoices_repo,
        transaction_repository=repository,
        extra_writes=(bucket_event_history_write(event_repository, (event,)),),
    )


def get_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> ManualLedgerTransactionResult:
    """Return one :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` from a bucket catalogue."""
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = require_transaction(repository.load(), transaction_id)
    return build_manual_ledger_result(bucket_id, transaction, ())


def list_manual_transactions(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Return every transaction in a bucket, sorted by effective date and id.

    Each element is a
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` for one
    stored transaction.
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transactions = sorted(
        repository.load().values(),
        key=lambda transaction: (
            transaction.raw.value_date or transaction.raw.booked_date,
            transaction.transaction_id,
        ),
    )
    return tuple(build_manual_ledger_result(bucket_id, transaction, ()) for transaction in transactions)


def query_ledger_review_rows(
    query: LedgerReviewQuery,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> LedgerReviewQueryResult:
    """Return review rows for bucket-local ledger transactions.

    Returns a :class:`~cadrumo.application.ledger.models.LedgerReviewQueryResult`.
    """
    repository = resolve_transaction_repository(bucket_id=query.bucket_id, repository=transaction_repository)
    catalogue = repository.load()
    return project_ledger_review_query(
        query=query,
        catalogue=catalogue,
        bucket_event_repository=bucket_event_repository,
        transaction_payload_builder=ledger_transaction_payload,
    )


def ledger_transaction_payload(transaction: Transaction) -> LedgerTransactionPayload:
    """Return the :class:`~cadrumo.application.ledger.models.LedgerTransactionPayload` for one ledger transaction."""
    raw = transaction.raw
    return LedgerTransactionPayload(
        transaction_id=transaction.transaction_id,
        date=(raw.value_date or raw.booked_date).isoformat(),
        booked_date=raw.booked_date.isoformat(),
        value_date=raw.value_date.isoformat() if raw.value_date else None,
        amount=display_decimal(raw.amount),
        currency=raw.currency,
        direction=transaction.direction.value,
        counterparty=raw.display_counterparty,
        description=raw.description,
        business_classification=transaction.business_classification.value,
        business_pct=display_decimal(transaction.business_pct) if transaction.business_pct is not None else None,
        category_id=transaction.category_id,
        taxable_base=display_decimal(transaction.taxable_base) if transaction.taxable_base is not None else None,
        iva_rate=display_decimal(transaction.iva_rate) if transaction.iva_rate is not None else None,
        iva_amount=display_decimal(transaction.iva_amount) if transaction.iva_amount is not None else None,
        iva_category=transaction.iva_category.value if transaction.iva_category is not None else None,
        counterparty_country=transaction.counterparty_country,
        counterparty_identification_state=(
            transaction.counterparty_identification_state.value
            if transaction.counterparty_identification_state is not None
            else None
        ),
        irpf_category=transaction.irpf_category,
        m210_income_classification=transaction.m210_income_classification,
        usage_ratio_id=transaction.usage_ratio_id,
        prorrata_reference=transaction.prorrata_reference,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        attachment_ids=transaction.attachment_ids,
        notes=transaction.notes,
        lifecycle_state=transaction.lifecycle_state.value,
        classified_by=transaction.classified_by,
        classified_at=transaction.classified_at.isoformat() if transaction.classified_at is not None else None,
        classification_reason=transaction.classification_reason,
        classification_confidence=(
            display_decimal(transaction.classification_confidence)
            if transaction.classification_confidence is not None
            else None
        ),
        source_jurisdiction=transaction.source_jurisdiction,
        value_in_eur=display_decimal(transaction.value_in_eur) if transaction.value_in_eur is not None else None,
        fx_rate=display_decimal(transaction.fx_rate) if transaction.fx_rate is not None else None,
        created_at=transaction.created_at.isoformat(),
        modified_at=transaction.modified_at.isoformat(),
    )


def ledger_transaction_review_payload(transaction: Transaction) -> LedgerTransactionReviewPayload:
    """Return one ledger transaction projection plus derived operator review status.

    Returns a
    :class:`~cadrumo.application.ledger.models.LedgerTransactionReviewPayload` with all
    operator-facing fields populated from the transaction record.
    """
    base = ledger_transaction_payload(transaction)
    return LedgerTransactionReviewPayload(
        **base.model_dump(),
        review_status=ledger_transaction_review_status(transaction),
    )


def ledger_transaction_result_payload(result: ManualLedgerTransactionResult) -> LedgerTransactionResultPayload:
    """Return the canonical result payload for one ledger mutation/read result.

    Returns a :class:`~cadrumo.application.ledger.models.LedgerTransactionResultPayload`.
    """
    return LedgerTransactionResultPayload(
        bucket_id=result.ref.bucket_id,
        transaction_id=result.ref.transaction_id,
        review_status=ledger_transaction_review_status(result.transaction),
        transaction=ledger_transaction_payload(result.transaction),
    )


def ledger_transaction_tracking_payload(transaction: Transaction) -> LedgerTransactionTrackingPayload:
    """Return durable event lineage fields for one ledger transaction.

    Returns a
    :class:`~cadrumo.application.ledger.models.LedgerTransactionTrackingPayload`.
    """
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
    """Return a read-only :class:`~cadrumo.application.ledger.models.LedgerStatusReport` for one bucket."""
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
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
        business_income_total=display_decimal(income_total),
        business_expense_total=display_decimal(expense_total),
        business_net_total=display_decimal(income_total - expense_total),
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
    _evidence_authority: bool = False,
) -> ManualLedgerTransactionResult:
    """Replace one manual ledger transaction from a validated command payload.

    The replacement is built from
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand` and saved
    as a new :class:`~cadrumo.domain.transactions.Transaction` revision.

    ``_evidence_authority`` is a private flag threaded only by the evidence
    attach authority (:func:`attach_manual_transaction_evidence`) and the
    evidence-driven split inheritance. When it is :data:`False` (every generic
    manual-field update) the command MUST NOT change
    ``purchase_invoice_evidence_id`` or ``attachment_ids``; evidence catalogue and
    provenance mutation are reserved for ``aeat app ledger attach``.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`.
    """
    now = normalise_timestamp(occurred_at)
    repository = resolve_transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    if not _evidence_authority and (
        command.purchase_invoice_evidence_id != current.purchase_invoice_evidence_id
        or command.attachment_ids != current.attachment_ids
    ):
        raise TransactionValidationError(
            "purchase evidence and attachments are managed only by `aeat app ledger attach`; "
            "a generic ledger transaction update must not change purchase_invoice_evidence_id or attachment_ids",
            context={"transaction_id": transaction_id},
        )
    blockers = blocking_modelo_references(
        bucket_id=command.bucket_id,
        transaction_ids=transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    # An evidence-only attachment cannot disturb a finalized revision (stable
    # transaction id, unchanged row fingerprint, frozen bundled evidence), so it
    # is exempt from the write guard — otherwise the documented remedy for an
    # export evidence refusal would itself be blocked by the calculation that
    # raised it. The cited revisions are reported back as stale so the operator
    # is told to recalculate; the exemption never widens past evidence fields.
    evidence_only = is_evidence_only_command(command, current)
    if blockers and not evidence_only:
        raise_finalized_modelo_blocked(
            operation="ledger transaction update",
            transaction_ids=transaction_modelo_source_ids(current),
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
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=replace_transaction(catalogue, old_transaction_id=transaction_id, replacement=replacement),
        events=events,
    )
    _record_attachment_back_references(
        replacement,
        attachment_store=attachment_store,
    )
    return build_manual_ledger_result(
        command.bucket_id,
        replacement,
        tuple(event.event_id for event in events),
        stale_finalized_revisions=blockers if evidence_only else (),
    )


def _record_attachment_back_references(
    transaction: Transaction,
    *,
    attachment_store: _AttachmentStoreProtocol | None,
) -> None:
    """Record the transaction on every attachment manifest the transaction cites.

    The transaction side of the link is written by the catalogue save above.
    Without this, the manifest side stayed empty, so
    :func:`~domain.attachments.list_attachments` with
    ``linked_to=<transaction_id>`` could not discover an attachment the
    transaction itself cites -- the manifest models the link and the evidence
    workflow documents the provenance as bidirectional.

    Runs after the transaction is durably persisted, so a failure here can only
    leave the manifest side behind, never a manifest pointing at a transaction
    that was never written. :func:`~domain.attachments.link_attachment_transaction`
    is idempotent, so a re-attach re-converges the pair rather than duplicating
    the reference.
    """
    if not transaction.attachment_ids:
        return
    store = resolve_attachment_store(attachment_store)
    for attachment_id in transaction.attachment_ids:
        link_attachment_transaction(
            store,
            attachment_id=attachment_id,
            transaction_id=transaction.transaction_id,
        )


def _prepare_manual_transaction_update(
    *,
    current: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
    now: datetime,
    currency_normalizer: CurrencyNormalizationService | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
) -> tuple[Transaction, tuple[BucketEvent, ...]] | None:
    """Build a replacement transaction and bucket events for one in-memory edit.

    Returns ``None`` when the command is a field-for-field no-op (the caller
    decides whether that is an error or a skip). Verifies evidence and usage-ratio
    references but performs **no** persistence and **no** catalogue load - the
    caller owns a single load/save so a batch re-encrypts the catalogue once
    rather than per row (the ``bulk_classify_from_csv`` load-once/save-once
    contract). Lifecycle and blocking-modelo guards remain the caller's
    responsibility before invoking this builder.
    """
    replacement = _transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.provider_transaction_id if command.idempotency_key is None else None,
        currency_normalizer=currency_normalizer,
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
    if mutation_signature(current) == mutation_signature(replacement):
        return None
    verify_evidence_references(
        command,
        transaction_id=replacement.transaction_id,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
    )
    verify_usage_ratio_reference(command, usage_ratio_profile=usage_ratio_profile)
    event_specs = _update_event_specs(
        current=current,
        replacement=replacement,
        command=command,
        previous_transaction_id=previous_transaction_id,
    )
    events = tuple(
        build_ledger_bucket_event(
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
    primary_event_id = primary_lineage_event_id(events)
    evidence_event_ids = derive_evidence_event_ids(events)
    replacement = _transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.provider_transaction_id if command.idempotency_key is None else None,
        currency_normalizer=currency_normalizer,
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
    _evidence_authority: bool = False,
) -> ManualLedgerTransactionResult:
    """Apply a typed field patch to one active bucket-scoped ledger transaction.

    The patch is a
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionPatch` converted
    into a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand`
    before the same replacement path used by
    :func:`~cadrumo.application.ledger.actions_manual.update_manual_transaction`.

    When ``reaffirm`` is :data:`True` the automatic re-affirmation no-op guard
    is bypassed and the command is forced through even if the patched fields are
    field-for-field identical to the stored transaction. This is the explicit
    operator-driven counterpart to the automatic silent no-op.

    ``_preloaded_catalogue`` is an internal optimisation: a caller that has
    already decrypted the bucket :class:`TransactionCatalogue` (e.g.
    :func:`~cadrumo.application.ledger.actions_manual.attach_manual_transaction_evidence`) passes
    it through so this function does not decrypt the whole catalogue a second
    time. There is no write between the caller's load and this one, so the
    preloaded view is current.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    reflecting the updated transaction state after the patch is applied.
    """
    if not _evidence_authority and patch.model_fields_set & _EVIDENCE_PATCH_FIELDS:
        raise TransactionValidationError(
            "purchase evidence and attachments are managed only by `aeat app ledger attach`; "
            "a generic ledger field update must not set purchase_invoice_evidence_id or attachment_ids",
            context={
                "transaction_id": transaction_id,
                "evidence_fields": ",".join(sorted(patch.model_fields_set & _EVIDENCE_PATCH_FIELDS)),
            },
        )
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue = _preloaded_catalogue if _preloaded_catalogue is not None else repository.load()
    current = require_transaction(catalogue, transaction_id)
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
    # confirmed no-ops rather than errors (the deliberate direction chosen for this guard).
    # When ``reaffirm`` is True the operator explicitly requests re-application; skip the guard.
    if (
        not reaffirm
        and "business_classification" in patch.model_fields_set
        and command_matches_current(command, current)
    ):
        return build_manual_ledger_result(bucket_id, current, ())
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
        _evidence_authority=_evidence_authority,
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
    booked_date = required_patched(patch, patch_fields, "booked_date", raw.booked_date)
    amount = required_patched(patch, patch_fields, "amount", raw.amount)
    currency = required_patched(patch, patch_fields, "currency", raw.currency)
    direction = required_patched(patch, patch_fields, "direction", current.direction)
    description = required_patched(patch, patch_fields, "description", raw.description)
    business_classification = required_patched(
        patch,
        patch_fields,
        "business_classification",
        current.business_classification,
    )
    business_pct = optional_patched(patch, patch_fields, "business_pct", current.business_pct)
    category_id = optional_patched(patch, patch_fields, "category_id", current.category_id)
    taxable_base = optional_patched(patch, patch_fields, "taxable_base", current.taxable_base)
    iva_rate = optional_patched(patch, patch_fields, "iva_rate", current.iva_rate)
    iva_amount = optional_patched(patch, patch_fields, "iva_amount", current.iva_amount)
    recargo_amount = optional_patched(patch, patch_fields, "recargo_amount", current.recargo_amount)
    irpf_category = optional_patched(patch, patch_fields, "irpf_category", current.irpf_category)
    m210_income_classification = optional_patched(
        patch,
        patch_fields,
        "m210_income_classification",
        current.m210_income_classification,
    )
    usage_ratio_id = optional_patched(patch, patch_fields, "usage_ratio_id", current.usage_ratio_id)
    prorrata_reference = optional_patched(patch, patch_fields, "prorrata_reference", current.prorrata_reference)
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
        m210_income_classification = None
        prorrata_reference = None
    notes = required_patched(patch, patch_fields, "notes", current.notes)
    attachment_ids = required_patched(patch, patch_fields, "attachment_ids", current.attachment_ids)
    iva_category = optional_patched(patch, patch_fields, "iva_category", current.iva_category)
    deduction_fact_kind = optional_patched(
        patch,
        patch_fields,
        "deduction_fact_kind",
        current.deduction_fact_kind,
    )
    counterparty_country = optional_patched(
        patch,
        patch_fields,
        "counterparty_country",
        current.counterparty_country,
    )
    counterparty_identification_state = optional_patched(
        patch,
        patch_fields,
        "counterparty_identification_state",
        current.counterparty_identification_state,
    )
    group_label = optional_patched(patch, patch_fields, "group_label", current.group_label)
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
        m210_income_classification=m210_income_classification,
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
        deduction_fact_kind=deduction_fact_kind,
        counterparty_country=counterparty_country,
        counterparty_identification_state=counterparty_identification_state,
        source_jurisdiction=(
            patch.source_jurisdiction if "source_jurisdiction" in patch_fields else current.source_jurisdiction
        ),
        group_label=group_label,
        actor=actor,
        source_command=source_command,
        classified_by_override=classified_by_override,
    )


def _event_payload(command: ManualLedgerTransactionCommand) -> dict[str, str]:
    payload = {
        "source_command": command.source_command,
        "direction": command.direction.value,
        "amount": format_decimal(command.amount),
        "currency": command.currency,
    }
    if command.business_pct is not None:
        payload["business_pct"] = format_decimal(command.business_pct)
    if command.usage_ratio_id is not None:
        payload["usage_ratio_id"] = command.usage_ratio_id
    return payload


def _update_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
) -> tuple[EventSpec, ...]:
    common_payload = {
        **_event_payload(command),
        "previous_transaction_id": previous_transaction_id,
    }
    specs: list[EventSpec] = []
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
                    "business_pct": optional_decimal(replacement.business_pct),
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
) -> tuple[EventSpec, ...]:
    specs: list[EventSpec] = []
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


def _invoice_evidence_provenance(
    command: ManualLedgerTransactionCommand,
) -> IvaDeductionClassificationProvenance | None:
    """Derive the deduction's evidence pointer from its linked purchase invoice.

    The operator declares WHICH deduction this is (the taxonomy is documented
    as non-inferable, so ``deduction_fact_kind`` is carried, never guessed);
    the evidence pointer behind it is not a judgement and must not be typed by
    hand. It is read from the registered evidence record the row already links,
    whose content-addressed ``attachment_id`` is the immutable digest the
    provenance contract asks for.

    Only the invoice-evidence authority is derivable here. A customs
    declaration, an intra-EU self-assessment, a REAGP receipt or a
    bienes-inversion regularisation is established by a record this link cannot
    see, so those kinds resolve to ``None`` and refuse downstream rather than
    being stamped with an invoice digest that did not establish them.
    """
    if command.deduction_fact_kind is None or command.purchase_invoice_evidence_id is None:
        return None
    if required_deduction_evidence_authority(command.deduction_fact_kind) is not (
        IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE
    ):
        return None
    evidence_id = command.purchase_invoice_evidence_id
    record = next(
        (
            candidate
            for candidate in purchase_invoice_evidence_records(command.bucket_id)
            if candidate.evidence_id == evidence_id
        ),
        None,
    )
    if record is None:
        return None
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        source_locator=record.evidence_id,
        evidence_digest=record.attachment_id,
    )


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
    currency_normalizer: CurrencyNormalizationService | None = None,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_transaction_id or _provider_transaction_id(command, occurred_at=occurred_at),
        booked_date=command.booked_date,
        value_date=command.value_date,
        amount=command.amount,
        currency=command.currency,
        counterparty=command.counterparty,
        description=command.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".cadrumo-manual-ledger",
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
        "m210_income_classification": command.m210_income_classification,
        "usage_ratio_id": command.usage_ratio_id,
        "prorrata_reference": command.prorrata_reference,
        "art_104_tres_exclusion": command.art_104_tres_exclusion,
        "input_classification": command.input_classification,
        "prorrata_sector_id": command.prorrata_sector_id,
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
        # Stamp the content-only movement fingerprint on manual rows when the
        # caller does not carry one forward (every create path). Edits pass the
        # stored fingerprint verbatim. This lets a manually-entered movement
        # participate in the import-path duplicate/likely-duplicate advisory.
        "import_fingerprint": (
            import_fingerprint
            if import_fingerprint is not None
            else derive_import_fingerprint(raw, direction=command.direction)
        ),
        "notes": command.notes,
        "iva_category": command.iva_category,
        "deduction_fact_kind": command.deduction_fact_kind,
        "deduction_provenance": _invoice_evidence_provenance(command),
        "counterparty_country": command.counterparty_country,
        "counterparty_identification_state": command.counterparty_identification_state,
        "source_jurisdiction": command.source_jurisdiction,
        "group_label": command.group_label,
        # D6: created_at is stamped once (defaults to occurred_at on first
        # construction) and carried verbatim through edits; modified_at
        # re-stamps to occurred_at on every mutating construction.
        "created_at": created_at if created_at is not None else occurred_at,
        "modified_at": modified_at if modified_at is not None else occurred_at,
    }
    # Convert a foreign-currency manual row at entry, exactly as the file-import
    # path does. Without this the row persists with no value_in_eur and every
    # aggregation gate withholds it, so a manually-entered foreign invoice never
    # reaches the modelo at all.
    payload.update(_fx_conversion_fields(raw, currency_normalizer))
    payload.update(_classification_fields(command, occurred_at=occurred_at))
    return Transaction.model_validate(payload)


def _fx_conversion_fields(
    raw: RawTransaction,
    currency_normalizer: CurrencyNormalizationService | None,
) -> dict[str, object]:
    """Project the converted foreign-currency fields, empty when no rate resolves."""
    fx_rate, value_in_eur, _rate_source, _rate_date_iso = _apply_fx_conversion(raw, currency_normalizer)
    if fx_rate is None or value_in_eur is None:
        return {}
    return {"fx_rate": fx_rate, "value_in_eur": value_in_eur}


def _classification_fields(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
) -> dict[str, object]:
    """Project the classification stamp, empty while the row is unprocessed."""
    if command.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return {}
    return {
        "classified_at": occurred_at,
        "classified_by": command.classified_by_override or CLASSIFIED_BY_MANUAL,
        # #231: the operator's free-text rationale (the manual `classify
        # --reason` value, threaded through as `command.notes`) is the
        # real "why" behind the decision and takes precedence; the
        # invoking command name remains the fallback for classification
        # paths that carry no operator-supplied reason (e.g. bulk
        # `--file` rows with no `notes` column).
        "classification_reason": command.notes or command.source_command,
        "classification_confidence": Decimal("1"),
    }


def _evidence_provenance(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    bucket_event_id: str | None,
    existing: tuple[TransactionEvidenceProvenanceEntry, ...],
    evidence_event_ids: Mapping[tuple[str, str], str],
) -> tuple[TransactionEvidenceProvenanceEntry, ...]:
    wanted: set[tuple[Literal["purchase_invoice_evidence", "attachment"], str]] = {
        ("attachment", attachment_id) for attachment_id in command.attachment_ids
    }
    if command.purchase_invoice_evidence_id is not None:
        wanted.add(("purchase_invoice_evidence", command.purchase_invoice_evidence_id))
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
        "taxable_base": optional_decimal(command.taxable_base),
        "iva_rate": optional_decimal(command.iva_rate),
        "iva_amount": optional_decimal(command.iva_amount),
        "recargo_amount": optional_decimal(command.recargo_amount),
        "irpf_category": command.irpf_category or "",
        "usage_ratio_id": command.usage_ratio_id or "",
        "prorrata_reference": command.prorrata_reference or "",
        "art_104_tres_exclusion": command.art_104_tres_exclusion.value if command.art_104_tres_exclusion else "",
        "input_classification": command.input_classification.value if command.input_classification else "",
        "prorrata_sector_id": command.prorrata_sector_id or "",
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id or "",
        "attachment_ids": ",".join(command.attachment_ids),
    }
    if command.business_pct is not None:
        values["business_pct"] = format_decimal(command.business_pct)
    if command.category_id is not None:
        values["category_id"] = command.category_id
    if command.idempotency_key is not None:
        values["idempotency_key"] = command.idempotency_key
    return values


command_from_patch = _command_from_patch
prepare_manual_transaction_update = _prepare_manual_transaction_update

__all__ = [
    "attach_manual_transaction_evidence",
    "create_manual_transaction",
    "detach_manual_transaction_attachments",
    "get_manual_transaction",
    "ledger_transaction_payload",
    "ledger_transaction_result_payload",
    "ledger_transaction_review_payload",
    "ledger_transaction_tracking_payload",
    "link_manual_transaction_invoice",
    "list_manual_transactions",
    "query_ledger_review_rows",
    "summarize_manual_transactions",
    "update_manual_transaction",
    "update_manual_transaction_fields",
]
