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
operator-friendly fields — synthesising a single line item from a taxable base
and IVA rate, mirroring the single-line synthesis the import path uses — and
persists it through the sanctioned :class:`InvoiceCatalogueRepository` (no
parallel write path). The returned :attr:`Invoice.invoice_id` is the
content-addressed hash ``link --invoice-id`` resolves, closing the documented
add->link gap without collapsing the two stores.
"""

from __future__ import annotations

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
    rate_provider: ExchangeRateProvider | None = None,
) -> Invoice:
    """Return a strict rich :class:`Invoice` from operator-supplied fields.

    A single line item is synthesised from ``taxable_base`` and the resolved
    IVA rate slot; the invoice totals are derived from that line so the
    :class:`Invoice` arithmetic invariants hold. The returned invoice carries
    no linked transactions yet — ``link --invoice-id`` populates them later.

    ``iva_category`` carries the intra-community classification the M349
    recapitulative resolver reads for historical goods/triangulation records.
    ``operation_type`` carries the explicit Modelo 349 clave for invoice
    records that need a key not represented by an IVA category.
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
    iva_amount = Decimal("0") if pct is None else round_to_cents(taxable_base * pct)
    base_total = round_to_cents(taxable_base)
    iva_total = iva_amount
    grand_total = base_total + iva_total
    line = {
        "description": invoice_number or "Invoice",
        "quantity": "1",
        "unit_price": format(base_total, "f"),
        "subtotal": format(base_total, "f"),
        "iva_rate": rate_slot.value,
        "iva_amount": format(iva_amount, "f"),
    }
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
        "lines": [line],
        "notes": notes,
    }
    if iva_category is not None:
        invoice_payload["iva_category"] = iva_category.value
    if operation_type is not None:
        invoice_payload["operation_type"] = operation_type.value
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
