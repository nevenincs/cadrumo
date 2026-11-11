"""Application lifecycle services for the rich catalogue :class:`Invoice`.

Reads and mutates the :class:`InvoiceCatalogue` aggregate.

The reconciliation catalogue gained ``create`` and ``list`` operator verbs but
no way to inspect or delete a single record. Without a single-record read an
operator cannot confirm the long content-addressed ``invoice_id`` that
``aeat app ledger link --invoice-id`` resolves, nor see which transactions a
catalogue invoice already binds; without a delete a mistaken
``catalogue create`` is permanent. These two services close that CRUD gap over
the same application-owned catalogue lifecycle capabilities. These verbs are the
operator's single-record surface over the canonical aggregate; an earlier form
of this docstring justified them as "keeping the slim-vs-rich split intact",
which is a rationale the canonical-structure work removes -- the split is being
retired, and these verbs survive it as the surviving store's own CRUD.

:func:`resolve_catalogue_invoice` resolves a full id or an unambiguous prefix
to one :class:`Invoice`. :func:`remove_catalogue_invoice` deletes one record,
refusing an invoice that still carries ``linked_transaction_ids`` so the
bidirectional link recorded on the transaction side is never silently orphaned
into a one-sided inconsistency (``verify_link_consistency``).

A sealed revision is guarded the way the ledger guards its contributors: the
figures are frozen and verify, export and filing do not compare them again, so a
write that would move what a sealed revision read is refused at the write. Those
revisions stay exactly as filed. An edit that moves no fact the revision read
passes, as does recording a later collection on an invoice whose devengo does not
depend on it: LIVA art. 75.Uno does not date the cuota by the collection;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from ...core.aggregation import IntracomOperationType
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.enums import InvoiceClass, PaymentStatus, advance_payment_received_role
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ..aggregation.invoice_filing_fingerprint import invoice_row_fingerprint
from .catalogue_lifecycle_ports import CatalogueLifecyclePorts
from .catalogue_selection import select_catalogue_invoice_id


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
        InvoiceLookupRefusedError: when the selector is empty, absent or ambiguous.

    Returns:
        The resolved :class:`Invoice`.
    """
    return catalogue.invoices[select_catalogue_invoice_id(catalogue.invoices.keys(), invoice_id)]


def _sealed_citations(
    invoice_id: str,
    ports: CatalogueLifecyclePorts,
) -> tuple[tuple[CalculationRevision, WorkUnit], ...]:
    """Return the sealed revisions whose stored fingerprint read this invoice."""
    return tuple(
        (revision, work_unit)
        for revision, work_unit in ports.sealed_revisions.sealed_revisions()
        if revision.invoice_fingerprint is not None
        and any(row.invoice_id == invoice_id for row in revision.invoice_fingerprint.rows)
    )


def _refuse_sealed_write(invoice_id: str, citation: tuple[CalculationRevision, WorkUnit]) -> None:
    revision, work_unit = citation
    raise InvoiceValidationError(
        translated_message="application.invoices.lifecycle.errors.sealed_invoice_refused",
        context={
            "invoice_id": invoice_id,
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "revision_state": revision.state.value,
            "calculation_revision_id": revision.calculation_revision_id,
        },
    )


def _as_a_sealed_revision_read_it(existing: Invoice, corrected: Invoice) -> Invoice:
    """Leave out a collection recorded on an invoice whose devengo does not rest on it."""
    advance = advance_payment_received_role()
    if corrected.payment_status is existing.payment_status or advance in (
        existing.operation_date_role,
        corrected.operation_date_role,
    ):
        return corrected
    return corrected.model_copy(update={"payment_status": existing.payment_status})


def _require_sealed_revisions_undisturbed(
    existing: Invoice,
    corrected: Invoice,
    ports: CatalogueLifecyclePorts,
) -> None:
    candidate = _as_a_sealed_revision_read_it(existing, corrected)
    for citation in _sealed_citations(existing.invoice_id, ports):
        snapshot = citation[0].invoice_fingerprint
        version = 1 if snapshot is None else snapshot.field_set_version
        if invoice_row_fingerprint(candidate, field_set_version=version) != invoice_row_fingerprint(
            existing, field_set_version=version
        ):
            _refuse_sealed_write(existing.invoice_id, citation)


def remove_catalogue_invoice(
    *,
    bucket_id: str,
    invoice_id: str,
    ports: CatalogueLifecyclePorts,
) -> CatalogueInvoiceRemoveResult:
    """Delete one rich catalogue invoice and return the updated catalogue.

    The id is resolved by full match or unambiguous prefix. An invoice that
    still carries ``linked_transaction_ids`` is refused: deleting it from the
    catalogue alone would leave the transaction side citing a vanished invoice
    — a one-sided link ``verify_link_consistency`` flags. The operator must
    unlink first. A sealed revision that read the invoice refuses too: its figures
    would stop matching the catalogue with nothing left to say so. The write rides
    the required application-owned mutation capability; no parallel write path is
    introduced.
    """
    resolved: list[Invoice] = []

    def _remove(catalogue: InvoiceCatalogue) -> InvoiceCatalogue:
        """Drop the resolved invoice, refusing one that still carries links."""
        invoice = resolve_catalogue_invoice(catalogue, invoice_id)
        for citation in _sealed_citations(invoice.invoice_id, ports):
            _refuse_sealed_write(invoice.invoice_id, citation)
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
    new_catalogue = ports.invoice_repository.mutate(_remove)
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


def _registered_refusal(error: ValidationError) -> InvoiceValidationError | None:
    """The invoice refusal a validator raised, which the validation failure carries as its cause."""
    for detail in error.errors(include_url=False):
        raised = (detail.get("ctx") or {}).get("error")
        for candidate in (raised, getattr(raised, "__cause__", None)):
            if isinstance(candidate, InvoiceValidationError):
                return candidate
    return None


def _admitted_correction(
    existing: Invoice, patch: CatalogueInvoicePatch, ports: CatalogueLifecyclePorts, *, updated_at: datetime
) -> Invoice:
    """Patch ``existing`` and admit the corrected record, or raise the refusal a person reads.

    A rule the corrected record breaks raises its registered refusal, with the
    rule's code and words, rather than the validation failure that carries it.
    """
    changes = patch.model_dump(exclude_unset=True)
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
    payload["updated_at"] = updated_at
    try:
        corrected = Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)
    except ValidationError as error:
        refusal = _registered_refusal(error)
        if refusal is None:
            raise
        raise refusal from error
    _require_sealed_revisions_undisturbed(existing, corrected, ports)
    return corrected


def update_catalogue_invoice(
    *,
    bucket_id: str,
    invoice_id: str,
    patch: CatalogueInvoicePatch,
    ports: CatalogueLifecyclePorts,
    occurred_at: datetime | None = None,
    actor: str = "cli",
    expected_invoice: Invoice | None = None,
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
    invoice. The write rides the required application-owned mutation
    capability; no parallel write path is introduced.

    Args:
        bucket_id: Profile bucket whose encrypted catalogue holds the record.
        invoice_id: Full id or an unambiguous prefix of the invoice to correct.
        patch: The fields to change; omitted fields are left as stored.
        ports: Required read, mutation, and bucket-event capabilities.
        occurred_at: Event timestamp; defaults to now.
        actor: Who performed the correction, recorded on the event.
        expected_invoice: Optional displayed baseline; a changed record refuses inside the guarded mutation.

    Returns:
        The corrected invoice, the updated catalogue, and the emitted event id.

    Raises:
        InvoiceNotFoundError: No invoice matches ``invoice_id``.
        InvoiceValidationError: The patch is empty, the corrected record would
            violate an invoice invariant, or it would move what a sealed revision read.
    """
    from .catalogue_creation import build_catalogue_invoice_event

    written: list[Invoice] = []
    commit_time = occurred_at or now()

    target_invoice_id = resolve_catalogue_invoice(ports.invoice_repository.load(), invoice_id).invoice_id

    def _apply(catalogue: InvoiceCatalogue) -> InvoiceCatalogue:
        """Re-resolve, re-patch and re-validate against the catalogue being written."""
        existing = resolve_catalogue_invoice(catalogue, target_invoice_id)
        if expected_invoice is not None and existing != expected_invoice:
            raise InvoiceValidationError(
                "invoice changed since it was opened; reopen it before editing",
                context={"invoice_id": existing.invoice_id},
            )

        corrected = _admitted_correction(existing, patch, ports, updated_at=commit_time)

        written.clear()
        written.append(corrected)
        updated = dict(catalogue.invoices)
        updated[corrected.invoice_id] = corrected
        return InvoiceCatalogue.model_validate({"invoices": updated})

    # The event names a stable invoice identity and immutable facts, so it can
    # be derived before the guarded mutation.  The committer re-applies the
    # patch to the current singleton after a conflict and writes both catalogue
    # and audit history in one batch.
    existing = resolve_catalogue_invoice(ports.invoice_repository.load(), target_invoice_id)
    event = build_catalogue_invoice_event(
        invoice=existing,
        bucket_id=bucket_id,
        slot=1,
        occurred_at=commit_time,
        actor=actor,
    )
    new_catalogue = ports.audit_commit.mutate_with_event(_apply, event)
    corrected = written[0]
    return CatalogueInvoiceUpdateResult(
        invoice=corrected,
        catalogue=new_catalogue,
        bucket_event_ids=(event.event_id,),
    )


__all__ = [
    "CatalogueInvoicePatch",
    "CatalogueInvoiceRemoveResult",
    "CatalogueInvoiceUpdateResult",
    "remove_catalogue_invoice",
    "resolve_catalogue_invoice",
    "update_catalogue_invoice",
]
