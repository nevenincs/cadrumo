"""Typed requests and projections for activity assets in the Ledger TUI."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ....domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge


class ActivityAssetCreationRequestV1(BaseModel):
    """Request to persist an initial immutable asset revision."""

    model_config = STRICT_FROZEN_CONFIG
    revision: ActivityAssetRevision


class ActivityAssetCorrectionRequestV1(BaseModel):
    """Request to append one superseding asset revision."""

    model_config = STRICT_FROZEN_CONFIG
    revision: ActivityAssetRevision


class ActivityAssetForecastRequestV1(BaseModel):
    """Request for a non-consuming schedule preview under the revision's election."""

    model_config = STRICT_FROZEN_CONFIG
    asset_id: str = Field(min_length=1, max_length=128)
    covered_from: date
    covered_until: date
    requested_free_amount: Decimal | None = None
    supersedes_claim_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ActivityAssetClaimRequestV1(BaseModel):
    """Request to explicitly materialize a forecast as a claim."""

    model_config = STRICT_FROZEN_CONFIG
    forecast: ScheduledAmortizationCharge
    creating_operation: str = Field(min_length=1, max_length=256)
    supersedes_claim_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


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


__all__ = [
    "ActivityAssetClaimRequestV1",
    "ActivityAssetCorrectionRequestV1",
    "ActivityAssetCreationRequestV1",
    "ActivityAssetFilingRequestV1",
    "ActivityAssetForecastRequestV1",
    "ActivityAssetInspectionV1",
]
