"""Private terminal result contracts for activity-asset operations."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FourDigitYear
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from ..operator_actions.models import PreconditionVerdict
from .activity_asset_contracts import (
    ActivityAssetAcceleratedDa18Facts,
    ActivityAssetAuthorityProvenance,
    ActivityAssetId,
    ActivityAssetRefusalCode,
    ActivityAssetRefusalReasonKey,
    require_da18_facts_match,
)
from .activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetDisposalCalculationView,
    ActivityAssetElectionLimits,
    ActivityAssetFormOptionsView,
    ActivityAssetListRow,
    ActivityAssetPlanAdvisory,
    ActivityAssetPlanRow,
    ActivityAssetReasonFactKind,
    ActivityAssetTimelineEvent,
    ServedWords,
)
from .filing_handoff import ActivityAssetFilingHandoff
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .result_requirements import (
    ActivityAssetInspectionRevision,
    require_claim_identity,
    require_filing_frame,
    require_inspected_asset_revisions,
)

ActivityAssetM130Period = Annotated[str, Field(min_length=1, max_length=16)]
"""The Modelo 130 period code a filing handoff is requested for."""


class ActivityAssetRefusalResult(BaseModel):
    """Private refusal detail retained behind the encrypted result reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ActivityAssetRefusalCode
    precondition_verdict: PreconditionVerdict | None = None
    accelerated_da18: ActivityAssetAcceleratedDa18Facts | None = None
    reason_key: ActivityAssetRefusalReasonKey | None = None
    reason_facts: dict[str, str] = Field(default_factory=dict)
    reason_fact_kinds: dict[str, ActivityAssetReasonFactKind] = Field(default_factory=dict)
    refusal_words: ServedWords | None = None
    refusal_words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _da18_facts_match_code(self) -> Self:
        require_da18_facts_match(self.code, self.accelerated_da18)
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        return self


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

    tax_year: FourDigitYear | None = None
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


class ActivityAssetDescribeResult(ActivityAssetOperationResult):
    """Private terminal result for appending one element's descriptive facts."""

    history: ActivityAssetHistory | None = None
    wrote: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetDisposeResult(ActivityAssetOperationResult):
    """Private terminal result for recording one baja."""

    history: ActivityAssetHistory | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.history is not None)
        return self


class ActivityAssetDisposalCalculateResult(ActivityAssetOperationResult):
    """Private terminal result with one baja's figures."""

    asset_id: ActivityAssetId | None = None
    calculation: ActivityAssetDisposalCalculationView | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.calculation is not None)
        return self


class ActivityAssetListResult(ActivityAssetOperationResult):
    """Private terminal result summarising the register."""

    rows: tuple[ActivityAssetListRow, ...] | None = None
    years: tuple[int, ...] = ()
    default_year: int | None = None
    """The year the register opens on: the latest listed year up to the backend's current one, else the earliest."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.rows is not None)
        return self


class ActivityAssetPlanResult(ActivityAssetOperationResult):
    """Private terminal result with one element's plan."""

    asset_id: ActivityAssetId | None = None
    rows: tuple[ActivityAssetPlanRow, ...] | None = None
    limits: ActivityAssetElectionLimits | None = None
    advisories: tuple[ActivityAssetPlanAdvisory, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.rows is not None)
        return self


class ActivityAssetTimelineResult(ActivityAssetOperationResult):
    """Private terminal result with one element's ordered history."""

    asset_id: ActivityAssetId | None = None
    events: tuple[ActivityAssetTimelineEvent, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.events is not None)
        return self


class ActivityAssetFormOptionsResult(ActivityAssetOperationResult):
    """Private terminal result with what the registry admits."""

    options: ActivityAssetFormOptionsView | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.options is not None)
        return self


class ActivityAssetAcquisitionCandidatesResult(ActivityAssetOperationResult):
    """Private terminal result listing candidate acquisitions."""

    candidates: tuple[ActivityAssetAcquisitionCandidate, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_result(self) -> Self:
        self._require_outcome(has_payload=self.candidates is not None)
        return self
