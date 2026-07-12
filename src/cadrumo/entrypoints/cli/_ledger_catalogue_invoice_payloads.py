"""JSON-contract payloads for the rich catalogue-invoice CLI verbs.

Each payload is a strict
:class:`OutputSchema` subclass registered with
:func:`register_schema` on the shared
:class:`SchemaEnvelope` surface through
:func:`_emit_envelope`.

The unified ``cadrumo app ledger invoice`` group drives the slim
:class:`BusinessOperationInvoice` operator record
(payloads in :mod:`_ledger_payloads`). The ``catalogue``
subgroup added here drives the **rich** :class:`Invoice`
in the
:class:`InvoiceCatalogue` — the only invoice aggregate
that carries ``linked_transaction_ids`` and the one ``link --invoice-id``
resolves through
:func:`link_invoice_transaction_repositories`. These
payloads are declared in their own module so the registration side-effects live
next to the verb that emits them without touching the slim
:mod:`_ledger_payloads` surface.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class CatalogueInvoiceRecordPayload(OutputSchema):
    """One rich catalogue invoice projected for the operator surface.

    Nested in
    :class:`CatalogueInvoiceCreateResult`,
    :class:`CatalogueInvoiceViewResult`,
    :class:`CatalogueInvoiceRemoveResult`,
    and
    :class:`CatalogueInvoiceListResult`.
    Carries the content-addressed
    ``invoice_id`` (the value ``link --invoice-id`` resolves) plus the identity
    and total fields. The ``linked_transaction_ids`` list reflects the
    bidirectional links the ``link`` verb writes onto the rich
    :class:`Invoice`.
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
    operation_type: str | None = None


@register_schema("ledger.invoice.catalogue.create")
class CatalogueInvoiceCreateResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``cadrumo app ledger invoice catalogue create``.

    Mirrors the ``invoice`` inside the application-layer create result returned
    by :func:`create_catalogue_invoice`.
    """


@register_schema("ledger.invoice.catalogue.wizard")
class CatalogueInvoiceWizardResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``cadrumo app ledger invoice catalogue wizard``.

    Mirrors the ``invoice`` inside the application-layer result returned by
    :func:`create_invoice_via_wizard`. ``already_existed`` reports the guarded
    idempotent no-op path: ``True`` when the same content-derived identity was
    already catalogued and nothing was written.
    """

    already_existed: bool = False


@register_schema("ledger.invoice.catalogue.view")
class CatalogueInvoiceViewResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``cadrumo app ledger invoice catalogue view``.

    Projects the rich :class:`Invoice` resolved by
    :func:`resolve_catalogue_invoice_from_repository`.
    """


@register_schema("ledger.invoice.catalogue.remove")
class CatalogueInvoiceRemoveResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``cadrumo app ledger invoice catalogue remove``.

    Reports the deleted rich :class:`Invoice` returned by
    :func:`remove_catalogue_invoice`; linked invoices are refused before this
    payload is emitted.
    """


@register_schema("ledger.invoice.catalogue.list")
class CatalogueInvoiceListResult(OutputSchema):
    """JSON envelope for ``cadrumo app ledger invoice catalogue list``.

    Each row is a
    :class:`CatalogueInvoiceRecordPayload`
    projected from the
    active bucket's :class:`InvoiceCatalogue`; ``kind``
    filtering stays in the CLI query before this envelope is validated.
    """

    bucket_id: str
    rows: list[CatalogueInvoiceRecordPayload]
    count: int


class BulkInvoiceImportRowFailurePayload(OutputSchema):
    """One refused row from a bulk invoice import, naming its row and field."""

    row_number: int
    field: str
    reason: str


@register_schema("ledger.invoice.catalogue.import")
class CatalogueInvoiceImportResult(OutputSchema):
    """JSON envelope for ``cadrumo app ledger invoice catalogue import``.

    Mirrors the application-layer
    :class:`~application.invoices.BulkInvoiceImportResult`: ``created``
    rows were persisted through
    :func:`~application.invoices.create_catalogue_invoice`;
    ``skipped_duplicate`` rows already existed under an identical
    content-derived identity (a guarded idempotent re-import no-op); ``refused``
    rows failed validation and were not persisted.
    """

    bucket_id: str
    rows: int
    created: int
    skipped_duplicate: int
    refused: list[BulkInvoiceImportRowFailurePayload] = []
    created_invoice_ids: list[str] = []


__all__ = [
    "BulkInvoiceImportRowFailurePayload",
    "CatalogueInvoiceCreateResult",
    "CatalogueInvoiceImportResult",
    "CatalogueInvoiceListResult",
    "CatalogueInvoiceRecordPayload",
    "CatalogueInvoiceRemoveResult",
    "CatalogueInvoiceViewResult",
    "CatalogueInvoiceWizardResult",
]
