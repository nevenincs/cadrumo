"""Read-only Modelo 100/130 projections for effective activity-asset claims."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from ...domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind


class CompetingDepreciationTreatment(BaseModel):
    """A transaction-ledger depreciation treatment competing with asset claims."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    transaction_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: str = Field(min_length=1, max_length=128)
    tax_year: int


class ActivityAssetExpenseObservation(BaseModel):
    """One effective claim projected through an existing Renta expense owner."""

    model_config = STRICT_FROZEN_CONFIG

    claim_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    modelo: str
    period: str = Field(min_length=2, max_length=2)
    target_casilla_id: CasillaId
    deductible_amount: Decimal = Field(ge=Decimal("0"))


def activity_asset_expense_observations(
    claims: tuple[AmortizationClaim, ...],
    *,
    modelo: str,
    period: Period,
) -> tuple[ActivityAssetExpenseObservation, ...]:
    """Project effective claims into the existing M100 or M130 expense family."""
    effective = tuple(claim for claim in effective_claims(claims) if claim.tax_year == period.filing_year)
    if modelo == "130":
        cutoff = period.end_date + timedelta(days=1)
        effective = tuple(claim for claim in effective if claim.covered_until <= cutoff)
        return tuple(
            ActivityAssetExpenseObservation(
                claim_id=claim.claim_id,
                modelo=modelo,
                period=period.registry_token,
                target_casilla_id=validated_casilla_id("02", surface="activity asset M130 observation"),
                deductible_amount=claim.amount,
            )
            for claim in effective
        )
    if modelo == "100":
        return tuple(
            ActivityAssetExpenseObservation(
                claim_id=claim.claim_id,
                modelo=modelo,
                period=period.registry_token,
                target_casilla_id=validated_casilla_id(
                    "0208" if claim.asset_kind is AssetKind.MATERIAL else "0227",
                    surface="activity asset M100 observation",
                ),
                deductible_amount=claim.amount,
            )
            for claim in effective
        )
    raise ValueError("activity-asset expense observations support only Modelos 100 and 130")


def refuse_competing_depreciation_treatments(
    assets: tuple[ActivityAssetRevision, ...],
    claims: tuple[AmortizationClaim, ...],
    competing: tuple[CompetingDepreciationTreatment, ...],
) -> None:
    """Refuse only ledger depreciation rows matching an effective asset claim."""
    effective_keys = {(claim.asset_id, claim.tax_year) for claim in effective_claims(claims)}
    assets_by_id = {asset.asset_id: asset for asset in assets}
    for treatment in competing:
        if (treatment.asset_id, treatment.tax_year) not in effective_keys:
            continue
        asset = assets_by_id.get(treatment.asset_id)
        if asset is None:
            continue
        raise ActividadAssetClaimConflictError(
            "competing transaction-ledger depreciation treatment "
            f"asset={treatment.asset_id!r} transaction={treatment.transaction_id!r} "
            f"category={treatment.category!r} tax_year={treatment.tax_year}; retain acquisition evidence and "
            "reclassify or reverse only the competing depreciation treatment",
        )


__all__ = [
    "ActivityAssetExpenseObservation",
    "CompetingDepreciationTreatment",
    "activity_asset_expense_observations",
    "refuse_competing_depreciation_treatments",
]
