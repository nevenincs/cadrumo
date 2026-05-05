"""Pydantic v2 schema for the :mod:`aeat.domain.filing` subpackage.

Every type in this module is a strict, frozen pydantic v2 model
or a closed :class:`enum.StrEnum`. These are the boundary-crossing
records the rest of the project pins against — keep them stable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ...core.i18n import Translatable as tr  # noqa: N813
from ..submission._protocols import FilingFindingSeverity

APPROVAL_BASIS_VERSION = "review-basis-v1"


class FilingDraftStatus(StrEnum):
    """Lifecycle status of a :class:`FilingDraft`.

    Drafts still build and validate up to ``READY_TO_SUBMIT``. Review adds
    the local approval states ``APPROVED`` and ``APPROVAL_STALE`` without
    introducing any write-path coupling.
    """

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    APPROVED = "APPROVED"
    APPROVAL_STALE = "APPROVAL_STALE"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"


class FilingValueKind(StrEnum):
    """Provenance kind of a :class:`FilingValue`."""

    LITERAL = "LITERAL"
    COMPUTED = "COMPUTED"
    INHERITED = "INHERITED"
    DEFAULT = "DEFAULT"
    EMPTY = "EMPTY"


# A type alias for the small set of primitive value types a casilla
# can carry. Pydantic will parse JSON values back into the right
# Python type via this union (Decimal is preferred over float for
# any monetary value).
FilingScalar = Decimal | int | str | bool | date | None


class FilingValue(BaseModel):
    """The typed value of one casilla on a :class:`FilingDraft`.

    Attributes:
        casilla_id: Stable casilla ID (e.g. ``"03"``).
        value: The scalar value carried by this casilla. ``None``
            iff ``kind`` is :attr:`FilingValueKind.EMPTY`.
        kind: Provenance kind — literal user input, computed,
            inherited from a previous draft, default from the
            casilla schema, or empty.
        source: Free-text provenance string — e.g.
            ``"user-supplied"``, ``"computed from 01,02"``,
            ``"default per modelo schema"``.
        formula_trace: For ``COMPUTED`` values, the casilla IDs
            that fed the computation. ``None`` for non-computed
            kinds.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: str
    value: FilingScalar
    kind: FilingValueKind
    source: str
    formula_trace: tuple[str, ...] | None = None


class FilingValidationFinding(BaseModel):
    """One finding produced by the validator.

    Attributes:
        casilla_id: The casilla the finding is about, or ``None``
            for cross-cutting findings such as deadline checks.
        severity: ERROR / WARNING / INFO.
        code: A stable machine-readable code (e.g.
            ``"casilla-required-missing"``).
        message: A strictly-typed :class:`Translatable` key.
        references_rules: Tuple of Manual práctico Rule IDs that
            justify the finding (see :class:`aeat.domain.manuals.Rule`).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: str | None
    severity: FilingFindingSeverity
    code: str
    message: tr
    references_rules: tuple[str, ...] = Field(default_factory=tuple)


class FilingApprovalBasis(BaseModel):
    """Persisted approval-basis digests for deterministic stale detection."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    version: str = APPROVAL_BASIS_VERSION
    draft_payload_fingerprint: str
    draft_review_fingerprint: str
    transaction_catalogue_fingerprint: str
    category_profiles_fingerprint: str
    schema_formula_fingerprint: str


class FilingDraft(BaseModel):
    """A typed, validated draft of one filing.

    The ``draft_id`` is a content-addressed hash of
    ``(modelo, period, profile_tax_id, schema_version, values)``.
    Re-validating a draft preserves its identity because findings,
    status, ``updated_at`` and ``notes`` are deliberately excluded
    from the hash.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    draft_id: str
    modelo: str
    period: str
    profile_tax_id: str
    status: FilingDraftStatus
    values: tuple[FilingValue, ...]
    findings: tuple[FilingValidationFinding, ...] = Field(default_factory=tuple)
    created_at: datetime
    updated_at: datetime
    schema_version: str
    notes: str = ""
    approved_at: datetime | None = None
    approved_by: str | None = None
    review_checksum: str | None = None
    approval_basis: FilingApprovalBasis | None = None


def compute_draft_id(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str,
    schema_version: str,
    values: tuple[FilingValue, ...],
) -> str:
    """Compute the stable, content-addressed ``draft_id``.

    Args:
        modelo: Modelo string ID.
        period: Period string (e.g. ``"2026Q1"``).
        profile_tax_id: Taxpayer tax ID.
        schema_version: The casilla DB version this draft was
            built against.
        values: The tuple of :class:`FilingValue` records to hash.

    Returns:
        A 16-character lowercase hex SHA-256 prefix.
    """
    sorted_values = sorted(values, key=lambda v: v.casilla_id)
    payload = {
        "modelo": modelo,
        "period": period,
        "profile_tax_id": profile_tax_id,
        "schema_version": schema_version,
        "values": [v.model_dump(mode="json") for v in sorted_values],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
