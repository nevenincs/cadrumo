"""Canonical public requests and bounded results for ledger ratio operations."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.unit_proportion import is_unit_proportion
from ..operations.models import CredentialFreeOperationRequest

LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID = "ledger.ratios.list"
LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID = "ledger.ratios.set"
LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID = "ledger.ratios.unset"
LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID = "ledger.ratios.eligible"
LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID = "ledger.ratios.validate"
LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE = "REFUSED_FINANCIAL_USAGE_RATIOS_CENSO_MISMATCH"
LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"

_Year = Annotated[int, Field(ge=1900, le=9999)]
_CategoryToken = Annotated[str, Field(min_length=1, max_length=96)]
_RatioText = Annotated[str, Field(min_length=1, max_length=128)]


def _validate_ratio_text(value: str, *, require_unit: bool) -> str:
    parsed = try_parse_canonical_decimal(value)
    if parsed is None:
        raise ValueError("ratio must be a canonical decimal string")
    if require_unit and not is_unit_proportion(parsed):
        raise ValueError("ratio must be within [0, 1]")
    return value


class LedgerRatiosListRequest(CredentialFreeOperationRequest):
    """Read the exact profile's persisted overrides under one filing year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year


class LedgerRatiosSetRequest(BaseModel):
    """Set one exact-profile override without journaling its numeric input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    category: _CategoryToken
    ratio: _RatioText
    year: _Year

    @field_validator("ratio")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_ratio(cls, value: str) -> str:
        return _validate_ratio_text(value, require_unit=True)


class LedgerRatiosUnsetRequest(BaseModel):
    """Clear one exact-profile category override."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    category: _CategoryToken


class LedgerRatiosEligibleRequest(CredentialFreeOperationRequest):
    """Read eligible ratio categories and defaults for one filing year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year


class LedgerRatiosValidateRequest(CredentialFreeOperationRequest):
    """Validate the exact profile's stored ratio overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class LedgerRatiosListRow(BaseModel):
    """One bounded per-category override returned by the application."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: _CategoryToken
    ratio: _RatioText

    @field_validator("ratio")
    @classmethod
    @pydantic_validation_boundary
    def _unit_ratio(cls, value: str) -> str:
        return _validate_ratio_text(value, require_unit=True)


class _LedgerRatiosListFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year
    outcome: Literal["available", "censo_mismatch"]
    rows: tuple[LedgerRatiosListRow, ...] = ()
    count: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _rows_match_outcome(self) -> _LedgerRatiosListFacts:
        if self.outcome == "available" and self.count != len(self.rows):
            raise ValueError("ratio-list count differs from its rows")
        if self.outcome == "censo_mismatch" and (self.count != 0 or self.rows):
            raise ValueError("censo-mismatch result cannot disclose stale ratio rows")
        categories = tuple(row.category for row in self.rows)
        if len(set(categories)) != self.count or categories != tuple(sorted(categories)):
            raise ValueError("ratio-list rows are duplicated or not canonically ordered")
        return self


class LedgerRatiosListResult(_LedgerRatiosListFacts):
    """Encrypted list result retained by the operation supervisor."""


class LedgerRatiosListProjection(_LedgerRatiosListFacts):
    """Independent, bounded frontend projection for the ratio list."""


class LedgerRatiosEligibleRow(BaseModel):
    """Bounded statutory category details shown by ``ratios eligible``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: _CategoryToken
    proportionality_kind: _CategoryToken
    default_ratio: _RatioText | None = None
    override_present: bool

    @field_validator("default_ratio")
    @classmethod
    @pydantic_validation_boundary
    def _default_is_unit_ratio(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ratio_text(value, require_unit=True)


class _LedgerRatiosEligibleFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year
    rows: tuple[LedgerRatiosEligibleRow, ...]
    count: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _rows_match_count(self) -> _LedgerRatiosEligibleFacts:
        if self.count != len(self.rows) or len({row.category for row in self.rows}) != self.count:
            raise ValueError("eligible ratio rows differ from their count or contain duplicate categories")
        if tuple(row.category for row in self.rows) != tuple(sorted(row.category for row in self.rows)):
            raise ValueError("eligible ratio rows are not canonically ordered")
        return self


class LedgerRatiosEligibleResult(_LedgerRatiosEligibleFacts):
    """Encrypted eligible-category result."""


class LedgerRatiosEligibleProjection(_LedgerRatiosEligibleFacts):
    """Independent, bounded eligible-category frontend projection."""


class LedgerRatiosValidationFinding(BaseModel):
    """One bounded finding from the existing validation service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: _CategoryToken
    kind: Annotated[str, Field(min_length=1, max_length=96)]
    detail: Annotated[str, Field(max_length=300)] = ""


class _LedgerRatiosValidateFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    profile_present: bool
    eligible_count: NonNegativeInt
    overrides_count: NonNegativeInt
    missing_overrides: tuple[_CategoryToken, ...] = ()
    findings: tuple[LedgerRatiosValidationFinding, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _counts_are_coherent(self) -> _LedgerRatiosValidateFacts:
        if self.overrides_count and not self.profile_present:
            raise ValueError("ratio validation count contradicts profile presence")
        if len(set(self.missing_overrides)) != len(self.missing_overrides):
            raise ValueError("ratio validation repeats a missing override")
        return self


class LedgerRatiosValidateResult(_LedgerRatiosValidateFacts):
    """Encrypted validation report."""


class LedgerRatiosValidateProjection(_LedgerRatiosValidateFacts):
    """Independent, bounded validation frontend projection."""


class _LedgerRatiosSetFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    requested_category: _CategoryToken
    category: _CategoryToken
    ratio: _RatioText
    prior_ratio: _RatioText | None = None

    @field_validator("ratio", "prior_ratio")
    @classmethod
    @pydantic_validation_boundary
    def _unit_ratio(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ratio_text(value, require_unit=True)


class LedgerRatiosSetResult(_LedgerRatiosSetFacts):
    """Encrypted exact-profile set result."""


class LedgerRatiosSetProjection(_LedgerRatiosSetFacts):
    """Independent set projection correlated to the submitted category and value."""


class _LedgerRatiosUnsetFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    requested_category: _CategoryToken
    category: _CategoryToken
    outcome: Literal["cleared", "no_override"]
    prior_ratio: _RatioText | None = None

    @field_validator("prior_ratio")
    @classmethod
    @pydantic_validation_boundary
    def _unit_ratio(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ratio_text(value, require_unit=True)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _outcome_matches_prior(self) -> _LedgerRatiosUnsetFacts:
        if (self.outcome == "cleared") != (self.prior_ratio is not None):
            raise ValueError("ratio-unset outcome differs from its prior value")
        return self


class LedgerRatiosUnsetResult(_LedgerRatiosUnsetFacts):
    """Encrypted exact-profile unset result."""


class LedgerRatiosUnsetProjection(_LedgerRatiosUnsetFacts):
    """Independent unset projection, including the explicit no-override outcome."""


__all__ = [
    "LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE",
    "LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE",
    "LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID",
    "LedgerRatiosEligibleProjection",
    "LedgerRatiosEligibleRequest",
    "LedgerRatiosEligibleResult",
    "LedgerRatiosEligibleRow",
    "LedgerRatiosListProjection",
    "LedgerRatiosListRequest",
    "LedgerRatiosListResult",
    "LedgerRatiosListRow",
    "LedgerRatiosSetProjection",
    "LedgerRatiosSetRequest",
    "LedgerRatiosSetResult",
    "LedgerRatiosUnsetProjection",
    "LedgerRatiosUnsetRequest",
    "LedgerRatiosUnsetResult",
    "LedgerRatiosValidateProjection",
    "LedgerRatiosValidateRequest",
    "LedgerRatiosValidateResult",
    "LedgerRatiosValidationFinding",
]
