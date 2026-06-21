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

import json
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Self, override

from pydantic import BaseModel, Field, ValidationError, field_serializer, field_validator, model_validator
from pydantic_core import core_schema

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import CoreValidationError
from ...core.external_constants import CLASSIFIED_BY_AUTO, CLASSIFIED_BY_MANUAL, DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex, sha256_hex
from ...core.identity import BucketId
from ...core.money import round_to_cents
from ...core.time import now, parse_iso_datetime
from ...core.time._utc import validate_utc_aware
from .._identifiers import canonical_decimal_string
from ..iva._schema import EUMemberState, IvaCategory
from ._enums import BusinessClassification, SplitRole, TransactionDirection, TransactionLifecycleState
from ._errors import TransactionValidationError
from ._ids import TransactionId
from ._raw_transaction import RawTransaction


def derive_transaction_id(raw: RawTransaction) -> str:
    """Return the stable transaction hash for one raw transaction.

    This content hash is the single authority for storage, audit, and
    machine consumers, and it intentionally **changes when an
    id-affecting fact is edited** (an ``update`` re-derives it and records
    the superseded id as a ``previous_transaction_id`` on the heir's
    :class:`TransactionEditLineageEntry` chain). The operator-facing
    *lineage* convenience that lets an old, written-down handle still
    resolve to the current row through ``ledger history`` / ``view`` /
    ``track`` (see
    :func:`aeat.application.ledger.resolve_lineage_transaction_id`) is a
    **read-side lookup layer over this authoritative id**; it never
    freezes or re-mints the id, so the content-addressing invariant import
    dedup relies on is untouched.

    Args:
        raw: The upstream immutable raw transaction emitted by a provider.

    Returns:
        A lowercase SHA-256 digest derived from the provider identity,
        effective value date, amount, and narrative fields.
    """
    effective_value_date = raw.value_date or raw.booked_date
    return content_hash_hex(
        {
            "amount": canonical_decimal_string(raw.amount),
            "narrative": raw.description,
            "provider_id": raw.transaction_id,
            "value_date": effective_value_date.isoformat(),
        }
    )


_REFERENCE_NOISE = re.compile(r"[^0-9a-z]+")


def normalise_movement_reference(value: str) -> str:
    """Return a provider-agnostic normalised form of a transaction narrative.

    OFX and CSV exports of the same bank movement describe it with
    different verbatim narratives (an OFX ``MEMO`` versus a CSV
    reference column), and a later manual edit may further reword the
    description. Cross-format and post-edit deduplication therefore
    cannot key on the raw narrative.

    This collapses a narrative to a stable comparison token: Unicode
    is NFKD-decomposed and combining accents are dropped (``Ó`` -> ``o``),
    the result is lower-cased, and every run of non-alphanumeric
    characters is squeezed out. Two narratives that differ only in
    accents, casing, punctuation, or whitespace map to the same token.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _REFERENCE_NOISE.sub("", stripped.lower())


def derive_import_fingerprint(raw: RawTransaction) -> str:
    """Return the stable cross-format import-dedup fingerprint for a raw row.

    Unlike :func:`derive_transaction_id` — which keys on the provider
    identifier and the verbatim narrative and therefore changes when a
    transaction is edited or re-exported in a different file format —
    this fingerprint keys only on the *movement identity* an operator
    would recognise: the effective date, the amount magnitude, and the
    normalised narrative (see :func:`normalise_movement_reference`).

    The fingerprint is stamped onto :class:`Transaction` at import time
    and carried verbatim through every later edit, so re-importing the
    same statement (or the same movements exported as a different file
    format) recognises the row as already present.
    """
    effective_value_date = raw.value_date or raw.booked_date
    return content_hash_hex(
        {
            "amount": canonical_decimal_string(raw.amount),
            "reference": normalise_movement_reference(raw.description),
            "value_date": effective_value_date.isoformat(),
        }
    )


def derive_movement_day_key(raw: RawTransaction) -> str:
    """Return the coarse (effective date, amount) key for a raw row.

    Two rows that share this key but not the full
    :func:`derive_import_fingerprint` are *likely* — but not
    confidently — the same movement: same day, same amount, divergent
    narrative. The import path uses this to warn the operator about a
    probable cross-format duplicate rather than silently importing it.
    """
    effective_value_date = raw.value_date or raw.booked_date
    return f"{effective_value_date.isoformat()}:{canonical_decimal_string(raw.amount)}"


def _json_default(value: object) -> str:
    """Serialize strict-python values into JSON-mode inputs for validation."""
    return str(value)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime string into an aware ``datetime``."""
    return parse_iso_datetime(value)


def _coerce_history(raw: object) -> tuple[object, ...]:
    """Freeze an inbound history sequence into a tuple; leave items for pydantic to validate."""
    if isinstance(raw, tuple):
        return raw
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes):
        return tuple(raw)
    raise TransactionValidationError("classification_history must be a sequence of history entries")


def _require_aware_datetime(value: datetime) -> datetime:
    """Reject naive ``classified_at`` timestamps; enum-safe for both models."""
    try:
        return validate_utc_aware(value)
    except CoreValidationError as exc:
        raise TransactionValidationError(str(exc)) from exc


def _validate_classified_by_shape(value: str) -> str:
    """Restrict ``classified_by`` to ``auto`` / ``manual`` / ``rule:<id>`` / ``llm:<model>`` / ``derived:<basis>``.

    The ``llm:<model>`` shape lets an LLM classifier emit confidence
    scores alongside its predictions; the pipeline distinguishes its
    output from manual and rule-based decisions via this prefix. The
    ``derived:<basis>`` shape marks a value the system computed from a
    grounded authority on an operator's instruction — e.g.
    ``derived:iva-category``, where the operator picks the IVA category
    and the registry rate plus the gross determine the base and amount —
    distinct from a ``manual`` value the operator typed by hand.
    """
    normalized = value.strip()
    if normalized in {CLASSIFIED_BY_AUTO, CLASSIFIED_BY_MANUAL}:
        return normalized
    for prefix in ("rule:", "llm:", "derived:"):
        if normalized.startswith(prefix) and normalized.removeprefix(prefix).strip():
            return normalized
    raise TransactionValidationError(
        "classified_by must be 'auto', 'manual', 'rule:<rule-id>', 'llm:<model>', or 'derived:<basis>'",
    )


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


def _coerce_identifier_tuple(raw: object) -> tuple[object, ...]:
    """Freeze inbound identifier sequences while rejecting scalar strings."""
    if isinstance(raw, tuple):
        return raw
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes):
        return tuple(raw)
    raise TransactionValidationError("identifier fields must be a sequence")


def _normalize_identifier_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    """Trim identifier tuples and reject blanks or duplicates."""
    normalized = tuple(item.strip() for item in value if item.strip())
    if len(normalized) != len(value):
        raise TransactionValidationError("identifier fields must not contain blank values")
    if len(set(normalized)) != len(normalized):
        raise TransactionValidationError("identifier fields must not contain duplicates")
    return normalized


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


def _validate_non_negative_decimal(value: Decimal | None, *, field_name: str) -> Decimal | None:
    """Reject negative monetary or percentage values when supplied."""
    if value is not None and value < Decimal("0"):
        raise TransactionValidationError(
            _NON_NEGATIVE_DECIMAL_HINTS.get(field_name, f"{field_name} must be non-negative"),
        )
    return value


def _coerce_raw_transaction(raw: object) -> RawTransaction:
    """Accept a RawTransaction or a mapping/JSON-like and produce the typed record."""
    if isinstance(raw, RawTransaction):
        return raw
    try:
        return RawTransaction.model_validate(raw)
    except ValidationError:
        return RawTransaction.model_validate_json(json.dumps(raw, default=_json_default, ensure_ascii=True))


_TRANSACTION_DECIMAL_KEYS: tuple[str, ...] = (
    "business_pct",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "recargo_amount",
    "classification_confidence",
    "fx_rate",
    "value_in_eur",
)
_TRANSACTION_COLLECTION_KEYS: tuple[str, ...] = (
    "evidence_provenance",
    "edit_lineage",
    "lifecycle_lineage",
)


def _coerce_transaction_enum_fields(payload: dict[str, object]) -> None:
    """Promote str enum payload values to their declared enum class."""
    enum_coercers: tuple[tuple[str, type], ...] = (
        ("direction", TransactionDirection),
        ("business_classification", BusinessClassification),
        ("lifecycle_state", TransactionLifecycleState),
        ("iva_category", IvaCategory),
        ("counterparty_eu_member_state", EUMemberState),
    )
    for key, enum_cls in enum_coercers:
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = enum_cls(value)


def _coerce_transaction_decimal_fields(payload: dict[str, object]) -> None:
    """Promote str payload values to Decimal for every decimal-typed key."""
    for key in _TRANSACTION_DECIMAL_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = Decimal(value)


def _coerce_transaction_temporal_fields(payload: dict[str, object]) -> None:
    """Parse the str-typed datetime fields via the shared helper."""
    for key in ("classified_at", "created_at", "modified_at"):
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = _parse_datetime(value)


def _normalize_transaction_optional_strings(payload: dict[str, object]) -> None:
    """Trim optional id strings and collapse empty strings to None."""
    for key in ("import_fingerprint", "purchase_invoice_evidence_id", "group_label"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        if key not in payload:
            continue
        normalized = value.strip()
        payload[key] = normalized or None


def _coerce_transaction_collection_fields(payload: dict[str, object]) -> None:
    """Coerce identifier tuples and history sequences into their canonical shape."""
    if "attachment_ids" in payload:
        payload["attachment_ids"] = _coerce_identifier_tuple(payload["attachment_ids"])
    history = payload.get("classification_history")
    if history is not None:
        payload["classification_history"] = _coerce_history(history)
    for key in _TRANSACTION_COLLECTION_KEYS:
        if key in payload:
            payload[key] = _coerce_history(payload[key])


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
            ``auto`` / ``manual`` / ``rule:<id>`` / ``llm:<model>`` /
            ``derived:<basis>`` shape.
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
    provenance: dict[str, object] | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_inbound(cls, data: object) -> object:
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


class TransactionEvidenceProvenanceEntry(BaseModel):
    """Actor/source lineage for evidence linked to one transaction."""

    model_config = _STRICT_FROZEN

    evidence_id: str = Field(min_length=1, max_length=128)
    evidence_kind: Literal["purchase_invoice_evidence", "attachment"]
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    linked_at: datetime
    bucket_event_id: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("evidence_id", "actor", "source_command", "bucket_event_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("lineage text fields must not be blank")
        return trimmed

    @field_validator("linked_at", mode="before")
    @classmethod
    def _parse_linked_at(cls, value: object) -> datetime:
        if isinstance(value, str):
            value = _parse_datetime(value)
        if not isinstance(value, datetime):
            raise TransactionValidationError("linked_at must be a datetime")
        return _require_aware_datetime(value)


class TransactionEditLineageEntry(BaseModel):
    """One durable manual correction applied to a transaction row."""

    model_config = _STRICT_FROZEN

    previous_transaction_id: TransactionId
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    edited_at: datetime
    bucket_event_id: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("previous_transaction_id", "actor", "source_command", "bucket_event_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("lineage text fields must not be blank")
        return trimmed

    @field_validator("edited_at", mode="before")
    @classmethod
    def _parse_edited_at(cls, value: object) -> datetime:
        if isinstance(value, str):
            value = _parse_datetime(value)
        if not isinstance(value, datetime):
            raise TransactionValidationError("edited_at must be a datetime")
        return _require_aware_datetime(value)


class TransactionLifecycleLineageEntry(BaseModel):
    """One durable lifecycle transition applied to a transaction row."""

    model_config = _STRICT_FROZEN

    previous_state: TransactionLifecycleState
    state: TransactionLifecycleState
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    changed_at: datetime
    reason: str = ""
    bucket_event_id: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def _coerce_lifecycle_states(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        for key in ("previous_state", "state"):
            if isinstance(payload.get(key), str):
                payload[key] = TransactionLifecycleState(payload[key])
        return payload

    @field_validator("actor", "source_command", "bucket_event_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("lineage text fields must not be blank")
        return trimmed

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("changed_at", mode="before")
    @classmethod
    def _parse_changed_at(cls, value: object) -> datetime:
        if isinstance(value, str):
            value = _parse_datetime(value)
        if not isinstance(value, datetime):
            raise TransactionValidationError("changed_at must be a datetime")
        return _require_aware_datetime(value)

    @model_validator(mode="after")
    def _reject_noop_transition(self) -> Self:
        if self.previous_state is self.state:
            raise TransactionValidationError("lifecycle transition must change state")
        return self


class SplitLineage(BaseModel):
    """Split-lineage anchor embedded on a parent/child/merged transaction.

    Attributes:
        split_group_id: Lowercase 64-char SHA-256 derived deterministically
            by :func:`derive_split_group_id` from the parent's
            ``transaction_id`` plus the sorted child amounts and narratives.
            Identical inputs yield identical group ids so re-emission is
            idempotent by construction.
        role: Position in the lineage — PARENT, CHILD, or MERGED.
        sibling_transaction_ids: For PARENT, every child id; for CHILD,
            the parent id followed by every other child id; for MERGED,
            the cohort of merged child ids (the original parent id is
            not included — the parent has its own MERGED entry on the
            archived parent record). Sorted lexicographically.
    """

    model_config = _STRICT_FROZEN

    split_group_id: str = Field(min_length=64, max_length=64)
    role: SplitRole
    sibling_transaction_ids: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _coerce_role(cls, data: object) -> object:
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        if isinstance(payload.get("role"), str):
            payload["role"] = SplitRole(payload["role"])
        return payload

    @field_validator("split_group_id")
    @classmethod
    def _require_lowercase_hex(cls, value: str) -> str:
        try:
            int(value, 16)
        except ValueError as exc:
            raise TransactionValidationError("split_group_id must be a 64-character lowercase hex digest") from exc
        if value != value.lower():
            raise TransactionValidationError("split_group_id must be lowercase")
        return value

    @field_validator("sibling_transaction_ids", mode="before")
    @classmethod
    def _coerce_siblings(cls, value: object) -> tuple[object, ...]:
        if isinstance(value, tuple):
            return value
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            return tuple(value)
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
    """Deterministically derive the ``split_group_id`` for a split cohort.

    Identical (parent_id, amounts, narratives) tuples yield an identical
    group id; this is what makes split-event re-emission idempotent.
    Caller is responsible for amount/narrative pairing — the function
    sorts amounts and narratives independently before hashing because
    the group id identifies the *cohort*, not the per-child ordering.

    Args:
        parent_transaction_id: The 64-char SHA-256 of the parent row.
        child_amounts: Per-child amounts, in any order.
        child_narratives: Per-child narrative strings, in any order.

    Returns:
        Lowercase 64-char SHA-256 hex digest.
    """
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
        taxable_base: Optional IVA-exclusive base amount.
        iva_rate: Optional IVA rate expressed as a decimal fraction.
        iva_amount: Optional IVA amount on the row.
        irpf_category: Optional IRPF-specific category key.
        usage_ratio_id: Optional proportionality reference.
        prorrata_reference: Optional IVA prorrata substrate reference.
        purchase_invoice_evidence_id: Canonical purchase-invoice evidence
            reference attached to the row.
        attachment_ids: Supplementary attachment references.
        created_by: Actor that first created the manual row when known.
        source_command: Backend/CLI command source that created the row.
        created_event_id: Bucket event id for the create event when available.
        evidence_provenance: Actor/source lineage for attached evidence.
        edit_lineage: Durable edit chain for manual corrections.
        lifecycle_state: Current active/archive/stash/split state.
        lifecycle_lineage: Durable lifecycle transition chain.
        split_lineage: Optional :class:`SplitLineage` recording this row's
            role within an N-way split cohort. ``None`` for transactions
            that have never been split.
        notes: Free-text notes.
        import_fingerprint: Stable cross-format dedup fingerprint stamped
            at import time (see :func:`derive_import_fingerprint`) and
            carried verbatim through every later edit so re-imports of
            the same statement — or the same movements in a different
            file format — are recognised as already present. ``None``
            for hand-entered rows that never came from an import.
        classified_at: Timezone-aware timestamp of the active decision
            (``None`` when never classified).
        classified_by: Classifier source string for the active decision.
        classification_reason: Free-text reason for the active decision.
        classification_confidence: Optional confidence in ``[0, 1]`` for
            the active decision.
        classification_history: Tuple of historical
            :class:`ClassificationHistoryEntry` records, oldest first.
        iva_category: Explicit IVA category override.  When set the
            aggregation layer uses this value in place of the
            rate-kind-derived domestic category, enabling non-domestic
            categories (intra-community, export, non-subject) to be
            expressed without a synthetic rate.  ``None`` for
            transactions where the standard domestic rate derivation
            is sufficient.
        counterparty_eu_member_state: ISO 3166-1 alpha-2 EU member
            state of the counterparty.  Required by the aggregation
            gate when ``iva_category`` is
            :attr:`IvaCategory.INTRA_COMMUNITY_SUPPLY`; rejected
            when the category is
            :attr:`IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED`.
            ``None`` otherwise.
        fx_rate: ECB reference rate applied at import time to convert
            ``raw.amount`` from ``raw.currency`` to EUR.  The rate is
            expressed as a multiplier: ``raw.amount * fx_rate =
            value_in_eur``.  ``None`` when the native currency is EUR
            or when the rate was unavailable at import time.
        value_in_eur: Pre-converted EUR-equivalent of ``raw.amount``
            computed at import time as ``raw.amount * fx_rate``,
            rounded to two decimal places.  Aggregation layers use
            this field in place of ``raw.amount`` for non-EUR
            transactions, making casilla sums deterministic and
            independent of rate changes after the import date.
            ``None`` when the native currency is EUR or when no rate
            was available.
        source_jurisdiction: ISO 3166-1 alpha-2 uppercase code identifying
            the regulatory source jurisdiction of the income or expense
            (``"ES"`` for Spanish-source, foreign two-letter codes for
            foreign-source). Drives the IRNR scope filter (non-resident
            profiles only emit Spanish-source rows into AEAT bases) and
            the Art. 93 LIRPF Beckham filter (impatriado IRPF base
            excludes foreign-source rows). ``None`` grandfathers rows
            authored before the axis was introduced.
        created_at: UTC-aware timestamp stamped once at construction and
            carried verbatim through every later edit.
        modified_at: UTC-aware timestamp re-stamped on every mutating edit.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    raw: RawTransaction
    direction: TransactionDirection
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
    business_pct: Decimal | None = None
    invoice_id: str | None = None
    category_id: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_amount: Decimal | None = None
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    created_by: str | None = None
    source_command: str | None = None
    created_event_id: str | None = None
    evidence_provenance: tuple[TransactionEvidenceProvenanceEntry, ...] = ()
    edit_lineage: tuple[TransactionEditLineageEntry, ...] = ()
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE
    lifecycle_lineage: tuple[TransactionLifecycleLineageEntry, ...] = ()
    split_lineage: SplitLineage | None = None
    notes: str = ""
    import_fingerprint: str | None = None
    classified_at: datetime | None = None
    classified_by: str = Field(default=CLASSIFIED_BY_AUTO, min_length=1)
    classification_reason: str = ""
    classification_confidence: Decimal | None = None
    classification_history: tuple[ClassificationHistoryEntry, ...] = ()
    iva_category: IvaCategory | None = None
    counterparty_eu_member_state: EUMemberState | None = None
    fx_rate: Decimal | None = None
    value_in_eur: Decimal | None = None
    # FX provenance (ledger-fx-conversion ADR): the rate source label (e.g.
    # "ecb_reference") and the effective rate date as an ISO-8601 string.
    # Optional/backward-compatible; populated at import when a normalizer supplied
    # them. Cannot exist without an fx_rate (a rate provenance with no rate is
    # meaningless). Stored as a string (not date) to roundtrip cleanly through the
    # strict-frozen JSON persistence boundary.
    rate_source: str | None = None
    rate_date: str | None = None
    source_jurisdiction: str | None = None
    # Operator-assigned free-text grouping label (e.g. "Proyecto Acme",
    # "Q1 viajes"). Orthogonal to category_id (the regulatory spending
    # category): it is a personal organisational axis for working at scale
    # over thousands of rows. ``None`` means ungrouped. Length-bounded so a
    # grouped display stays legible.
    group_label: str | None = Field(default=None, max_length=64)
    # Persistence-record lifecycle timestamps (ledger-interface-contract D6).
    # ``created_at`` is stamped once and carried verbatim through every later
    # edit; ``modified_at`` is re-stamped on every mutating edit
    # (update/classify/allocate/attach/doclink/archive/stash/restore/link/
    # split/merge). They make ``--sort-by created_at|modified_at`` honest for
    # hand-added rows, which otherwise carry no creation timestamp (only
    # imported rows have ``raw.provenance.ingested_at``). Both are UTC-aware.
    created_at: datetime = Field(default_factory=now)
    modified_at: datetime = Field(default_factory=now)

    @model_validator(mode="before")
    @classmethod
    def _enforce_derived_transaction_id(cls, data: object) -> object:
        """Compute or validate ``transaction_id`` from the wrapped raw record."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        if "raw" not in payload:
            return data
        raw_transaction = _coerce_raw_transaction(payload["raw"])
        derived = derive_transaction_id(raw_transaction)
        existing = payload.get("transaction_id")
        if existing is not None and str(existing).strip() != derived:
            raise TransactionValidationError("transaction_id must match the stable hash derived from raw")
        payload["raw"] = raw_transaction
        _coerce_transaction_enum_fields(payload)
        _coerce_transaction_decimal_fields(payload)
        _coerce_transaction_temporal_fields(payload)
        _normalize_transaction_optional_strings(payload)
        _coerce_transaction_collection_fields(payload)
        payload["transaction_id"] = derived
        return payload

    @field_validator(
        "invoice_id",
        "category_id",
        "irpf_category",
        "usage_ratio_id",
        "prorrata_reference",
        "purchase_invoice_evidence_id",
        "created_by",
        "source_command",
        "created_event_id",
    )
    @classmethod
    def _validate_optional_ids(cls, value: str | None) -> str | None:
        """Trim optional foreign keys while rejecting blank strings."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("foreign-key identifiers must not be blank")
        return trimmed

    @field_validator("attachment_ids")
    @classmethod
    def _validate_identifier_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Trim and freeze attachment identifiers."""
        return _normalize_identifier_tuple(value)

    @field_validator("taxable_base", "iva_rate", "iva_amount", "recargo_amount")
    @classmethod
    def _validate_tax_amounts(cls, value: Decimal | None, info: core_schema.ValidationInfo) -> Decimal | None:
        """Reject negative tax substrate values."""
        return _validate_non_negative_decimal(value, field_name=info.field_name or "")

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

    @field_validator("classified_at", "created_at", "modified_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        """Reject naive classification/lifecycle timestamps; ``None`` remains valid here."""
        if value is None:
            return None
        return _require_aware_datetime(value)

    @field_validator("classification_confidence")
    @classmethod
    def _validate_classification_confidence(cls, value: Decimal | None) -> Decimal | None:
        """Restrict classification_confidence to the inclusive 0..1 range when not None."""
        return _validate_confidence_range(value)

    @field_validator("fx_rate", "value_in_eur")
    @classmethod
    def _validate_fx_fields(cls, value: Decimal | None, info: core_schema.ValidationInfo) -> Decimal | None:
        """Reject negative FX rate or converted amounts."""
        return _validate_non_negative_decimal(value, field_name=info.field_name or "")

    @field_validator("source_jurisdiction")
    @classmethod
    def _validate_source_jurisdiction(cls, value: str | None) -> str | None:
        """Restrict source_jurisdiction to an ISO 3166-1 alpha-2 uppercase code.

        Carries the regulatory-source axis (Spanish-source vs foreign-source)
        through every ledger boundary. Required for IRNR scope enforcement and
        for the Art. 93 LIRPF impatriado base filter; ``None`` grandfathers
        rows that pre-date the axis.
        """
        if value is None:
            return None
        normalised = value.strip()
        if len(normalised) != 2 or not normalised.isalpha() or normalised != normalised.upper():
            raise TransactionValidationError(
                "source_jurisdiction must be a two-letter ISO 3166-1 alpha-2 uppercase code",
            )
        return normalised

    @model_validator(mode="after")
    def _enforce_business_pct(self) -> Self:
        """Enforce the classification/business percentage coupling."""
        _validate_business_pct_coupling(self.business_classification, self.business_pct)
        return self

    @model_validator(mode="after")
    def _enforce_fx_coupling(self) -> Self:
        """Enforce that fx_rate and value_in_eur are both set or both absent.

        A non-EUR transaction may carry neither (rate unavailable at import)
        but must never carry only one of the pair, which would signal a
        partially-applied conversion.  EUR-native transactions must have
        both fields absent.
        """
        fx_set = self.fx_rate is not None
        eur_set = self.value_in_eur is not None
        if fx_set != eur_set:
            raise TransactionValidationError("fx_rate and value_in_eur must both be set or both be absent")
        if self.raw.currency == DEFAULT_CURRENCY and (fx_set or eur_set):
            raise TransactionValidationError("fx_rate and value_in_eur must be absent for EUR-native transactions")
        if (self.rate_source is not None or self.rate_date is not None) and not fx_set:
            raise TransactionValidationError("rate_source/rate_date require an fx_rate (rate provenance needs a rate)")
        return self

    @model_validator(mode="after")
    def _enforce_gross_equals_base_plus_iva(self) -> Self:
        """Enforce ``gross == taxable_base + iva_amount`` to the cent.

        The IVA-exclusive :attr:`taxable_base` and the :attr:`iva_amount`
        charged on the row must reconstitute the IVA-inclusive gross. The
        gross reference is ``raw.amount`` taken as an absolute value: the
        tax substrate is denominated in the row's native currency (the
        aggregation layer carries ``value_in_eur`` as a separate parallel
        EUR projection and does **not** apply ``fx_rate`` to the base or
        amount), and the income/expense direction lives on
        :attr:`direction`, not on the sign of the tax substrate.

        For self-assessed IVA categories (reverse charge and imports),
        the paid cash gross matches the taxable base; the IVA amount is
        self-assessed but not paid in the transaction itself.

        The check fires **only when both** :attr:`taxable_base` and
        :attr:`iva_amount` are present. A row with either field unset (the
        common case — most transactions never carry the tax substrate)
        validates unconditionally, so the invariant cannot break the
        existing transaction corpus.
        """
        if self.taxable_base is None or self.iva_amount is None:
            return self
        if self.iva_category in {
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            IvaCategory.DOMESTIC_REVERSE_CHARGE,
            IvaCategory.IMPORT_THIRD_COUNTRY,
        }:
            expected = round_to_cents(abs(self.raw.amount))
            reconstituted = round_to_cents(self.taxable_base)
            if reconstituted != expected:
                raise TransactionValidationError(
                    "taxable_base must equal the gross to the cent for self-assessed IVA: "
                    f"{self.taxable_base} != {expected}",
                )
            return self
        expected = round_to_cents(abs(self.raw.amount))
        reconstituted = round_to_cents(self.taxable_base + self.iva_amount)
        if reconstituted != expected:
            raise TransactionValidationError(
                "taxable_base + iva_amount must equal the gross to the cent: "
                f"{self.taxable_base} + {self.iva_amount} = {reconstituted} != {expected}",
            )
        return self


class BucketTransactionRef(BaseModel):
    """A transaction identifier qualified by its owning profile bucket."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    transaction_id: TransactionId

    @field_validator("bucket_id", "transaction_id")
    @classmethod
    def _trim_non_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("bucket transaction reference fields must not be blank")
        return trimmed


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
    def _coerce_catalogue_input(cls, data: object) -> object:
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
                    f"catalogue key {key!r} does not match transaction_id {transaction.transaction_id!r}",
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
    def from_transactions(cls, transactions: Iterable[Transaction | Mapping[str, object]]) -> Self:
        """Build a catalogue from an iterable of transactions.

        Args:
            transactions: Transactions or transaction payloads to load.

        Returns:
            A validated immutable transaction catalogue.
        """
        return cls.model_validate(tuple(transactions))

    @override
    def __iter__(self) -> Iterator[Transaction]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
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
            The matching :class:`Transaction`, or ``None`` when absent.
        """
        return self.transactions.get(transaction_id)

    def values(self) -> Iterator[Transaction]:
        """Iterate over catalogue :class:`Transaction` records."""
        return iter(self.transactions.values())
