"""Validation helpers for strict transaction boundary models.

The transaction models keep their Pydantic validators on the boundary records,
while this helper module owns the reusable parsing and invariant checks those
validators call. It normalizes raw transactions, UTC timestamps, classifier
provenance, confidence ranges, identifier tuples, lineage text, and non-negative
tax amount fields without turning those rules into a separate public API.

See Also:
    :class:`~domain.transactions.Transaction`
        Strict transaction record whose validators delegate to these helpers.
    :class:`~domain.transactions.RawTransaction`
        Upstream row model accepted directly or coerced from JSON-compatible
        payloads.
    :class:`~domain.transactions.BusinessClassification`
        Classification enum coupled to ``business_pct`` by this module.
    :class:`~domain.transactions.TransactionValidationError`
        Typed domain error raised for validation failures.
    :func:`~core.time.validate_utc_aware`
        UTC-awareness gate wrapped into the transaction error hierarchy.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from pydantic import ValidationError

from ...core.errors.hierarchy import CoreValidationError
from ...core.external_constants import CLASSIFIED_BY_AUTO, CLASSIFIED_BY_MANUAL
from ...core.time import parse_iso_datetime, validate_utc_aware
from ...core.unit_proportion import is_unit_proportion
from .enums import BusinessClassification
from .errors import TransactionValidationError
from .raw_transaction import RawTransaction

_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")

_NON_NEGATIVE_DECIMAL_HINTS = {
    "taxable_base": (
        "taxable_base must be non-negative; it is the IVA-exclusive base amount, "
        "and the income/expense direction is taken from the transaction itself, "
        "not from the sign of this value"
    ),
    "iva_amount": "iva_amount must be non-negative; it is the IVA charged on the row, never a signed delta",
    "iva_rate": "iva_rate must be non-negative; express the rate as a fraction such as 0.21",
    "recargo_amount": (
        "recargo_amount must be non-negative; it is the recargo de equivalencia "
        "cuota the supplier charged on a repercutido sale to a recargo-regime "
        "retailer, never a signed delta"
    ),
}


def _json_default(value: object) -> str:
    return str(value)


def require_aware_datetime(value: datetime) -> datetime:
    """Return *value* if it is UTC-aware, as a transaction error if not.

    Delegates to the canonical awareness check and only translates the
    exception, so the rule stays in one place.
    """
    try:
        return validate_utc_aware(value)
    except CoreValidationError as exc:
        raise TransactionValidationError(str(exc)) from exc


def validate_classified_by_shape(value: str) -> str:
    """Return the classifier attribution if it names a recognised author."""
    normalized = value.strip()
    if normalized in {CLASSIFIED_BY_AUTO, CLASSIFIED_BY_MANUAL}:
        return normalized
    for prefix in ("rule:", "llm:", "derived:"):
        if normalized.startswith(prefix) and normalized.removeprefix(prefix).strip():
            return normalized
    raise TransactionValidationError(
        "classified_by must be 'auto', 'manual', 'rule:<rule-id>', 'llm:<model>', or 'derived:<basis>'",
    )


def validate_confidence_range(value: Decimal | None) -> Decimal | None:
    """Return a classifier confidence if it is a share of one, or None."""
    if value is None:
        return None
    if not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
        raise TransactionValidationError("confidence must be within the inclusive 0..1 range")
    return value


def validate_business_pct_coupling(
    state: BusinessClassification,
    pct: Decimal | None,
) -> None:
    """Refuse a business share that disagrees with its classification.

    A MIXED transaction must carry a share and any other classification must
    not, which is the coupling every write path checks.
    """
    if state is BusinessClassification.MIXED:
        if pct is None:
            raise TransactionValidationError("business_pct is required when classification is MIXED")
        if not is_unit_proportion(pct):
            raise TransactionValidationError("business_pct must be within 0..1 when classification is MIXED")
        return
    if pct is not None:
        raise TransactionValidationError("business_pct must be None unless classification is MIXED")


def normalize_identifier_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    """Return the identifiers stripped, refusing blanks and duplicates."""
    normalized = tuple(item.strip() for item in value if item.strip())
    if len(normalized) != len(value):
        raise TransactionValidationError("identifier fields must not contain blank values")
    if len(set(normalized)) != len(normalized):
        raise TransactionValidationError("identifier fields must not contain duplicates")
    return normalized


def trim_lineage_text(value: str | None) -> str | None:
    """Return lineage prose stripped, or None when it carries nothing."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise TransactionValidationError("lineage text fields must not be blank")
    return trimmed


def parse_required_aware_datetime(value: object, *, field_name: str) -> datetime:
    """Return *value* as a UTC-aware datetime, naming the field on refusal."""
    if isinstance(value, str):
        value = parse_iso_datetime(value)
    if not isinstance(value, datetime):
        raise TransactionValidationError(f"{field_name} must be a datetime")
    return require_aware_datetime(value)


def validate_non_negative_decimal(value: Decimal | None, *, field_name: str) -> Decimal | None:
    """Return *value* if it is not negative, naming the field on refusal."""
    if value is not None and value < Decimal("0"):
        raise TransactionValidationError(
            _NON_NEGATIVE_DECIMAL_HINTS.get(field_name, f"{field_name} must be non-negative"),
        )
    return value


def coerce_raw_transaction(raw: object) -> RawTransaction:
    """Return *raw* as a RawTransaction, accepting the model or its payload."""
    if isinstance(raw, RawTransaction):
        return raw
    try:
        return RawTransaction.model_validate(raw, strict=False)
    except ValidationError:
        return RawTransaction.model_validate_json(json.dumps(raw, default=_json_default, ensure_ascii=True))
