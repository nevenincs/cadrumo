"""Strict immutable transaction-catalogue boundary models.

Defines :class:`Transaction`, :class:`ClassificationHistoryEntry`, and :class:`TransactionCatalogue`.
Every model is strict + frozen + ``extra="forbid"``; no dataclasses or bare ``dict[str, Any]`` at the boundary.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Self, override

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator
from pydantic_core import core_schema

from ...core import ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS, Art104TresExclusion
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import CLASSIFIED_BY_AUTO, DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex, sha256_hex
from ...core.identity import BucketId
from ...core.money import round_to_cents
from ...core.parsing import parse_iso8601_date
from ...core.time import now
from .._identifiers import canonical_decimal_string
from ..iva import (
    EUMemberState,
    InputClassification,
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
)
from ._enums import BusinessClassification, SplitRole, TransactionDirection, TransactionLifecycleState
from ._errors import TransactionValidationError
from ._ids import TransactionId
from ._irpf_categories import (
    IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
    PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    format_irpf_category_ids,
    has_activity_irpf_category,
    has_non_work_irpf_category,
    has_rent_irpf_category,
)
from ._model_validation import (
    _coerce_raw_transaction,
    _normalize_identifier_tuple,
    _parse_datetime,
    _parse_required_aware_datetime,
    _require_aware_datetime,
    _trim_lineage_text,
    _validate_business_pct_coupling,
    _validate_classified_by_shape,
    _validate_confidence_range,
    _validate_non_negative_decimal,
)
from ._raw_transaction import RawTransaction

# LIRPF art. 101.5 / RIRPF art. 95: supported professional activity
# withholding rates are 15% or lower reduced rates, not the 21% IVA delta.
_MAX_SUPPORTED_ACTIVITY_WITHHOLDING_RATE = Decimal("0.15")


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
    :func:`application.ledger.resolve_lineage_transaction_id`) is a
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
            "provider_id": raw.provider_transaction_id,
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


def derive_import_fingerprint(raw: RawTransaction, *, direction: TransactionDirection | str | None = None) -> str:
    """Return the stable cross-format import-dedup fingerprint for a raw row.

    Unlike :func:`derive_transaction_id` — which keys on the provider
    identifier and the verbatim narrative and therefore changes when a
    transaction is edited or re-exported in a different file format —
    this fingerprint keys only on the *movement identity* an operator
    would recognise: the effective date, amount magnitude, currency,
    direction, and the normalised narrative (see
    :func:`normalise_movement_reference`).

    The fingerprint is stamped onto :class:`Transaction` at import time
    and carried verbatim through every later edit, so re-importing the
    same statement (or the same movements exported as a different file
    format) recognises the row as already present. Import callers that
    have parsed flow direction must pass it; callers without a parse-boundary
    direction receive an explicit ``UNSPECIFIED`` discriminator.
    """
    effective_value_date = raw.value_date or raw.booked_date
    if isinstance(direction, TransactionDirection):
        direction_value = direction.value
    elif direction is None:
        direction_value = "UNSPECIFIED"
    else:
        direction_value = direction
    return content_hash_hex(
        {
            "amount": canonical_decimal_string(raw.amount),
            "currency": raw.currency,
            "direction": direction_value,
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


def _derive_transaction_id_from_validated_data(data: dict[str, object]) -> str:
    raw = data.get("raw")
    if not isinstance(raw, RawTransaction):
        raise TransactionValidationError("raw is required before transaction_id can be derived")
    return derive_transaction_id(raw)


class DecisionProvenance(BaseModel):
    """Typed provenance for one classification decision.

    Carries the classifier that decided (:attr:`decided_by`, in the same
    ``auto`` / ``manual`` / ``rule:<id>`` / ``llm:<model>`` /
    ``derived:<basis>`` shape as
    :attr:`ClassificationHistoryEntry.classified_by`), when it decided
    (:attr:`decided_at`), the free-text justification, an optional
    confidence in ``[0, 1]``, and whether the decision was a manual
    override of an automated classification. This is the typed
    replacement for the formerly ``dict``-widened reserved
    :attr:`ClassificationHistoryEntry.provenance` payload; a persisted
    record must carry a typed provenance, never a bare
    ``dict[str, object]``.

    Attributes:
        decided_by: Classifier source string in the approved
            ``auto`` / ``manual`` / ``rule:<id>`` / ``llm:<model>`` /
            ``derived:<basis>`` shape.
        decided_at: Timezone-aware UTC timestamp of the decision.
        reason: Free-text justification (may be empty).
        confidence: Optional decision confidence in ``[0, 1]``.
        manual_override: ``True`` when the decision manually overrode an
            earlier automated classification.
    """

    model_config = _STRICT_FROZEN

    decided_by: str = Field(min_length=1, max_length=128)
    decided_at: datetime
    reason: str = ""
    confidence: Decimal | None = None
    manual_override: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce_inbound(cls, data: object) -> object:
        """Parse JSON-mode confidence strings back into ``Decimal`` on load."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        if isinstance(payload.get("confidence"), str):
            payload["confidence"] = Decimal(payload["confidence"])
        return payload

    @field_validator("decided_by")
    @classmethod
    def _validate_decided_by(cls, value: str) -> str:
        """Restrict ``decided_by`` to the approved classifier shapes."""
        return _validate_classified_by_shape(value)

    @field_validator("decided_at", mode="before")
    @classmethod
    def _parse_decided_at(cls, value: object) -> datetime:
        """Reject naive or blank decision timestamps."""
        return _parse_required_aware_datetime(value, field_name="decided_at")

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        """Trim the free-text reason while allowing the empty string."""
        return value.strip()

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: Decimal | None) -> Decimal | None:
        """Restrict confidence to the inclusive 0..1 range when not None."""
        return _validate_confidence_range(value)


class ClassificationHistoryEntry(BaseModel):
    """One frozen record in a transaction's classification chain.

    The :attr:`confidence` and :attr:`provenance` fields default to
    ``None`` and are populated by writers without a schema bump because
    the field list is stable; :attr:`provenance` is the typed
    :class:`DecisionProvenance` record (never a bare ``dict``).

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
        category_id: Optional :class:`domain.categories.SpendingCategory`
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
    provenance: DecisionProvenance | None = None

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
        return _trim_lineage_text(value)

    @field_validator("linked_at", mode="before")
    @classmethod
    def _parse_linked_at(cls, value: object) -> datetime:
        return _parse_required_aware_datetime(value, field_name="linked_at")


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
        return _trim_lineage_text(value)

    @field_validator("edited_at", mode="before")
    @classmethod
    def _parse_edited_at(cls, value: object) -> datetime:
        return _parse_required_aware_datetime(value, field_name="edited_at")


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
        return _trim_lineage_text(value)

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("changed_at", mode="before")
    @classmethod
    def _parse_changed_at(cls, value: object) -> datetime:
        return _parse_required_aware_datetime(value, field_name="changed_at")

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
            :class:`domain.transactions._raw_transaction.RawTransaction`.
        direction: Closed :class:`TransactionDirection`.
        business_classification: Current :class:`BusinessClassification`
            decision; defaults to
            :attr:`BusinessClassification.NOT_YET_PROCESSED`.
        business_pct: Required when ``business_classification`` is
            :attr:`BusinessClassification.MIXED`; ``None`` otherwise.
        invoice_id: Optional invoice foreign key.
        category_id: Optional :class:`domain.categories.SpendingCategory`
            foreign key.
        taxable_base: Optional IVA-exclusive base amount.
        iva_rate: Optional IVA rate expressed as a decimal fraction.
        iva_amount: Optional IVA amount on the row.
        irpf_category: Optional IRPF-specific category key.
        usage_ratio_id: Optional proportionality reference.
        prorrata_reference: Optional IVA prorrata substrate reference.
        art_104_tres_exclusion: Operator-declared LIVA art. 104.Tres
            denominator-exclusion tag. Set ONLY for the two judgment
            exclusions the ledger cannot infer -- foreign permanent
            establishment (1.º) and non-habitual inmobiliario/financiero
            operations (4.º); the transaction boundary rejects any
            auto-derived member (art. 7 no-sujeta, art. 9.1.d autoconsumo,
            bienes-inversión disposal, direct cuotas) since those are
            recognised from the category / register / structure. When set,
            the annual prorrata volume rollup excludes this operation from
            both terms of the art. 104.Dos ratio; the operation's own IVA
            cuota treatment is unaffected. ``None`` for every operation that
            is not an art. 104.Tres judgment exclusion.
        input_classification: Operator-declared LIVA art. 106 prorrata-especial
            per-input use classification (:class:`~domain.iva.InputClassification`):
            ``EXCLUSIVELY_DEDUCTIBLE`` (regla 1.ª, deducted in full),
            ``EXCLUSIVELY_NON_DEDUCTIBLE`` (regla 2.ª, no deduction), or
            ``COMMON`` (regla 3.ª, deducted at the general percentage). Meaningful
            only for a purchase row in a bucket whose prorrata register regime is
            especial; the regime-aware aggregation routes the deducible cuota by
            this classification. ``None`` for rows that are not under especial or
            carry no per-input use declaration.
        prorrata_sector_id: Operator-declared LIVA arts. 9.1.c / 101 differentiated
            sector this input belongs to. References a ``sector_id`` declared in
            the bucket's prorrata register sector definitions; the sector-aware
            aggregation applies THAT sector's provisional percentage to the row's
            deducible cuota. ``None`` means common-use (usable across sectors),
            apportioned by the art. 104.Dos common percentage in a sectorized
            bucket; in a non-sectorized bucket ``None`` is the whole-entity
            default (today's behaviour), so an unsectored taxpayer is unaffected.
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
        exemption_article: Optional Ley 37/1992 Art. 20 sub-article
            discriminator. Valid only when ``iva_category`` is
            :attr:`IvaCategory.DOMESTIC_EXEMPT`; ``None`` preserves
            the broad exempt category with no sub-article distinction.
        counterparty_eu_member_state: ISO 3166-1 alpha-2 EU member
            state of the counterparty.  Required by the aggregation
            gate when ``iva_category`` is
            :attr:`IvaCategory.INTRA_COMMUNITY_SUPPLY`; rejected
            when the category is
            :attr:`IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED`.
            ``None`` otherwise.
        cash_accounting_treatment: Independent criterio-de-caja axis.
            It never replaces ``iva_category``: the operation remains
            domestic/export/intracom/etc. and this field only records
            whether the taxpayer's special regime or a supplier's
            special regime changes IVA timing.
        cash_accounting_operation_date: Art. 75 general-devengo
            operation date for cash-accounting informational reporting.
            Required whenever ``cash_accounting_treatment`` is not
            ``NONE`` so the aggregator never silently reuses a bank
            movement date as the legal devengo projection.
        cash_accounting_payment_evidence: Total or partial
            collection/payment events that settle affected base/cuota
            under LIVA arts. 163 terdecies / quinquiesdecies.
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
            excludes foreign-source rows). ``None`` records an explicitly
            unknown jurisdiction.
        created_at: UTC-aware timestamp stamped once at construction and
            carried verbatim through every later edit.
        modified_at: UTC-aware timestamp re-stamped on every mutating edit.
    """

    model_config = _STRICT_FROZEN

    raw: RawTransaction
    transaction_id: TransactionId = Field(default_factory=_derive_transaction_id_from_validated_data)
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
    art_104_tres_exclusion: Art104TresExclusion | None = None
    input_classification: InputClassification | None = None
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
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
    exemption_article: IvaExemptionArticle | None = None
    counterparty_eu_member_state: EUMemberState | None = None
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE
    cash_accounting_operation_date: date | None = None
    cash_accounting_payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...] = ()
    fx_rate: Decimal | None = None
    value_in_eur: Decimal | None = None
    # FX provenance (ledger-fx-conversion ADR): the rate source label (e.g.
    # "ecb_reference") and the effective rate date as an ISO-8601 string.
    # Optional; populated at import when a normalizer supplied them. Cannot
    # exist without an fx_rate (a rate provenance with no rate is
    # meaningless). Stored as a string (not date) to roundtrip cleanly through the
    # strict-frozen JSON persistence boundary.
    rate_source: str | None = None
    rate_date: str | None = None
    source_jurisdiction: str | None
    # Operator-assigned free-text grouping label (e.g. "Proyecto Acme",
    # "Q1 viajes"). Orthogonal to category_id (the regulatory spending
    # category): it is a personal organisational axis for working at scale
    # over thousands of rows. ``None`` means ungrouped. Length-bounded so a
    # grouped display stays legible.
    group_label: str | None = Field(..., max_length=64)
    # Persistence-record lifecycle timestamps (ledger-interface-contract D6).
    # ``created_at`` is stamped once and carried verbatim through every later
    # edit; ``modified_at`` is re-stamped on every mutating edit
    # (update/classify/allocate/attach/doclink/archive/stash/restore/link/
    # split/merge). They make ``--sort-by created_at|modified_at`` honest for
    # hand-added rows, which otherwise carry no creation timestamp (only
    # imported rows have ``raw.provenance.ingested_at``). Both are UTC-aware.
    created_at: datetime = Field(default_factory=now)
    modified_at: datetime = Field(default_factory=now)

    @field_validator("raw", mode="before")
    @classmethod
    def _coerce_raw_field(cls, value: object) -> object:
        """Accept a ``RawTransaction`` or a JSON-shaped/python-native mapping.

        Delegates to :func:`_coerce_raw_transaction`, which validates through
        ``RawTransaction``'s own validators -- never ``Transaction``'s -- so
        this carries no re-entrant recursion risk (unlike a model-level
        ``Transaction`` before-validator that called back into
        ``Transaction.model_validate*``, which recurses forever because that
        re-invokes this exact model-level hook on the still string-shaped
        JSON-decoded dict).
        """
        return _coerce_raw_transaction(value)

    @field_validator(
        "direction",
        "business_classification",
        "lifecycle_state",
        "iva_category",
        "exemption_article",
        "counterparty_eu_member_state",
        "cash_accounting_treatment",
        "art_104_tres_exclusion",
        "input_classification",
        mode="before",
    )
    @classmethod
    def _coerce_enum_field(cls, value: object, info: core_schema.ValidationInfo) -> object:
        """Accept a JSON-decoded enum string alongside a real enum instance.

        A field-level ``mode="before"`` coercion inspects only this one
        field's value and never re-triggers model-level validation, so it
        carries no re-entrancy risk. No-op for an already-typed enum member
        or ``None``.
        """
        if not isinstance(value, str):
            return value
        enum_by_field: dict[str, type] = {
            "direction": TransactionDirection,
            "business_classification": BusinessClassification,
            "lifecycle_state": TransactionLifecycleState,
            "iva_category": IvaCategory,
            "exemption_article": IvaExemptionArticle,
            "counterparty_eu_member_state": EUMemberState,
            "cash_accounting_treatment": IvaCashAccountingTreatment,
            "art_104_tres_exclusion": Art104TresExclusion,
            "input_classification": InputClassification,
        }
        return enum_by_field[info.field_name or ""](value)

    @field_validator("cash_accounting_operation_date", mode="before")
    @classmethod
    def _parse_cash_accounting_operation_date(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_iso8601_date(value)
        return value

    @field_validator(
        "business_pct",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "recargo_amount",
        "classification_confidence",
        "fx_rate",
        "value_in_eur",
        mode="before",
    )
    @classmethod
    def _coerce_decimal_field(cls, value: object) -> object:
        """Accept a JSON-decoded ``Decimal`` string alongside a real ``Decimal``."""
        if isinstance(value, str):
            return Decimal(value)
        return value

    @field_validator("classified_at", "created_at", "modified_at", mode="before")
    @classmethod
    def _coerce_datetime_field(cls, value: object) -> object:
        """Accept a JSON-decoded ISO-8601 datetime string alongside a real ``datetime``."""
        if isinstance(value, str):
            return _parse_datetime(value)
        return value

    @field_validator(
        "attachment_ids",
        "evidence_provenance",
        "edit_lineage",
        "lifecycle_lineage",
        "classification_history",
        "cash_accounting_payment_evidence",
        mode="before",
    )
    @classmethod
    def _coerce_collection_field(cls, value: object) -> object:
        """Freeze a JSON-decoded list into the declared tuple shape.

        Under strict mode a python-mode ``list`` fails ``tuple_type`` even
        though a JSON-decoded array is legitimately a list; this makes the
        JSON-shaped list acceptable without loosening the frozen-tuple
        contract on the stored value. ``None`` also collapses to the field's
        empty-tuple default rather than failing ``tuple_type``.
        """
        if value is None:
            return ()
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _enforce_derived_transaction_id(self) -> Self:
        """Validate ``transaction_id`` against the already-validated raw record."""
        if self.transaction_id != derive_transaction_id(self.raw):
            raise TransactionValidationError("transaction_id must match the stable hash derived from raw")
        return self

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
        for the Art. 93 LIRPF impatriado base filter; ``None`` means the
        current record explicitly declares the jurisdiction unknown.
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
    def _enforce_exemption_article_category(self) -> Self:
        """Keep the Art. 20 discriminator coupled to domestic exempt IVA rows."""
        if self.exemption_article is not None and self.iva_category is not IvaCategory.DOMESTIC_EXEMPT:
            actual = self.iva_category.value if self.iva_category is not None else None
            raise TransactionValidationError(
                f"exemption_article is only valid when iva_category is DOMESTIC_EXEMPT; got iva_category {actual!r}",
            )
        return self

    @model_validator(mode="after")
    def _enforce_art_104_tres_exclusion_is_operator_declared(self) -> Self:
        """Reject an auto-derived art. 104.Tres exclusion as an operator transaction tag.

        Only the two judgment exclusions (foreign PE, non-habitual
        inmobiliario/financiero) are operator-declared. The other four are
        recognised structurally, from the IVA category, or from the
        bienes-inversión register; declaring one on a transaction would
        double-count or misroute a value the ledger already excludes, so the
        boundary refuses it loudly rather than silently mis-scoping the
        prorrata denominator.
        """
        if (
            self.art_104_tres_exclusion is not None
            and self.art_104_tres_exclusion not in ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS
        ):
            accepted = ", ".join(sorted(member.value for member in ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS))
            raise TransactionValidationError(
                "art_104_tres_exclusion is operator-declared only for the two judgment exclusions "
                f"({accepted}); {self.art_104_tres_exclusion.value!r} is auto-derived and must not be tagged on a "
                "transaction",
            )
        return self

    @model_validator(mode="after")
    def _enforce_cash_accounting_axis(self) -> Self:
        """Keep cash-accounting timing evidence independent and complete."""
        if self.cash_accounting_treatment is IvaCashAccountingTreatment.NONE:
            if self.cash_accounting_operation_date is not None or self.cash_accounting_payment_evidence:
                raise TransactionValidationError(
                    "cash_accounting_operation_date/payment_evidence require a non-NONE cash_accounting_treatment",
                )
            return self
        if self.cash_accounting_operation_date is None:
            raise TransactionValidationError(
                "cash_accounting_operation_date is required when cash_accounting_treatment is not NONE",
            )
        if not self.cash_accounting_payment_evidence:
            raise TransactionValidationError(
                "cash_accounting_payment_evidence is required for cash-accounting operations; "
                "wholly unpaid fallback-only operations are not yet represented",
            )
        if self.taxable_base is None or self.iva_amount is None:
            raise TransactionValidationError(
                "cash-accounting operations require taxable_base and iva_amount facts",
            )
        if (
            self.cash_accounting_treatment is IvaCashAccountingTreatment.SUPPLIER_REGIME
            and self.direction is not TransactionDirection.OUTGOING
        ):
            raise TransactionValidationError(
                "supplier-regime cash-accounting treatment is only valid on received/purchase rows",
            )
        fallback_date = date(self.cash_accounting_operation_date.year + 1, 12, 31)
        total_base = sum((evidence.taxable_base for evidence in self.cash_accounting_payment_evidence), Decimal("0"))
        total_iva = sum((evidence.iva_amount for evidence in self.cash_accounting_payment_evidence), Decimal("0"))
        total_recargo = sum(
            (evidence.recargo_amount for evidence in self.cash_accounting_payment_evidence),
            Decimal("0"),
        )
        recargo_amount = self.recargo_amount or Decimal("0")
        if total_base > self.taxable_base or total_iva > self.iva_amount or total_recargo > recargo_amount:
            raise TransactionValidationError(
                "cash_accounting_payment_evidence totals must not exceed taxable_base, iva_amount, or recargo_amount",
            )
        if any(evidence.payment_date > fallback_date for evidence in self.cash_accounting_payment_evidence):
            raise TransactionValidationError(
                "cash_accounting_payment_evidence cannot fall after the 31 December statutory fallback date",
            )
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

        For professional activity invoices paid or received net of IRPF
        withholding, the bank cash can be lower than the invoice gross while
        the declared base and IVA still need to preserve the invoice substrate.
        That relaxation is accepted only for INCOMING activity rows, or for
        OUTGOING professional-service expense rows, with an explicit
        actividad-economica ``irpf_category`` and only when
        ``taxable_base + iva_amount`` is above the cash movement;
        under-declared invoice gross remains refused.

        For rent expenses paid net of withholding, the same substrate
        preservation is accepted only for OUTGOING rows in the scoped rent
        categories with an explicit non-work ``irpf_category``. The supplier
        invoice base and IVA still reconstitute the invoice gross, while the
        bank movement reflects cash after withholding.

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
        if reconstituted == expected:
            return self
        if (
            self.direction == TransactionDirection.INCOMING
            and has_non_work_irpf_category(self.irpf_category)
            and reconstituted > expected
        ):
            inferred_withholding = round_to_cents(reconstituted - expected)
            if has_activity_irpf_category(self.irpf_category):
                maximum_supported_withholding = round_to_cents(
                    self.taxable_base * _MAX_SUPPORTED_ACTIVITY_WITHHOLDING_RATE,
                )
                if inferred_withholding > maximum_supported_withholding:
                    raise TransactionValidationError(
                        "inferred IRPF withholding exceeds supported activity rate; "
                        "cash amount may be invoice base without IVA",
                    )
            return self
        if (
            self.direction == TransactionDirection.OUTGOING
            and self.category_id in PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING
            and has_activity_irpf_category(self.irpf_category)
            and reconstituted > expected
        ):
            inferred_withholding = round_to_cents(reconstituted - expected)
            maximum_supported_withholding = round_to_cents(
                self.taxable_base * _MAX_SUPPORTED_ACTIVITY_WITHHOLDING_RATE,
            )
            if inferred_withholding > maximum_supported_withholding:
                raise TransactionValidationError(
                    "inferred IRPF withholding exceeds supported activity rate; "
                    "cash amount may be invoice base without IVA",
                )
            return self
        if (
            self.direction == TransactionDirection.OUTGOING
            and self.category_id in RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING
            and has_rent_irpf_category(self.irpf_category)
            and reconstituted > expected
        ):
            return self
        detail = ""
        if reconstituted > expected and self.direction == TransactionDirection.INCOMING:
            detail = (
                " If this is an income receipt paid net of IRPF withholding, "
                f"set irpf_category={IRPF_CATEGORY_ACTIVIDAD_ECONOMICA} for professional invoices "
                "so the invoice base and IVA can be kept. Run `aeat app ledger categories` "
                "to list public IRPF category ids."
            )
        if (
            reconstituted > expected
            and self.direction == TransactionDirection.OUTGOING
            and self.category_id in PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING
        ):
            detail = (
                " If this is a professional service invoice paid net of withholding, "
                f"set irpf_category={IRPF_CATEGORY_ACTIVIDAD_ECONOMICA} so the invoice "
                "base and IVA can be kept. Run `aeat app ledger categories` to list "
                "public IRPF category ids."
            )
        if (
            reconstituted > expected
            and self.direction == TransactionDirection.OUTGOING
            and self.category_id in RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING
        ):
            rent_irpf_ids = format_irpf_category_ids(RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING)
            detail = (
                " If this is rent paid net of withholding, set irpf_category "
                f"to the matching rental withholding category ({rent_irpf_ids}) so the invoice "
                "base and IVA can be kept. Run `aeat app ledger categories` to list public "
                "IRPF category ids."
            )
        if reconstituted != expected:
            raise TransactionValidationError(
                "taxable_base + iva_amount must equal the gross to the cent: "
                f"{self.taxable_base} + {self.iva_amount} = {reconstituted} != {expected}.{detail}",
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

    ``transactions`` is a frozen :class:`types.MappingProxyType` from stable
    transaction id to :class:`Transaction`, built via :meth:`from_transactions`
    or by passing a mapping / iterable to ``model_validate``.
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
    def __iter__(self) -> Iterator[Transaction]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration adapter — yields domain items not field-value tuples
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


class OutOfWindowTransactionStub(BaseModel):
    """A catalogue transaction outside a requested date window, undecrypted.

    Carries ONLY the two plaintext, non-sensitive facts a period-scoped
    aggregator needs to report the transaction as excluded --
    ``transaction_id`` and its ``filing_date`` -- never any decrypted field
    (amount, category, counterparty, direction, business classification).
    This is the O2 period-first partition contract
    (``2026-07-05-ledger-latency-budget-adr``): an out-of-window row is
    diagnosed from the plaintext date-index fact alone, without paying the
    decrypt-and-validate cost, and without leaking anything the index itself
    does not already carry.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    filing_date: date


class OutOfWindowTransactionSummary(BaseModel):
    """Compact diagnostics-only summary for out-of-window catalogue rows.

    Carries only the facts authorized by the 2026-07-06 diagnostic-summary
    amendment to the latency ADR: excluded-row count and the filing-date span
    covered by those rows. It never carries decrypted transaction facts.
    """

    model_config = _STRICT_FROZEN

    count: int = Field(ge=1)
    min_filing_date: date
    max_filing_date: date

    @classmethod
    def from_stubs(cls, stubs: Iterable[OutOfWindowTransactionStub]) -> Self | None:
        """Build a summary from row-level plaintext stubs, or ``None`` when empty."""
        materialized = tuple(stubs)
        if not materialized:
            return None
        filing_dates = tuple(stub.filing_date for stub in materialized)
        return cls(
            count=len(materialized),
            min_filing_date=min(filing_dates),
            max_filing_date=max(filing_dates),
        )

    @model_validator(mode="after")
    def _validate_date_span(self) -> Self:
        if self.max_filing_date < self.min_filing_date:
            raise TransactionValidationError("out-of-window summary date span must be ordered")
        return self


class LedgerDatePartition(BaseModel):
    """A ledger catalogue split into an in-window and an out-of-window half.

    ``in_window`` is a real, fully decrypted :class:`TransactionCatalogue`
    scoped to ``[start, end]`` -- every regulated classifier gate runs over it
    unchanged. ``out_of_window`` is the plaintext-only remainder
    (:class:`OutOfWindowTransactionStub` rows): transactions the catalogue
    holds outside the window, reported without decryption so a caller can
    still surface a period-exclusion diagnostic for them.

    ``out_of_window_summary`` is the compact diagnostics-channel replacement:
    count plus filing-date span, with no decrypted fields and no row-level
    allocation requirement. During the migration, callers may see either the
    row-level stubs, the summary, or both.

    ``index_complete`` records whether the partition was served from a
    complete plaintext date index (``True``) or from a full-scan fallback
    after a completeness-gate mismatch (``False`` -- see
    ``ledger-participation-index-is-derived-rebuildable``): both cases return
    an identical partition shape, so a caller cannot observe which path
    served it except through this flag and through latency.
    """

    model_config = _STRICT_FROZEN

    in_window: TransactionCatalogue
    out_of_window: tuple[OutOfWindowTransactionStub, ...] = ()
    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    index_complete: bool
