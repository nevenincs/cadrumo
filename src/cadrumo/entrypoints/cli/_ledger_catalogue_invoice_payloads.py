"""JSON-contract payloads for the ``aeat app ledger invoice`` verbs.

Each payload is a strict
:class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets on the shared
:class:`SchemaEnvelope` surface through
:func:`emit_envelope`.

Every verb in the group projects the canonical :class:`Invoice`
held in the :class:`InvoiceCatalogue` — the sole invoice
aggregate, carrying ``linked_transaction_ids`` and the identity
``link --invoice-id`` resolves through
:func:`link_invoice_transaction_repositories`. The
``Catalogue`` prefix on these classes names that aggregate, not a CLI
subgroup: the operator surface is the bare ``invoice`` noun, so the
graph-declared command identifiers are ``ledger.invoice.<verb>``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import Field, NonNegativeInt, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.country_code import CountryCodeAlpha2
from ...core.identity import BucketId, InvoiceId, TaxIdIdentityToken, TransactionId, validate_spanish_tax_id
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr, NonNegativeDecimal, PositiveCount
from ...domain.invoices.enums import PaymentStatus
from ...domain.invoices.validators import validate_country_code, validate_iva_number
from ...domain.iva.classification import InvoiceKind


class CatalogueInvoiceRecordPayload(OutputSchema):
    """One rich catalogue invoice projected for the operator surface.

    Nested in
    :class:`CatalogueInvoiceCreatePayload`,
    :class:`CatalogueInvoiceViewResult`,
    :class:`CatalogueInvoiceRemovePayload`,
    and
    :class:`CatalogueInvoiceListResult`.
    Carries the content-addressed
    ``invoice_id`` (the value ``link --invoice-id`` resolves) plus the identity
    and total fields. The ``linked_transaction_ids`` list reflects the
    bidirectional links the ``link`` verb writes onto the rich
    :class:`Invoice`.
    """

    invoice_id: InvoiceId
    bucket_id: BucketId | None = None
    kind: InvoiceKind
    invoice_number: NonEmptyStr
    issued_at: date
    counterparty_name: NonEmptyStr
    counterparty_tax_id: TaxIdIdentityToken | None = None
    counterparty_country: CountryCodeAlpha2
    base_total: NonNegativeDecimal
    iva_total: NonNegativeDecimal
    grand_total: NonNegativeDecimal
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    payment_status: PaymentStatus
    linked_transaction_ids: list[TransactionId] = Field(default_factory=list)
    notes: str = ""
    operation_type: IntracomOperationType | None = None
    # The euro conversion stamp and the euro projection of the three totals.
    # Present at parity with the evidence-confirm surface through the shared
    # field tuple both projections read. A foreign invoice whose rate could not
    # be resolved carries the stamp fields ``None`` AND the eur totals ``None``:
    # the record says, on its face, that no euro figure exists for it rather
    # than presenting the foreign face value as though it were euro.
    fx_rate: Decimal | None = Field(default=None, gt=Decimal("0"))
    fx_rate_date: date | None = None
    fx_rate_source: NonEmptyStr | None = None
    base_total_eur: Decimal | None = Field(default=None, ge=Decimal("0"))
    iva_total_eur: Decimal | None = Field(default=None, ge=Decimal("0"))
    grand_total_eur: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def _validate_counterparty_identity(self) -> Self:
        """Reuse the rich invoice identity validators for the wire projection.

        ``None`` is skipped rather than validated: a factura simplificada may
        legitimately carry no counterparty tax id (RD 1619/2012 art. 6.1.d),
        and the rich :class:`~domain.invoices.Invoice` this payload projects
        already enforces the cases where one is mandatory.
        """
        if self.counterparty_tax_id is None:
            return self
        country = validate_country_code(self.counterparty_country)
        if country == "ES":
            validate_spanish_tax_id(self.counterparty_tax_id)
        else:
            validate_iva_number(self.counterparty_tax_id, country)
        return self


class CatalogueInvoiceCreatePayload(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice add``.

    Mirrors the ``invoice`` inside the application-layer create result returned
    by :func:`create_catalogue_invoice`.
    """


class CatalogueInvoiceWizardResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice wizard``.

    Mirrors the ``invoice`` inside the application-layer result returned by
    :func:`create_invoice_via_wizard`. ``already_existed`` reports the guarded
    idempotent no-op path: ``True`` when the same content-derived identity was
    already catalogued and nothing was written.
    """

    already_existed: bool = False


class CatalogueInvoiceViewResult(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice view``.

    Projects the rich :class:`Invoice` resolved by
    :func:`resolve_catalogue_invoice_from_repository`.
    """


class CatalogueInvoiceUpdatePayload(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice update``.

    Projects the re-validated :class:`Invoice` returned by
    :func:`update_catalogue_invoice`. The content-addressed ``invoice_id`` is
    unchanged: identity fields are structurally excluded from
    :class:`~application.invoices.CatalogueInvoicePatch`, so a correction never
    silently re-mints the record under a new identity.

    ``bucket_event_ids`` carries the lifecycle events the correction emitted,
    so the operator can trace the write without a second read.
    """

    bucket_event_ids: list[str] = Field(default_factory=list)


class CatalogueInvoiceRemovePayload(CatalogueInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice remove``.

    Reports the deleted rich :class:`Invoice` returned by
    :func:`remove_catalogue_invoice`; linked invoices are refused before this
    payload is emitted.
    """


class CatalogueInvoiceListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger invoice list``.

    Each row is a
    :class:`CatalogueInvoiceRecordPayload`
    projected from the
    active bucket's :class:`InvoiceCatalogue`; ``kind``
    filtering stays in the CLI query before this envelope is validated.
    """

    bucket_id: BucketId
    rows: list[CatalogueInvoiceRecordPayload]
    count: NonNegativeInt


class BulkInvoiceImportRowFailurePayload(OutputSchema):
    """One refused row from a bulk invoice import, naming its row and field."""

    row_number: PositiveCount
    field: NonEmptyStr
    reason: NonEmptyStr


class CatalogueInvoiceImportResult(OutputSchema):
    """JSON envelope for ``aeat app ledger invoice import``.

    Mirrors the application-layer
    :class:`~application.invoices.BulkInvoiceImportResult`: ``created``
    rows were persisted through
    :func:`~application.invoices.create_catalogue_invoice`;
    ``skipped_duplicate`` rows already existed under an identical
    content-derived identity (a guarded idempotent re-import no-op); ``refused``
    rows failed validation and were not persisted.
    """

    bucket_id: BucketId
    rows: NonNegativeInt
    created: NonNegativeInt
    skipped_duplicate: NonNegativeInt
    refused: list[BulkInvoiceImportRowFailurePayload] = []
    created_invoice_ids: list[InvoiceId] = Field(default_factory=list)


__all__ = [
    "BulkInvoiceImportRowFailurePayload",
    "CatalogueInvoiceCreatePayload",
    "CatalogueInvoiceImportResult",
    "CatalogueInvoiceListResult",
    "CatalogueInvoiceRecordPayload",
    "CatalogueInvoiceRemovePayload",
    "CatalogueInvoiceUpdatePayload",
    "CatalogueInvoiceViewResult",
    "CatalogueInvoiceWizardResult",
]
