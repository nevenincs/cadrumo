"""Validated public receipt projections for activity-asset operations."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .activity_asset_contracts import (
    ActivityAssetAuthorityProvenance,
    ActivityAssetId,
    ActivityAssetRefusal,
    ActivityAssetTaxYear,
)
from .activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetDisposalCalculationView,
    ActivityAssetElectionLimits,
    ActivityAssetFormOptionsView,
    ActivityAssetListRow,
    ActivityAssetPlanRow,
    ActivityAssetTimelineEvent,
)
from .activity_asset_results import (
    ActivityAssetInspectionRevision,
    ActivityAssetM130Period,
    require_claim_identity,
    require_filing_frame,
    require_inspected_asset_revisions,
)
from .operation_dtos import (
    ActivityAssetFilingHandoffSnapshot,
    ActivityAssetHistoryClaimResultSnapshot,
    ActivityAssetHistorySnapshot,
    ScheduledAmortizationChargeSnapshot,
)


class _ActivityAssetOperationProjection(BaseModel):
    """Public, closed receipt common to all activity-asset result projections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    authority: ActivityAssetAuthorityProvenance
    outcome: Literal["succeeded", "refused"]
    refusal: ActivityAssetRefusal | None = None

    def _require_outcome(self, *, has_payload: bool) -> None:
        refused = self.outcome == "refused"
        if refused != (self.refusal is not None) or refused == has_payload:
            raise ValueError("activity-asset projection outcome differs from its typed payload")


class ActivityAssetCreateProjection(_ActivityAssetOperationProjection):
    """Public create result with the complete persisted revision and claim history."""

    history: ActivityAssetHistorySnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetInspectProjection(_ActivityAssetOperationProjection):
    """Public typed revision chain, including correction identities."""

    asset_id: ActivityAssetId | None = None
    revisions: tuple[ActivityAssetInspectionRevision, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.revisions is not None)
        require_inspected_asset_revisions(outcome=self.outcome, asset_id=self.asset_id, revisions=self.revisions)
        return self


class ActivityAssetCorrectProjection(_ActivityAssetOperationProjection):
    """Public correction result with the complete persisted revision and claim history."""

    history: ActivityAssetHistorySnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetForecastProjection(_ActivityAssetOperationProjection):
    """Public typed forecast retaining the generation embedded in its schedule."""

    forecast: ScheduledAmortizationChargeSnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.forecast is not None)
        if self.forecast is not None and self.forecast.authority_generation != self.authority.logical_generation:
            raise ValueError("activity-asset forecast differs from its pinned authority generation")
        return self


class ActivityAssetClaimProjection(_ActivityAssetOperationProjection):
    """Public complete history/claim receipt and its deterministic claim ID."""

    claim_result: ActivityAssetHistoryClaimResultSnapshot | None = None
    claim_id: Hex64Str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.claim_result is not None and self.claim_id is not None)
        require_claim_identity(
            self.claim_id,
            None if self.claim_result is None else self.claim_result.claim.to_domain().claim_id,
        )
        return self


class ActivityAssetFilingHandoffProjection(_ActivityAssetOperationProjection):
    """Public typed filing handoff without recomputing or consuming claims."""

    tax_year: ActivityAssetTaxYear | None = None
    m130_period: ActivityAssetM130Period | None = None
    filing_handoff: ActivityAssetFilingHandoffSnapshot | None = None

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


class ActivityAssetDescribeProjection(_ActivityAssetOperationProjection):
    """Public describe result with the complete persisted history."""

    history: ActivityAssetHistorySnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetDisposeProjection(_ActivityAssetOperationProjection):
    """Public baja result with the complete persisted history."""

    history: ActivityAssetHistorySnapshot | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetDisposalCalculateProjection(_ActivityAssetOperationProjection):
    """Public figures of one baja, recorded or previewed."""

    asset_id: ActivityAssetId | None = None
    calculation: ActivityAssetDisposalCalculationView | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.calculation is not None)
        return self


class ActivityAssetListProjection(_ActivityAssetOperationProjection):
    """Public summary of the register."""

    rows: tuple[ActivityAssetListRow, ...] | None = None
    years: tuple[int, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.rows is not None)
        return self


class ActivityAssetPlanProjection(_ActivityAssetOperationProjection):
    """Public amortization plan of one element."""

    asset_id: ActivityAssetId | None = None
    rows: tuple[ActivityAssetPlanRow, ...] | None = None
    limits: ActivityAssetElectionLimits | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.rows is not None)
        return self


class ActivityAssetTimelineProjection(_ActivityAssetOperationProjection):
    """Public ordered history of one element."""

    asset_id: ActivityAssetId | None = None
    events: tuple[ActivityAssetTimelineEvent, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.events is not None)
        return self


class ActivityAssetFormOptionsProjection(_ActivityAssetOperationProjection):
    """Public form options read from the registry."""

    options: ActivityAssetFormOptionsView | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.options is not None)
        return self


class ActivityAssetAcquisitionCandidatesProjection(_ActivityAssetOperationProjection):
    """Public list of ledger payments an element could name as its acquisition."""

    candidates: tuple[ActivityAssetAcquisitionCandidate, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.candidates is not None)
        return self
