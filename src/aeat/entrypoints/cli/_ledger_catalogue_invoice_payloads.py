"""JSON-contract payloads for the rich catalogue-invoice CLI verbs.

The unified ``aeat app ledger invoice`` group drives the slim
:class:`~aeat.application.ledger.BusinessOperationInvoice` operator record
(payloads in :mod:`._ledger_payloads`). The ``catalogue`` subgroup added here
drives the **rich** :class:`~aeat.domain.invoices.Invoice` in the
:class:`~aeat.domain.invoices.InvoiceCatalogue` — the only invoice aggregate
that carries ``linked_transaction_ids`` and the one ``link --invoice-id``
resolves. These payloads are declared in their own module so the registration
side-effects live next to the verb that emits them without touching the slim
:mod:`._ledger_payloads` surface.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class CatalogueInvoiceRecordPayload(OutputSchema):
    """One rich catalogue invoice projected for the operator surface.

    Carries the content-addressed ``invoice_id`` (the value
    ``link --invoice-id`` resolves) plus the identity and total fields. The
    ``linked_transaction_ids`` list reflects the bidirectional links the
    ``link`` verb writes onto the rich :class:`Invoice`.
    """

    invoice_id: str
    bucket_id: str | None = None
    kind: str
    invoice_number: str
    issued_at: str
    counterparty_name: str
    counterparty_tax_id: str
    counterparty_country: str
    base_total: str
    iva_total: str
    grand_total: str
    currency: str
    payment_status: str
    linked_transaction_ids: list[str] = []
    notes: str = ""


@register_schema("ledger.invoice.catalogue.create")
class CatalogueInvoiceCreateResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice catalogue create``."""


@register_schema("ledger.invoice.catalogue.view")
class CatalogueInvoiceViewResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice catalogue view``."""


@register_schema("ledger.invoice.catalogue.remove")
class CatalogueInvoiceRemoveResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice catalogue remove``."""


@register_schema("ledger.invoice.catalogue.list")
class CatalogueInvoiceListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger invoice catalogue list``."""

    bucket_id: str
    rows: list[CatalogueInvoiceRecordPayload]
    count: int


__all__ = [
    "CatalogueInvoiceCreateResult",
    "CatalogueInvoiceListResult",
    "CatalogueInvoiceRecordPayload",
    "CatalogueInvoiceRemoveResult",
    "CatalogueInvoiceViewResult",
]
