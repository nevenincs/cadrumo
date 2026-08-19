"""Shared ledger action helpers for repositories, events, and guards.

This module normalizes concrete :class:`TransactionCatalogueRepository`,
:class:`InvoiceCatalogueRepository`, and :class:`BucketEventHistoryRepository`
instances; builds :class:`~cadrumo.domain.buckets.BucketEvent` audit entries;
mutates :class:`TransactionCatalogue` and :class:`InvoiceCatalogue` snapshots
atomically; and verifies evidence, attachment, usage-ratio, and
finalized-modelo blockers for the public ledger action services.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from ...core.decimal import format_decimal
from ...core.external_constants import CLASSIFIED_BY_AUTO, CLASSIFIED_BY_MANUAL
from ...core.time import now

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectWrite

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.profile.usage_ratios import load_usage_ratios
from ...adapters.persistence.storage import TRANSACTION_CATALOGUE_NAMESPACE
from ...core.time import coerce_utc_aware
from ...domain.attachments import AttachmentNotFoundError, AttachmentValidationError
from ...domain.attachments import AttachmentStoreProtocol as _AttachmentStoreProtocol
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
    emit_bucket_events,
)
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepositoryProtocol
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.transactions import (
    BucketTransactionRef,
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepositoryProtocol,
    TransactionNotFoundError,
    TransactionValidationError,
)
from ...domain.usage_ratios import (
    UsageRatioProfile,
    UsageRatioValidationError,
    validate_usage_ratio_reference,
)
from ._evidence import PurchaseInvoiceEvidence
from ._evidence_reference import (
    EvidenceReferenceOutcome,
    classify_evidence_reference,
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
    from ...adapters.persistence.storage import secure_object_repository_for_bucket

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
    patch but explicitly nulled - the patch contract forbids resetting a
    required value to None. Generic in ``T`` so the caller's field type
    flows through to the assignment site (type checkers see the concrete
    type at the use point, not ``object``).
    """
    if field not in patch_fields:
        return fallback
    value = getattr(patch, field)
    if value is None:
        raise TransactionValidationError(f"manual ledger patch {field} must not be null")
    return _typed_patch_value(patch, field, value, fallback)


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
    return _typed_patch_value(patch, field, getattr(patch, field), fallback)


def _typed_patch_value[T](patch: ManualLedgerTransactionPatch, field: str, value: object, expected: T) -> T:
    """Validate a dynamic patch field through its declared Pydantic type."""
    adapter: TypeAdapter[T] = TypeAdapter(ManualLedgerTransactionPatch.model_fields[field].annotation)
    return adapter.validate_python(value)


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
    (aeat-ledger-contract).
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
    (the load-once half of the ``bulk_classify_from_csv`` batching contract).
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


_EVIDENCE_MUTATION_FIELDS: frozenset[str] = frozenset(
    {"purchase_invoice_evidence_id", "attachment_ids"},
)


def _is_evidence_only_command(command: ManualLedgerTransactionCommand, current: Transaction) -> bool:
    """Return whether ``command`` adds evidence provenance and changes nothing else.

    An evidence-only mutation is exempt from the finalized-modelo write guard,
    because it cannot disturb any finalized revision that cites the row. Three
    independent project contracts establish that:

    * :func:`~cadrumo.domain.transactions.derive_transaction_id` hashes the
      provider identity, effective value date, amount, and narrative only, so an
      evidence-only edit re-derives the SAME id. A finalized revision's
      ``source_transaction_ids`` citation therefore keeps resolving.
    * The ledger filing snapshot's fingerprint field set (the canonical
      "tax facts" of a row) excludes both evidence fields, so ``row_fingerprint``
      and the revision's ``snapshot_fingerprint`` are unchanged and the revision's
      :class:`LedgerFilingSnapshot` still reconciles against the live catalogue.
    * A finalized revision's casilla values and bundled ledger evidence are frozen
      persisted snapshots; this write touches the transaction catalogue alone.

    The exemption is deliberately the narrowest that unblocks the operator: it
    requires at least one evidence field to differ AND every other persisted
    field to match, so a value-affecting edit smuggled alongside an attachment
    still meets the guard. Adding evidence DOES change what a *later*
    recalculation would compute (an incoming row with purchase evidence becomes a
    Renta refund, and a resolved invoice's base/IVA override the row's own), which
    is why the caller reports the cited revisions as stale rather than silently
    accepting the write.
    """
    command_fields = _command_idempotency_fields(command)
    current_fields = _transaction_idempotency_fields(current)
    differing = {name for name, value in command_fields.items() if current_fields[name] != value}
    return bool(differing) and differing <= _EVIDENCE_MUTATION_FIELDS


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


def resolve_attachment_store(
    attachment_store: _AttachmentStoreProtocol | None,
) -> _AttachmentStoreProtocol:
    """Resolve the shared attachment-store port for ledger action helpers.

    The concrete fallback belongs to the persistence adapter. Keeping this
    construction helper with the other shared ledger action infrastructure
    prevents individual action modules from each reaching into storage.
    """
    from ...adapters.persistence.storage import resolve_attachment_store

    return resolve_attachment_store(attachment_store)


def purchase_invoice_evidence_records(bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
    """Return the bucket's registered ``PurchaseInvoiceEvidence`` records.

    Reads the bucket-scoped encrypted purchase-invoice evidence store written by
    ``aeat app ledger evidence add``, distinct from the rich
    :class:`InvoiceCatalogue` written by invoice-import flows. Local imports mirror
    this module's existing deferred-import style.
    """
    from ...adapters.persistence.storage import secure_object_repository_for_bucket
    from ...core.config import load_settings
    from ._evidence import PurchaseInvoiceEvidenceRepository

    repository = PurchaseInvoiceEvidenceRepository(
        objects=secure_object_repository_for_bucket(bucket_id, load_settings()),
    )
    document = repository.load(bucket_id)
    return () if document is None else document.records


def _verify_purchase_invoice_evidence(
    command: ManualLedgerTransactionCommand,
    *,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> None:
    """Refuse a purchase-invoice evidence reference that no id space accepts.

    The write gate over :func:`classify_evidence_reference`, which owns the
    definition of the two id spaces, their consultation order, and the
    bucket-ownership and ``RECEIVED``-kind policy. This function only turns an
    unacceptable outcome into the operator-facing refusal; it decides nothing about
    which space an id belongs to, so it cannot drift from the other consumers of the
    same field.
    """
    evidence_id = command.purchase_invoice_evidence_id
    if evidence_id is None:
        return
    reference = classify_evidence_reference(
        evidence_id,
        bucket_id=command.bucket_id,
        evidence_records=purchase_invoice_evidence_records(command.bucket_id),
        invoices=_invoice_repository(bucket_id=command.bucket_id, repository=invoice_repository).load(),
    )
    if reference.is_acceptable:
        return
    if reference.outcome is EvidenceReferenceOutcome.UNRESOLVED:
        raise TransactionValidationError(
            "purchase_invoice_evidence_id must reference an existing purchase invoice evidence record "
            "(register one from a PDF/image with `aeat app ledger evidence add`) or an imported "
            "received-invoice id from the invoice catalogue; ids minted by `aeat app ledger invoice add` "
            "are operator invoice records, not evidence references",
            context={"purchase_invoice_evidence_id": evidence_id},
        )
    invoice = reference.invoice
    assert invoice is not None  # every remaining outcome carries its catalogue invoice
    if reference.outcome is EvidenceReferenceOutcome.INVOICE_OUTSIDE_BUCKET:
        raise TransactionValidationError(
            "purchase_invoice_evidence_id must belong to the manual ledger command bucket",
            context={
                "purchase_invoice_evidence_id": evidence_id,
                "command_bucket_id": command.bucket_id,
                "evidence_bucket_id": invoice.bucket_id or "",
            },
        )
    raise TransactionValidationError(
        "purchase_invoice_evidence_id must reference a received purchase invoice evidence record",
        context={
            "purchase_invoice_evidence_id": evidence_id,
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
    store = resolve_attachment_store(attachment_store)
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
            context={"namespace": TRANSACTION_CATALOGUE_NAMESPACE.namespace, "transaction_id": transaction_id},
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
        transaction.source_jurisdiction,
        transaction.business_classification,
        transaction.business_pct,
        transaction.category_id,
        transaction.taxable_base,
        transaction.iva_rate,
        transaction.iva_amount,
        transaction.iva_category,
        transaction.counterparty_country,
        transaction.counterparty_identification_state,
        transaction.irpf_category,
        transaction.m210_income_classification,
        transaction.usage_ratio_id,
        transaction.prorrata_reference,
        transaction.art_104_tres_exclusion,
        transaction.input_classification,
        transaction.prorrata_sector_id,
        transaction.purchase_invoice_evidence_id,
        transaction.attachment_ids,
        transaction.notes,
        transaction.group_label,
    )


def _persisted_classified_by(command: ManualLedgerTransactionCommand) -> str:
    """Return the ``classified_by`` value a write of ``command`` would persist.

    Mirrors the stamp in ``_transaction_from_command``: a command that carries a real
    classification stamps ``classified_by_override or CLASSIFIED_BY_MANUAL``; a
    still-unprocessed command leaves the field unstamped, so the rebuilt transaction
    takes the ``Transaction.classified_by`` model default. Projecting the *effective*
    value keeps the comparison apples-to-apples: a retry that omits the override on a
    row already stamped ``manual`` still matches, while a retry that changes the
    override (``rule:a`` -> ``rule:b``) is correctly seen as different content.
    """
    if command.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return CLASSIFIED_BY_AUTO
    return command.classified_by_override or CLASSIFIED_BY_MANUAL


def _command_idempotency_fields(command: ManualLedgerTransactionCommand) -> dict[str, object]:
    """Project every persisted field of ``command`` into a name-keyed mapping.

    The full-field idempotency contract (``aeat-cli-contract``)
    requires the no-op match to compare EVERY persisted field. Keeping the field set as one
    ordered mapping makes a new model field omitted here a single greppable site, paired with
    :func:`_transaction_idempotency_fields` key-for-key.

    The mapping is the single source for both consumers:
    :func:`_command_idempotency_projection` folds it to the positional tuple the
    idempotency guard compares, and :func:`_is_evidence_only_command` reads it by
    name to isolate which fields a command would actually change.

    Four command fields are deliberately excluded, because none of them is content a
    retry could silently drop:

    - ``bucket_id`` scopes the lookup rather than describing the movement; the stored
      row is only ever found by scanning that bucket's own catalogue, so a differing
      bucket yields a different row, not a false match.
    - ``actor`` and ``source_command`` are provenance of the invocation, not of the
      movement. They are stamped once at creation (``created_by`` / ``source_command``)
      and deliberately NOT re-stamped by a retry, so folding them in would turn a
      benign retry from a different entry point into a spurious conflict.
    - ``idempotency_key`` is the match key itself: the guard has already resolved the
      stored row by the clock-free provider id derived from it, so both sides are equal
      by construction.

    ``classified_by_override`` is NOT excluded: it is persisted content
    (``Transaction.classified_by``) and is projected through
    :func:`_persisted_classified_by`.
    """
    return {
        "booked_date": command.booked_date,
        "value_date": command.value_date,
        "amount": command.amount,
        "currency": command.currency,
        "counterparty": command.counterparty,
        "description": command.description,
        "direction": command.direction,
        "business_classification": command.business_classification,
        "business_pct": command.business_pct,
        "category_id": command.category_id,
        "taxable_base": command.taxable_base,
        "iva_rate": command.iva_rate,
        "iva_amount": command.iva_amount,
        "iva_category": command.iva_category,
        "deduction_fact_kind": command.deduction_fact_kind,
        "recargo_amount": command.recargo_amount,
        "source_jurisdiction": command.source_jurisdiction,
        "counterparty_country": command.counterparty_country,
        "counterparty_identification_state": command.counterparty_identification_state,
        "irpf_category": command.irpf_category,
        "m210_income_classification": command.m210_income_classification,
        "usage_ratio_id": command.usage_ratio_id,
        "prorrata_reference": command.prorrata_reference,
        "art_104_tres_exclusion": command.art_104_tres_exclusion,
        "input_classification": command.input_classification,
        "prorrata_sector_id": command.prorrata_sector_id,
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
        # tuple[str, ...] compared value-equal, not identity-equal, by tuple equality.
        "attachment_ids": command.attachment_ids,
        "notes": command.notes,
        "group_label": command.group_label,
        "classified_by": _persisted_classified_by(command),
    }


def _command_idempotency_projection(command: ManualLedgerTransactionCommand) -> tuple[object, ...]:
    """Fold :func:`_command_idempotency_fields` into the positional idempotency tuple."""
    return tuple(_command_idempotency_fields(command).values())


def _transaction_idempotency_fields(current: Transaction) -> dict[str, object]:
    """Project the stored transaction's persisted fields, aligned with the command mapping.

    The banking-boundary fields read from ``current.raw``; the classification and
    provenance fields read from the transaction directly — key-for-key with
    :func:`_command_idempotency_fields`. The ``classified_by`` entry holds the stored
    stamp, compared against the value a write of the command would persist
    (:func:`_persisted_classified_by`).
    """
    raw = current.raw
    return {
        "booked_date": raw.booked_date,
        "value_date": raw.value_date,
        "amount": raw.amount,
        "currency": raw.currency,
        "counterparty": raw.counterparty,
        "description": raw.description,
        "direction": current.direction,
        "business_classification": current.business_classification,
        "business_pct": current.business_pct,
        "category_id": current.category_id,
        "taxable_base": current.taxable_base,
        "iva_rate": current.iva_rate,
        "iva_amount": current.iva_amount,
        "iva_category": current.iva_category,
        "deduction_fact_kind": current.deduction_fact_kind,
        "recargo_amount": current.recargo_amount,
        "source_jurisdiction": current.source_jurisdiction,
        "counterparty_country": current.counterparty_country,
        "counterparty_identification_state": current.counterparty_identification_state,
        "irpf_category": current.irpf_category,
        "m210_income_classification": current.m210_income_classification,
        "usage_ratio_id": current.usage_ratio_id,
        "prorrata_reference": current.prorrata_reference,
        "art_104_tres_exclusion": current.art_104_tres_exclusion,
        "input_classification": current.input_classification,
        "prorrata_sector_id": current.prorrata_sector_id,
        "purchase_invoice_evidence_id": current.purchase_invoice_evidence_id,
        "attachment_ids": current.attachment_ids,
        "notes": current.notes,
        "group_label": current.group_label,
        "classified_by": current.classified_by,
    }


def _transaction_idempotency_projection(current: Transaction) -> tuple[object, ...]:
    """Fold :func:`_transaction_idempotency_fields` into the positional idempotency tuple."""
    return tuple(_transaction_idempotency_fields(current).values())


def _command_matches_current(command: ManualLedgerTransactionCommand, current: Transaction) -> bool:
    """Return True when a command would produce no observable change against the stored transaction.

    Used to detect re-affirmation patches (operator supplies the same ``business_classification``
    the record already carries) so the caller can treat them as confirmed no-ops instead of
    raising a mutation-required error.
    """
    return _command_idempotency_projection(command) == _transaction_idempotency_projection(current)


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
    """Append one event through the domain emitter rather than a local copy.

    These two helpers used to load, append and save the catalogue here. That is
    exactly what the domain emitters do, and the copies drifted the moment those
    gained a revision guard: the history is a singleton row, so a local
    load-append-save discards an event a concurrent caller wrote, and the
    content-addressed survivors leave no gap to notice it happened.
    """
    emit_bucket_events(repository=repository, events=(event,))


def _append_bucket_events(*, repository: BucketEventHistoryRepositoryProtocol, events: tuple[BucketEvent, ...]) -> None:
    """Append a batch through the domain emitter, for the reason above."""
    emit_bucket_events(repository=repository, events=events)


def _commit_with_guarded_events(
    *,
    # rationale: calls to_secure_object_write(), an adapter-only escape
    # hatch absent from BucketEventHistoryRepositoryProtocol.
    event_repository: BucketEventHistoryRepository,
    events: tuple[BucketEvent, ...],
    commit: Callable[[SecureObjectWrite], None],
    attempts: int = 4,
) -> None:
    """Commit ``commit`` with the events composed in, guarded on their revision.

    The co-commit is what these ledger writes need and what the self-committing
    domain emitter cannot give them: the audit entry has to land in the SAME
    batch as the record it describes, or a crash records a linkage that never
    happened, or lands one with nothing saying so.

    What the composition lacked was the other half. Reading the event catalogue
    and handing it straight to the batch writes back whatever revision was read,
    so an event another process appended in between is discarded -- the same
    singleton-row loss ``append_guarded`` closes for the standalone path, on the
    one shape that could not use it. Content-addressed events hide it perfectly:
    every survivor is intact and the missing one leaves no gap.

    So the write carries the revision the catalogue was READ at, and the whole
    composition is re-run against the newly-current catalogue when the substrate
    refuses it. ``commit`` is therefore called once per attempt and must be safe
    to re-run; it is, because the domain catalogues it closes over are values
    computed before this call, not reads that could go stale inside it.

    Args:
        event_repository: The bucket event-history repository.
        events: The events to append, in order.
        commit: Performs the real batch write, given the composed event write.
        attempts: Maximum reads before the contention is surfaced.

    Raises:
        SecureObjectRevisionConflictError: Contention persisted across every
            attempt. Refusing beats the silent discard this replaced.
    """
    from ...adapters.persistence.storage import SecureObjectRevisionConflictError

    last_conflict: SecureObjectRevisionConflictError | None = None
    for _attempt in range(attempts):
        event_catalogue, revision_id = event_repository.load_revisioned()
        for event in events:
            event_catalogue = append_bucket_event(event_catalogue, event)
        try:
            commit(event_repository.to_secure_object_write(event_catalogue, expected_revision_id=revision_id))
        except SecureObjectRevisionConflictError as exc:
            last_conflict = exc
            continue
        return
    if last_conflict is not None:
        raise last_conflict
    raise AssertionError("guarded event co-commit exhausted without a conflict")


def _save_transaction_catalogue_and_events(
    *,
    transaction_repository: TransactionCatalogueRepository,
    # rationale: calls to_secure_object_write(), an adapter-only escape
    # hatch absent from BucketEventHistoryRepositoryProtocol.
    event_repository: BucketEventHistoryRepository,
    catalogue: TransactionCatalogue,
    events: tuple[BucketEvent, ...],
) -> None:
    _commit_with_guarded_events(
        event_repository=event_repository,
        events=events,
        commit=lambda event_write: transaction_repository.save_with_secure_object_writes(
            catalogue,
            (event_write,),
        ),
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
    _commit_with_guarded_events(
        event_repository=event_repository,
        events=events,
        commit=lambda event_write: transaction_repository.save_with_secure_object_writes(
            transaction_catalogue,
            (
                invoice_repository.to_secure_object_write(invoice_catalogue),
                event_write,
            ),
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
    *,
    stale_finalized_revisions: tuple[LedgerRemovalBlocker, ...] = (),
) -> ManualLedgerTransactionResult:
    return ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id),
        transaction=transaction,
        bucket_event_ids=bucket_event_ids,
        stale_finalized_revisions=stale_finalized_revisions,
    )


# Public supporting contract for sibling ledger action services.
persist_bucket_event = _append_bucket_event
persist_bucket_events = _append_bucket_events
blocking_modelo_references = _blocking_modelo_references
blockers_by_source_transaction_id = _blockers_by_source_transaction_id
bucket_event_repository = _bucket_event_repository
build_bucket_event = _build_bucket_event
catalogue_modelo_source_ids = _catalogue_modelo_source_ids
command_matches_current = _command_matches_current
decimal_to_string = _decimal_to_string
display_decimal = _display_decimal
draft_revision_advisories = _draft_revision_advisories
EventSpec = _EventSpec
evidence_event_ids = _evidence_event_ids
invoice_repository = _invoice_repository
is_evidence_only_command = _is_evidence_only_command
merge_identifier_tuple = _merge_identifier_tuple
mutation_signature = _mutation_signature
normalise_attachment_patch_ids = _normalise_attachment_patch_ids
normalise_timestamp = _normalise_timestamp
optional_decimal = _optional_decimal
optional_patched = _optional_patched
primary_lineage_event_id = _primary_lineage_event_id
raise_finalized_modelo_blocked = _raise_finalized_modelo_blocked
replace_transaction = _replace_transaction
remove_transaction = _remove_transaction
require_actor = _require_actor
require_source_command = _require_source_command
require_transaction = _require_transaction
required_patched = _required_patched
result = _result
save_transaction_catalogue_and_events = _save_transaction_catalogue_and_events
save_transaction_catalogue_invoices_and_events = _save_transaction_catalogue_invoices_and_events
transaction_modelo_source_ids = _transaction_modelo_source_ids
transaction_repository = _transaction_repository
upsert_transaction = _upsert_transaction
verify_evidence_references = _verify_evidence_references
verify_usage_ratio_reference = _verify_usage_ratio_reference
