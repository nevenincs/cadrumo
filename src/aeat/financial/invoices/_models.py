"""Strict immutable models for the invoice catalogue."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from ._enums import InvoiceKind, IvaRate, PaymentStatus, iva_rate_percentage
from ._validators import validate_country_code, validate_spanish_tax_id, validate_vat_number

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_LINE_TOLERANCE = Decimal("0.01")
_HEX_TRANSACTION_ID_LENGTH = 64
_HEX_INVOICE_ID_LENGTH = 64


def _canonical_decimal(value: Decimal) -> str:
    """Render a ``Decimal`` into a stable fixed-point string for hashing."""
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


def derive_invoice_id(
    *,
    kind: InvoiceKind,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str,
    currency: str,
    grand_total: Decimal,
) -> str:
    """Return the stable invoice hash for one invoice record.

    The digest is computed over a canonical JSON payload so that two
    invoices with equal logical identity produce identical IDs regardless
    of whitespace or numeric formatting.

    Args:
        kind: Invoice direction (issued / received).
        invoice_number: AEAT-significant invoice number as printed on the
            document.
        issued_at: ISO calendar date printed on the invoice.
        counterparty_tax_id: Counterparty NIF / NIE / CIF / VAT number
            already validated and uppercased.
        currency: ISO-4217 currency code already uppercased.
        grand_total: Invoice grand total.

    Returns:
        A lowercase SHA-256 digest that uniquely identifies the invoice.
    """
    payload = json.dumps(
        {
            "counterparty_tax_id": counterparty_tax_id,
            "currency": currency,
            "grand_total": _canonical_decimal(grand_total),
            "invoice_number": invoice_number,
            "issued_at": issued_at.isoformat(),
            "kind": kind.value,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_hex_digest(value: str, *, length: int) -> bool:
    return len(value) == length and all(char in "0123456789abcdef" for char in value)


def _coerce_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError("expected a Decimal, int, or str value")


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("expected a date or ISO-8601 string")


class InvoiceLine(BaseModel):
    """Immutable line item on an invoice."""

    model_config = _STRICT_FROZEN

    description: str = Field(min_length=1)
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    iva_rate: IvaRate
    iva_amount: Decimal
    category_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_inputs(cls, data: Any) -> Any:
        """Coerce JSON-decoded strings into their strict pydantic types."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        for key in ("quantity", "unit_price", "subtotal", "iva_amount"):
            if key in payload and not isinstance(payload[key], Decimal):
                payload[key] = _coerce_decimal(payload[key])
        if "iva_rate" in payload and isinstance(payload["iva_rate"], str):
            payload["iva_rate"] = IvaRate(payload["iva_rate"])
        return payload

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("description must not be blank")
        return trimmed

    @field_validator("category_id")
    @classmethod
    def _validate_category_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("category_id must not be blank")
        return trimmed

    @field_validator("quantity")
    @classmethod
    def _require_positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise ValueError("quantity must be strictly positive")
        return value

    @field_validator("unit_price", "subtotal", "iva_amount")
    @classmethod
    def _require_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("monetary value must be non-negative")
        return value

    @model_validator(mode="after")
    def _validate_arithmetic(self) -> Self:
        expected_subtotal = (self.quantity * self.unit_price).quantize(Decimal("0.0001"))
        if abs(self.subtotal - expected_subtotal) > _LINE_TOLERANCE:
            raise ValueError("subtotal must equal quantity * unit_price within 1 cent")
        rate = iva_rate_percentage(self.iva_rate)
        if rate is None:
            if self.iva_amount != Decimal("0"):
                raise ValueError("iva_amount must be zero for EXEMPT / NOT_SUBJECT lines")
        else:
            expected_iva = (self.subtotal * rate).quantize(Decimal("0.0001"))
            if abs(self.iva_amount - expected_iva) > _LINE_TOLERANCE:
                raise ValueError("iva_amount must equal subtotal * iva_rate within 1 cent")
        return self


class Invoice(BaseModel):
    """Strict frozen record for one issued or received invoice."""

    model_config = _STRICT_FROZEN

    invoice_id: str = Field(min_length=_HEX_INVOICE_ID_LENGTH, max_length=_HEX_INVOICE_ID_LENGTH)
    kind: InvoiceKind
    invoice_number: str = Field(min_length=1)
    issued_at: date
    counterparty_name: str = Field(min_length=1)
    counterparty_tax_id: str = Field(min_length=1)
    counterparty_country: str = Field(min_length=2, max_length=2)
    base_total: Decimal
    iva_total: Decimal
    grand_total: Decimal
    currency: str = Field(min_length=3, max_length=3)
    lines: tuple[InvoiceLine, ...]
    payment_status: PaymentStatus
    linked_transaction_ids: tuple[str, ...] = ()
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalise_and_derive_invoice_id(cls, data: Any) -> Any:
        """Canonicalise identity-bearing fields and derive ``invoice_id``."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)

        if "kind" in payload and isinstance(payload["kind"], str):
            payload["kind"] = InvoiceKind(payload["kind"])
        if "payment_status" in payload and isinstance(payload["payment_status"], str):
            payload["payment_status"] = PaymentStatus(payload["payment_status"])

        if "invoice_number" in payload and isinstance(payload["invoice_number"], str):
            payload["invoice_number"] = payload["invoice_number"].strip().upper()

        if "issued_at" in payload:
            payload["issued_at"] = _coerce_date(payload["issued_at"])

        if "counterparty_name" in payload and isinstance(payload["counterparty_name"], str):
            payload["counterparty_name"] = payload["counterparty_name"].strip()

        if "counterparty_country" in payload and isinstance(payload["counterparty_country"], str):
            payload["counterparty_country"] = validate_country_code(payload["counterparty_country"])

        if "counterparty_tax_id" in payload and isinstance(payload["counterparty_tax_id"], str):
            tax_id_raw = payload["counterparty_tax_id"].strip().upper()
            country = payload.get("counterparty_country")
            if isinstance(country, str) and country == "ES":
                payload["counterparty_tax_id"] = validate_spanish_tax_id(tax_id_raw)
            elif isinstance(country, str):
                payload["counterparty_tax_id"] = validate_vat_number(tax_id_raw, country)
            else:
                payload["counterparty_tax_id"] = tax_id_raw

        if "currency" in payload and isinstance(payload["currency"], str):
            currency_value = payload["currency"].strip().upper()
            if len(currency_value) != 3 or not currency_value.isalpha():
                raise ValueError("currency must be a three-letter ISO 4217 code")
            payload["currency"] = currency_value

        if "grand_total" in payload:
            payload["grand_total"] = _coerce_decimal(payload["grand_total"])
        if "base_total" in payload:
            payload["base_total"] = _coerce_decimal(payload["base_total"])
        if "iva_total" in payload:
            payload["iva_total"] = _coerce_decimal(payload["iva_total"])

        required_for_hash = {
            "kind",
            "invoice_number",
            "issued_at",
            "counterparty_tax_id",
            "currency",
            "grand_total",
        }
        if required_for_hash.issubset(payload):
            derived = derive_invoice_id(
                kind=payload["kind"],
                invoice_number=payload["invoice_number"],
                issued_at=payload["issued_at"],
                counterparty_tax_id=payload["counterparty_tax_id"],
                currency=payload["currency"],
                grand_total=payload["grand_total"],
            )
            existing = payload.get("invoice_id")
            if existing is not None and str(existing).strip().lower() != derived:
                raise ValueError("invoice_id must match the stable hash derived from identity fields")
            payload["invoice_id"] = derived

        if "linked_transaction_ids" in payload:
            payload["linked_transaction_ids"] = _normalise_linked_transaction_ids(payload["linked_transaction_ids"])

        if "notes" in payload and isinstance(payload["notes"], str):
            payload["notes"] = payload["notes"].strip()

        if (
            "lines" in payload
            and isinstance(payload["lines"], Sequence)
            and not isinstance(payload["lines"], str | bytes)
        ):
            payload["lines"] = tuple(payload["lines"])

        return payload

    @field_validator("base_total", "iva_total", "grand_total")
    @classmethod
    def _require_non_negative_totals(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("invoice totals must be non-negative")
        return value

    @field_validator("invoice_id")
    @classmethod
    def _validate_invoice_id_shape(cls, value: str) -> str:
        if not _is_hex_digest(value, length=_HEX_INVOICE_ID_LENGTH):
            raise ValueError("invoice_id must be a 64-character lowercase hex digest")
        return value

    @field_validator("lines")
    @classmethod
    def _require_lines(cls, value: tuple[InvoiceLine, ...]) -> tuple[InvoiceLine, ...]:
        if not value:
            raise ValueError("invoice must carry at least one line")
        return value

    @model_validator(mode="after")
    def _validate_totals_and_exempt_invariants(self) -> Self:
        line_subtotal_sum = sum((line.subtotal for line in self.lines), start=Decimal("0"))
        line_iva_sum = sum((line.iva_amount for line in self.lines), start=Decimal("0"))
        if self.base_total != line_subtotal_sum:
            raise ValueError("base_total must equal the exact sum of line subtotals")
        if self.iva_total != line_iva_sum:
            raise ValueError("iva_total must equal the exact sum of line iva amounts")
        if self.grand_total != self.base_total + self.iva_total:
            raise ValueError("grand_total must equal base_total + iva_total exactly")
        all_non_numeric = all(iva_rate_percentage(line.iva_rate) is None for line in self.lines)
        if all_non_numeric:
            if self.iva_total != Decimal("0"):
                raise ValueError("iva_total must be zero when every line is EXEMPT or NOT_SUBJECT")
            if self.grand_total != self.base_total:
                raise ValueError("grand_total must equal base_total when every line is EXEMPT or NOT_SUBJECT")
        return self


def _normalise_linked_transaction_ids(value: Any) -> tuple[str, ...]:
    """Deduplicate-preserve-order and validate the shape of linked transaction IDs."""
    if isinstance(value, str | bytes):
        raise ValueError("linked_transaction_ids must be a sequence of IDs, not a single string")
    if not isinstance(value, Iterable):
        raise ValueError("linked_transaction_ids must be iterable")
    seen: dict[str, None] = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError("each linked_transaction_id must be a string")
        normalized = item.strip().lower()
        if not _is_hex_digest(normalized, length=_HEX_TRANSACTION_ID_LENGTH):
            raise ValueError("each linked_transaction_id must be a 64-character lowercase hex digest")
        if normalized not in seen:
            seen[normalized] = None
    return tuple(seen.keys())


class InvoiceCatalogue(BaseModel):
    """Immutable invoice catalogue keyed by ``invoice_id``."""

    model_config = _STRICT_FROZEN

    invoices: Mapping[str, Invoice] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if isinstance(data, Mapping):
            if "invoices" in data:
                return data
            if all(isinstance(key, str) for key in data):
                return {"invoices": dict(data)}
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            invoices: dict[str, Invoice] = {}
            for item in data:
                invoice = item if isinstance(item, Invoice) else Invoice.model_validate(item)
                if invoice.invoice_id in invoices:
                    raise ValueError(f"duplicate invoice_id: {invoice.invoice_id}")
                invoices[invoice.invoice_id] = invoice
            return {"invoices": invoices}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        for key, invoice in self.invoices.items():
            if key != invoice.invoice_id:
                raise ValueError(f"catalogue key {key!r} does not match invoice_id {invoice.invoice_id!r}")
        return self

    @field_validator("invoices")
    @classmethod
    def _freeze_invoices(cls, value: Mapping[str, Invoice]) -> Mapping[str, Invoice]:
        return MappingProxyType(dict(value))

    @field_serializer("invoices")
    def _serialize_invoices(self, value: Mapping[str, Invoice]) -> dict[str, Invoice]:
        return dict(value)

    @classmethod
    def from_invoices(cls, invoices: Iterable[Invoice | Mapping[str, Any]]) -> Self:
        """Build an immutable catalogue from an iterable of invoices.

        Args:
            invoices: Invoices or invoice payloads to load.

        Returns:
            A validated immutable invoice catalogue.

        Raises:
            pydantic.ValidationError: If any invoice fails validation or a
                duplicate ``invoice_id`` is encountered.
        """
        return cls.model_validate(tuple(invoices))

    def __iter__(self):  # type: ignore[override]
        """Iterate over catalogue invoices."""
        return iter(self.invoices.values())

    def __len__(self) -> int:
        """Return the number of invoices in the catalogue."""
        return len(self.invoices)

    def __contains__(self, invoice_id: object) -> bool:
        """Return whether the catalogue contains ``invoice_id``."""
        if isinstance(invoice_id, Invoice):
            return invoice_id.invoice_id in self.invoices
        if isinstance(invoice_id, str):
            return invoice_id in self.invoices
        return False

    def get(self, invoice_id: str) -> Invoice | None:
        """Fetch one invoice by ID if present.

        Args:
            invoice_id: Stable invoice identifier.

        Returns:
            The matching invoice, or ``None`` when absent.
        """
        return self.invoices.get(invoice_id)

    def values(self) -> Iterator[Invoice]:
        """Iterate over catalogue invoices."""
        return iter(self.invoices.values())
