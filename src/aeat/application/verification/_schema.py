"""Strict pydantic v2 records for declaración verification verdicts.

Defines the closed schema returned by
:func:`aeat.application.verification.verify_declaracion`:
:class:`DiscrepancyCause`, :class:`VerificationStatus`,
:class:`ClassifiedDiscrepancy`, and the top-level
:class:`VerificationVerdict`. Every model is frozen, strict, and rejects
extra keys so that the operator's UI and any persisted verdict survive an
end-to-end JSON round trip without drift.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ...domain.calculations.registry._ids import CasillaId

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` enforcing strict, frozen, no-extras."""


class DiscrepancyCause(StrEnum):
    """Cause classification for a printed-vs-computed value mismatch.

    Attributes:
        EXTRACTION_UNRELIABLE: The extractor warned about this casilla
            (bbox fallback, ambiguous label, unparseable value, missing
            casilla). The operator should re-check the source PDF.
        ROUNDING: Small delta within ``10 * tolerance`` on a computed
            casilla. Non-blocking.
        UNMODELLED_RULE: The registry snapshot has no formula for this casilla;
            the user's value is accepted as-is.
        CORRECTNESS_DIVERGENCE: Material disagreement — likely an
            extractor bug or a formula bug. Requires operator review.
    """

    EXTRACTION_UNRELIABLE = "EXTRACTION_UNRELIABLE"
    ROUNDING = "ROUNDING"
    UNMODELLED_RULE = "UNMODELLED_RULE"
    CORRECTNESS_DIVERGENCE = "CORRECTNESS_DIVERGENCE"


class VerificationStatus(StrEnum):
    """Operator-facing single-word verdict.

    Attributes:
        VERIFIED: No correctness or reliability findings; rounding and
            unmodelled-rule discrepancies (if any) are non-blocking.
        NEEDS_REVIEW: At least one
            :attr:`DiscrepancyCause.EXTRACTION_UNRELIABLE` or
            :attr:`DiscrepancyCause.CORRECTNESS_DIVERGENCE` finding, or
            registry coverage below 30%.
    """

    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ClassifiedDiscrepancy(BaseModel):
    """One discrepancy with its cause classification and operator-facing rationale.

    Attributes:
        casilla_id: Identifier of the casilla that diverged.
        expected: The value the formula engine derived.
        actual: The value extracted from the printed PDF.
        delta: ``actual - expected`` (signed).
        cause: The :class:`DiscrepancyCause` category the operator uses
            to route the next action.
        cause_rationale: Multilingual human-readable explanation surfaced
            in the UI.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    expected: Decimal
    actual: Decimal
    delta: Decimal
    cause: DiscrepancyCause
    cause_rationale: str


class VerificationVerdict(BaseModel):
    """Persisted calc-verification verdict for one imported filing.

    Attributes:
        modelo: AEAT modelo identifier.
        period: Period identifier (e.g. ``"2025Q1"``).
        registry_snapshot_id: Identifier of the registry snapshot used for the audit,
        verification_expectation_ids: Registry expectation ids that governed the verdict.
        status: The :class:`VerificationStatus` summarising the verdict.
        discrepancies: Every :class:`ClassifiedDiscrepancy` produced by
            the engine audit.
        coverage: Fraction of the registry casillas the extraction
            supplied, in the inclusive ``0.0..1.0`` range.
        narrative: Multilingual user-facing summary string.
        verified_at: UTC timestamp of when the verdict was produced.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    registry_snapshot_id: str
    verification_expectation_ids: tuple[str, ...]
    status: VerificationStatus
    discrepancies: tuple[ClassifiedDiscrepancy, ...]
    coverage: float = Field(ge=0.0, le=1.0)
    narrative: str
    verified_at: datetime
