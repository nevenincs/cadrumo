"""Strict immutable models for the transaction catalogue.

Defines the boundary records that flow through the transaction
pipeline:

- :class:`Transaction` -- the immutable wrapper that preserves the
  upstream :class:`aeat.domain.transactions._raw_transaction.RawTransaction`
  verbatim and adds classification metadata.
- :class:`ClassificationHistoryEntry` -- one frozen record in the
  per-transaction classification chain.
- :class:`TransactionCatalogue` -- the immutable mapping keyed by
  ``transaction_id``.

Every model is strict + frozen + ``extra="forbid"``; no dataclasses;
no bare ``dict[str, Any]`` at the boundary.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, field_validator, model_validator

from .._identifiers import canonical_decimal_string
from ._enums import BusinessClassification, TransactionDirection
from ._errors import TransactionValidationError
from ._raw_transaction import RawTransaction

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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
            "amount": canonical_decimal_string(raw.amount),
            "narrative": raw.description,
            "provider_id": raw.transaction_id,
            "value_date": effective_value_date.isoformat(),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> str:
    """Serialize strict-python values into JSON-mode inputs for validation."""
    return str(value)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime string into an aware ``datetime``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _coerce_history(raw: Any) -> tuple[Any, ...]:
    """Freeze an inbound history sequence into a tuple; leave items for pydantic to validate."""
    if isinstance(raw, tuple):
        return raw
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes):
        return tuple(raw)
    raise TransactionValidationError("classification_history must be a sequence of history entries")


def _require_aware_datetime(value: datetime) -> datetime:
    """Reject naive ``classified_at`` timestamps; enum-safe for both models."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise TransactionValidationError("classified_at must be timezone-aware")
    return value


def _validate_classified_by_shape(value: str) -> str:
    """Restrict ``classified_by`` to ``auto`` / ``manual`` / ``rule:<id>`` / ``llm:<model>``.

    The ``llm:<model>`` shape lets an LLM classifier emit confidence
    scores alongside its predictions; the pipeline distinguishes its
    output from manual and rule-based decisions via this prefix.
    """
    normalized = value.strip()
    if normalized in {"auto", "manual"}:
        return normalized
    for prefix in ("rule:", "llm:"):
        if normalized.startswith(prefix) and normalized.removeprefix(prefix).strip():
            return normalized
    raise TransactionValidationError("classified_by must be 'auto', 'manual', 'rule:<rule-id>', or 'llm:<model>'")


_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")


def _validate_confidence_range(value: Decimal | None) -> Decimal | None:
    """Restrict confidence to the inclusive 0..1 range when not None."""
    if value is None:
        return None
    if not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
        raise TransactionValidationError("confidence must be within the inclusive 0..1 range")
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
            raise TransactionValidationError("business_pct is required when classification is MIXED")
        if not Decimal("0") <= pct <= Decimal("1"):
            raise TransactionValidationError("business_pct must be within 0..1 when classification is MIXED")
        return
    if pct is not None:
        raise TransactionValidationError("business_pct must be None unless classification is MIXED")


class ClassificationHistoryEntry(BaseModel):
    """One frozen record in a transaction's classification chain.

    The :attr:`confidence` and :attr:`provenance` fields are reserved
    extension points; today both default to ``None`` and future writers
    populate them without a schema bump because the field list is
    stable.

    Attributes:
        business_classification: The :class:`BusinessClassification`
            decided at this point in the chain.
        business_pct: Required when ``business_classification`` is
            :attr:`BusinessClassification.MIXED`; must be ``None``
            otherwise. Coupling enforced via
            :func:`_validate_business_pct_coupling`.
        classified_at: Timezone-aware UTC timestamp of the decision.
        classified_by: Classifier source string in the
            ``auto`` / ``manual`` / ``rule:<id>`` / ``llm:<model>``
            shape.
        reason: Free-text justification (may be empty).
        category_id: Optional :class:`aeat.domain.categories.SpendingCategory`
            foreign key.
        notes: Free-text notes (may be empty).
        confidence: Optional decision confidence in ``[0, 1]``.
        provenance: Optional reserved provenance payload; the pydantic
            type intentionally widens to a dict so future writers can
            replace it with a typed record without a breaking schema
            change.
    """

    model_config = _STRICT_FROZEN

    business_classification: BusinessClassification
    business_pct: Decimal | None = None
    classified_at: datetime
    classified_by: str = Field(min_length=1)
    reason: str = ""
    category_id: str | None = None
    notes: str = ""
    confidence: Decimal | None = None
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
            payload["business_classification"] = BusinessClassification(raw_state)
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

    @field_validator("category_id")
    @classmethod
    def _validate_category_id(cls, value: str | None) -> str | None:
        """Trim optional foreign key while rejecting blank strings."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("foreign-key identifiers must not be blank")
        return trimmed

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str) -> str:
        """Trim free-text notes while allowing the empty string."""
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
    """Immutable transaction wrapper that preserves raw provenance verbatim.

    Attributes:
        transaction_id: Lowercase 64-char SHA-256 derived deterministically
            from the wrapped raw record by :func:`derive_transaction_id`.
            Re-validated on every parse to detect tampering.
        raw: The verbatim
            :class:`aeat.domain.transactions._raw_transaction.RawTransaction`.
        direction: Closed :class:`TransactionDirection`.
        business_classification: Current :class:`BusinessClassification`
            decision; defaults to
            :attr:`BusinessClassification.NOT_YET_PROCESSED`.
        business_pct: Required when ``business_classification`` is
            :attr:`BusinessClassification.MIXED`; ``None`` otherwise.
        invoice_id: Optional invoice foreign key.
        category_id: Optional :class:`aeat.domain.categories.SpendingCategory`
            foreign key.
        notes: Free-text notes.
        classified_at: Timezone-aware timestamp of the active decision
            (``None`` when never classified).
        classified_by: Classifier source string for the active decision.
        classification_reason: Free-text reason for the active decision.
        classification_confidence: Optional confidence in ``[0, 1]`` for
            the active decision.
        classification_history: Tuple of historical
            :class:`ClassificationHistoryEntry` records, oldest first.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=64, max_length=64)
    raw: RawTransaction
    direction: TransactionDirection
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
    business_pct: Decimal | None = None
    invoice_id: str | None = None
    category_id: str | None = None
    notes: str = ""
    source_import_id: str | None = None
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
            raise TransactionValidationError("transaction_id must match the stable hash derived from raw")
        payload = dict(data)
        payload["raw"] = raw_transaction
        if isinstance(payload.get("direction"), str):
            payload["direction"] = TransactionDirection(payload["direction"])
        raw_state = payload.get("business_classification")
        if isinstance(raw_state, str):
            payload["business_classification"] = BusinessClassification(raw_state)
        if isinstance(payload.get("business_pct"), str):
            payload["business_pct"] = Decimal(payload["business_pct"])
        if isinstance(payload.get("classified_at"), str):
            payload["classified_at"] = _parse_datetime(payload["classified_at"])
        if isinstance(payload.get("classification_confidence"), str):
            payload["classification_confidence"] = Decimal(payload["classification_confidence"])
        history = payload.get("classification_history")
        if history is not None:
            payload["classification_history"] = _coerce_history(history)
        if "source_import_id" in payload and isinstance(payload["source_import_id"], str):
            normalized_import_id = payload["source_import_id"].strip()
            payload["source_import_id"] = normalized_import_id if normalized_import_id else None
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
            raise TransactionValidationError("foreign-key identifiers must not be blank")
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
    """Immutable catalogue keyed by ``transaction_id``.

    Attributes:
        transactions: Frozen :class:`types.MappingProxyType` from
            stable transaction id to :class:`Transaction`. Built via
            :meth:`from_transactions` or by passing a mapping / iterable
            to ``model_validate``.
    """

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
                    raise TransactionValidationError(f"duplicate transaction_id: {transaction.transaction_id}")
                transactions[transaction.transaction_id] = transaction
            return {"transactions": transactions}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        """Ensure every mapping key matches the embedded transaction ID."""
        for key, transaction in self.transactions.items():
            if key != transaction.transaction_id:
                raise TransactionValidationError(
                    f"catalogue key {key!r} does not match transaction_id {transaction.transaction_id!r}"
                )
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
