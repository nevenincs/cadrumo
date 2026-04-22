"""Strict pydantic v2 records for verification verdicts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..i18n import Translatable

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class DiscrepancyCause(StrEnum):
    """Why a printed value disagrees with the engine-derived value."""

    EXTRACTION_UNRELIABLE = "EXTRACTION_UNRELIABLE"
    """Extractor warned about this casilla (bbox fallback / ambiguous)."""
    ROUNDING = "ROUNDING"
    """Small delta within ``10x tolerance`` on a computed casilla."""
    UNMODELLED_RULE = "UNMODELLED_RULE"
    """The ruleset does not know this casilla; user's value accepted as-is."""
    CORRECTNESS_DIVERGENCE = "CORRECTNESS_DIVERGENCE"
    """Material disagreement — extractor bug or formula bug. Kent reviews."""


class VerificationStatus(StrEnum):
    """Kent-facing single-word verdict."""

    VERIFIED = "VERIFIED"
    """No correctness / reliability findings; rounding and unmodelled rules ok."""
    NEEDS_REVIEW = "NEEDS_REVIEW"
    """At least one EXTRACTION_UNRELIABLE or CORRECTNESS_DIVERGENCE finding."""
    UNVERIFIABLE = "UNVERIFIABLE"
    """No ruleset registered for this (modelo, período); nothing to compare."""


class ClassifiedDiscrepancy(BaseModel):
    """One discrepancy plus its cause classification + Kent-readable rationale."""

    model_config = _STRICT_FROZEN

    casilla_id: str = Field(min_length=1)
    expected: Decimal
    actual: Decimal
    delta: Decimal
    cause: DiscrepancyCause
    cause_rationale: Translatable


class VerificationVerdict(BaseModel):
    """Persisted calc-verification verdict for one imported filing."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    ruleset_id: str | None
    status: VerificationStatus
    discrepancies: tuple[ClassifiedDiscrepancy, ...]
    coverage: float = Field(ge=0.0, le=1.0)
    narrative: Translatable
    verified_at: datetime
