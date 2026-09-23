"""Application orchestration for registry-backed activity-asset forecasts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...domain.calculations.registry.actividad_asset_bindings import resolve_activity_asset_schedule_authority
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduledAmortizationCharge,
    schedule_charge,
)


def forecast_activity_asset_charge(
    asset_revision: ActivityAssetRevision,
    *,
    modelo_100_revision: ModeloRevision,
    authority_generation: str,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    """Forecast through published authority without creating a claim."""
    authority = resolve_activity_asset_schedule_authority(
        modelo_100_revision,
        tax_year=covered_from.year,
        asset_revision=asset_revision,
        authority_generation=authority_generation,
    )
    return schedule_charge(
        asset_revision,
        authority,
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


__all__ = ["forecast_activity_asset_charge"]
