"""Shared application operations for IRPF activity-asset frontends."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    ClaimProjection,
    asset_schedule_history,
    effective_claims,
    project_m100,
    project_m130,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS, DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .ports import ActivityAssetHistoryRepository, TaxpayerModalityReader
from .service import ActivityAssetHistoryService


class ActivityAssetFilingHandoff(BaseModel):
    """Non-consuming projections for both supported IRPF filing destinations."""

    model_config = STRICT_FROZEN_CONFIG

    material_m100: ClaimProjection
    intangible_m100: ClaimProjection
    material_m130: ClaimProjection
    intangible_m130: ClaimProjection


class ActivityAssetForecastOperation(Protocol):
    """Trusted registry-backed forecast capability supplied by composition."""

    def __call__(
        self,
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None,
    ) -> ScheduledAmortizationCharge:
        """Resolve the revision's election and calculate one non-consuming forecast."""
        ...


class ActivityAssetOperations:
    """One use-case boundary shared by CLI, TUI, and installed acceptance flows."""

    def __init__(
        self,
        *,
        repository: ActivityAssetHistoryRepository,
        forecast_operation: ActivityAssetForecastOperation,
        taxpayer_modality: TaxpayerModalityReader,
    ) -> None:
        """Bind the operations to one bucket-scoped history and taxpayer profile."""
        self._service = ActivityAssetHistoryService(repository=repository)
        self._forecast_operation = forecast_operation
        self._taxpayer_modality = taxpayer_modality

    def create(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Create an asset from its first immutable revision."""
        if revision.revision_number != 1:
            raise ActividadAssetValidationError("asset creation requires revision number one")
        history = self._service.reopen()
        if any(item.asset_id == revision.asset_id for item in history.revisions):
            raise ActividadAssetValidationError("activity asset already exists")
        return self._service.append_revision(revision)

    def inspect(self, asset_id: str) -> tuple[ActivityAssetRevision, ...]:
        """Return the complete immutable revision chain for one asset."""
        revisions = tuple(item for item in self._service.reopen().revisions if item.asset_id == asset_id)
        if not revisions:
            raise ActividadAssetValidationError("activity asset does not exist")
        return revisions

    def correct(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Append a correction that directly supersedes the current revision."""
        current = self.inspect(revision.asset_id)[-1]
        if (
            revision.revision_number != current.revision_number + 1
            or revision.supersedes_revision_id != current.revision_id
        ):
            raise ActividadAssetValidationError("asset correction must supersede the current revision")
        return self._service.append_revision(revision)

    def forecast(
        self,
        *,
        asset_id: str,
        covered_from: date,
        covered_until: date,
        requested_free_amount: Decimal | None = None,
        supersedes_claim_id: str | None = None,
    ) -> ScheduledAmortizationCharge:
        """Calculate a forecast under the current revision's election without recording it.

        A forecast for a superseding claim leaves out the effective claim it
        will replace, exactly as recording that claim does.
        """
        if supersedes_claim_id is not None and not any(
            claim.claim_id == supersedes_claim_id and claim.asset_id == asset_id
            for claim in effective_claims(self._service.reopen().claims)
        ):
            raise ActividadAssetValidationError("the superseded claim is not an effective claim of this asset")
        return self._forecast(
            asset_id=asset_id,
            covered_from=covered_from,
            covered_until=covered_until,
            requested_free_amount=requested_free_amount,
            excluding_claim_id=supersedes_claim_id,
        )

    def _forecast(
        self,
        *,
        asset_id: str,
        covered_from: date,
        covered_until: date,
        requested_free_amount: Decimal | None,
        excluding_claim_id: str | None,
    ) -> ScheduledAmortizationCharge:
        history = self._service.reopen()
        revision = self.inspect(asset_id)[-1]
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        return self._forecast_operation(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=asset_schedule_history(
                history.claims,
                history.revisions,
                asset_id=asset_id,
                tax_year=covered_from.year,
                excluding_claim_id=excluding_claim_id,
            ),
            requested_free_amount=requested_free_amount,
        )

    def record_claim(
        self,
        forecast: ScheduledAmortizationCharge,
        *,
        creating_operation: str,
        supersedes_claim_id: str | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Explicitly materialize a forecast as one idempotent claim operation.

        A forecast is caller-held data (the CLI receives it as JSON), so a new
        claim is recorded only when recomputing the forecast against current
        history, authority and profile reproduces it exactly.  An exact replay
        of an already recorded claim returns that claim unchanged.
        """
        revision = self.inspect(forecast.asset_id)[-1]
        if revision.revision_id != forecast.asset_revision_id:
            raise ActividadAssetValidationError("forecast does not reference the current asset revision")
        claim = AmortizationClaim.from_schedule(
            forecast,
            asset_kind=revision.asset_kind,
            creating_operation=creating_operation,
            supersedes_claim_id=supersedes_claim_id,
        )
        if any(existing.claim_id == claim.claim_id for existing in self._service.reopen().claims):
            return self._service.record_claim(claim)
        recomputed = self._forecast(
            asset_id=forecast.asset_id,
            covered_from=forecast.covered_from,
            covered_until=forecast.covered_until,
            requested_free_amount=forecast.amount if forecast.method in FREE_AMOUNT_METHODS else None,
            excluding_claim_id=supersedes_claim_id,
        )
        if recomputed != forecast:
            raise ActividadAssetValidationError(
                "the forecast no longer matches the schedule under current history and authority; forecast again",
            )
        return self._service.record_claim(claim)

    def filing_handoff(self, *, tax_year: int, m130_period: Period) -> ActivityAssetFilingHandoff:
        """Project effective claims to M100 and M130 without recording new claims."""
        claims = self._service.reopen().claims
        return ActivityAssetFilingHandoff(
            material_m100=project_m100(claims, asset_kind=AssetKind.MATERIAL, tax_year=tax_year),
            intangible_m100=project_m100(claims, asset_kind=AssetKind.INTANGIBLE, tax_year=tax_year),
            material_m130=project_m130(claims, period=m130_period, asset_kind=AssetKind.MATERIAL),
            intangible_m130=project_m130(claims, period=m130_period, asset_kind=AssetKind.INTANGIBLE),
        )


def _require_profile_modality(elected: DirectEstimationRegime, declared: DirectEstimationRegime) -> None:
    """Refuse an election whose modality the taxpayer profile does not declare (RIRPF art. 28.3)."""
    if declared is not elected:
        raise ActividadAssetValidationError(
            f"the asset elects the {elected.value} modality but the taxpayer profile declares {declared.value}",
        )


__all__ = ["ActivityAssetFilingHandoff", "ActivityAssetForecastOperation", "ActivityAssetOperations"]
