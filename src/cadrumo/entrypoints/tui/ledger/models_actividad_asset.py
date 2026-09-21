"""Typed requests and projections for activity assets in the Ledger TUI."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
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
    """Request for a non-consuming schedule preview."""

    model_config = STRICT_FROZEN_CONFIG
    asset_id: str = Field(min_length=1, max_length=128)
    regime: str = Field(min_length=1, max_length=32)
    asset_kind: AssetKind
    authority_class_key: str = Field(min_length=1, max_length=128)
    covered_from: date
    covered_until: date


class ActivityAssetAuthorityInputV1(BaseModel):
    """Frontend authority coordinates with no caller-authored rate."""

    model_config = STRICT_FROZEN_CONFIG
    regime: str = Field(min_length=1, max_length=32)
    asset_kind: AssetKind
    authority_class_key: str = Field(min_length=1, max_length=128)


class ActivityAssetClaimRequestV1(BaseModel):
    """Request to explicitly materialize a forecast as a claim."""

    model_config = STRICT_FROZEN_CONFIG
    forecast: ScheduledAmortizationCharge
    creating_operation: str = Field(min_length=1, max_length=256)
    supersedes_claim_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ActivityAssetFilingRequestV1(BaseModel):
    """Request for M100 and cumulative M130 filing projections."""

    model_config = STRICT_FROZEN_CONFIG
    tax_year: int = Field(ge=2025, le=2025)
    m130_period: Period


class ActivityAssetInspectionV1(BaseModel):
    """Asset identity and its complete immutable revision chain."""

    model_config = STRICT_FROZEN_CONFIG
    asset_id: str
    revisions: tuple[ActivityAssetRevision, ...]


__all__ = [
    "ActivityAssetAuthorityInputV1",
    "ActivityAssetClaimRequestV1",
    "ActivityAssetCorrectionRequestV1",
    "ActivityAssetCreationRequestV1",
    "ActivityAssetFilingRequestV1",
    "ActivityAssetForecastRequestV1",
    "ActivityAssetInspectionV1",
]
