"""Closed invoice read snapshots for authenticated frontend disclosure."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Self

from pydantic import BaseModel, PositiveInt, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.country_code import CountryCodeAlpha2
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import InvoiceId
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.text_bounds import NonEmptyStr
from ...domain.attachments.enums import AttachmentSource
from ...domain.attachments.models import Attachment, normalize_media_type
from ...domain.invoices.enums import PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.invoices.service import invoice_settlement
from ...domain.iva.schema import InvoiceKind
from ..operations.host_path_name import host_path_file_name
from ..operations.public_scalar import PublicDecimal
from .catalogue_reads_ports import InvoiceDocumentManifestReader


def _decimal(value: Decimal) -> PublicDecimal:
    return PublicDecimal(decimal=str(value))


def _optional_decimal(value: Decimal | None) -> PublicDecimal | None:
    return _decimal(value) if value is not None else None


def _bounded_decimal(value: PublicDecimal | None, *, positive: bool = False) -> bool:
    return value is None or (Decimal(value.decimal) > 0 if positive else Decimal(value.decimal) >= 0)


class InvoiceLineSnapshot(BaseModel):
    """Only the line fields emitted by the existing catalogue CLI payload."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    description: NonEmptyStr
    quantity: PublicDecimal
    unit_price: PublicDecimal
    subtotal: PublicDecimal
    iva_rate: str
    iva_amount: PublicDecimal
    spending_category_id: str | None = None
    oss_rate_kind: str | None = None

    @model_validator(mode="after")
    def _bounds(self) -> Self:
        if (
            not self.description.strip()
            or not self.iva_rate
            or not _bounded_decimal(self.quantity, positive=True)
            or not all(_bounded_decimal(value) for value in (self.unit_price, self.subtotal, self.iva_amount))
        ):
            raise ValueError("invoice line has invalid disclosed values")
        return self

    @classmethod
    def from_line(cls, line: InvoiceLine) -> Self:
        """Copy exactly the line's existing output fields and decimal values."""
        return cls(
            description=line.description,
            quantity=_decimal(line.quantity),
            unit_price=_decimal(line.unit_price),
            subtotal=_decimal(line.subtotal),
            iva_rate=str(line.iva_rate),
            iva_amount=_decimal(line.iva_amount),
            spending_category_id=line.spending_category_id,
            oss_rate_kind=str(line.oss_rate_kind) if line.oss_rate_kind is not None else None,
        )


def _is_bare_file_name(value: str) -> bool:
    return value not in {"", ".", ".."} and "/" not in value and "\\" not in value


def _document_file_name(attachment: Attachment) -> str | None:
    # Only a document read from a local file records that file's path; any
    # other channel's reference (a message id, a URL) is not a file name.
    if attachment.source is not AttachmentSource.LOCAL_FILE:
        return None
    name = host_path_file_name(attachment.source_reference)
    return name if name is not None and _is_bare_file_name(name) else None


class InvoiceDocumentSnapshot(BaseModel):
    """One stored document kept as an invoice's source, named by its file name alone."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    attachment_id: Hex64Str
    #: The name of the file the document was read from, without its folder;
    #: absent when the document did not come from a local file.
    name: NonEmptyStr | None
    media_type: NonEmptyStr

    @model_validator(mode="after")
    def _bare_name(self) -> Self:
        if self.name is not None and not _is_bare_file_name(self.name):
            raise ValueError("an invoice document is named by its file name alone")
        return self

    @classmethod
    def from_attachment(cls, attachment: Attachment) -> Self:
        """Copy the document's identity, file name and media type from its manifest."""
        return cls(
            attachment_id=attachment.attachment_id,
            name=_document_file_name(attachment),
            media_type=normalize_media_type(attachment.mime_type),
        )


class InvoiceDocumentIndex:
    """Each invoice's stored documents, gathered from the manifests in one pass."""

    __slots__ = ("_documents",)

    def __init__(self, documents: Mapping[str, tuple[InvoiceDocumentSnapshot, ...]]) -> None:
        """Hold an already ordered invoice-to-documents mapping."""
        self._documents: Mapping[str, tuple[InvoiceDocumentSnapshot, ...]] = MappingProxyType(dict(documents))

    @classmethod
    def from_manifests(cls, manifests: Iterable[Attachment]) -> Self:
        """Index every manifest by each invoice it records, ordered by attachment id."""
        gathered: dict[str, list[InvoiceDocumentSnapshot]] = {}
        for manifest in manifests:
            if not manifest.linked_invoice_ids:
                continue
            document = InvoiceDocumentSnapshot.from_attachment(manifest)
            for invoice_id in manifest.linked_invoice_ids:
                gathered.setdefault(invoice_id, []).append(document)
        return cls(
            {
                invoice_id: tuple(sorted(documents, key=lambda document: document.attachment_id))
                for invoice_id, documents in gathered.items()
            }
        )

    @classmethod
    def read(cls, reader: InvoiceDocumentManifestReader) -> Self:
        """Read the profile's manifests once and index them."""
        return cls.from_manifests(reader.iter_manifests())

    def of(self, invoice_id: str) -> tuple[InvoiceDocumentSnapshot, ...]:
        """The documents kept for ``invoice_id``; empty when the records hold none."""
        return self._documents.get(invoice_id, ())


class CatalogueInvoiceSnapshot(BaseModel):
    """The existing catalogue readback fields, excluding full source paths."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice_id: InvoiceId
    bucket_id: BucketId | None
    kind: InvoiceKind
    invoice_number: NonEmptyStr
    issued_at: date
    counterparty_name: NonEmptyStr
    counterparty_tax_id: TaxIdIdentityToken | None
    counterparty_country: CountryCodeAlpha2
    base_total: PublicDecimal
    iva_total: PublicDecimal
    grand_total: PublicDecimal
    currency: str
    payment_status: PaymentStatus
    linked_transaction_ids: tuple[TransactionId, ...]
    source_filename: NonEmptyStr | None
    source_sha256: Hex64Str | None
    source_row_index: PositiveInt | None
    notes: str
    retention_rate: PublicDecimal | None
    retention_amount: PublicDecimal | None
    recargo_amount: PublicDecimal | None
    operation_type: IntracomOperationType | None
    lines: tuple[InvoiceLineSnapshot, ...]
    invoice_class: str
    series: str | None
    operation_date: date | None
    operation_date_role: str | None
    iva_category: str | None
    rectifies_invoice_number: str | None
    fx_rate: PublicDecimal | None
    fx_rate_date: date | None
    fx_rate_source: NonEmptyStr | None
    base_total_eur: PublicDecimal | None
    iva_total_eur: PublicDecimal | None
    grand_total_eur: PublicDecimal | None
    referencia_catastral: str | None
    #: The cash the invoice settles for: its total less the retención withheld at source.
    settlement_amount: PublicDecimal
    #: The stored documents kept as this invoice's source, ordered by attachment id.
    documents: tuple[InvoiceDocumentSnapshot, ...]

    @model_validator(mode="after")
    def _bounds(self) -> Self:
        _require_snapshot_amounts(self)
        _require_snapshot_classification_and_source(self)
        return self

    @classmethod
    def from_invoice(cls, invoice: Invoice, *, documents: InvoiceDocumentIndex) -> Self:
        """Copy the existing list/view surface and the invoice's stored documents without forwarding the aggregate.

        ``documents`` is required so that no reader serves an invoice as having
        no document merely because it did not look.
        """
        provenance = invoice.provenance
        return cls(
            invoice_id=invoice.invoice_id,
            bucket_id=invoice.bucket_id,
            kind=invoice.kind,
            invoice_number=invoice.invoice_number,
            issued_at=invoice.issued_at,
            counterparty_name=invoice.counterparty_name,
            counterparty_tax_id=invoice.counterparty_tax_id,
            counterparty_country=invoice.counterparty_country,
            base_total=_decimal(invoice.base_total),
            iva_total=_decimal(invoice.iva_total),
            grand_total=_decimal(invoice.grand_total),
            currency=invoice.currency,
            payment_status=invoice.payment_status,
            linked_transaction_ids=invoice.linked_transaction_ids,
            source_filename=provenance.source_path.name if provenance is not None else None,
            source_sha256=provenance.source_sha256 if provenance is not None else None,
            source_row_index=provenance.source_row_index if provenance is not None else None,
            notes=invoice.notes,
            retention_rate=_optional_decimal(invoice.retention_rate),
            retention_amount=_optional_decimal(invoice.retention_amount),
            recargo_amount=_optional_decimal(invoice.recargo_amount),
            operation_type=invoice.operation_type,
            lines=tuple(InvoiceLineSnapshot.from_line(line) for line in invoice.lines),
            invoice_class=str(invoice.invoice_class),
            series=invoice.series,
            operation_date=invoice.operation_date,
            operation_date_role=str(invoice.operation_date_role) if invoice.operation_date_role is not None else None,
            iva_category=str(invoice.iva_category) if invoice.iva_category is not None else None,
            rectifies_invoice_number=invoice.rectifies_invoice_number,
            fx_rate=_optional_decimal(invoice.fx_rate),
            fx_rate_date=invoice.fx_rate_date,
            fx_rate_source=invoice.fx_rate_source,
            base_total_eur=_optional_decimal(invoice.base_total_eur),
            iva_total_eur=_optional_decimal(invoice.iva_total_eur),
            grand_total_eur=_optional_decimal(invoice.grand_total_eur),
            referencia_catastral=(
                invoice.business_premises_lease.referencia_catastral
                if invoice.business_premises_lease is not None
                else None
            ),
            settlement_amount=_decimal(invoice_settlement(invoice)),
            documents=documents.of(invoice.invoice_id),
        )


def _require_snapshot_amounts(snapshot: CatalogueInvoiceSnapshot) -> None:
    if not snapshot.lines or not all(
        _bounded_decimal(value)
        for value in (
            snapshot.base_total,
            snapshot.iva_total,
            snapshot.grand_total,
            snapshot.retention_rate,
            snapshot.retention_amount,
            snapshot.recargo_amount,
            snapshot.base_total_eur,
            snapshot.iva_total_eur,
            snapshot.grand_total_eur,
        )
    ):
        raise ValueError("invoice snapshot has invalid disclosed values")


def _require_snapshot_classification_and_source(snapshot: CatalogueInvoiceSnapshot) -> None:
    if (
        not _bounded_decimal(snapshot.fx_rate, positive=True)
        or not snapshot.invoice_class
        or normalise_iso_4217_currency(snapshot.currency) != snapshot.currency
        or (snapshot.source_filename is not None and not _is_bare_file_name(snapshot.source_filename))
        or len({document.attachment_id for document in snapshot.documents}) != len(snapshot.documents)
    ):
        raise ValueError("invoice snapshot has invalid disclosed values")


__all__ = ["CatalogueInvoiceSnapshot", "InvoiceDocumentIndex", "InvoiceDocumentSnapshot", "InvoiceLineSnapshot"]
