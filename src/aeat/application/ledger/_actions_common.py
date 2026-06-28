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
from typing import TYPE_CHECKING

from ...core.decimal import format_decimal
from ...core.time import now

if TYPE_CHECKING:
    pass

from ...core.time._utc import coerce_utc_aware
from ...domain.attachments import AttachmentNotFoundError, AttachmentValidationError
from ...domain.attachments._protocols import AttachmentStoreProtocol as _AttachmentStoreProtocol
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
from ...domain.invoices._protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva import InvoiceKind
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import CalculationRevisionState
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.transactions import (
    TX_BUCKET_NAMESPACE,
    BucketTransactionRef,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionNotFoundError,
    TransactionValidationError,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ...domain.usage_ratios import (
    UsageRatioProfile,
    UsageRatioValidationError,
    load_usage_ratios,
    validate_usage_ratio_reference,
)
from ._models import (
    LedgerRemovalBlocker,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)

_BUCKET_EVENT_PAYLOAD_VERSION = 1

_EventSpec = tuple[BucketEventType, BucketEventObjectType, str, dict[str, str]]
_REMOVAL_BLOCKING_REVISION_STATES = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    },
)
# Draft revisions do not block removal (the operator may legitimately prune a row
# before finalising), but a draft that still cites the removed row will assert an
# income/expense no longer in the books on the next verify/file. Surfacing a
# non-blocking advisory keeps that under-declaration non-silent
# (no-silent-under-declaration). DESCARTADO (discarded) drafts are excluded: they
# are not live filings.
_REMOVAL_ADVISORY_REVISION_STATES = frozenset(
    {
        CalculationRevisionState.BORRADOR,
    },
)


def _transaction_repository(
    *,
    bucket_id: str,
    repository: TransactionCatalogueRepository | TransactionCatalogueRepositoryProtocol | None,
) -> TransactionCatalogueRepository:
    if repository is None:
        return TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise TransactionValidationError(
            "transaction repository bucket_id does not match the manual ledger command bucket",
            context={"command_bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    assert isinstance(repository, TransactionCatalogueRepository)
    return repository


def _invoice_repository(
    *,
    bucket_id: str,
    repository: InvoiceCatalogueRepositoryProtocol | None,
) -> InvoiceCatalogueRepository:
    if repository is None:
        return InvoiceCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id is not None and repository.bucket_id != bucket_id:
        raise TransactionValidationError(
            "invoice repository bucket_id does not match the manual ledger command bucket",
            context={"command_bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    assert isinstance(repository, InvoiceCatalogueRepository)
    return repository


def _bucket_event_repository(
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol | None,
) -> BucketEventHistoryRepository:
    if repository is not None:
        assert isinstance(repository, BucketEventHistoryRepository)
        return repository
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    return BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))


def _require_actor(value: str, *, operation: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise TransactionValidationError(f"{operation} actor must not be blank")
    return trimmed


def _require_source_command(value: str, *, operation: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise TransactionValidationError(f"{operation} source_command must not be blank")
    return trimmed


def _normalise_attachment_patch_ids(attachment_ids: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(item.strip() for item in attachment_ids if item.strip())
    if len(set(normalized)) != len(normalized):
        raise TransactionValidationError("ledger evidence attachment ids must not contain duplicates")
    return normalized


def _merge_identifier_tuple(existing: tuple[str, ...], incoming: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = list(existing)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def _required_patched[T](
    patch: ManualLedgerTransactionPatch,
    patch_fields: set[str],
    field: str,
    fallback: T,
) -> T:
    """Return ``patch.<field>`` when in patch_fields and non-null; otherwise the fallback.

    Raises ``TransactionValidationError`` when the field is set on the
    patch but explicitly nulled â€” the patch contract forbids resetting a
    required value to None. Generic in ``T`` so the caller's field type
    flows through to the assignment site (type checkers see the concrete
    type at the use point, not ``object``).
    """
    if field not in patch_fields:
        return fallback
    value = getattr(patch, field)
    if value is None:
        raise TransactionValidationError(f"manual ledger patch {field} must not be null")
    # TYPE-IGNORE-RATIONALE-GENERIC-GETATTR-BOUNDED:
    # getattr returns Any but the caller binds the result to a generic T
    # via the fallback parameter.
    return value  # type: ignore[no-any-return]


def _optional_patched[T](
    patch: ManualLedgerTransactionPatch,
    patch_fields: set[str],
    field: str,
    fallback: T,
) -> T:
    """Return ``patch.<field>`` when in patch_fields (None allowed); otherwise the fallback.

    Generic in ``T`` for the same reason as :func:`_required_patched`.
    """
    if field not in patch_fields:
        return fallback
    # TYPE-IGNORE-RATIONALE-GENERIC-GETATTR-BOUNDED:
    # getattr returns Any but the caller binds the result to a generic T
    # via the fallback parameter.
    return getattr(patch, field)  # type: ignore[no-any-return]


def _blocking_modelo_references(
    *,
    bucket_id: str,
    transaction_ids: tuple[str, ...],
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> tuple[LedgerRemovalBlocker, ...]:
    if not transaction_ids:
        return ()
    wanted = set(transaction_ids)
    work_units = (work_unit_repository or WorkUnitCatalogueRepository()).load()
    revisions = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    blockers: list[LedgerRemovalBlocker] = []
    for revision in revisions.values():
        if revision.state not in _REMOVAL_BLOCKING_REVISION_STATES:
            continue
        if not wanted.intersection(revision.source_transaction_ids):
            continue
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        blockers.append(
            LedgerRemovalBlocker(
                work_unit_id=work_unit.work_unit_id,
                calculation_revision_id=revision.calculation_revision_id,
                revision_state=revision.state.value,
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            ),
        )
    return tuple(
        sorted(
            blockers,
            key=lambda blocker: (
                blocker.modelo,
                blocker.filing_year,
                blocker.period,
                blocker.calculation_revision_id,
            ),
        ),
    )


def _draft_revision_advisories(
    *,
    bucket_id: str,
    transaction_ids: tuple[str, ...],
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> tuple[LedgerRemovalBlocker, ...]:
    """Collect DRAFT (BORRADOR) revisions still citing the wanted transaction ids.

    Removal proceeds for draft-cited rows, but the draft's
    ``source_transaction_ids`` will still assert the removed row's income/expense
    on the next verify/file. These advisory rows name each affected draft so the
    operator can recalculate it (no-silent-under-declaration). Correctness rides
    on the live revision-catalogue scan, never the derived participation index
    (ledger-participation-index-is-derived-rebuildable).
    """
    if not transaction_ids:
        return ()
    wanted = set(transaction_ids)
    work_units = (work_unit_repository or WorkUnitCatalogueRepository()).load()
    revisions = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    advisories: list[LedgerRemovalBlocker] = []
    for revision in revisions.values():
        if revision.state not in _REMOVAL_ADVISORY_REVISION_STATES:
            continue
        if not wanted.intersection(revision.source_transaction_ids):
            continue
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        advisories.append(
            LedgerRemovalBlocker(
                work_unit_id=work_unit.work_unit_id,
                calculation_revision_id=revision.calculation_revision_id,
                revision_state=revision.state.value,
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            ),
        )
    return tuple(
        sorted(
            advisories,
            key=lambda advisory: (
                advisory.modelo,
                advisory.filing_year,
                advisory.period,
                advisory.calculation_revision_id,
            ),
        ),
    )


def _blockers_by_source_transaction_id(
    *,
    bucket_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> dict[str, tuple[LedgerRemovalBlocker, ...]]:
    """Map each source transaction id to the finalized-modelo blockers referencing it.

    Computed once so a batch edit can look up the finalized-modelo guard per row
    without reloading the work-unit and calculation repositories on every row
    (the load-once half of the ``bulk_classify_from_csv`` S31 contract).
    """
    work_units = (work_unit_repository or WorkUnitCatalogueRepository()).load()
    revisions = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    out: dict[str, list[LedgerRemovalBlocker]] = {}
    for revision in revisions.values():
        if revision.state not in _REMOVAL_BLOCKING_REVISION_STATES:
            continue
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        blocker = LedgerRemovalBlocker(
            work_unit_id=work_unit.work_unit_id,
            calculation_revision_id=revision.calculation_revision_id,
            revision_state=revision.state.value,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
        for txid in revision.source_transaction_ids:
            out.setdefault(txid, []).append(blocker)
    return {txid: tuple(found) for txid, found in out.items()}


def _transaction_modelo_source_ids(transaction: Transaction) -> tuple[str, ...]:
    return tuple(
        sorted({transaction.transaction_id, *(entry.previous_transaction_id for entry in transaction.edit_lineage)}),
    )


def _catalogue_modelo_source_ids(catalogue: TransactionCatalogue) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                source_id
                for transaction in catalogue.values()
                for source_id in _transaction_modelo_source_ids(transaction)
            },
        ),
    )


def _raise_finalized_modelo_blocked(
    *,
    operation: str,
    transaction_ids: tuple[str, ...],
    blockers: tuple[LedgerRemovalBlocker, ...],
) -> None:
    first = blockers[0]
    raise TransactionValidationError(
        f"{operation} refused because finalized modelo revisions cite the transaction",
        context={
            "transaction_ids": ",".join(transaction_ids),
            "calculation_revision_id": first.calculation_revision_id,
            "work_unit_id": first.work_unit_id,
            "modelo": first.modelo,
            "filing_year": str(first.filing_year),
            "period": first.period,
            "blocking_reference_count": str(len(blockers)),
        },
    )


def transaction_catalogue_object_id(bucket_id: str) -> str:
    return f"transaction-catalogue:{bucket_id.strip()}"


def _verify_evidence_references(
    command: ManualLedgerTransactionCommand,
    *,
    transaction_id: str,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
    attachment_store: _AttachmentStoreProtocol | None,
) -> None:
    if command.purchase_invoice_evidence_id is not None:
        _verify_purchase_invoice_evidence(command, invoice_repository=invoice_repository)
    if command.attachment_ids:
        _verify_attachment_references(command, transaction_id=transaction_id, attachment_store=attachment_store)


def _purchase_invoice_evidence_record_exists(bucket_id: str, evidence_id: str) -> bool:
    """Return True when a ``PurchaseInvoiceEvidence`` record with ``evidence_id`` exists in the bucket.

    Resolves the bucket-scoped encrypted purchase-invoice evidence store written by
    ``aeat app ledger evidence add`` (the :class:`PurchaseInvoiceEvidence` namespace),
    distinct from the rich :class:`InvoiceCatalogue` written by invoice-import flows.
    Local imports mirror this module's existing deferred-import style.
    """
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ...core.config import load_settings
    from ._evidence import PurchaseInvoiceEvidenceRepository

    repository = PurchaseInvoiceEvidenceRepository(
        objects=secure_object_repository_for_bucket(bucket_id, load_settings()),
    )
    document = repository.load(bucket_id)
    if document is None:
        return False
    return any(record.evidence_id == evidence_id for record in document.records)


def _verify_purchase_invoice_evidence(
    command: ManualLedgerTransactionCommand,
    *,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> None:
    """Verify a purchase-invoice evidence reference resolves to one of two distinct id spaces.

    The ``purchase_invoice_evidence_id`` may name either of two bucket-scoped id
    spaces, checked in order:

    1. A :class:`PurchaseInvoiceEvidence` record minted by ``aeat app ledger
       evidence add`` (PDF/image evidence registered into the dedicated evidence
       store). This is the path the receipt-OCR/PDF-evidence ADR's acceptance
       criterion requires — an id produced by ``evidence add`` must be accepted by
       ``aeat app ledger attach`` in the same shell session (ADR
       ``2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence``, 2026-05-14
       amendment).
    2. An imported received-invoice id in the rich :class:`InvoiceCatalogue`
       (bucket match plus :attr:`InvoiceKind.RECEIVED`), written only by the
       invoice-import flows.

    Ids minted by ``aeat app ledger invoice add`` (slim operator invoice records)
    are deliberately NOT a valid evidence reference per the ledger-invoice
    unification ADR's store split; they are refused with an instructive message.
    """
    evidence_id = command.purchase_invoice_evidence_id
    if evidence_id is None:
        return
    if _purchase_invoice_evidence_record_exists(command.bucket_id, evidence_id):
        return
    invoices = _invoice_repository(bucket_id=command.bucket_id, repository=invoice_repository).load()
    invoice = invoices.get(evidence_id)
    if invoice is None:
        raise TransactionValidationError(
            "purchase_invoice_evidence_id must reference an existing purchase invoice evidence record "
            "(register one from a PDF/image with `aeat app ledger evidence add`) or an imported "
            "received-invoice id from the invoice catalogue; ids minted by `aeat app ledger invoice add` "
            "are operator invoice records, not evidence references",
            context={"purchase_invoice_evidence_id": command.purchase_invoice_evidence_id},
        )
    if invoice.bucket_id != command.bucket_id:
        raise TransactionValidationError(
            "purchase_invoice_evidence_id must belong to the manual ledger command bucket",
            context={
                "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
                "command_bucket_id": command.bucket_id,
                "evidence_bucket_id": invoice.bucket_id or "",
            },
        )
    if invoice.kind is not InvoiceKind.RECEIVED:
        raise TransactionValidationError(
            "purchase_invoice_evidence_id must reference a received purchase invoice evidence record",
            context={
                "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
                "invoice_kind": invoice.kind.value,
            },
        )


def _verify_attachment_references(
    command: ManualLedgerTransactionCommand,
    *,
    transaction_id: str,
    attachment_store: _AttachmentStoreProtocol | None,
) -> None:
    """Verify every declared attachment manifest exists, lives in the bucket, and is link-compatible."""
    if attachment_store is None:
        from ...adapters.persistence.storage.attachment import AttachmentStore

        store: _AttachmentStoreProtocol = AttachmentStore()
    else:
        store = attachment_store
    for attachment_id in command.attachment_ids:
        _verify_single_attachment(
            attachment_id,
            command=command,
            transaction_id=transaction_id,
            store=store,
        )


def _verify_single_attachment(
    attachment_id: str,
    *,
    command: ManualLedgerTransactionCommand,
    transaction_id: str,
    store: _AttachmentStoreProtocol,
) -> None:
    try:
        attachment = store.load_manifest(attachment_id)
        store.verify_blob(attachment_id)
    except (AttachmentNotFoundError, AttachmentValidationError) as exc:
        raise TransactionValidationError(
            "attachment_ids must reference existing secure attachment manifests and blobs",
            context={"attachment_id": attachment_id},
        ) from exc
    if attachment.bucket_id != command.bucket_id:
        raise TransactionValidationError(
            "attachment_ids must belong to the manual ledger command bucket",
            context={
                "attachment_id": attachment_id,
                "command_bucket_id": command.bucket_id,
                "attachment_bucket_id": attachment.bucket_id or "",
            },
        )
    if attachment.linked_transaction_ids and transaction_id not in attachment.linked_transaction_ids:
        raise TransactionValidationError(
            "attachment_id is linked to different ledger transactions",
            context={"attachment_id": attachment_id, "transaction_id": transaction_id},
        )


def _verify_usage_ratio_reference(
    command: ManualLedgerTransactionCommand,
    *,
    usage_ratio_profile: UsageRatioProfile | None,
) -> None:
    if command.usage_ratio_id is None:
        return
    profile = usage_ratio_profile or load_usage_ratios(bucket_id=command.bucket_id)
    try:
        validate_usage_ratio_reference(
            profile,
            category_id=command.category_id,
            usage_ratio_id=command.usage_ratio_id,
            business_pct=command.business_pct,
        )
    except UsageRatioValidationError as exc:
        raise TransactionValidationError(
            str(exc),
            context={
                "bucket_id": command.bucket_id,
                "category_id": command.category_id or "",
                "usage_ratio_id": command.usage_ratio_id,
            },
        ) from exc


def _optional_decimal(value: Decimal | None) -> str:
    return "" if value is None else _decimal_to_string(value)


def _display_decimal(value: Decimal) -> str:
    return format_decimal(value, normalize=True)


def _decimal_to_string(value: Decimal) -> str:
    return format_decimal(value)


def _normalise_timestamp(value: datetime | None) -> datetime:
    timestamp = value or now()
    return coerce_utc_aware(timestamp)


def _upsert_transaction(catalogue: TransactionCatalogue, transaction: Transaction) -> TransactionCatalogue:
    updated = dict(catalogue.transactions)
    updated[transaction.transaction_id] = transaction
    return TransactionCatalogue.model_validate({"transactions": updated})


def _replace_transaction(
    catalogue: TransactionCatalogue,
    *,
    old_transaction_id: str,
    replacement: Transaction,
) -> TransactionCatalogue:
    updated = dict(catalogue.transactions)
    updated.pop(old_transaction_id, None)
    updated[replacement.transaction_id] = replacement
    return TransactionCatalogue.model_validate({"transactions": updated})


def _remove_transaction(catalogue: TransactionCatalogue, *, transaction_id: str) -> TransactionCatalogue:
    updated = dict(catalogue.transactions)
    updated.pop(transaction_id, None)
    return TransactionCatalogue.model_validate({"transactions": updated})


def _require_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction:
    transaction = catalogue.get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            f"transaction not found: {transaction_id}",
            context={"namespace": TX_BUCKET_NAMESPACE, "transaction_id": transaction_id},
        )
    return transaction


def _mutation_signature(transaction: Transaction) -> tuple[object, ...]:
    raw = transaction.raw
    return (
        raw.booked_date,
        raw.value_date,
        raw.amount,
        raw.currency,
        raw.counterparty,
        raw.description,
        transaction.direction,
        transaction.business_classification,
        transaction.business_pct,
        transaction.category_id,
        transaction.taxable_base,
        transaction.iva_rate,
        transaction.iva_amount,
        transaction.iva_category,
        transaction.counterparty_eu_member_state,
        transaction.irpf_category,
        transaction.usage_ratio_id,
        transaction.prorrata_reference,
        transaction.purchase_invoice_evidence_id,
        transaction.attachment_ids,
        transaction.notes,
        transaction.group_label,
    )


def _command_matches_current(command: ManualLedgerTransactionCommand, current: Transaction) -> bool:
    """Return True when a command would produce no observable change against the stored transaction.

    Used to detect re-affirmation patches (operator supplies the same ``business_classification``
    the record already carries) so the caller can treat them as confirmed no-ops instead of
    raising a mutation-required error.
    """
    raw = current.raw
    return (
        command.booked_date == raw.booked_date
        and command.value_date == raw.value_date
        and command.amount == raw.amount
        and command.currency == raw.currency
        and command.counterparty == raw.counterparty
        and command.description == raw.description
        and command.direction == current.direction
        and command.business_classification == current.business_classification
        and command.business_pct == current.business_pct
        and command.category_id == current.category_id
        and command.taxable_base == current.taxable_base
        and command.iva_rate == current.iva_rate
        and command.iva_amount == current.iva_amount
        and command.iva_category == current.iva_category
        and command.counterparty_eu_member_state == current.counterparty_eu_member_state
        and command.irpf_category == current.irpf_category
        and command.usage_ratio_id == current.usage_ratio_id
        and command.prorrata_reference == current.prorrata_reference
        and command.purchase_invoice_evidence_id == current.purchase_invoice_evidence_id
        # tuple[str, ...] on both sides â€” Python tuple equality is value-equal, not identity-equal.
        and command.attachment_ids == current.attachment_ids
        and command.notes == current.notes
        and command.group_label == current.group_label
    )


def _build_bucket_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_id: str,
    payload: Mapping[str, str],
    object_type: BucketEventObjectType = BucketEventObjectType.LEDGER_TRANSACTION,
) -> BucketEvent:
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
        payload=dict(payload),
    )
    return event


def _append_bucket_event(*, repository: BucketEventHistoryRepositoryProtocol, event: BucketEvent) -> None:
    repository.save(append_bucket_event(repository.load(), event))


def _append_bucket_events(*, repository: BucketEventHistoryRepositoryProtocol, events: tuple[BucketEvent, ...]) -> None:
    catalogue = repository.load()
    for event in events:
        catalogue = append_bucket_event(catalogue, event)
    repository.save(catalogue)


def _save_transaction_catalogue_and_events(
    *,
    transaction_repository: TransactionCatalogueRepository,
    # rationale: calls to_secure_object_write(), an adapter-only escape
    # hatch absent from BucketEventHistoryRepositoryProtocol.
    event_repository: BucketEventHistoryRepository,
    catalogue: TransactionCatalogue,
    events: tuple[BucketEvent, ...],
) -> None:
    event_catalogue = event_repository.load()
    for event in events:
        event_catalogue = append_bucket_event(event_catalogue, event)
    transaction_repository.save_with_secure_object_writes(
        catalogue,
        (event_repository.to_secure_object_write(event_catalogue),),
    )


def _save_transaction_catalogue_invoices_and_events(
    *,
    transaction_repository: TransactionCatalogueRepository,
    invoice_repository: InvoiceCatalogueRepository,
    # rationale: calls to_secure_object_write(), an adapter-only escape
    # hatch absent from BucketEventHistoryRepositoryProtocol.
    event_repository: BucketEventHistoryRepository,
    transaction_catalogue: TransactionCatalogue,
    invoice_catalogue: InvoiceCatalogue,
    events: tuple[BucketEvent, ...],
) -> None:
    event_catalogue = event_repository.load()
    for event in events:
        event_catalogue = append_bucket_event(event_catalogue, event)
    transaction_repository.save_with_secure_object_writes(
        transaction_catalogue,
        (
            invoice_repository.to_secure_object_write(invoice_catalogue),
            event_repository.to_secure_object_write(event_catalogue),
        ),
    )


def _primary_lineage_event_id(events: tuple[BucketEvent, ...]) -> str:
    for event in events:
        if event.object_type is BucketEventObjectType.LEDGER_TRANSACTION:
            return event.event_id
    return events[0].event_id


def _evidence_event_ids(events: tuple[BucketEvent, ...]) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for event in events:
        if event.event_type in {
            BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
            BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
        }:
            mapping[("purchase_invoice_evidence", event.object_id)] = event.event_id
        if event.event_type is BucketEventType.ATTACHMENT_LINKED:
            mapping[("attachment", event.object_id)] = event.event_id
    return mapping


def _result(
    bucket_id: str,
    transaction: Transaction,
    bucket_event_ids: tuple[str, ...],
) -> ManualLedgerTransactionResult:
    return ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id),
        transaction=transaction,
        bucket_event_ids=bucket_event_ids,
    )
