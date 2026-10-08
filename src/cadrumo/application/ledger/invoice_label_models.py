"""Shared value records for deterministic invoice-label reading."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .invoice_draft_records import DraftDiscrepancyFinding, FieldAmbiguityCandidate

HUNDRED = Decimal(100)


class InvoiceLabelParty(StrEnum):
    """Party roles represented by invoice headings and identifiers."""

    SUPPLIER = "supplier"
    CUSTOMER = "customer"


class InvoiceLabelKind(StrEnum):
    """Amount-label classes used by the deterministic text reader."""

    PAYABLE = "payable"
    IVA_TOTAL = "iva_total"
    BASE_TOTAL = "base_total"
    GRAND_TOTAL = "grand_total"
    RECARGO = "recargo"
    RETENCION = "retencion"
    SUPLIDOS = "suplidos"
    BASE = "base"
    RATE = "rate"
    IVA = "iva"
    INCLUDED = "included"


@dataclass
class PrintedValue[T]:
    """A normalized reading paired with the exact text that anchored it."""

    value: T
    anchor: str


@dataclass
class InvoiceLabelTier:
    """Printed base, rate, tax, and surcharge for one invoice tax tier."""

    rate: PrintedValue[Decimal] | None = None
    base: PrintedValue[Decimal] | None = None
    iva: PrintedValue[Decimal] | None = None
    re_rate: PrintedValue[Decimal] | None = None
    re_amount: PrintedValue[Decimal] | None = None


@dataclass
class InvoiceLabelCollection:
    """Every labelled occurrence, before any is accepted."""

    values: dict[str, list[PrintedValue[str]]] = field(default_factory=dict)
    amounts: dict[InvoiceLabelKind, list[tuple[PrintedValue[Decimal], PrintedValue[Decimal] | None]]] = field(
        default_factory=dict
    )
    rates: list[PrintedValue[Decimal]] = field(default_factory=list)
    ambiguous_amounts: dict[InvoiceLabelKind, list[str]] = field(default_factory=dict)
    table_tiers: list[InvoiceLabelTier] = field(default_factory=list)
    role_evidence: dict[str, str] = field(default_factory=dict)
    rejected_tax_ids: dict[str, str] = field(default_factory=dict)

    def add_value(self, name: str, value: str, anchor: str) -> None:
        """Append a textual observation without resolving competing values."""
        self.values.setdefault(name, []).append(PrintedValue(value, anchor))


@dataclass
class InvoiceLabelAssembly:
    """Accepted values and supporting evidence assembled from label readings."""

    values: dict[str, object] = field(default_factory=dict)
    anchors: dict[str, str] = field(default_factory=dict)
    role_evidence: dict[str, str] = field(default_factory=dict)
    ambiguities: dict[str, tuple[FieldAmbiguityCandidate, ...]] = field(default_factory=dict)
    derived: dict[str, tuple[str, ...]] = field(default_factory=dict)
    findings: list[DraftDiscrepancyFinding] = field(default_factory=list)

    def put(self, name: str, printed: PrintedValue[str] | PrintedValue[Decimal] | None) -> None:
        """Store a present reading and its printed anchor."""
        if printed is None:
            return
        self.values[name] = printed.value
        self.anchors[name] = printed.anchor

    def clear(self, *names: str) -> None:
        """Remove accepted values and their source metadata after a failed check."""
        for name in names:
            self.values.pop(name, None)
            self.anchors.pop(name, None)
            self.derived.pop(name, None)

    def value(self, name: str) -> Decimal | None:
        """Return an accepted decimal, excluding textual fields."""
        value = self.values.get(name)
        return value if isinstance(value, Decimal) else None


__all__ = [
    "HUNDRED",
    "InvoiceLabelAssembly",
    "InvoiceLabelCollection",
    "InvoiceLabelKind",
    "InvoiceLabelParty",
    "InvoiceLabelTier",
    "PrintedValue",
]
