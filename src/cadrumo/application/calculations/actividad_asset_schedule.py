"""Application orchestration for registry-backed activity-asset forecasts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetAuthoritySelection,
    resolve_activity_asset_schedule_authority,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge, schedule_charge


def forecast_activity_asset_charge(
    asset_revision: ActivityAssetRevision,
    *,
    modelo_100_revision: ModeloRevision,
    selection: ActivityAssetAuthoritySelection,
    authority_generation: str,
    covered_from: date,
    covered_until: date,
    accumulated_effective_claims: Decimal = Decimal("0"),
) -> ScheduledAmortizationCharge:
    """Forecast through published authority without creating a claim."""
    authority = resolve_activity_asset_schedule_authority(
        modelo_100_revision,
        tax_year=covered_from.year,
        selection=selection,
        authority_generation=authority_generation,
    )
    return schedule_charge(
        asset_revision,
        authority,
        covered_from=covered_from,
        covered_until=covered_until,
        accumulated_effective_claims=accumulated_effective_claims,
    )


__all__ = ["forecast_activity_asset_charge"]
