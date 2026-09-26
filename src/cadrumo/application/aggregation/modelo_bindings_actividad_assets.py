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
from ._models import CasillaAggregation


class ActivityAssetFilingProjection(BaseModel):
    """A non-consuming filing projection retaining effective claim identity."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    period: Period
    casilla_values: dict[CasillaId, Decimal]
    claim_ids: tuple[str, ...]


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


def project_activity_assets_to_m100(
    claims: tuple[AmortizationClaim, ...],
    *,
    period: Period,
) -> ActivityAssetFilingProjection:
    """Project each effective annual claim once to material/intangible destinations."""
    selected = tuple(claim for claim in effective_claims(claims) if claim.tax_year == period.filing_year)
    values = {
        validated_casilla_id("0208", surface="activity asset material projection"): _sum_kind(
            selected, AssetKind.MATERIAL
        ),
        validated_casilla_id("0227", surface="activity asset intangible projection"): _sum_kind(
            selected, AssetKind.INTANGIBLE
        ),
    }
    return ActivityAssetFilingProjection(
        modelo="100",
        period=period,
        casilla_values=values,
        claim_ids=tuple(claim.claim_id for claim in selected),
    )


def add_activity_assets_to_m130_expenses(
    ordinary: CasillaAggregation,
    claims: tuple[AmortizationClaim, ...],
) -> ActivityAssetFilingProjection:
    """Add effective YTD claims to the existing sole casilla-02 expense result."""
    if ordinary.modelo != "130":
        raise ValueError("activity-asset M130 composition requires a Modelo 130 ordinary-expense aggregation")
    end_date = ordinary.period.end_date
    selected = tuple(
        claim
        for claim in effective_claims(claims)
        if claim.tax_year == ordinary.period.filing_year and claim.covered_until <= end_date + timedelta(days=1)
    )
    target = validated_casilla_id("02", surface="activity asset M130 expense projection")
    values = dict(ordinary.casilla_values)
    values[target] = values.get(target, Decimal("0")) + sum((claim.amount for claim in selected), Decimal("0"))
    return ActivityAssetFilingProjection(
        modelo="130",
        period=ordinary.period,
        casilla_values=values,
        claim_ids=tuple(claim.claim_id for claim in selected),
    )


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


def _sum_kind(claims: tuple[AmortizationClaim, ...], kind: AssetKind) -> Decimal:
    return sum((claim.amount for claim in claims if claim.asset_kind is kind), Decimal("0"))


__all__ = [
    "ActivityAssetExpenseObservation",
    "ActivityAssetFilingProjection",
    "CompetingDepreciationTreatment",
    "activity_asset_expense_observations",
    "add_activity_assets_to_m130_expenses",
    "project_activity_assets_to_m100",
    "refuse_competing_depreciation_treatments",
]
