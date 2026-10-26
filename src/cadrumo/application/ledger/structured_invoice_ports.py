"""Application-owned contract for deterministic structured-invoice reads.

The inbound e-invoice parser owns syntax, XML handling, and format-specific
vocabularies.  The ledger use case needs only the values a structured record
states, so an outer binding translates the parser's result into these
syntax-neutral in-memory records before it crosses into the application.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol

from ...core.document_shape import DocumentShape


class StructuredInvoiceClassificationKind(StrEnum):
    """Application-relevant class of a structured invoice document."""

    ORDINARY = "ordinary"
    CORRECTIVE = "corrective"
    SUMMARY = "summary"


@dataclass(frozen=True, slots=True)
class StructuredInvoiceClassification:
    """A document class translated from a syntax-specific source code."""

    source_code: str
    kind: StructuredInvoiceClassificationKind


@dataclass(frozen=True, slots=True)
class StructuredInvoiceLine:
    """One syntax-neutral line read from a structured invoice."""

    description: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    taxable_base: Decimal | None
    iva_rate: Decimal | None
    iva_amount: Decimal | None


#: The location report of a reader whose fields all sit where the format fixes
#: them. Read-only so one shared default cannot be mutated into another record's
#: report.
_NO_ELEMENT_PATHS: Final[Mapping[str, str]] = MappingProxyType[str, str]({})


@dataclass(frozen=True, slots=True)
class StructuredInvoiceRecord:
    """The structured-record facts consumed by ledger extraction."""

    shape: DocumentShape
    supplier_tax_id: str | None
    customer_tax_id: str | None
    supplier_name: str | None
    customer_name: str | None
    supplier_postal_code: str | None
    customer_postal_code: str | None
    supplier_country_code: str | None
    customer_country_code: str | None
    invoice_number: str | None
    invoice_series: str | None
    invoice_classification: StructuredInvoiceClassification | None
    rectifies_invoice_number: str | None
    invoice_date: str | None
    currency: str | None
    taxable_base: Decimal | None
    iva_amount: Decimal | None
    grand_total: Decimal | None
    recargo_amount: Decimal | None
    retencion_amount: Decimal | None
    suplidos_amount: Decimal | None
    iva_category: str | None
    regime_legend: str | None
    record_text: str
    lines: tuple[StructuredInvoiceLine, ...]
    iva_breakdown: tuple[tuple[Decimal | None, Decimal | None, Decimal | None], ...]
    #: Where a field was read from, keyed by field name, for the fields whose
    #: location the document shape alone does not settle. A reader supplies an
    #: entry only when the format offers alternative elements for the same fact;
    #: provenance falls back to the per-shape location otherwise. An absent entry
    #: therefore means "the usual place", never "unknown".
    element_paths: Mapping[str, str] = _NO_ELEMENT_PATHS


class StructuredInvoiceReader(Protocol):
    """Required capability for reading one structured invoice from bytes."""

    def __call__(self, data: bytes) -> StructuredInvoiceRecord:
        """Return application-owned facts or raise the application read error."""
        ...


__all__ = [
    "StructuredInvoiceClassification",
    "StructuredInvoiceClassificationKind",
    "StructuredInvoiceLine",
    "StructuredInvoiceReader",
    "StructuredInvoiceRecord",
]
