"""Strict immutable models for the invoice catalogue.

Defines the pydantic v2 records that back :mod:`aeat.domain.invoices`:
:class:`InvoiceLine`, :class:`Invoice`, and the keyed
:class:`InvoiceCatalogue`. Every model is strict, frozen, and forbids
extra fields; identity-bearing fields on :class:`Invoice` are
canonicalised in a ``model_validator`` and the stable
:attr:`Invoice.invoice_id` is derived via :func:`derive_invoice_id`.
Counterparty identity validation is delegated to
:mod:`aeat.domain.invoices._validators`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Self, override

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.decimal import coerce_decimal
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, validate_spanish_tax_id
from ...core.parsing._dates import _parse_iso8601_date
from .._identifiers import canonical_decimal_string
from ..iva import EUMemberState, InvoiceKind, IvaCategory, IvaRateKind, OssIossRegime, TransactionKind
from ._enums import IvaRate, PaymentStatus, iva_rate_percentage
from ._errors import InvoiceValidationError
from ._ids import InvoiceId

if TYPE_CHECKING:
    pass
from ._validators import (
    is_eu_member_state_code,
    validate_country_code,
    validate_iva_number,
)

_LINE_TOLERANCE = Decimal("0.01")


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
        counterparty_tax_id: Counterparty NIF / NIE / CIF / IVA number
            already validated and uppercased.
        currency: ISO-4217 currency code already uppercased.
        grand_total: Invoice grand total.

    Returns:
        A lowercase SHA-256 digest that uniquely identifies the invoice.
    """
    return content_hash_hex(
        {
            "counterparty_tax_id": counterparty_tax_id,
            "currency": currency,
            "grand_total": canonical_decimal_string(grand_total),
            "invoice_number": invoice_number,
            "issued_at": issued_at.isoformat(),
            "kind": kind.value,
        }
    )


def _is_hex_digest(value: str, *, length: int) -> bool:
    return len(value) == length and all(char in "0123456789abcdef" for char in value)


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            result = _parse_iso8601_date(value)
        except ValueError as exc:
            raise InvoiceValidationError(str(exc)) from exc
        if result is None:
            raise InvoiceValidationError("expected a date or ISO-8601 string")
        return result
    raise InvoiceValidationError("expected a date or ISO-8601 string")


def _normalise_invoice_enum_fields(payload: dict[str, object]) -> dict[str, object]:
    if "kind" in payload and isinstance(payload["kind"], str):
        try:
            payload["kind"] = InvoiceKind(payload["kind"])
        except ValueError as exc:
            raise InvoiceValidationError("kind must be an InvoiceKind") from exc
    if "payment_status" in payload and isinstance(payload["payment_status"], str):
        try:
            payload["payment_status"] = PaymentStatus(payload["payment_status"])
        except ValueError as exc:
            raise InvoiceValidationError("payment_status must be a PaymentStatus") from exc
    if "iva_category" in payload and isinstance(payload["iva_category"], str):
        stripped = payload["iva_category"].strip()
        if stripped:
            try:
                payload["iva_category"] = IvaCategory(stripped)
            except ValueError as exc:
                raise InvoiceValidationError("iva_category must be an IvaCategory") from exc
        else:
            payload["iva_category"] = None
    if "oss_ioss_regime" in payload and isinstance(payload["oss_ioss_regime"], str):
        stripped = payload["oss_ioss_regime"].strip()
        if stripped:
            try:
                payload["oss_ioss_regime"] = OssIossRegime(stripped)
            except ValueError as exc:
                raise InvoiceValidationError("oss_ioss_regime must be an OssIossRegime") from exc
        else:
            payload["oss_ioss_regime"] = None
    if "oss_transaction_kind" in payload and isinstance(payload["oss_transaction_kind"], str):
        stripped = payload["oss_transaction_kind"].strip()
        if stripped:
            try:
                payload["oss_transaction_kind"] = TransactionKind(stripped)
            except ValueError as exc:
                raise InvoiceValidationError("oss_transaction_kind must be a TransactionKind") from exc
        else:
            payload["oss_transaction_kind"] = None
    return payload


def _normalise_invoice_string_fields(payload: dict[str, object]) -> dict[str, object]:
    if "bucket_id" in payload and isinstance(payload["bucket_id"], str):
        normalized_bucket = payload["bucket_id"].strip()
        payload["bucket_id"] = normalized_bucket or None
    if "invoice_number" in payload and isinstance(payload["invoice_number"], str):
        payload["invoice_number"] = payload["invoice_number"].strip().upper()
    if "counterparty_name" in payload and isinstance(payload["counterparty_name"], str):
        payload["counterparty_name"] = payload["counterparty_name"].strip()
    if "notes" in payload and isinstance(payload["notes"], str):
        payload["notes"] = payload["notes"].strip()
    return payload


def _normalise_invoice_dates(payload: dict[str, object]) -> dict[str, object]:
    if "issued_at" in payload:
        payload["issued_at"] = _coerce_date(payload["issued_at"])
    return payload


def _normalise_invoice_counterparty(payload: dict[str, object]) -> dict[str, object]:
    if "counterparty_country" in payload and isinstance(payload["counterparty_country"], str):
        payload["counterparty_country"] = validate_country_code(payload["counterparty_country"])
    if "counterparty_tax_id" in payload and isinstance(payload["counterparty_tax_id"], str):
        tax_id_raw = payload["counterparty_tax_id"].strip().upper()
        country = payload.get("counterparty_country")
        if isinstance(country, str) and country == "ES":
            payload["counterparty_tax_id"] = validate_spanish_tax_id(tax_id_raw)
        elif isinstance(country, str):
            payload["counterparty_tax_id"] = validate_iva_number(tax_id_raw, country)
        else:
            payload["counterparty_tax_id"] = tax_id_raw
    return payload


def _normalise_invoice_currency(payload: dict[str, object]) -> dict[str, object]:
    if "currency" in payload and isinstance(payload["currency"], str):
        currency_value = payload["currency"].strip().upper()
        if len(currency_value) != 3 or not currency_value.isalpha():
            raise InvoiceValidationError("currency must be a three-letter ISO 4217 code")
        payload["currency"] = currency_value
    return payload


def _normalise_invoice_monetary_fields(payload: dict[str, object]) -> dict[str, object]:
    for key in ("grand_total", "base_total", "iva_total"):
        if key in payload:
            payload[key] = coerce_decimal(payload[key])
    for key in ("retention_rate", "retention_amount"):
        if key in payload and payload[key] is not None:
            payload[key] = coerce_decimal(payload[key])
    return payload


_INVOICE_ID_REQUIRED_FIELDS = frozenset(
    {
        "kind",
        "invoice_number",
        "issued_at",
        "counterparty_tax_id",
        "currency",
        "grand_total",
    },
)


def _derive_invoice_id_when_complete(payload: dict[str, object]) -> dict[str, object]:
    if not _INVOICE_ID_REQUIRED_FIELDS.issubset(payload):
        return payload
    kind = payload["kind"]
    invoice_number = payload["invoice_number"]
    issued_at = payload["issued_at"]
    counterparty_tax_id = payload["counterparty_tax_id"]
    currency = payload["currency"]
    grand_total = payload["grand_total"]
    if not isinstance(kind, InvoiceKind):
        raise InvoiceValidationError("kind must be an InvoiceKind")
    if not isinstance(invoice_number, str):
        raise InvoiceValidationError("invoice_number must be a string")
    if not isinstance(issued_at, date):
        raise InvoiceValidationError("issued_at must be a date")
    if not isinstance(counterparty_tax_id, str):
        raise InvoiceValidationError("counterparty_tax_id must be a string")
    if not isinstance(currency, str):
        raise InvoiceValidationError("currency must be a string")
    if not isinstance(grand_total, Decimal):
        raise InvoiceValidationError("grand_total must be a Decimal")
    derived = derive_invoice_id(
        kind=kind,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency=currency,
        grand_total=grand_total,
    )
    existing = payload.get("invoice_id")
    if existing is not None and str(existing).strip().lower() != derived:
        raise InvoiceValidationError("invoice_id must match the stable hash derived from identity fields")
    payload["invoice_id"] = derived
    return payload


def _normalise_invoice_collections(payload: dict[str, object]) -> dict[str, object]:
    if "linked_transaction_ids" in payload:
        payload["linked_transaction_ids"] = _normalise_linked_transaction_ids(payload["linked_transaction_ids"])
    if "lines" in payload and isinstance(payload["lines"], Sequence) and not isinstance(payload["lines"], str | bytes):
        payload["lines"] = tuple(payload["lines"])
    return payload


def _normalise_invoice_payment_id(payload: dict[str, object]) -> dict[str, object]:
    if "payment_id" not in payload or not isinstance(payload["payment_id"], str):
        return payload
    normalized = payload["payment_id"].strip().lower()
    if not normalized:
        payload["payment_id"] = None
        return payload
    if not _is_hex_digest(normalized, length=64):
        raise InvoiceValidationError("payment_id must be a 64-character lowercase hex digest")
    payload["payment_id"] = normalized
    return payload


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
    oss_rate_kind: IvaRateKind | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_inputs(cls, data: object) -> object:
        """Coerce JSON-decoded strings into their strict pydantic types."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        for key in ("quantity", "unit_price", "subtotal", "iva_amount"):
            if key in payload and not isinstance(payload[key], Decimal):
                payload[key] = coerce_decimal(payload[key])
        if "iva_rate" in payload and isinstance(payload["iva_rate"], str):
            payload["iva_rate"] = IvaRate(payload["iva_rate"])
        if "oss_rate_kind" in payload and isinstance(payload["oss_rate_kind"], str):
            stripped = payload["oss_rate_kind"].strip()
            payload["oss_rate_kind"] = IvaRateKind(stripped) if stripped else None
        return payload

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise InvoiceValidationError("description must not be blank")
        return trimmed

    @field_validator("category_id")
    @classmethod
    def _validate_category_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise InvoiceValidationError("category_id must not be blank")
        return trimmed

    @field_validator("quantity")
    @classmethod
    def _require_positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise InvoiceValidationError("quantity must be strictly positive")
        return value

    @field_validator("unit_price", "subtotal", "iva_amount")
    @classmethod
    def _require_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise InvoiceValidationError("monetary value must be non-negative")
        return value

    @model_validator(mode="after")
    def _validate_arithmetic(self) -> Self:
        expected_subtotal = (self.quantity * self.unit_price).quantize(Decimal("0.0001"))
        if abs(self.subtotal - expected_subtotal) > _LINE_TOLERANCE:
            raise InvoiceValidationError("subtotal must equal quantity * unit_price within 1 cent")
        rate = iva_rate_percentage(self.iva_rate)
        if self.oss_rate_kind is not None:
            return self
        if rate is None:
            if self.iva_amount != Decimal("0"):
                raise InvoiceValidationError("iva_amount must be zero for EXEMPT / NOT_SUBJECT lines")
        else:
            expected_iva = (self.subtotal * rate).quantize(Decimal("0.0001"))
            if abs(self.iva_amount - expected_iva) > _LINE_TOLERANCE:
                raise InvoiceValidationError("iva_amount must equal subtotal * iva_rate within 1 cent")
        return self


class Invoice(BaseModel):
    """Strict frozen record for one issued or received invoice."""

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    bucket_id: BucketId | None = Field(default=None)
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
    iva_category: IvaCategory | None = None
    oss_ioss_regime: OssIossRegime | None = None
    oss_transaction_kind: TransactionKind | None = None
    retention_rate: Decimal | None = None
    retention_amount: Decimal | None = None
    payment_id: str | None = None

    @override
    def __hash__(self) -> int:
        return hash(self.invoice_id)

    @model_validator(mode="before")
    @classmethod
    def _normalise_and_derive_invoice_id(cls, data: object) -> object:
        """Canonicalise identity-bearing fields and derive ``invoice_id``."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        payload = _normalise_invoice_enum_fields(payload)
        payload = _normalise_invoice_string_fields(payload)
        payload = _normalise_invoice_dates(payload)
        payload = _normalise_invoice_counterparty(payload)
        payload = _normalise_invoice_currency(payload)
        payload = _normalise_invoice_monetary_fields(payload)
        payload = _derive_invoice_id_when_complete(payload)
        payload = _normalise_invoice_collections(payload)
        payload = _normalise_invoice_payment_id(payload)
        return payload

    @field_validator("base_total", "iva_total", "grand_total")
    @classmethod
    def _require_non_negative_totals(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise InvoiceValidationError("invoice totals must be non-negative")
        return value

    @field_validator("lines")
    @classmethod
    def _require_lines(cls, value: tuple[InvoiceLine, ...]) -> tuple[InvoiceLine, ...]:
        if not value:
            raise InvoiceValidationError("invoice must carry at least one line")
        return value

    @model_validator(mode="after")
    def _validate_totals_and_exempt_invariants(self) -> Self:
        line_subtotal_sum = sum((line.subtotal for line in self.lines), start=Decimal("0"))
        line_iva_sum = sum((line.iva_amount for line in self.lines), start=Decimal("0"))
        if self.base_total != line_subtotal_sum:
            raise InvoiceValidationError("base_total must equal the exact sum of line subtotals")
        if self.iva_total != line_iva_sum:
            raise InvoiceValidationError("iva_total must equal the exact sum of line iva amounts")
        if self.grand_total != self.base_total + self.iva_total:
            raise InvoiceValidationError("grand_total must equal base_total + iva_total exactly")
        all_non_numeric = all(iva_rate_percentage(line.iva_rate) is None for line in self.lines)
        if all_non_numeric:
            if self.iva_total != Decimal("0"):
                raise InvoiceValidationError("iva_total must be zero when every line is EXEMPT or NOT_SUBJECT")
            if self.grand_total != self.base_total:
                raise InvoiceValidationError(
                    "grand_total must equal base_total when every line is EXEMPT or NOT_SUBJECT",
                )
        return self

    @model_validator(mode="after")
    def _validate_oss_ioss_axes(self) -> Self:
        """Validate the optional OSS/IOSS projection axes used by Modelo 369."""
        has_oss_line_rate = any(line.oss_rate_kind is not None for line in self.lines)
        if self.oss_ioss_regime is None and self.oss_transaction_kind is None:
            if has_oss_line_rate:
                raise InvoiceValidationError("oss_rate_kind requires invoice-level OSS/IOSS axes")
            return self
        if self.oss_ioss_regime is None or self.oss_transaction_kind is None:
            raise InvoiceValidationError("oss_ioss_regime and oss_transaction_kind must be supplied together")
        if self.kind is not InvoiceKind.ISSUED:
            raise InvoiceValidationError("OSS/IOSS invoice projection only applies to issued invoices")
        if self.counterparty_eu_member_state is None:
            raise InvoiceValidationError("OSS/IOSS invoice projection requires an EU destination member state")

        allowed_kinds_by_regime: Mapping[OssIossRegime, frozenset[TransactionKind]] = {
            OssIossRegime.EXTERNAL_SCHEME: frozenset({TransactionKind.EXTERNAL_SCHEME_SERVICES}),
            OssIossRegime.UNION_SCHEME: frozenset(
                {
                    TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
                    TransactionKind.OSS_UNION_GOODS_INTERFACE_FACILITATED,
                    TransactionKind.OSS_UNION_SERVICES,
                },
            ),
            OssIossRegime.IMPORT_SCHEME: frozenset({TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE}),
        }
        if self.oss_transaction_kind not in allowed_kinds_by_regime[self.oss_ioss_regime]:
            raise InvoiceValidationError("oss_transaction_kind is not valid for the supplied oss_ioss_regime")
        return self

    @property
    def counterparty_eu_member_state(self) -> EUMemberState | None:
        """Return the substrate-typed EUMemberState for the counterparty, or ``None`` for non-EU.

        :attr:`counterparty_country` carries the raw uppercase ISO-3166-1
        alpha-2 code (validated at construction time). This typed
        accessor lets downstream consumers (Modelo 369 OSS bindings,
        intra-community classification, OSS classifier dispatch) work
        with the closed substrate enum without a per-call lowercase /
        membership check. Anchored to
        :data:`aeat.domain.invoices.EU_MEMBER_STATE_CODES` which
        derives from :class:`aeat.domain.iva.EUMemberState`.
        """
        if not is_eu_member_state_code(self.counterparty_country):
            return None
        return EUMemberState(self.counterparty_country.lower())

    @property
    def counterparty_is_eu_member(self) -> bool:
        """Return ``True`` iff the counterparty is in one of the 27 EU Member States.

        Convenience predicate keyed off the substrate enum; equivalent
        to ``invoice.counterparty_eu_member_state is not None``.
        Modelo classification routes (OSS / IOSS / intra-community)
        gate on this predicate to decide which substrate flow path
        applies.
        """
        return self.counterparty_eu_member_state is not None


def _normalise_linked_transaction_ids(value: object) -> tuple[str, ...]:
    """Deduplicate-preserve-order and validate the shape of linked transaction IDs."""
    if isinstance(value, str | bytes):
        raise InvoiceValidationError("linked_transaction_ids must be a sequence of IDs, not a single string")
    if not isinstance(value, Iterable):
        raise InvoiceValidationError("linked_transaction_ids must be iterable")
    seen: dict[str, None] = {}
    for item in value:
        if not isinstance(item, str):
            raise InvoiceValidationError("each linked_transaction_id must be a string")
        normalized = item.strip().lower()
        if not _is_hex_digest(normalized, length=64):
            raise InvoiceValidationError("each linked_transaction_id must be a 64-character lowercase hex digest")
        if normalized not in seen:
            seen[normalized] = None
    return tuple(seen.keys())


class InvoiceCatalogue(BaseModel):
    """Immutable invoice catalogue keyed by ``invoice_id``."""

    model_config = _STRICT_FROZEN

    invoices: Mapping[str, Invoice] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: object) -> object:
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
                    raise InvoiceValidationError(f"duplicate invoice_id: {invoice.invoice_id}")
                invoices[invoice.invoice_id] = invoice
            return {"invoices": invoices}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        for key, invoice in self.invoices.items():
            if key != invoice.invoice_id:
                raise InvoiceValidationError(f"catalogue key {key!r} does not match invoice_id {invoice.invoice_id!r}")
        return self

    @field_validator("invoices")
    @classmethod
    def _freeze_invoices(cls, value: Mapping[str, Invoice]) -> Mapping[str, Invoice]:
        return MappingProxyType(dict(value))

    @field_serializer("invoices")
    def _serialize_invoices(self, value: Mapping[str, Invoice]) -> dict[str, Invoice]:
        return dict(value)

    @classmethod
    def from_invoices(cls, invoices: Iterable[Invoice | Mapping[str, object]]) -> Self:
        """Build an immutable catalogue from an iterable of invoices.

        Args:
            invoices: Invoices or invoice payloads to load.

        Returns:
            A validated immutable invoice catalogue.
        """
        return cls.model_validate(tuple(invoices))

    @override
    def __iter__(self) -> Iterator[Invoice]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
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
            The matching :class:`Invoice`, or ``None`` when absent.
        """
        return self.invoices.get(invoice_id)

    def values(self) -> Iterator[Invoice]:
        """Iterate over catalogue :class:`Invoice` records."""
        return iter(self.invoices.values())
