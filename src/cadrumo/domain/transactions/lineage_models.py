"""Immutable transaction provenance and split-lineage models."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self, TypeGuard

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from ...core.hashing import sha256_hex
from ...core.hex import Hex64Str
from ...core.identity import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.utc import UtcInstant, parse_iso_datetime
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER
from ..identifiers import canonical_decimal_string
from .enums import BusinessClassification, SplitRole, TransactionLifecycleState
from .errors import TransactionValidationError
from .model_validation import (
    parse_required_aware_datetime,
    require_aware_datetime,
    trim_lineage_text,
    validate_business_pct_coupling,
    validate_classified_by_shape,
    validate_confidence_range,
)

_STRING_KEYED_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object],
    config=ConfigDict(strict=True),
)


def _string_keyed_mapping(data: object) -> dict[str, object]:
    """Materialize an untrusted mapping after enforcing JSON-object keys."""
    try:
        return _STRING_KEYED_MAPPING_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise TransactionValidationError("transaction payload keys must be strings") from exc


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """Narrow an unparameterized runtime mapping to untrusted object entries."""
    return isinstance(value, Mapping)


class DecisionProvenance(BaseModel):
    """Typed provenance for one classification decision."""

    model_config = _STRICT_FROZEN

    decided_by: str = Field(min_length=1, max_length=128)
    decided_at: UtcInstant
    reason: str = ""
    confidence: Decimal | None = None
    manual_override: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce_inbound(cls, data: object) -> object:
        """Parse JSON-mode confidence strings back into ``Decimal`` on load."""
        if isinstance(data, cls):
            return data
        if not _is_object_mapping(data):
            return data
        payload = _string_keyed_mapping(data)
        raw_confidence = payload.get("confidence")
        if isinstance(raw_confidence, str):
            payload["confidence"] = Decimal(raw_confidence)
        return payload

    @field_validator("decided_by")
    @classmethod
    def _validate_decided_by(cls, value: str) -> str:
        """Restrict ``decided_by`` to the approved classifier shapes."""
        return validate_classified_by_shape(value)

    @field_validator("decided_at", mode="before")
    @classmethod
    def _parse_decided_at(cls, value: object) -> datetime:
        """Reject naive or blank decision timestamps."""
        return parse_required_aware_datetime(value, field_name="decided_at")

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        """Trim the free-text reason while allowing the empty string."""
        return value.strip()

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: Decimal | None) -> Decimal | None:
        """Restrict confidence to the inclusive 0..1 range when not None."""
        return validate_confidence_range(value)


class ClassificationHistoryEntry(BaseModel):
    """One frozen record in a transaction's classification chain."""

    model_config = _STRICT_FROZEN

    business_classification: BusinessClassification
    business_pct: Decimal | None = None
    classified_at: UtcInstant
    classified_by: str = Field(min_length=1)
    reason: str = ""
    category_id: str | None = None
    notes: str = ""
    confidence: Decimal | None = None
    provenance: DecisionProvenance | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_inbound(cls, data: object) -> object:
        """Parse JSON-mode strings back into strict Python types on load."""
        if isinstance(data, cls):
            return data
        if not _is_object_mapping(data):
            return data
        payload = _string_keyed_mapping(data)
        raw_state = payload.get("business_classification")
        if isinstance(raw_state, str):
            payload["business_classification"] = BusinessClassification(raw_state)
        raw_business_pct = payload.get("business_pct")
        if isinstance(raw_business_pct, str):
            payload["business_pct"] = Decimal(raw_business_pct)
        raw_classified_at = payload.get("classified_at")
        if isinstance(raw_classified_at, str):
            payload["classified_at"] = parse_iso_datetime(raw_classified_at)
        raw_confidence = payload.get("confidence")
        if isinstance(raw_confidence, str):
            payload["confidence"] = Decimal(raw_confidence)
        return payload

    @field_validator("classified_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        """Reject naive classification timestamps."""
        return require_aware_datetime(value)

    @field_validator("classified_by")
    @classmethod
    def _validate_classified_by(cls, value: str) -> str:
        """Restrict ``classified_by`` to the approved shapes."""
        return validate_classified_by_shape(value)

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        """Trim free-text reasons while allowing the empty string."""
        return value.strip()

    @field_validator("category_id")
    @classmethod
    def _normalize_category_id(cls, value: str | None) -> str | None:
        """Trim the optional foreign key while rejecting blank strings."""
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
        return validate_confidence_range(value)

    @model_validator(mode="after")
    def _enforce_business_pct(self) -> Self:
        """Enforce the classification/business percentage coupling for a history entry."""
        validate_business_pct_coupling(self.business_classification, self.business_pct)
        return self


class TransactionEvidenceProvenanceEntry(BaseModel):
    """Actor/source lineage for evidence linked to one transaction."""

    model_config = _STRICT_FROZEN

    evidence_id: str = Field(min_length=1, max_length=128)
    evidence_kind: Literal["purchase_invoice_evidence", "attachment"]
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    linked_at: UtcInstant
    bucket_event_id: Hex64Str | None = None

    @field_validator("evidence_id", "actor", "source_command", "bucket_event_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        return trim_lineage_text(value)

    @field_validator("linked_at", mode="before")
    @classmethod
    def _parse_linked_at(cls, value: object) -> datetime:
        return parse_required_aware_datetime(value, field_name="linked_at")


class TransactionEditLineageEntry(BaseModel):
    """One durable manual correction applied to a transaction row."""

    model_config = _STRICT_FROZEN

    previous_transaction_id: TransactionId
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    edited_at: UtcInstant
    bucket_event_id: Hex64Str | None = None

    @field_validator("previous_transaction_id", "actor", "source_command", "bucket_event_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        return trim_lineage_text(value)

    @field_validator("edited_at", mode="before")
    @classmethod
    def _parse_edited_at(cls, value: object) -> datetime:
        return parse_required_aware_datetime(value, field_name="edited_at")


class TransactionLifecycleLineageEntry(BaseModel):
    """One durable lifecycle transition applied to a transaction row."""

    model_config = _STRICT_FROZEN

    previous_state: TransactionLifecycleState
    state: TransactionLifecycleState
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    changed_at: UtcInstant
    reason: str = ""
    bucket_event_id: Hex64Str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_lifecycle_states(cls, data: object) -> object:
        if not _is_object_mapping(data):
            return data
        payload = _string_keyed_mapping(data)
        for key in ("previous_state", "state"):
            raw_state = payload.get(key)
            if isinstance(raw_state, str):
                payload[key] = TransactionLifecycleState(raw_state)
        return payload

    @field_validator("actor", "source_command", "bucket_event_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        return trim_lineage_text(value)

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("changed_at", mode="before")
    @classmethod
    def _parse_changed_at(cls, value: object) -> datetime:
        return parse_required_aware_datetime(value, field_name="changed_at")

    @model_validator(mode="after")
    def _reject_noop_transition(self) -> Self:
        if self.previous_state is self.state:
            raise TransactionValidationError("lifecycle transition must change state")
        return self


class SplitLineage(BaseModel):
    """Split-lineage anchor embedded on a parent/child/merged transaction."""

    model_config = _STRICT_FROZEN

    split_group_id: Hex64Str
    role: SplitRole
    sibling_transaction_ids: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _coerce_role(cls, data: object) -> object:
        if not _is_object_mapping(data):
            return data
        payload = _string_keyed_mapping(data)
        raw_role = payload.get("role")
        if isinstance(raw_role, str):
            payload["role"] = SplitRole(raw_role)
        return payload

    @field_validator("sibling_transaction_ids", mode="before")
    @classmethod
    def _coerce_siblings(cls, value: object) -> tuple[object, ...]:
        if isinstance(value, tuple):
            return OBJECT_TUPLE_ADAPTER.validate_python(value)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            return OBJECT_TUPLE_ADAPTER.validate_python(value)
        raise TransactionValidationError("sibling_transaction_ids must be a sequence")

    @field_validator("sibling_transaction_ids")
    @classmethod
    def _normalise_siblings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        for sibling in value:
            trimmed = sibling.strip()
            if not trimmed:
                raise TransactionValidationError("sibling_transaction_ids entries must not be blank")
            if len(trimmed) != 64:
                raise TransactionValidationError("sibling_transaction_ids entries must be 64-character SHA-256 digests")
            try:
                int(trimmed, 16)
            except ValueError as exc:
                raise TransactionValidationError(
                    "sibling_transaction_ids entries must be lowercase hex digests",
                ) from exc
            if trimmed != trimmed.lower():
                raise TransactionValidationError("sibling_transaction_ids entries must be lowercase")
            cleaned.append(trimmed)
        if len(set(cleaned)) != len(cleaned):
            raise TransactionValidationError("sibling_transaction_ids must be unique")
        return tuple(sorted(cleaned))

    @model_validator(mode="after")
    def _require_siblings_for_lineage(self) -> Self:
        if not self.sibling_transaction_ids:
            raise TransactionValidationError("split_lineage must reference at least one sibling transaction id")
        return self


def derive_split_group_id(
    *,
    parent_transaction_id: str,
    child_amounts: tuple[Decimal, ...],
    child_narratives: tuple[str, ...],
) -> str:
    """Deterministically derive the ``split_group_id`` for a split cohort."""
    payload = json.dumps(
        {
            "parent_transaction_id": parent_transaction_id,
            "child_amounts": sorted(canonical_decimal_string(amount) for amount in child_amounts),
            "child_narratives": sorted(child_narratives),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_hex(payload.encode("utf-8"))


__all__ = [
    "ClassificationHistoryEntry",
    "DecisionProvenance",
    "SplitLineage",
    "TransactionEditLineageEntry",
    "TransactionEvidenceProvenanceEntry",
    "TransactionLifecycleLineageEntry",
    "_is_object_mapping",
    "_string_keyed_mapping",
    "derive_split_group_id",
]
