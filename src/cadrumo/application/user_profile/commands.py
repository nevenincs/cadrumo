"""Pydantic command and result contracts for the user-profile boundary.

Import these contracts directly from this defining module. Keeping the Pydantic
records together makes their validation dependency explicit without making the
``user_profile`` package namespace a second public API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Hex64Str
from ...core.period import Period
from ...core.prose_elision import ElidedProse
from ...core.errors.severity import BaseSeverity as _BaseSeverity
from ...core.filing_year import FilingYear
from ...core.identity import ProfileId
from ...domain.calculations.registry.ids import RevisionId
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord

__all__ = [
    "ProfileImportResult",
    "ProfilePreflightReport",
    "ProfilePreflightRequirement",
    "ProfileSnapshot",
    "ProfileStaleCheckReport",
    "ProfileValidationIssue",
    "ProfileValidationReport",
]

# ---------------------------------------------------------------------------
# Validation and preflight
# ---------------------------------------------------------------------------


#: The validation-issue ``message`` annotation: elides rather than refusing.
#:
#: Every one of these is assembled from profile data — field paths, declared
#: values, the set of modelos a gap affects — so its length belongs to the
#: taxpayer's configuration, not to the author. Refusing the issue would fail
#: the very validation pass that exists to report the problem.
_IssueMessage = Annotated[str, ElidedProse(512)]


class ProfileValidationIssue(BaseModel):
    """One validation finding raised against a profile snapshot."""

    model_config = _STRICT_FROZEN

    severity: _BaseSeverity
    code: str = Field(min_length=1, max_length=64)
    path: str | None = None
    message: _IssueMessage


class ProfileValidationReport(BaseModel):
    """Aggregate validation report for a profile or a registration command."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    schema_version: int = Field(ge=1)
    issues: tuple[ProfileValidationIssue, ...] = ()


class ProfilePreflightRequirement(BaseModel):
    """One required-but-missing profile selector for a modelo / revision."""

    model_config = _STRICT_FROZEN

    selector: str = Field(min_length=1, max_length=128)
    section_key: str = Field(min_length=1, max_length=64)
    field_key: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)
    legal_refs: tuple[str, ...] = ()
    modelos: tuple[str, ...] = ()


class ProfilePreflightReport(BaseModel):
    """Per-`(modelo, revision, filing_year, period)` profile readiness report."""

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: RevisionId = Field(min_length=1, max_length=64)
    filing_year: FilingYear
    period: Period
    missing: tuple[ProfilePreflightRequirement, ...] = ()
    ready: bool
    #: Whether the per-operation axis actually assessed anything for this modelo
    #: — that is, whether any schema field declaring ``required`` also declared a
    #: ``modelo_<code>`` selector matching it. When false, no schema-required
    #: field was examined, so ``ready`` reports only the export-identity and
    #: conditional checks and MUST NOT be read as a clean bill of health.
    #: Deliberately carries no default: the single producer states it, and a
    #: default would silently assert an assessment that never ran.
    per_operation_requirements_assessed: bool

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("filing_year must match period.filing_year")
        return self


# ---------------------------------------------------------------------------
# Filing snapshots
# ---------------------------------------------------------------------------


class ProfileSnapshot(BaseModel):
    """Immutable filing-time snapshot of one profile's projection."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    profile_id: ProfileId
    schema_version: int = Field(ge=1)
    modelo: str = Field(min_length=1, max_length=16)
    revision_id: RevisionId = Field(min_length=1, max_length=64)
    filing_year: FilingYear
    period: Period
    canonical_hash: Hex64Str
    created_at: datetime
    facts: tuple[UserProfileFact, ...]

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("filing_year must match period.filing_year")
        return self


class ProfileStaleCheckReport(BaseModel):
    """Result of checking a draft's stored snapshot against the current projection."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    profile_id: ProfileId
    stored_hash: Hex64Str
    current_hash: Hex64Str
    stale: bool


# ---------------------------------------------------------------------------
# Portable export / import
# ---------------------------------------------------------------------------


class ProfileImportResult(BaseModel):
    """Outcome of importing a portable bundle.

    Attributes:
        profile: The imported :class:`UserProfileRecord`.
        imported_at: The timestamp of import.
        issues: Any validation issues.
    """

    model_config = _STRICT_FROZEN

    profile: UserProfileRecord
    imported_at: datetime
    issues: tuple[ProfileValidationIssue, ...] = ()
