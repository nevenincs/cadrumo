"""Strict immutable models for the transaction catalogue."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, field_validator, model_validator

from ...logging import get_logger
from ..providers import RawTransaction
from ._enums import LEGACY_UNCLASSIFIED_ALIAS, BusinessClassification, TransactionDirection

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_LOGGER = get_logger(__name__)
# Module-local flag so the legacy-alias INFO line fires at most once per process.
# Wrapped in a list to permit mutation from helper functions without ``global``.
_LEGACY_ALIAS_LOGGED: list[bool] = [False]


def derive_transaction_id(raw: RawTransaction) -> str:
    """Return the stable transaction hash for one raw transaction.

    Args:
        raw: The upstream immutable raw transaction emitted by a provider.

    Returns:
        A lowercase SHA-256 digest derived from the provider identity,
        effective value date, amount, and narrative fields.
    """
    effective_value_date = raw.value_date or raw.booked_date
    payload = json.dumps(
        {
            "amount": _canonical_decimal(raw.amount),
            "narrative": raw.description,
            "provider_id": raw.transaction_id,
            "value_date": effective_value_date.isoformat(),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_decimal(value: Decimal) -> str:
    """Render a ``Decimal`` into a stable fixed-point string."""
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


def _json_default(value: Any) -> str:
    """Serialize strict-python values into JSON-mode inputs for validation."""
    return str(value)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime string into an aware ``datetime``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _coerce_classification_state(raw: str) -> BusinessClassification:
    """Coerce a string classification value, normalising the legacy alias.

    Pre-#237 catalogues stored the literal ``"UNCLASSIFIED"``. New
    enum members do not include that value, so the loader normalises
    it to ``NOT_YET_PROCESSED`` and logs one INFO line per process so
    Kent knows to re-save his catalogue.
    """
    if raw == LEGACY_UNCLASSIFIED_ALIAS:
        if not _LEGACY_ALIAS_LOGGED[0]:
            _LOGGER.info(
                "legacy classification value 'UNCLASSIFIED' aliased to 'NOT_YET_PROCESSED' "
                "(issue #237). Re-save the catalogue to migrate."
            )
            _LEGACY_ALIAS_LOGGED[0] = True
        return BusinessClassification.NOT_YET_PROCESSED
    return BusinessClassification(raw)


def _coerce_history(raw: Any) -> tuple[Any, ...]:
    """Freeze an inbound history sequence into a tuple; leave items for pydantic to validate."""
    if isinstance(raw, tuple):
        return raw
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes):
        return tuple(raw)
    raise ValueError("classification_history must be a sequence of history entries")


def _require_aware_datetime(value: datetime) -> datetime:
    """Reject naive ``classified_at`` timestamps; enum-safe for both models."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("classified_at must be timezone-aware")
    return value


def _validate_classified_by_shape(value: str) -> str:
    """Restrict ``classified_by`` to ``auto`` / ``manual`` / ``rule:<rule-id>``."""
    normalized = value.strip()
    if normalized in {"auto", "manual"}:
        return normalized
    if normalized.startswith("rule:") and normalized.removeprefix("rule:").strip():
        return normalized
    raise ValueError("classified_by must be 'auto', 'manual', or 'rule:<rule-id>'")


_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")


def _validate_confidence_range(value: Decimal | None) -> Decimal | None:
    """Restrict confidence to the inclusive 0..1 range when not None."""
    if value is None:
        return None
    if not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
        raise ValueError("confidence must be within the inclusive 0..1 range")
    return value


def _validate_business_pct_coupling(
    state: BusinessClassification,
    pct: Decimal | None,
) -> None:
    """Enforce the classification/business-percentage coupling rule.

    Raises ``ValueError`` when the pct field is set without ``MIXED``,
    missing for ``MIXED``, or outside the inclusive 0..1 range.
    """
    if state is BusinessClassification.MIXED:
        if pct is None:
            raise ValueError("business_pct is required when classification is MIXED")
        if not Decimal("0") <= pct <= Decimal("1"):
            raise ValueError("business_pct must be within 0..1 when classification is MIXED")
        return
    if pct is not None:
        raise ValueError("business_pct must be None unless classification is MIXED")


class ClassificationHistoryEntry(BaseModel):
    """One frozen record in a transaction's classification chain.

    Reserved `confidence` and `provenance` slots anticipate issue #236
    (decision confidence and `DecisionProvenance`). Today both default to
    ``None``; future writers populate them without a schema bump because
    the field list is stable.
    """

    model_config = _STRICT_FROZEN

    business_classification: BusinessClassification
    business_pct: Decimal | None = None
    classified_at: datetime
    classified_by: str = Field(min_length=1)
    reason: str = ""
    confidence: Decimal | None = None
    # Placeholder for the future ``DecisionProvenance`` pydantic record added
    # by issue #236. Because this model declares ``extra="forbid"``, the next
    # ADR must widen this type via a compatible union (``dict[str, Any] |
    # DecisionProvenance | None``) rather than swap it, so payloads written
    # under #237 keep validating once #236 lands.
    provenance: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_inbound(cls, data: Any) -> Any:
        """Parse JSON-mode strings back into strict Python types on load."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        raw_state = payload.get("business_classification")
        if isinstance(raw_state, str):
            payload["business_classification"] = _coerce_classification_state(raw_state)
        if isinstance(payload.get("business_pct"), str):
            payload["business_pct"] = Decimal(payload["business_pct"])
        if isinstance(payload.get("classified_at"), str):
            payload["classified_at"] = _parse_datetime(payload["classified_at"])
        if isinstance(payload.get("confidence"), str):
            payload["confidence"] = Decimal(payload["confidence"])
        return payload

    @field_validator("classified_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        """Reject naive classification timestamps."""
        return _require_aware_datetime(value)

    @field_validator("classified_by")
    @classmethod
    def _validate_classified_by(cls, value: str) -> str:
        """Restrict ``classified_by`` to the approved shapes."""
        return _validate_classified_by_shape(value)

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        """Trim free-text reasons while allowing the empty string."""
        return value.strip()

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: Decimal | None) -> Decimal | None:
        """Restrict confidence to the inclusive 0..1 range when not None."""
        return _validate_confidence_range(value)

    @model_validator(mode="after")
    def _enforce_business_pct(self) -> Self:
        """Enforce the classification/business percentage coupling for a history entry."""
        _validate_business_pct_coupling(self.business_classification, self.business_pct)
        return self


class Transaction(BaseModel):
    """Immutable transaction wrapper that preserves raw provenance verbatim."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=64, max_length=64)
    raw: RawTransaction
    direction: TransactionDirection
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
    business_pct: Decimal | None = None
    invoice_id: str | None = None
    category_id: str | None = None
    notes: str = ""
    classified_at: datetime | None = None
    classified_by: str = Field(default="auto", min_length=1)
    classification_reason: str = ""
    classification_confidence: Decimal | None = None
    classification_history: tuple[ClassificationHistoryEntry, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _enforce_derived_transaction_id(cls, data: Any) -> Any:
        """Compute or validate ``transaction_id`` from the wrapped raw record."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping) or "raw" not in data:
            return data
        raw = data["raw"]
        if isinstance(raw, RawTransaction):
            raw_transaction = raw
        else:
            try:
                raw_transaction = RawTransaction.model_validate(raw)
            except ValidationError:
                raw_transaction = RawTransaction.model_validate_json(
                    json.dumps(raw, default=_json_default, ensure_ascii=True)
                )
        derived = derive_transaction_id(raw_transaction)
        existing = data.get("transaction_id")
        if existing is not None and str(existing).strip() != derived:
            raise ValueError("transaction_id must match the stable hash derived from raw")
        payload = dict(data)
        payload["raw"] = raw_transaction
        if isinstance(payload.get("direction"), str):
            payload["direction"] = TransactionDirection(payload["direction"])
        raw_state = payload.get("business_classification")
        if isinstance(raw_state, str):
            payload["business_classification"] = _coerce_classification_state(raw_state)
        if isinstance(payload.get("business_pct"), str):
            payload["business_pct"] = Decimal(payload["business_pct"])
        if isinstance(payload.get("classified_at"), str):
            payload["classified_at"] = _parse_datetime(payload["classified_at"])
        if isinstance(payload.get("classification_confidence"), str):
            payload["classification_confidence"] = Decimal(payload["classification_confidence"])
        history = payload.get("classification_history")
        if history is not None:
            payload["classification_history"] = _coerce_history(history)
        payload["transaction_id"] = derived
        return payload

    @field_validator("invoice_id", "category_id")
    @classmethod
    def _validate_optional_ids(cls, value: str | None) -> str | None:
        """Trim optional foreign keys while rejecting blank strings."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("foreign-key identifiers must not be blank")
        return trimmed

    @field_validator("notes", "classification_reason")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        """Trim free-text fields while allowing the empty string."""
        return value.strip()

    @field_validator("classified_by")
    @classmethod
    def _validate_classified_by(cls, value: str) -> str:
        """Restrict ``classified_by`` to the approved shapes."""
        return _validate_classified_by_shape(value)

    @field_validator("classified_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        """Reject naive classification timestamps; ``None`` remains valid here."""
        if value is None:
            return None
        return _require_aware_datetime(value)

    @field_validator("classification_confidence")
    @classmethod
    def _validate_classification_confidence(cls, value: Decimal | None) -> Decimal | None:
        """Restrict classification_confidence to the inclusive 0..1 range when not None."""
        return _validate_confidence_range(value)

    @model_validator(mode="after")
    def _enforce_business_pct(self) -> Self:
        """Enforce the classification/business percentage coupling."""
        _validate_business_pct_coupling(self.business_classification, self.business_pct)
        return self


class TransactionCatalogue(BaseModel):
    """Immutable catalogue keyed by ``transaction_id``."""

    model_config = _STRICT_FROZEN

    transactions: Mapping[str, Transaction] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: Any) -> Any:
        """Accept either a bare mapping or an iterable of transactions."""
        if isinstance(data, cls):
            return data
        if isinstance(data, Mapping):
            if "transactions" in data:
                return data
            if all(isinstance(key, str) for key in data):
                return {"transactions": dict(data)}
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            transactions: dict[str, Transaction] = {}
            for item in data:
                transaction = item if isinstance(item, Transaction) else Transaction.model_validate(item)
                if transaction.transaction_id in transactions:
                    raise ValueError(f"duplicate transaction_id: {transaction.transaction_id}")
                transactions[transaction.transaction_id] = transaction
            return {"transactions": transactions}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        """Ensure every mapping key matches the embedded transaction ID."""
        for key, transaction in self.transactions.items():
            if key != transaction.transaction_id:
                raise ValueError(f"catalogue key {key!r} does not match transaction_id {transaction.transaction_id!r}")
        return self

    @field_validator("transactions")
    @classmethod
    def _freeze_transactions(cls, value: Mapping[str, Transaction]) -> Mapping[str, Transaction]:
        """Freeze the catalogue mapping to preserve immutability."""
        return MappingProxyType(dict(value))

    @field_serializer("transactions")
    def _serialize_transactions(self, value: Mapping[str, Transaction]) -> dict[str, Transaction]:
        """Serialize the immutable mapping back to a JSON object."""
        return dict(value)

    @classmethod
    def from_transactions(cls, transactions: Iterable[Transaction | Mapping[str, Any]]) -> Self:
        """Build a catalogue from an iterable of transactions.

        Args:
            transactions: Transactions or transaction payloads to load.

        Returns:
            A validated immutable transaction catalogue.
        """
        return cls.model_validate(tuple(transactions))

    def __iter__(self):  # type: ignore[override]
        """Iterate over catalogue transactions."""
        return iter(self.transactions.values())

    def __len__(self) -> int:
        """Return the number of transactions in the catalogue."""
        return len(self.transactions)

    def __contains__(self, transaction_id: object) -> bool:
        """Return whether the catalogue contains ``transaction_id``."""
        if isinstance(transaction_id, Transaction):
            return transaction_id.transaction_id in self.transactions
        if isinstance(transaction_id, str):
            return transaction_id in self.transactions
        return False

    def get(self, transaction_id: str) -> Transaction | None:
        """Fetch one transaction by ID if present.

        Args:
            transaction_id: Stable transaction identifier.

        Returns:
            The matching transaction, or ``None`` when absent.
        """
        return self.transactions.get(transaction_id)

    def values(self) -> Iterator[Transaction]:
        """Iterate over catalogue transactions."""
        return iter(self.transactions.values())
