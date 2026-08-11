"""Strict pydantic v2 records for declaración verification verdicts.

Defines the closed schema returned by
:func:`cadrumo.application.verification.verify_declaracion`:
:class:`~cadrumo.domain.calculations.registry.DiscrepancyCause`, :class:`VerificationStatus`,
:class:`ClassifiedDiscrepancy`, and the top-level
:class:`VerificationVerdict`. Every model is frozen, strict, and rejects
extra keys so that the operator's UI and any persisted verdict survive an
end-to-end JSON round trip without drift.

The :attr:`VerificationVerdict.period` field is typed as the canonical
:class:`~cadrumo.core.Period` value object (``filing_year`` + ``code``),
serialising to ``{"filing_year": YYYY, "code": "1T"}`` in JSON.

See Also:
    :class:`VerificationVerdict`,
    :class:`ClassifiedDiscrepancy`,
    :class:`~cadrumo.domain.calculations.registry.DiscrepancyCause`, and
    :class:`VerificationStatus`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import CasillaId, Period
from ...domain.calculations.registry import DiscrepancyCause


class VerificationStatus(StrEnum):
    """Operator-facing single-word verdict.

    Attributes:
        VERIFIED: No correctness, reliability, or unmodelled-registry
            findings; rounding discrepancies (if any) are non-blocking.
        NEEDS_REVIEW: At least one
            :attr:`DiscrepancyCause.EXTRACTION_UNRELIABLE` or
            :attr:`DiscrepancyCause.UNMODELLED_RULE` or
            :attr:`DiscrepancyCause.CORRECTNESS_DIVERGENCE` finding, or
            registry coverage below the active threshold.
    """

    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ClassifiedDiscrepancy(BaseModel):
    """One discrepancy with its cause classification and operator-facing rationale.

    Attributes:
        casilla_id: :class:`CasillaId` of the casilla that diverged.
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
        period: The filing :class:`~cadrumo.core.Period` (year + registry code).
        registry_snapshot_id: Identifier of the
            :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`
            used for the audit.
        verification_expectation_ids: Registry expectation ids that
            governed the verdict.
        status: The :class:`VerificationStatus` summarising the verdict.
        discrepancies: Every :class:`ClassifiedDiscrepancy` produced by
            the engine audit.
        coverage: Fraction of the registry casillas the extraction
            supplied, in the inclusive ``0.0..1.0`` range.
        externally_grounded_casilla_ids: The reconciled casillas (from
            ``computed_casilla_ids`` or ``reconcile_when_present_casilla_ids``)
            whose reconciliation is backed by an AEAT-authoritative
            independent oracle expected value, rather than only the app's
            own engine. Registry-declared data; see
            :attr:`~cadrumo.domain.calculations.registry.RegistryVerificationPolicy.externally_grounded_casilla_ids`.
        independently_grounded_fraction: Fraction of the reconciled casilla
            set that is externally grounded, in the inclusive ``0.0..1.0``
            range. A grounding-depth signal, not a correctness score: a low
            value means most reconciliation was engine-only, not that the
            filing is wrong.
        narrative: Multilingual user-facing summary string.
        verified_at: UTC timestamp of when the verdict was produced.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    registry_snapshot_id: str
    verification_expectation_ids: tuple[str, ...]
    status: VerificationStatus
    discrepancies: tuple[ClassifiedDiscrepancy, ...]
    coverage: float = Field(ge=0.0, le=1.0)
    externally_grounded_casilla_ids: tuple[CasillaId, ...] = ()
    independently_grounded_fraction: float = Field(ge=0.0, le=1.0, default=0.0)
    narrative: str
    verified_at: datetime
