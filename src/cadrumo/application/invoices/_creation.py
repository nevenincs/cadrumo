"""Application service for creating one rich catalogue :class:`Invoice`.

The operator-facing ``aeat app ledger invoice catalogue create`` verb needs
a path to mint a **linkable** invoice. The slim
:class:`~application.ledger.BusinessOperationInvoice` written by
``invoice add`` is an operator-edit record with no ``linked_transaction_ids``
field, so ``link --invoice-id`` cannot resolve it. Only the rich
:class:`~domain.invoices.Invoice` in the
:class:`~domain.invoices.InvoiceCatalogue` carries
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
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.fx import default_ecb_rate_provider
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core import IntracomOperationType
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.money import round_to_cents
from ...core.parsing import normalise_iso_4217_currency
from ...domain.currency import ExchangeRateProvider
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceClass,
    InvoiceLine,
    InvoiceOperationDateRole,
    InvoiceValidationError,
    IvaRate,
    PaymentStatus,
)
from ...domain.iva import InvoiceKind, IvaCategory

_NUMERIC_IVA_RATE_SLOTS: dict[Decimal, IvaRate] = {
    Decimal("0"): IvaRate.RATE_0,
    Decimal("4"): IvaRate.RATE_4,
    Decimal("10"): IvaRate.RATE_10,
    Decimal("21"): IvaRate.RATE_21,
}


def numeric_iva_rate_slots() -> dict[Decimal, IvaRate]:
    """Return the closed set of operator-supplied IVA percentage slots.

    A copy of the module-private mapping :func:`_resolve_iva_rate_slot` and
    :func:`build_catalogue_invoice` consume internally, exposed for other
    invoice-creation transports (e.g. the manual-entry wizard) that must
    validate a percentage against the same accepted set before it reaches
    :func:`build_catalogue_invoice`.
    """
    return dict(_NUMERIC_IVA_RATE_SLOTS)


class CatalogueInvoiceCreateResult(BaseModel):
    """Result of persisting one rich catalogue invoice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice: Invoice
    catalogue: InvoiceCatalogue


def _resolve_iva_rate_slot(iva_rate: Decimal | None) -> IvaRate:
    """Map an operator-supplied integer IVA percentage to its rate slot.

    ``None`` resolves to :attr:`IvaRate.EXEMPT` so a base-only invoice with no
    cuota is accepted. A percentage outside the closed slot taxonomy is refused
    with the accepted set named, never a bare "value invalid".
    """
    if iva_rate is None:
        return IvaRate.EXEMPT
    slot = _NUMERIC_IVA_RATE_SLOTS.get(iva_rate)
    if slot is None:
        accepted = ", ".join(format(rate, "f") for rate in sorted(_NUMERIC_IVA_RATE_SLOTS))
        raise InvoiceValidationError(
            "iva_rate is not a recognised IVA percentage",
            translated_message="application.invoices.creation.errors.unsupported_iva_rate",
            context={"iva_rate": format(iva_rate, "f"), "accepted": accepted},
        )
    return slot


def build_catalogue_invoice(
    *,
    bucket_id: str | None,
    kind: InvoiceKind,
    counterparty_name: str,
    counterparty_tax_id: str,
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
    from ...domain.invoices import iva_rate_percentage

    # Normalise once, before either the persisted payload or the FX lookup
    # reads it: a padded or lowercase token ("gbp", " gbp ") must resolve the
    # SAME provider rate as its canonical "GBP" form, not silently miss the
    # rate and leave the invoice unstamped.
    currency = normalise_iso_4217_currency(currency)
    rate_slot = _resolve_iva_rate_slot(iva_rate)
    # Resolve the cuota with the same default-date the Invoice line validator
    # uses (``iva_rate_percentage(self.iva_rate)``), so the synthesised
    # ``iva_amount`` matches the model's own re-derivation within tolerance and
    # the line-arithmetic invariant holds. The cuota is grounded against the
    # registry-resolved rate, never a hand-typed percentage. EXEMPT /
    # NOT_SUBJECT resolve to None and carry a zero cuota.
    pct = iva_rate_percentage(rate_slot)
    if lines:
        if not all(isinstance(item, InvoiceLine) for item in lines):
            raise InvoiceValidationError("lines must be InvoiceLine records")
        base_total = round_to_cents(sum((item.subtotal for item in lines), Decimal("0")))
        iva_total = round_to_cents(sum((item.iva_amount for item in lines), Decimal("0")))
        declared_base = round_to_cents(taxable_base)
        if declared_base != base_total:
            raise InvoiceValidationError(
                f"taxable_base {declared_base} does not equal the summed line subtotals {base_total}",
            )
        payload_lines = [item.model_dump(mode="json") for item in lines]
    else:
        iva_amount = Decimal("0") if pct is None else round_to_cents(taxable_base * pct)
        base_total = round_to_cents(taxable_base)
        iva_total = iva_amount
        payload_lines = [
            {
                "description": invoice_number or "Invoice",
                "quantity": "1",
                "unit_price": format(base_total, "f"),
                "subtotal": format(base_total, "f"),
                "iva_rate": rate_slot.value,
                "iva_amount": format(iva_amount, "f"),
            },
        ]
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
    if series is not None:
        invoice_payload["series"] = series
    if rectifies_invoice_number is not None:
        invoice_payload["rectifies_invoice_number"] = rectifies_invoice_number
    if recargo_amount is not None:
        invoice_payload["recargo_amount"] = format(recargo_amount, "f")
    if iva_category is not None:
        invoice_payload["iva_category"] = iva_category.value
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
    _stamp_fx_conversion(invoice_payload, currency=currency, issued_at=issued_at, rate_provider=rate_provider)
    return Invoice.model_validate(invoice_payload)


def _stamp_fx_conversion(
    payload: dict[str, object],
    *,
    currency: str,
    issued_at: date,
    rate_provider: ExchangeRateProvider | None,
) -> None:
    """Stamp the euro conversion rate for a foreign-currency invoice.

    ``currency`` must already be the canonical uppercase ISO 4217 token (the
    caller normalises it once via :func:`core.parsing.normalise_iso_4217_currency`
    before both the persisted payload and this lookup read it), so the
    provider is queried with the same token the record stores.

    Converts at the invoice's issue date, which is the operation date Spanish
    law binds the official rate to (Ley 46/1998 art. 36), matching the ledger's
    convert-once-at-ingest shape rather than converting at read time.

    A euro invoice is left unstamped. A foreign invoice whose rate cannot be
    resolved is also left unstamped rather than defaulted: the record then
    reports no euro value and is gated out of projection, which is recoverable,
    where a fabricated rate would not be.
    """
    if currency.strip().upper() == DEFAULT_CURRENCY:
        return
    provider = rate_provider or default_ecb_rate_provider()
    rate = provider.get_eur_rate(currency, issued_at)
    if rate is None:
        return
    payload["fx_rate"] = format(rate, "f")
    payload["fx_rate_date"] = issued_at.isoformat()


def create_catalogue_invoice(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_name: str,
    counterparty_tax_id: str,
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
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
    rate_provider: ExchangeRateProvider | None = None,
) -> CatalogueInvoiceCreateResult:
    """Persist one rich catalogue :class:`Invoice` and return the updated catalogue.

    The invoice is built via :func:`build_catalogue_invoice`, merged into the
    loaded :class:`InvoiceCatalogue`, and written back through the sanctioned
    :class:`InvoiceCatalogueRepository`. A duplicate logical identity (same
    derived ``invoice_id`` already present) is refused so an accidental
    re-create cannot silently overwrite a linked record.
    """
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    invoice = build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        invoice_number=invoice_number,
        issued_at=issued_at,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        currency=currency,
        payment_status=payment_status,
        notes=notes,
        iva_category=iva_category,
        operation_type=operation_type,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        recargo_amount=recargo_amount,
        lines=lines,
        rate_provider=rate_provider,
    )
    catalogue = repo.load()
    if invoice.invoice_id in catalogue:
        raise InvoiceValidationError(
            "an invoice with the same identity already exists in the catalogue",
            translated_message="application.invoices.creation.errors.duplicate_invoice",
            context={"invoice_id": invoice.invoice_id},
        )
    updated = dict(catalogue.invoices)
    updated[invoice.invoice_id] = invoice
    new_catalogue = InvoiceCatalogue.model_validate({"invoices": updated})
    repo.save(new_catalogue)
    return CatalogueInvoiceCreateResult(invoice=invoice, catalogue=new_catalogue)


__all__ = [
    "CatalogueInvoiceCreateResult",
    "build_catalogue_invoice",
    "create_catalogue_invoice",
    "numeric_iva_rate_slots",
]
