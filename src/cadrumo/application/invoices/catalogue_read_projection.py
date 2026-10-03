"""Closed invoice read snapshots for authenticated frontend disclosure."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
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
from ...domain.invoices.enums import PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ..operations.public_scalar import PublicDecimal


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

    @model_validator(mode="after")
    def _bounds(self) -> Self:
        if (
            not self.lines
            or not all(
                _bounded_decimal(value)
                for value in (
                    self.base_total,
                    self.iva_total,
                    self.grand_total,
                    self.retention_rate,
                    self.retention_amount,
                    self.recargo_amount,
                    self.base_total_eur,
                    self.iva_total_eur,
                    self.grand_total_eur,
                )
            )
            or not _bounded_decimal(self.fx_rate, positive=True)
            or not self.invoice_class
            or normalise_iso_4217_currency(self.currency) != self.currency
            or (
                self.source_filename is not None
                and (not self.source_filename or "/" in self.source_filename or "\\" in self.source_filename)
            )
        ):
            raise ValueError("invoice snapshot has invalid disclosed values")
        return self

    @classmethod
    def from_invoice(cls, invoice: Invoice) -> Self:
        """Copy the existing list/view surface without forwarding the aggregate."""
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
        )


__all__ = ["CatalogueInvoiceSnapshot", "InvoiceLineSnapshot"]
