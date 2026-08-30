"""Application service for creating one rich catalogue :class:`Invoice`.

The operator-facing ``aeat app ledger invoice add`` verb mints a **linkable**
invoice directly: the :class:`~domain.invoices.Invoice` in the
:class:`~domain.invoices.InvoiceCatalogue` is the only invoice record, and it
carries
``linked_transaction_ids`` and is the reconciliation authority ``link`` targets.

:func:`create_catalogue_invoice` builds a strict :class:`Invoice` from
operator-friendly fields and persists it through the sanctioned
:class:`InvoiceCatalogueRepository` (no parallel write path). A caller that
supplies no line set gets a single line synthesised from the taxable base and
IVA rate; a caller that supplies one gets those lines, which is how an invoice
carrying several IVA rates is expressed.

This is the ONE line-synthesis site. The bulk import path does not carry its
own: it routes every row through :func:`build_catalogue_invoice`, so the two
transports cannot disagree about the shape they produce. Its row model does
still admit only one rate per row, which is a limit of that file format rather
than a second synthesis to keep in step. The returned :attr:`Invoice.invoice_id` is the
content-addressed hash ``link --invoice-id`` resolves, closing the documented
add->link gap without collapsing the two stores.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.fx import default_ecb_rate_provider
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core import IntracomOperationType
from ...core.money import round_to_cents
from ...core.parsing import normalise_iso_4217_currency
from ...core.time import now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import emit_bucket_event
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.currency.service import ExchangeRateProvider, resolve_fx_conversion_stamp
from ...domain.invoices.enums import InvoiceClass, InvoiceOperationDateRole, IvaRate, PaymentStatus, numeric_iva_rate_slots
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva import InvoiceKind, IvaCategory
from ._catalogue_mutation import mutate_catalogue


class CatalogueInvoiceCreateResult(BaseModel):
    """Result of persisting one rich catalogue invoice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice: Invoice
    catalogue: InvoiceCatalogue
    bucket_event_ids: tuple[str, ...] = ()


# An invoice's DIRECTION decides which lifecycle event it emits, so the
# canonical store speaks the same event vocabulary the slim store did rather
# than inventing a second one. Issued invoices are collectible (a customer owes
# us); received ones are payable (we owe a vendor).
_EVENT_OBJECT_BY_KIND: dict[InvoiceKind, BucketEventObjectType] = {
    InvoiceKind.ISSUED: BucketEventObjectType.COLLECTIBLE_INVOICE,
    InvoiceKind.RECEIVED: BucketEventObjectType.PAYABLE_INVOICE,
}

# (created, updated, removed) per direction, mirroring the triple the slim
# store declared. Kept as one table so a caller cannot pair a created event
# with a removed object type, and so the three verbs stay visibly related.
_EVENT_TYPES_BY_KIND: dict[InvoiceKind, tuple[BucketEventType, BucketEventType, BucketEventType]] = {
    InvoiceKind.ISSUED: (
        BucketEventType.COLLECTIBLE_INVOICE_CREATED,
        BucketEventType.COLLECTIBLE_INVOICE_UPDATED,
        BucketEventType.COLLECTIBLE_INVOICE_REMOVED,
    ),
    InvoiceKind.RECEIVED: (
        BucketEventType.PAYABLE_INVOICE_CREATED,
        BucketEventType.PAYABLE_INVOICE_UPDATED,
        BucketEventType.PAYABLE_INVOICE_REMOVED,
    ),
}

_INVOICE_EVENT_PAYLOAD_VERSION = 1


def emit_catalogue_invoice_event(
    *,
    invoice: Invoice,
    bucket_id: str,
    slot: int,
    event_repository: BucketEventHistoryRepositoryProtocol | None,
    occurred_at: datetime,
    actor: str,
) -> tuple[str, ...]:
    """Append the creation event for a canonically-written invoice.

    The canonical write paths emitted NO bucket event of any kind, while the
    slim store emitted six types and returned their ids to the operator. So
    repointing the operator's verbs onto this store would have dropped the
    invoice audit trail and the event-ids field in the same change -- a
    capability loss with no replacement, which is why it blocked the fold.

    The event type is chosen by direction so this store speaks the vocabulary
    that already exists rather than minting a parallel one; the six members
    outlive the slim store that used to be their only emitter.
    """
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...adapters.persistence.storage import secure_object_repository_for_bucket

    repository = event_repository or BucketEventHistoryRepository(
        objects=secure_object_repository_for_bucket(bucket_id),
    )
    event_type = _EVENT_TYPES_BY_KIND[invoice.kind][slot]
    object_type = _EVENT_OBJECT_BY_KIND[invoice.kind]
    event = emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=invoice.invoice_id,
        payload={
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.issued_at.isoformat(),
            "counterparty_nif": invoice.counterparty_tax_id or "",
        },
        payload_version=_INVOICE_EVENT_PAYLOAD_VERSION,
    )
    return (event.event_id,)


#: The one IVA category that does NOT settle its Modelo 349 clave.
#:
#: Every other intra-community category determines its clave outright: the two
#: service categories give S and I, and triangulation gives T. An entrega
#: intracomunitaria de bienes does not, because claves M and H -- supplies
#: following an exempt importation, LIVA art. 27.12 -- share this exact
#: category with the ordinary clave E. No category predicate can separate the
#: three, so the fact lives with the operator or nowhere.
_CATEGORY_NEEDING_AN_EXPLICIT_CLAVE: Final = IvaCategory.INTRA_COMMUNITY_SUPPLY


def _require_operation_type_where_the_category_cannot_settle_it(
    *,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
) -> None:
    """Refuse an entrega intracomunitaria that does not state its clave.

    Closing the ambiguity HERE rather than screening it at calculate time is
    the whole point. At creation the operator is looking at the document and
    knows whether this supply followed an exempt importation; by the time the
    Modelo 349 resolver runs, nobody does, and the best it can offer is to
    infer E and disclose that it guessed. A fact that only one party holds
    should be captured from that party, not reconstructed downstream from
    evidence that cannot carry it.

    Scoped to the single category where the ambiguity is real. Demanding an
    operation type for the service or triangulation categories would make the
    operator restate a clave their category already determines, and a
    redundant required field is how a boundary check earns the reputation that
    gets it removed.

    Raises:
        InvoiceValidationError: When an ``INTRA_COMMUNITY_SUPPLY`` invoice
            carries no ``operation_type``, naming the three candidate claves so
            the refusal tells the operator what to state rather than only that
            something is missing.
    """
    if iva_category is not _CATEGORY_NEEDING_AN_EXPLICIT_CLAVE or operation_type is not None:
        return
    raise InvoiceValidationError(
        "an intra-community supply must state its Modelo 349 operation type: the category alone "
        "cannot distinguish an ordinary entrega intracomunitaria (clave E) from a supply following "
        "an exempt importation (clave M, or H when made by a fiscal representative), because all "
        "three carry this same IVA category",
        translated_message="application.invoices.creation.errors.intracom_operation_type_required",
        context={"iva_category": _CATEGORY_NEEDING_AN_EXPLICIT_CLAVE.value},
    )


def resolve_iva_rate_slot(iva_rate: Decimal | None) -> IvaRate:
    """Map a percentage to its rate slot, refusing one the taxonomy does not carry.

    ``None`` resolves to :attr:`IvaRate.EXEMPT` so a base-only invoice with no
    cuota is accepted. A percentage outside the closed slot taxonomy is refused
    with the accepted set named, never a bare "value invalid".

    Public because the percentage does not only come from an operator: the
    ledger's evidence-confirm path reads it off the document itself and needs
    the SAME refusal. Two resolvers previously split that job between them and
    disagreed about the outcome -- one raised a localised error naming the
    accepted set, the other a raw English one -- so which message an operator
    saw depended on whether their document happened to print a cuota.
    """
    if iva_rate is None:
        return IvaRate.EXEMPT
    slots = numeric_iva_rate_slots()
    slot = slots.get(iva_rate)
    if slot is None:
        accepted = ", ".join(format(rate, "f") for rate in sorted(slots))
        raise InvoiceValidationError(
            "iva_rate is not a recognised IVA percentage",
            translated_message="application.invoices.creation.errors.unsupported_iva_rate",
            context={"iva_rate": format(iva_rate, "f"), "accepted": accepted},
        )
    return slot


def _resolve_invoice_line_totals(
    *,
    taxable_base: Decimal,
    lines: Sequence[InvoiceLine] | None,
    invoice_number: str,
    rate_slot: IvaRate,
    iva_percentage: Decimal | None,
) -> tuple[Decimal, Decimal, object]:
    """Return the authoritative line payload and totals for one invoice.

    Supplied lines own their own amounts and must agree with the declared base;
    otherwise this is the sole synthesis of the one operator-supplied rate line.
    """
    if lines:
        if not all(isinstance(item, InvoiceLine) for item in lines):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise InvoiceValidationError("lines must be InvoiceLine records")
        base_total = round_to_cents(sum((item.subtotal for item in lines), Decimal("0")))
        iva_total = round_to_cents(sum((item.iva_amount for item in lines), Decimal("0")))
        declared_base = round_to_cents(taxable_base)
        if declared_base != base_total:
            raise InvoiceValidationError(
                f"taxable_base {declared_base} does not equal the summed line subtotals {base_total}",
            )
        return base_total, iva_total, [item.model_dump(mode="json") for item in lines]

    base_total = round_to_cents(taxable_base)
    iva_amount = Decimal("0") if iva_percentage is None else round_to_cents(taxable_base * iva_percentage)
    return (
        base_total,
        iva_amount,
        [
            {
                "description": invoice_number or "Invoice",
                "quantity": "1",
                "unit_price": format(base_total, "f"),
                "subtotal": format(base_total, "f"),
                "iva_rate": rate_slot.value,
                "iva_amount": format(iva_amount, "f"),
            },
        ],
    )


def _apply_operator_asserted_invoice_facts(
    invoice_payload: dict[str, object],
    *,
    series: str | None,
    rectifies_invoice_number: str | None,
    recargo_amount: Decimal | None,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    operation_date: date | None,
    retention_rate: Decimal | None,
    retention_amount: Decimal | None,
) -> None:
    if series is not None:
        invoice_payload["series"] = series
    if rectifies_invoice_number is not None:
        invoice_payload["rectifies_invoice_number"] = rectifies_invoice_number
    if recargo_amount is not None:
        invoice_payload["recargo_amount"] = format(recargo_amount, "f")
    if iva_category is not None:
        invoice_payload["iva_category"] = iva_category.value
    _require_operation_type_where_the_category_cannot_settle_it(
        iva_category=iva_category,
        operation_type=operation_type,
    )
    if operation_type is not None:
        invoice_payload["operation_type"] = operation_type.value
    if operation_date is not None:
        # LIVA art. 75.Uno: the general-regime devengo. The art. 75.Dos
        # advance-payment role carries its own preconditions (money actually
        # received, art. 25 entregas excluded) and is not something this
        # operator-supplied date can assert, so it is not offered here.
        invoice_payload["operation_date"] = operation_date.isoformat()
        invoice_payload["operation_date_role"] = InvoiceOperationDateRole.OPERATION_PERFORMED.value
    if retention_rate is not None:
        invoice_payload["retention_rate"] = format(retention_rate, "f")
    if retention_amount is not None:
        invoice_payload["retention_amount"] = format(retention_amount, "f")


def _apply_fx_conversion_stamp(
    invoice_payload: dict[str, object],
    *,
    currency: str,
    issued_at: date,
    rate_provider: ExchangeRateProvider | None,
) -> None:
    fx_stamp = resolve_fx_conversion_stamp(
        currency=currency,
        on_date=issued_at,
        rate_provider=rate_provider or default_ecb_rate_provider(),
    )
    if fx_stamp is not None:
        invoice_payload["fx_rate"] = format(fx_stamp.rate, "f")
        invoice_payload["fx_rate_date"] = fx_stamp.rate_date.isoformat()
        invoice_payload["fx_rate_source"] = fx_stamp.source


def build_catalogue_invoice(
    *,
    bucket_id: str | None,
    kind: InvoiceKind,
    counterparty_name: str,
    counterparty_tax_id: str | None,
    counterparty_country: str,
    invoice_number: str,
    issued_at: date,
    taxable_base: Decimal,
    iva_rate: Decimal | None,
    currency: str,
    payment_status: PaymentStatus = PaymentStatus.PENDING,
    notes: str = "",
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: date | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    invoice_class: InvoiceClass = InvoiceClass.ORDINARIA,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    recargo_amount: Decimal | None = None,
    lines: Sequence[InvoiceLine] | None = None,
    rate_provider: ExchangeRateProvider | None = None,
) -> Invoice:
    """Return a strict rich :class:`Invoice` from operator-supplied fields.

    When ``lines`` is omitted a single line item is synthesised from
    ``taxable_base`` and the resolved IVA rate slot, and the invoice totals are
    derived from that line so the :class:`Invoice` arithmetic invariants hold.
    The returned invoice carries no linked transactions yet — ``link
    --invoice-id`` populates them later.

    When ``lines`` IS supplied they are authoritative and the totals are summed
    from them, which is what lets one invoice carry several IVA rates. A real
    invoice mixing 21% and 10% lines is not exotic — collapsing it to one line
    at a single rate reports the right grand total while attributing the cuota
    to the wrong rate, and the per-rate breakdown is precisely what the IVA
    modelos declare.

    ``taxable_base`` must then AGREE with the summed line subtotals, and a
    mismatch refuses rather than resolving. Two disagreeing sources of truth
    for the same base is the shape that silently mis-declares, so the caller is
    made to state one number, not two.

    ``iva_category`` carries the intra-community classification the M349
    recapitulative resolver reads for historical goods/triangulation records.
    ``operation_type`` carries the explicit Modelo 349 clave for invoice
    records that need a key not represented by an IVA category.

    ``retention_rate`` / ``retention_amount`` record the RIRPF art. 95
    withholding a payer settles against a received invoice (or a customer
    against an issued one). Neither is derived here: :class:`Invoice`'s own
    ``_validate_retencion_consistency`` accepts an amount alone, requires an
    amount whenever a rate is supplied, and refuses either that does not
    match the invoice's ``base_total``.

    ``invoice_class``, ``series``, ``rectifies_invoice_number`` and
    ``recargo_amount`` reach axes the aggregate has always modelled and no
    write path could set. Until they existed here every canonically-written
    invoice was ORDINARIA with no series and no recargo **by construction**,
    and a rectificativa was unrepresentable — so the aggregate claimed a
    vocabulary the writer could not speak.

    The recargo rides INSIDE ``grand_total`` (LIVA art. 161) while a retención
    is settled outside it, which is why only the recargo enters the totals
    identity. The model re-checks that identity exactly, so a stated recargo
    the lines do not support refuses rather than being balanced silently.
    """
    from ...domain.invoices.enums import iva_rate_slot_percentage

    # Normalise once, before either the persisted payload or the FX lookup
    # reads it: a padded or lowercase token ("gbp", " gbp ") must resolve the
    # SAME provider rate as its canonical "GBP" form, not silently miss the
    # rate and leave the invoice unstamped.
    currency = normalise_iso_4217_currency(currency)
    rate_slot = resolve_iva_rate_slot(iva_rate)
    # Resolve the cuota through the same undated helper the Invoice line
    # validator uses (``iva_rate_slot_percentage(self.iva_rate)``), so the
    # synthesised ``iva_amount`` matches the model's own re-derivation within
    # tolerance and the line-arithmetic invariant holds. The rate comes from the
    # slot the operator chose, never a hand-typed percentage. Whether that rate
    # was in force is settled by the invoice-level validator against the
    # operation date, not here -- resolving it against today would refuse to
    # record a legitimate 2024 transitional-rate invoice. EXEMPT / NOT_SUBJECT
    # resolve to None and carry a zero cuota.
    pct = iva_rate_slot_percentage(rate_slot)
    base_total, iva_total, payload_lines = _resolve_invoice_line_totals(
        taxable_base=taxable_base,
        lines=lines,
        invoice_number=invoice_number,
        rate_slot=rate_slot,
        iva_percentage=pct,
    )
    # The recargo de equivalencia rides INSIDE the invoice total (LIVA art. 161)
    # while a retencion is settled outside it, which is why only the recargo
    # appears here. The model re-checks this identity exactly, so a caller that
    # states a recargo the lines do not support is refused rather than balanced.
    recargo = recargo_amount or Decimal("0")
    grand_total = base_total + iva_total + recargo
    invoice_payload: dict[str, object] = {
        "bucket_id": bucket_id,
        "kind": kind.value,
        "invoice_number": invoice_number,
        "issued_at": issued_at.isoformat(),
        "counterparty_name": counterparty_name,
        "counterparty_tax_id": counterparty_tax_id,
        "counterparty_country": counterparty_country,
        "base_total": format(base_total, "f"),
        "iva_total": format(iva_total, "f"),
        "grand_total": format(grand_total, "f"),
        "currency": currency,
        "payment_status": payment_status.value,
        "lines": payload_lines,
        "notes": notes,
        "invoice_class": invoice_class.value,
    }
    _apply_operator_asserted_invoice_facts(
        invoice_payload,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        recargo_amount=recargo_amount,
        iva_category=iva_category,
        operation_type=operation_type,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
    )
    # The euro-conversion stamp. ``currency`` is already the canonical uppercase
    # ISO 4217 token (normalised once above), so the provider is queried with the
    # same token the record stores. WHICH date the rate is taken at, and when a
    # record is deliberately left unstamped, are resolve_fx_conversion_stamp's to
    # answer -- this only writes the result into the payload shape.
    _apply_fx_conversion_stamp(
        invoice_payload,
        currency=currency,
        issued_at=issued_at,
        rate_provider=rate_provider,
    )
    return Invoice.model_validate(invoice_payload)


def create_catalogue_invoice(
    *,
    invoice: Invoice,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
    event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
    actor: str = "cli",
) -> CatalogueInvoiceCreateResult:
    """Persist one pre-built catalogue invoice and return the updated catalogue.

    :func:`build_catalogue_invoice` is the sole construction authority for
    operator-supplied fields and line synthesis. This service owns only the
    catalogue mutation and its post-save audit event, so the construction
    contract cannot drift between an in-memory candidate and the written record.
    """
    bucket_id = invoice.bucket_id
    if bucket_id is None:
        raise InvoiceValidationError("a catalogue invoice must declare its bucket_id before persistence")
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)

    def _add(catalogue: InvoiceCatalogue) -> InvoiceCatalogue:
        """Rebuild the catalogue with this invoice, refusing an identity it already holds."""
        if invoice.invoice_id in catalogue:
            raise InvoiceValidationError(
                "an invoice with the same identity already exists in the catalogue",
                translated_message="application.invoices.creation.errors.duplicate_invoice",
                context={"invoice_id": invoice.invoice_id},
            )
        updated = dict(catalogue.invoices)
        updated[invoice.invoice_id] = invoice
        return InvoiceCatalogue.model_validate({"invoices": updated})

    # Guarded rather than load-then-save: the catalogue is one encrypted row, so
    # two operators adding DIFFERENT invoices at once would both read the same
    # catalogue and the later write would drop the earlier invoice. Nothing
    # would report it -- the duplicate check above cannot see an invoice it
    # never read -- and a dropped invoice under-declares. Re-running the
    # duplicate check on each attempt is the point: it must be judged against
    # the catalogue actually being written to, not the one first read.
    new_catalogue = mutate_catalogue(repo, _add)
    # Emitted AFTER the save, so the audit trail never records a creation that
    # did not persist. The reverse order would leave an event pointing at an
    # invoice that is not there, which is worse than a missing event: it reads
    # as evidence.
    event_ids = emit_catalogue_invoice_event(
        invoice=invoice,
        bucket_id=bucket_id,
        slot=0,
        event_repository=event_repository,
        occurred_at=occurred_at or now(),
        actor=actor,
    )
    return CatalogueInvoiceCreateResult(
        invoice=invoice,
        catalogue=new_catalogue,
        bucket_event_ids=event_ids,
    )


__all__ = [
    "CatalogueInvoiceCreateResult",
    "build_catalogue_invoice",
    "create_catalogue_invoice",
]
