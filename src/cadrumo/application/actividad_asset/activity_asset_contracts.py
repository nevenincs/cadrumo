"""Typed worker and public contracts for activity-asset operations."""

from __future__ import annotations

from collections.abc import Mapping
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
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ..operations.models import CredentialFreeOperationRequest
from ..operations.public_scalar import PublicDecimal
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..user_profile.profile_read_ports import ProfilePathValuesReadPort
from .operation_dtos import (
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from .ports import ActivityAssetHistoryRepository

ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID = "ledger.actividad-asset.create"

ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID = "ledger.actividad-asset.inspect"

ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID = "ledger.actividad-asset.correct"

ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID = "ledger.actividad-asset.forecast"

ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID = "ledger.actividad-asset.claim"

ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID = "ledger.actividad-asset.filing-handoff"

ACTIVITY_ASSET_REFUSED_VALIDATION = "REFUSED_ACTIVIDAD_ASSET_VALIDATION"

ACTIVITY_ASSET_REFUSED_UNSUPPORTED = "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED"

ACTIVITY_ASSET_REFUSED_INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE"

ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT"

ACTIVITY_ASSET_REFUSAL_CODES = frozenset(
    {
        ACTIVITY_ASSET_REFUSED_VALIDATION,
        ACTIVITY_ASSET_REFUSED_UNSUPPORTED,
        ACTIVITY_ASSET_REFUSED_INCOMPLETE,
        ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT,
    }
)

ActivityAssetId = Annotated[str, Field(min_length=1, max_length=128)]

ActivityAssetOperationName = Annotated[str, Field(min_length=1, max_length=256)]

ActivityAssetTaxYear = Annotated[int, Field(ge=1900, le=9999)]

ActivityAssetRefusalCode = Literal[
    "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
    "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE",
    "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT",
]


@dataclass(frozen=True, slots=True)
class ActivityAssetOperationPorts:
    """Canonical encrypted history and pinned-schema profile read ports."""

    history_repository: ActivityAssetHistoryRepository
    profile_path_values: ProfilePathValuesReadPort


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


class ActivityAssetRefusal(BaseModel):
    """Bounded public refusal detail without persisted exception prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ActivityAssetRefusalCode
    precondition_verdict: PreconditionVerdictSnapshot | None = None

    def to_domain_error(self, *, context: Mapping[str, object]) -> ActividadAssetError:
        """Rebuild the domain refusal this detail was recorded from, carrying the settled receipt facts."""
        if self.code == ACTIVITY_ASSET_REFUSED_INCOMPLETE:
            return ActividadAssetIncompleteError(
                context=context,
                precondition_verdict=(
                    self.precondition_verdict.to_verdict() if self.precondition_verdict is not None else None
                ),
            )
        if self.code == ACTIVITY_ASSET_REFUSED_UNSUPPORTED:
            return ActividadAssetUnsupportedError(context=context)
        if self.code == ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT:
            return ActividadAssetClaimConflictError(context=context)
        return ActividadAssetValidationError(context=context)


class ActivityAssetCreateRequest(BaseModel):
    """Create one immutable first revision in the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    revision: ActivityAssetRevisionSnapshot


class ActivityAssetInspectRequest(BaseModel):
    """Inspect one complete immutable revision chain."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId


class ActivityAssetCorrectRequest(BaseModel):
    """Append one correction to the current immutable asset revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    revision: ActivityAssetRevisionSnapshot


class ActivityAssetForecastRequest(BaseModel):
    """Request a non-consuming charge forecast from pinned authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    asset_id: ActivityAssetId
    covered_from: date
    covered_until: date
    requested_free_amount: PublicDecimal | None = None
    supersedes_claim_id: Hex64Str | None = None


class ActivityAssetClaimRequest(BaseModel):
    """Materialize a forecast as one explicit idempotent claim."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    forecast: ScheduledAmortizationChargeSnapshot
    creating_operation: ActivityAssetOperationName
    supersedes_claim_id: Hex64Str | None = None


class ActivityAssetFilingHandoffRequest(CredentialFreeOperationRequest):
    """Read the exact profile's existing M100 and M130 claim projections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    tax_year: ActivityAssetTaxYear
    m130_period: Annotated[str, Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_canonical_period(self) -> Self:
        Period.from_year_and_code(self.tax_year, self.m130_period)
        return self
