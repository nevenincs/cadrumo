"""Deserialisation-boundary coercion for raw invoice payloads.

:class:`~domain.invoices.Invoice` is strict and frozen, so a payload arriving
from storage or a CLI boundary carries plain strings where the model declares
enums, and untrimmed text where it declares canonical values. These helpers are
the one place that gap is closed, before pydantic sees the mapping.

They are declared as rules rather than as one branch per field. Each field
differed only in its key, its target type, its refusal wording, its casing and
whether a blank means absence -- so as straight-line code the differences that
matter were the easiest thing to miss, and the shared shape was invisible.

The blank-handling axis is the load-bearing one. A field that is
``absent_when_blank`` treats the empty string as the same absence a missing key
is: an empty string is not a Member State, an IVA category or an OSS regime, and
must not become one. A field without it is required, so a blank is a value its
enum rejects, which is the refusal the caller wants.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Final, NamedTuple

from ...core import IntracomOperationType
from ..iva import (
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    OssIossRegime,
    TransactionKind,
)
from .enums import (
    InvoiceClass,
    InvoiceLegalMention,
    InvoiceOperationDateRole,
    PaymentStatus,
)
from .errors import InvoiceValidationError

__all__ = ["normalise_invoice_enum_fields", "normalise_invoice_string_fields"]


class _EnumFieldRule(NamedTuple):
    """How one raw payload string becomes its typed enum member."""

    field: str
    enum: type[StrEnum]
    message: str
    absent_when_blank: bool = False
    normalise: Callable[[str], str] | None = None


class _StringFieldRule(NamedTuple):
    """How one raw payload string is canonicalised before the model sees it."""

    field: str
    uppercase: bool = False
    absent_when_blank: bool = False


def _normalise_eu_member_state(value: str) -> str:
    """Return the canonical lower-case member-state code from raw input."""
    return value.strip().lower()


def _normalise_intracom_operation_type(value: str) -> str:
    """Return the canonical upper-case intracom operation code from raw input."""
    return value.strip().upper()


_ENUM_FIELD_RULES: Final[tuple[_EnumFieldRule, ...]] = (
    _EnumFieldRule("kind", InvoiceKind, "kind must be an InvoiceKind"),
    _EnumFieldRule("payment_status", PaymentStatus, "payment_status must be a PaymentStatus"),
    _EnumFieldRule("invoice_class", InvoiceClass, "invoice_class must be an InvoiceClass"),
    _EnumFieldRule(
        "operation_date_role",
        InvoiceOperationDateRole,
        "operation_date_role must be an InvoiceOperationDateRole",
        absent_when_blank=True,
        normalise=str.strip,
    ),
    _EnumFieldRule(
        "counterparty_identification_state",
        EUMemberState,
        "counterparty_identification_state must be an EUMemberState",
        absent_when_blank=True,
        normalise=_normalise_eu_member_state,
    ),
    _EnumFieldRule(
        "iva_category",
        IvaCategory,
        "iva_category must be an IvaCategory",
        absent_when_blank=True,
        normalise=str.strip,
    ),
    _EnumFieldRule(
        "operation_type",
        IntracomOperationType,
        "operation_type must be an IntracomOperationType",
        absent_when_blank=True,
        normalise=_normalise_intracom_operation_type,
    ),
    _EnumFieldRule(
        "oss_ioss_regime",
        OssIossRegime,
        "oss_ioss_regime must be an OssIossRegime",
        absent_when_blank=True,
        normalise=str.strip,
    ),
    _EnumFieldRule(
        "oss_transaction_kind",
        TransactionKind,
        "oss_transaction_kind must be a TransactionKind",
        absent_when_blank=True,
        normalise=str.strip,
    ),
)

_STRING_FIELD_RULES: Final[tuple[_StringFieldRule, ...]] = (
    _StringFieldRule("bucket_id", absent_when_blank=True),
    _StringFieldRule("invoice_number", uppercase=True),
    _StringFieldRule("counterparty_name"),
    _StringFieldRule("notes"),
    _StringFieldRule("series", absent_when_blank=True),
    _StringFieldRule("issuer_address", absent_when_blank=True),
    _StringFieldRule("recipient_address", absent_when_blank=True),
    _StringFieldRule("exemption_reference", absent_when_blank=True),
    _StringFieldRule("rectifies_invoice_number", uppercase=True, absent_when_blank=True),
)


def _coerce_enum_field(payload: dict[str, object], rule: _EnumFieldRule) -> None:
    """Coerce one enum-typed payload field in place, per its rule."""
    raw = payload.get(rule.field)
    if not isinstance(raw, str):
        return
    text = rule.normalise(raw) if rule.normalise is not None else raw
    if rule.absent_when_blank and not text:
        payload[rule.field] = None
        return
    try:
        payload[rule.field] = rule.enum(text)
    except ValueError as exc:
        raise InvoiceValidationError(rule.message) from exc


def _coerce_legal_mentions(payload: dict[str, object]) -> None:
    """Coerce the legal-mention sequence in place.

    Kept as its own branch rather than folded into the rule table: this field is
    a SEQUENCE whose entries may already be typed, so it has no single raw
    string to normalise and no blank case to decide.
    """
    if "legal_mentions" not in payload:
        return
    raw_mentions = payload["legal_mentions"]
    if not isinstance(raw_mentions, Sequence) or isinstance(raw_mentions, str | bytes):
        return
    coerced: list[InvoiceLegalMention] = []
    # Deserialisation boundary: the payload is a raw mapping, so the narrowed
    # sequence carries no element type. Each entry is inspected by isinstance
    # below before anything is read off it.
    entries: Sequence[object] = raw_mentions  # pyright: ignore[reportUnknownVariableType]  # reason: deserialisation boundary, the payload sequence carries no element type and every entry is isinstance-checked below
    for entry in entries:
        if isinstance(entry, InvoiceLegalMention):
            coerced.append(entry)
            continue
        if not isinstance(entry, str):
            raise InvoiceValidationError("legal_mentions entries must be an InvoiceLegalMention or its value")
        try:
            coerced.append(InvoiceLegalMention(entry))
        except ValueError as exc:
            raise InvoiceValidationError("legal_mentions entries must be an InvoiceLegalMention") from exc
    payload["legal_mentions"] = tuple(coerced)


def normalise_invoice_enum_fields(payload: dict[str, object]) -> dict[str, object]:
    """Coerce every enum-typed invoice payload field, refusing off-catalogue values."""
    for rule in _ENUM_FIELD_RULES:
        _coerce_enum_field(payload, rule)
    _coerce_legal_mentions(payload)
    return payload


def normalise_invoice_string_fields(payload: dict[str, object]) -> dict[str, object]:
    """Canonicalise every free-text invoice payload field."""
    for rule in _STRING_FIELD_RULES:
        raw = payload.get(rule.field)
        if not isinstance(raw, str):
            continue
        text = raw.strip().upper() if rule.uppercase else raw.strip()
        payload[rule.field] = (text or None) if rule.absent_when_blank else text
    return payload
