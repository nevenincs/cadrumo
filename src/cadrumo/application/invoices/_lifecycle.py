"""Application lifecycle services for the rich catalogue :class:`Invoice`.

Reads and mutates the :class:`InvoiceCatalogue` aggregate.

The reconciliation catalogue gained ``create`` and ``list`` operator verbs but
no way to inspect or delete a single record. Without a single-record read an
operator cannot confirm the long content-addressed ``invoice_id`` that
``aeat app ledger link --invoice-id`` resolves, nor see which transactions a
catalogue invoice already binds; without a delete a mistaken
``catalogue create`` is permanent. These two services close that CRUD gap over
the same sanctioned :class:`InvoiceCatalogueRepository` write path
(``aeat-architecture-boundaries``). These verbs are the
operator's single-record surface over the canonical aggregate; an earlier form
of this docstring justified them as "keeping the slim-vs-rich split intact",
which is a rationale the canonical-structure work removes -- the split is being
retired, and these verbs survive it as the surviving store's own CRUD.

:func:`resolve_catalogue_invoice` resolves a full id or an unambiguous prefix
to one :class:`Invoice`. :func:`remove_catalogue_invoice` deletes one record,
refusing an invoice that still carries ``linked_transaction_ids`` so the
bidirectional link recorded on the transaction side is never silently orphaned
into a one-sided inconsistency (``verify_link_consistency``).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core.aggregation import IntracomOperationType
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time import now
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices.enums import InvoiceClass, PaymentStatus
from ...domain.invoices.errors import InvoiceNotFoundError, InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceCatalogue
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.schema import IvaCategory
from ._catalogue_mutation import mutate_catalogue


class CatalogueInvoiceRemoveResult(BaseModel):
    """Result of deleting one rich catalogue invoice."""

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    catalogue: InvoiceCatalogue


def resolve_catalogue_invoice(catalogue: InvoiceCatalogue, invoice_id: str) -> Invoice:
    """Return one :class:`InvoiceCatalogue` invoice by full id or unambiguous prefix.

    A catalogue invoice carries a long content-addressed id; operators rarely
    type it in full. An exact match wins outright. Otherwise a case-sensitive
    prefix is accepted only when it is unambiguous: a prefix that matches more
    than one invoice is refused with the candidate set named, never silently
    resolved to the first hit.

    Raises:
        InvoiceNotFoundError: when no invoice matches the id or prefix.
        InvoiceValidationError: when a prefix matches more than one invoice.

    Returns:
        The resolved :class:`Invoice`.
    """
    trimmed = invoice_id.strip()
    if not trimmed:
        raise InvoiceNotFoundError(
            translated_message="application.invoices.lifecycle.errors.invoice_id_required",
        )
    exact = catalogue.get(trimmed)
    if exact is not None:
        return exact
    matches = tuple(invoice for invoice in catalogue.values() if invoice.invoice_id.startswith(trimmed))
    if not matches:
        raise InvoiceNotFoundError(
            translated_message="application.invoices.lifecycle.errors.invoice_not_found",
            context={"invoice_id": trimmed},
        )
    if len(matches) > 1:
        candidates = ", ".join(invoice.invoice_id for invoice in matches)
        raise InvoiceValidationError(
            translated_message="application.invoices.lifecycle.errors.ambiguous_invoice_prefix",
            context={"invoice_id": trimmed, "candidates": candidates},
        )
    return next(iter(matches))


def resolve_catalogue_invoice_from_repository(
    *,
    bucket_id: str,
    invoice_id: str,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> Invoice:
    """Load the catalogue and resolve one invoice by id or unambiguous prefix.

    Returns:
        The resolved :class:`Invoice`.
    """
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    return resolve_catalogue_invoice(repo.load(), invoice_id)


def remove_catalogue_invoice(
    *,
    bucket_id: str,
    invoice_id: str,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> CatalogueInvoiceRemoveResult:
    """Delete one rich catalogue invoice and return the updated catalogue.

    The id is resolved by full match or unambiguous prefix. An invoice that
    still carries ``linked_transaction_ids`` is refused: deleting it from the
    catalogue alone would leave the transaction side citing a vanished invoice
    — a one-sided link ``verify_link_consistency`` flags. The operator must
    unlink first. The write rides the sanctioned
    :class:`InvoiceCatalogueRepository`; no parallel write path is introduced.
    """
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    resolved: list[Invoice] = []

    def _remove(catalogue: InvoiceCatalogue) -> InvoiceCatalogue:
        """Drop the resolved invoice, refusing one that still carries links."""
        invoice = resolve_catalogue_invoice(catalogue, invoice_id)
        if invoice.linked_transaction_ids:
            linked = ", ".join(invoice.linked_transaction_ids)
            raise InvoiceValidationError(
                translated_message="application.invoices.lifecycle.errors.remove_linked_invoice",
                context={"invoice_id": invoice.invoice_id, "linked_transaction_ids": linked},
            )
        resolved.clear()
        resolved.append(invoice)
        remaining = {key: value for key, value in catalogue.invoices.items() if key != invoice.invoice_id}
        return InvoiceCatalogue.model_validate({"invoices": remaining})

    # Guarded, because removing ONE invoice rewrites the whole singleton row: an
    # invoice created while this removal was in flight would be discarded by it,
    # silently and for an operator who was only deleting something else. The
    # resolution and the linked-transaction refusal run inside the unit of work
    # so a retry re-judges them against the catalogue the write lands on -- a
    # prefix that was unambiguous a moment ago may not be after a concurrent
    # create, and refusing then is correct where deleting the wrong invoice is
    # not.
    new_catalogue = mutate_catalogue(repo, _remove)
    return CatalogueInvoiceRemoveResult(invoice=resolved[0], catalogue=new_catalogue)


class CatalogueInvoicePatch(BaseModel):
    """The fields of a persisted canonical invoice an operator may correct.

    Deliberately EXCLUDES every field the invoice id is derived from -- kind,
    invoice number, issue date, counterparty tax id, currency and the totals.
    That exclusion is structural rather than a runtime refusal: a patch cannot
    even express an identity change, so there is no path where one is attempted
    and silently produces a record under a different id.

    The reason is that the canonical id is CONTENT-ADDRESSED. Changing any of
    those fields does not correct the record, it describes a different invoice,
    and rewriting it in place would leave every transaction already linked to
    the old id pointing at something that no longer exists. The slim store this
    replaces had no such constraint because its id was independent of content;
    this is the narrowing that content-addressing buys, and it is stated in the
    update verb's refusal rather than left for an operator to discover.

    An operator who genuinely must change an identity field removes the record
    and creates it again -- which the remove verb already guards, refusing to
    delete an invoice that still carries links.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty_name: str | None = None
    counterparty_country: str | None = None
    notes: str | None = None
    payment_status: PaymentStatus | None = None
    iva_category: IvaCategory | None = None
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    retention_rate: Decimal | None = None
    retention_amount: Decimal | None = None
    series: str | None = None
    invoice_class: InvoiceClass | None = None
    rectifies_invoice_number: str | None = None
    payment_id: str | None = None


class CatalogueInvoiceUpdateResult(BaseModel):
    """Result of correcting one rich catalogue invoice."""

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    catalogue: InvoiceCatalogue
    bucket_event_ids: tuple[str, ...] = ()


def update_catalogue_invoice(
    *,
    bucket_id: str,
    invoice_id: str,
    patch: CatalogueInvoicePatch,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
    event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
    actor: str = "cli",
) -> CatalogueInvoiceUpdateResult:
    """Apply a correction to one persisted canonical invoice.

    Only fields present on the patch are changed; an omitted field keeps its
    stored value, so a correction never has to restate the whole record. The
    identity fields are absent from the patch model entirely, so the record's
    ``invoice_id`` is stable across an update by construction and every
    transaction already linked to it stays bound.

    ``linked_transaction_ids`` is carried forward explicitly rather than being
    left to survive by accident: it is the reason this aggregate is the
    reconciliation authority, and an update that dropped it would sever the
    bidirectional link without the operator asking for it.

    The corrected record is re-validated in full, so a patch that would break
    an invariant -- a retención above its base, a counterparty country that no
    longer matches the tax id -- refuses rather than persisting an inconsistent
    invoice. The write rides the sanctioned
    :class:`InvoiceCatalogueRepository`; no parallel write path is introduced.

    Args:
        bucket_id: Profile bucket whose encrypted catalogue holds the record.
        invoice_id: Full id or an unambiguous prefix of the invoice to correct.
        patch: The fields to change; omitted fields are left as stored.
        repository: Optional injected catalogue repository (testing seam).
        event_repository: Optional injected bucket-event repository.
        occurred_at: Event timestamp; defaults to now.
        actor: Who performed the correction, recorded on the event.

    Returns:
        The corrected invoice, the updated catalogue, and the emitted event id.

    Raises:
        InvoiceNotFoundError: No invoice matches ``invoice_id``.
        InvoiceValidationError: The patch is empty, or the corrected record
            would violate an invoice invariant.
    """
    from ._creation import emit_catalogue_invoice_event

    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    written: list[Invoice] = []

    def _apply(catalogue: InvoiceCatalogue) -> InvoiceCatalogue:
        """Re-resolve, re-patch and re-validate against the catalogue being written."""
        existing = resolve_catalogue_invoice(catalogue, invoice_id)

        changes = patch.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            raise InvoiceValidationError(
                translated_message="application.invoices.lifecycle.errors.empty_invoice_patch",
                context={"invoice_id": existing.invoice_id},
            )

        payload = existing.model_dump()
        payload.update(changes)
        # Carried explicitly, not by accident: the links are why this aggregate
        # is the reconciliation authority, and an update that dropped them would
        # sever a bidirectional binding the operator never asked to break.
        payload["linked_transaction_ids"] = existing.linked_transaction_ids
        payload["updated_at"] = occurred_at or now()
        corrected = Invoice.model_validate(payload)

        written.clear()
        written.append(corrected)
        updated = dict(catalogue.invoices)
        updated[corrected.invoice_id] = corrected
        return InvoiceCatalogue.model_validate({"invoices": updated})

    # Guarded: correcting one invoice rewrites the whole singleton row, so an
    # invoice created in the interim would be discarded by the correction. The
    # patch is re-applied to the CURRENT stored record on a retry rather than to
    # the one first read, which matters because the correction is a merge onto
    # stored values -- replaying a merge computed against a superseded record
    # would silently revert whatever changed in between.
    new_catalogue = mutate_catalogue(repo, _apply)
    corrected = written[0]
    event_ids = emit_catalogue_invoice_event(
        invoice=corrected,
        bucket_id=bucket_id,
        slot=1,
        event_repository=event_repository,
        occurred_at=occurred_at or now(),
        actor=actor,
    )
    return CatalogueInvoiceUpdateResult(
        invoice=corrected,
        catalogue=new_catalogue,
        bucket_event_ids=event_ids,
    )


__all__ = [
    "CatalogueInvoicePatch",
    "CatalogueInvoiceRemoveResult",
    "CatalogueInvoiceUpdateResult",
    "remove_catalogue_invoice",
    "resolve_catalogue_invoice",
    "resolve_catalogue_invoice_from_repository",
    "update_catalogue_invoice",
]
