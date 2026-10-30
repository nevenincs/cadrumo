"""Typed worker and public contracts for activity-asset operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.renta.actividad_asset.claims import covered_until_after, last_day_covered
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetAcceleratedDa18DepreciationError,
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ..operations.models import CredentialFreeOperationRequest
from ..operations.public_scalar import PublicDecimal
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..user_profile.profile_read_ports import ProfilePathValuesReadPort
from .activity_asset_read_models import ActivityAssetReasonFact
from .operation_dtos import (
    ActivityAssetDisposalSnapshot,
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from .ports import AcquisitionLedgerReader, ActivityAssetHistoryRepository

ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.create"

ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID = "ledger.actividad-asset.inspect"

ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID = "ledger.actividad-asset.correct"

ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID = "ledger.actividad-asset.forecast"

ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID = "ledger.actividad-asset.claim"

ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID = "ledger.actividad-asset.filing-handoff"

ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.describe"

ACTIVITY_ASSET_DISPOSE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.dispose"

ACTIVITY_ASSET_DISPOSAL_CALCULATE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.disposal-calculate"

ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID = "ledger.actividad-asset.list"

ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID = "ledger.actividad-asset.plan"

ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.timeline"

ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID = "ledger.actividad-asset.form-options"

ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID = "ledger.actividad-asset.acquisition-candidates"

ACTIVITY_ASSET_REFUSED_VALIDATION = "REFUSED_ACTIVIDAD_ASSET_VALIDATION"

ACTIVITY_ASSET_REFUSED_UNSUPPORTED = "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED"

ACTIVITY_ASSET_REFUSED_INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE"

ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT"

ACTIVITY_ASSET_REFUSED_ACCELERATED_DA18 = "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED"

ACTIVITY_ASSET_REFUSAL_CODES = frozenset(
    {
        ACTIVITY_ASSET_REFUSED_VALIDATION,
        ACTIVITY_ASSET_REFUSED_UNSUPPORTED,
        ACTIVITY_ASSET_REFUSED_INCOMPLETE,
        ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT,
        ACTIVITY_ASSET_REFUSED_ACCELERATED_DA18,
    }
)

ActivityAssetId = Annotated[str, Field(min_length=1, max_length=128)]

ActivityAssetTaxYear = Annotated[int, Field(ge=1900, le=9999)]

ActivityAssetRefusalCode = Literal[
    "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
    "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE",
    "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT",
    "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED",
]


@dataclass(frozen=True, slots=True)
class ActivityAssetOperationPorts:
    """Canonical encrypted history, ledger and pinned-schema profile read ports."""

    history_repository: ActivityAssetHistoryRepository
    ledger: AcquisitionLedgerReader
    profile_path_values: ProfilePathValuesReadPort
    claim_consumers: Callable[[Iterable[str]], Mapping[str, tuple[str, ...]]]


class ActivityAssetOperationPortsFactory(Protocol):
    """Compose repositories for the immutable worker profile and authority pin."""

    def __call__(
        self,
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
    ) -> ActivityAssetOperationPorts:
        """Return only ports bound to ``bucket_id`` and ``operation``."""
        ...


class ActivityAssetAuthorityProvenance(BaseModel):
    """Exact published generation and reader incarnation used by this operation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    logical_generation: Hex64Str
    reader_incarnation: Hex64Str


class ActivityAssetAcceleratedDa18Facts(BaseModel):
    """The typed facts that name a claim LIS DA 18 places under the accelerated regime."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    asset_id: ActivityAssetId
    method: Annotated[str, Field(min_length=1, max_length=64)]
    tax_year: ActivityAssetTaxYear
    legal_reference: Annotated[str, Field(min_length=1, max_length=128)]

    @classmethod
    def from_error(cls, error: ActividadAssetAcceleratedDa18DepreciationError) -> Self:
        """Keep the bounded facts the domain refusal names, never its prose."""
        context = error.context or {}
        return cls.model_validate(
            {key: context.get(key) for key in ("asset_id", "method", "tax_year", "legal_reference")}
        )


def require_da18_facts_match(code: str, facts: ActivityAssetAcceleratedDa18Facts | None) -> None:
    """Hold the DA 18 facts to the one refusal code that names them."""
    if (code == ACTIVITY_ASSET_REFUSED_ACCELERATED_DA18) != (facts is not None):
        raise ValueError("activity-asset DA 18 facts accompany exactly the DA 18 refusal")


ActivityAssetRefusalReasonKey = Annotated[str, Field(pattern=r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$", max_length=256)]
"""The catalogue key naming why, inside the broader refusal code."""


class ActivityAssetRefusal(BaseModel):
    """Bounded public refusal detail without persisted exception prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ActivityAssetRefusalCode
    precondition_verdict: PreconditionVerdictSnapshot | None = None
    accelerated_da18: ActivityAssetAcceleratedDa18Facts | None = None
    reason_key: ActivityAssetRefusalReasonKey | None = None
    reason_facts: tuple[ActivityAssetReasonFact, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _da18_facts_match_code(self) -> Self:
        require_da18_facts_match(self.code, self.accelerated_da18)
        return self

    def to_domain_error(self, *, context: Mapping[str, object]) -> ActividadAssetError:
        """Rebuild the domain refusal this detail was recorded from, carrying the settled receipt facts."""
        if self.accelerated_da18 is not None:
            return ActividadAssetAcceleratedDa18DepreciationError(
                context={**self.accelerated_da18.model_dump(mode="python"), **context},
                translated_message=self.reason_key,
            )
        merged = {**{fact.key: fact.value for fact in self.reason_facts}, **context}
        if self.code == ACTIVITY_ASSET_REFUSED_INCOMPLETE:
            return ActividadAssetIncompleteError(
                context=merged,
                translated_message=self.reason_key,
                precondition_verdict=(
                    self.precondition_verdict.to_verdict() if self.precondition_verdict is not None else None
                ),
            )
        if self.code == ACTIVITY_ASSET_REFUSED_UNSUPPORTED:
            return ActividadAssetUnsupportedError(context=merged, translated_message=self.reason_key)
        if self.code == ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT:
            return ActividadAssetClaimConflictError(context=merged, translated_message=self.reason_key)
        return ActividadAssetValidationError(context=merged, translated_message=self.reason_key)


class ActivityAssetCreateRequest(BaseModel):
    """Create one immutable first revision in the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    revision: ActivityAssetRevisionSnapshot
    descriptor: ActivityAssetDescriptorFacts


class ActivityAssetDescribeRequest(BaseModel):
    """Append one element's descriptive facts, which change no calculation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId
    descriptor: ActivityAssetDescriptorFacts


class ActivityAssetDisposeRequest(BaseModel):
    """Record one element's baja and supersede the claims it invalidates, as one change."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId
    disposal: ActivityAssetDisposalSnapshot


class ActivityAssetDisposalCalculateRequest(BaseModel):
    """Work out a baja's figures: the stated one as a preview, or else the recorded one."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId
    disposal: ActivityAssetDisposalSnapshot | None = None


class ActivityAssetInspectRequest(BaseModel):
    """Inspect one complete immutable revision chain."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId


class ActivityAssetSupersedingClaim(BaseModel):
    """A recorded claim the correction replaces; the backend works out the new figure."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    supersedes_claim_id: Hex64Str
    requested_free_amount: PublicDecimal | None = None


class ActivityAssetCorrectRequest(BaseModel):
    """Append one correction and the claims it replaces, as one atomic change."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    revision: ActivityAssetRevisionSnapshot
    superseding_claims: tuple[ActivityAssetSupersedingClaim, ...] = ()


class ActivityAssetForecastRequest(BaseModel):
    """Request a non-consuming charge forecast from pinned authority.

    The interval ends at ``covered_until``, the exclusive boundary the operations compute with,
    or at ``covered_through``, the inclusive last day covered. Decoding converts the stated one
    into the other once and keeps both, so either spelling yields the same request. Stating both
    is accepted only when they name the same day.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId
    covered_from: date
    covered_until: date | None = None
    covered_through: date | None = None
    requested_free_amount: PublicDecimal | None = None
    supersedes_claim_id: Hex64Str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _state_both_ends_of_the_interval(self) -> Self:
        until, through = self.covered_until, self.covered_through
        if until is None:
            if through is None:
                raise ValueError("a forecast interval states covered_until or covered_through")
            if through == date.max:
                raise ValueError("covered_through has no boundary after it")
            object.__setattr__(self, "covered_until", covered_until_after(through))
            return self
        if until == date.min:
            raise ValueError("covered_until has no day before it")
        if through is None:
            object.__setattr__(self, "covered_through", last_day_covered(until))
            return self
        if through != last_day_covered(until):
            raise ValueError("covered_through is the day before covered_until")
        return self

    def exclusive_end(self) -> date:
        """Return the exclusive boundary of the interval, which decoding always settles."""
        if self.covered_until is None:
            raise ValueError("a decoded forecast interval has its boundary")
        return self.covered_until


class ActivityAssetClaimRequest(BaseModel):
    """Materialize a forecast as one explicit idempotent claim."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    forecast: ScheduledAmortizationChargeSnapshot
    supersedes_claim_id: Hex64Str | None = None


class ActivityAssetListRequest(CredentialFreeOperationRequest):
    """Summarise the exact profile's register."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class ActivityAssetPlanRequest(BaseModel):
    """Work out one element's amortization plan."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId


class ActivityAssetTimelineRequest(BaseModel):
    """List one element's ordered history."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId


class ActivityAssetFormOptionsRequest(CredentialFreeOperationRequest):
    """Read what the registry admits for an asset kind and tax year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_kind: AssetKind
    tax_year: ActivityAssetTaxYear


class ActivityAssetAcquisitionCandidatesRequest(CredentialFreeOperationRequest):
    """List the ledger payments an element could name as its acquisition."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class ActivityAssetFilingHandoffRequest(CredentialFreeOperationRequest):
    """Read the exact profile's M100 claim projections and M130 accruals."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    tax_year: ActivityAssetTaxYear
    m130_period: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    """The Modelo 130 period to project, or null to project the Modelo 100 boxes alone."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_canonical_period(self) -> Self:
        if self.m130_period is not None:
            Period.from_year_and_code(self.tax_year, self.m130_period)
        return self
