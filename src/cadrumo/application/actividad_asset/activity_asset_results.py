"""Private terminal result contracts for activity-asset operations."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from ..operator_actions.models import PreconditionVerdict
from .activity_asset_contracts import (
    ActivityAssetAuthorityProvenance,
    ActivityAssetId,
    ActivityAssetRefusalCode,
    ActivityAssetTaxYear,
)
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .operation_dtos import ActivityAssetFilingHandoffSnapshot, ActivityAssetRevisionSnapshot
from .operations import ActivityAssetFilingHandoff

ActivityAssetM130Period = Annotated[str, Field(min_length=1, max_length=16)]
"""The Modelo 130 period code a filing handoff is requested for."""


class ActivityAssetRefusalResult(BaseModel):
    """Private refusal detail retained behind the encrypted result reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ActivityAssetRefusalCode
    precondition_verdict: PreconditionVerdict | None = None


class ActivityAssetOperationResult(BaseModel):
    """Validated terminal result stored behind the encrypted operation reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    authority: ActivityAssetAuthorityProvenance
    outcome: Literal["succeeded", "refused"]
    refusal: ActivityAssetRefusalResult | None = None

    def _require_outcome(self, *, has_payload: bool) -> None:
        refused = self.outcome == "refused"
        if refused != (self.refusal is not None) or refused == has_payload:
            raise ValueError("activity-asset result outcome differs from its typed payload")


class ActivityAssetCreateResult(ActivityAssetOperationResult):
    """Private terminal result for creating one immutable asset revision."""

    history: ActivityAssetHistory | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetInspectionRevision(BaseModel):
    """One typed revision plus its deterministic identity for correction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    revision: ActivityAssetRevisionSnapshot
    revision_id: Hex64Str

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _identity_matches(self) -> Self:
        if self.revision_id != self.revision.to_domain().revision_id:
            raise ValueError("activity-asset inspection revision identity does not reproduce")
        return self


def require_inspected_asset_revisions(
    *,
    outcome: Literal["succeeded", "refused"],
    asset_id: ActivityAssetId | None,
    revisions: tuple[ActivityAssetInspectionRevision, ...] | None,
) -> None:
    """Require a successful inspection to name its asset and describe only that asset."""
    if outcome == "succeeded" and asset_id is None:
        raise ValueError("successful activity-asset inspection must identify its asset")
    if revisions is not None and (
        not revisions or asset_id is None or any(item.revision.asset_id != asset_id for item in revisions)
    ):
        raise ValueError("activity-asset inspection revisions must describe the requested asset")


def require_claim_identity(claim_id: str | None, reproduced_claim_id: str | None) -> None:
    """Require a claim and its identity together, and the identity to reproduce from the claim."""
    if (reproduced_claim_id is None) != (claim_id is None):
        raise ValueError("activity-asset claim result and identity must appear together")
    if reproduced_claim_id is not None and claim_id != reproduced_claim_id:
        raise ValueError("activity-asset claim identity does not reproduce")


def require_filing_frame(
    *,
    outcome: Literal["succeeded", "refused"],
    tax_year: ActivityAssetTaxYear | None,
    m130_period: str | None,
    filing_handoff: ActivityAssetFilingHandoff | ActivityAssetFilingHandoffSnapshot | None,
) -> None:
    """Require a handoff to sit inside the requested M100 tax year and M130 period."""
    if outcome == "succeeded" and (tax_year is None or m130_period is None):
        raise ValueError("successful activity-asset handoff must identify its filing frame")
    if filing_handoff is not None:
        if tax_year is None or m130_period is None:
            raise ValueError("activity-asset filing handoff requires its requested filing frame")
        if (filing_handoff.material_m100.tax_year, filing_handoff.intangible_m100.tax_year) != (tax_year, tax_year):
            raise ValueError("activity-asset filing handoff differs from its requested tax year")
        Period.from_year_and_code(tax_year, m130_period)


class ActivityAssetInspectResult(ActivityAssetOperationResult):
    """Private terminal result containing one complete asset revision chain."""

    asset_id: ActivityAssetId | None = None
    revisions: tuple[ActivityAssetInspectionRevision, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.revisions is not None)
        require_inspected_asset_revisions(outcome=self.outcome, asset_id=self.asset_id, revisions=self.revisions)
        return self


class ActivityAssetCorrectResult(ActivityAssetOperationResult):
    """Private terminal result for appending one asset correction."""

    history: ActivityAssetHistory | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetForecastResult(ActivityAssetOperationResult):
    """Private terminal result containing one pinned-authority forecast."""

    forecast: ScheduledAmortizationCharge | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.forecast is not None)
        if self.forecast is not None and self.forecast.authority_generation != self.authority.logical_generation:
            raise ValueError("activity-asset forecast differs from its pinned authority generation")
        return self


class ActivityAssetClaimResult(ActivityAssetOperationResult):
    """Private terminal result recording or replaying one forecast claim."""

    claim_result: ActivityAssetHistoryClaimResult | None = None
    claim_id: Hex64Str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.claim_result is not None and self.claim_id is not None)
        require_claim_identity(
            self.claim_id,
            None if self.claim_result is None else self.claim_result.claim.claim_id,
        )
        return self


class ActivityAssetFilingHandoffResult(ActivityAssetOperationResult):
    """Private terminal result for the requested M100/M130 filing frame."""

    tax_year: ActivityAssetTaxYear | None = None
    m130_period: ActivityAssetM130Period | None = None
    filing_handoff: ActivityAssetFilingHandoff | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.filing_handoff is not None)
        require_filing_frame(
            outcome=self.outcome,
            tax_year=self.tax_year,
            m130_period=self.m130_period,
            filing_handoff=self.filing_handoff,
        )
        return self
