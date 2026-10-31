"""Typed requests and projections for activity assets in the Ledger TUI."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field

from ....application.actividad_asset.activity_asset_contracts import ActivityAssetSupersedingClaim
from ....application.actividad_asset.activity_asset_projections import (
    ActivityAssetListProjection,
    ActivityAssetPlanProjection,
)
from ....application.actividad_asset.activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetDisposalCalculationView,
    ActivityAssetFormOptionsView,
    ActivityAssetTimelineEvent,
)
from ....application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ....application.actividad_asset.operation_dtos import ActivityAssetDisposalSnapshot
from ....application.actividad_asset.operations import ActivityAssetFilingHandoff
from ....core.filing_year import FilingYear
from ....core.hex import Hex64Str
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ....domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge


class ActivityAssetCreationRequestV1(BaseModel):
    """Request to persist an initial immutable asset revision with its descriptive facts."""

    model_config = STRICT_FROZEN_CONFIG
    revision: ActivityAssetRevision
    descriptor: ActivityAssetDescriptorFacts


class ActivityAssetCorrectionRequestV1(BaseModel):
    """Request to append one superseding asset revision and the claims it replaces."""

    model_config = STRICT_FROZEN_CONFIG
    revision: ActivityAssetRevision
    superseding_claims: tuple[ActivityAssetSupersedingClaim, ...] = ()


class ActivityAssetForecastRequestV1(BaseModel):
    """Request for a non-consuming schedule preview under the revision's election."""

    model_config = STRICT_FROZEN_CONFIG
    asset_id: str = Field(min_length=1, max_length=128)
    covered_from: date
    covered_until: date
    requested_free_amount: Decimal | None = None
    supersedes_claim_id: Hex64Str | None = None


class ActivityAssetClaimRequestV1(BaseModel):
    """Request to explicitly materialize a forecast as a claim."""

    model_config = STRICT_FROZEN_CONFIG
    forecast: ScheduledAmortizationCharge
    supersedes_claim_id: Hex64Str | None = None


class ActivityAssetFilingRequestV1(BaseModel):
    """Request for M100 and cumulative M130 filing projections."""

    model_config = STRICT_FROZEN_CONFIG
    tax_year: FilingYear
    m130_period: Period


class ActivityAssetInspectionV1(BaseModel):
    """Asset identity and its complete immutable revision chain."""

    model_config = STRICT_FROZEN_CONFIG
    asset_id: str
    revisions: tuple[ActivityAssetRevision, ...]


class ActivityAssetTuiActionsV1(Protocol):
    """Typed action door backed by the installed session's runtime operations."""

    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        """Create an asset and return its persisted revision chain."""
        ...

    def inspect(self, asset_id: str) -> ActivityAssetInspectionV1:
        """Inspect one asset's immutable revision chain."""
        ...

    def correct(self, request: ActivityAssetCorrectionRequestV1) -> ActivityAssetInspectionV1:
        """Append a correction and return the resulting chain."""
        ...

    def forecast(self, request: ActivityAssetForecastRequestV1) -> ScheduledAmortizationCharge:
        """Preview a schedule through the application boundary."""
        ...

    def record_claim(self, request: ActivityAssetClaimRequestV1) -> ActivityAssetHistoryClaimResult:
        """Record an explicit claim through the application boundary."""
        ...

    def describe(self, asset_id: str, descriptor: ActivityAssetDescriptorFacts) -> ActivityAssetHistory:
        """Append an element's descriptive facts."""
        ...

    def dispose(self, asset_id: str, disposal: ActivityAssetDisposalSnapshot) -> ActivityAssetHistory:
        """Record an element's baja and the claims it supersedes."""
        ...

    def disposal_calculate(
        self,
        asset_id: str,
        disposal: ActivityAssetDisposalSnapshot | None,
    ) -> ActivityAssetDisposalCalculationView:
        """Work out a baja's figures: the stated one as a preview, or else the recorded one."""
        ...

    def list_elements(self) -> ActivityAssetListProjection:
        """Summarise the register, with the year it opens on."""
        ...

    def plan(self, asset_id: str) -> ActivityAssetPlanProjection:
        """Read one element's amortization plan."""
        ...

    def timeline(self, asset_id: str) -> tuple[ActivityAssetTimelineEvent, ...]:
        """Read one element's ordered history."""
        ...

    def form_options(self, asset_kind: AssetKind, tax_year: int) -> ActivityAssetFormOptionsView:
        """Read what the registry admits for an asset kind and tax year."""
        ...

    def acquisition_candidates(self) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
        """List the ledger payments an element could name as its acquisition."""
        ...

    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        """Build non-consuming filing projections."""
        ...


__all__ = [
    "ActivityAssetClaimRequestV1",
    "ActivityAssetCorrectionRequestV1",
    "ActivityAssetCreationRequestV1",
    "ActivityAssetFilingRequestV1",
    "ActivityAssetForecastRequestV1",
    "ActivityAssetInspectionV1",
    "ActivityAssetTuiActionsV1",
]
