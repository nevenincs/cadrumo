"""Recompute activity-asset claims affected by a disposal boundary."""

from datetime import date
from decimal import Decimal

from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    amount_before_baja_zeroed,
    asset_schedule_history,
    claims_through_year,
    effective_claims,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS, DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from .history import ActivityAssetHistory
from .ports import ActivityAssetForecastOperation, TaxpayerModalityReader


def baja_supersessions(
    forecast: ActivityAssetForecastOperation,
    taxpayer_modality: TaxpayerModalityReader,
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    origin: str | None,
) -> tuple[AmortizationClaim, ...]:
    """Work out what a baja, or its removal or new date, replaces in one write.

    Claims after the boundary go to zero and a crossing one is shortened.  A zero
    claim an earlier baja wrote comes back inside the service window: with no
    boundary or a later one it would otherwise keep the year's deduction at zero.
    The claims after the boundary go first, so that later charges are judged
    without them, and the rest run in date order on the state the earlier ones
    leave.  A free amount is the taxpayer's election and carries over; any other
    amount is recomputed.  A shortened claim keeps its interval, because a claim
    never widens: the rest of its year reads as a gap.
    """
    disposal = revision.disposal
    boundary = None if disposal is None else disposal.boundary
    creating_operation = origin or revision.asset_id
    standing = tuple(claim for claim in effective_claims(history.claims) if claim.asset_id == revision.asset_id)
    recorded = _baja_zero_claims(standing, boundary, revision.revision_id, creating_operation)
    recompute = sorted(
        (claim for claim in standing if _baja_needs_recomputation(claim, boundary)),
        key=lambda claim: claim.covered_from,
    )
    if not recompute:
        return tuple(recorded)
    require_profile_modality(revision.amortization.regime, taxpayer_modality())
    for claim in recompute:
        replacement = _baja_recomputed_claim(
            forecast,
            claim,
            revision,
            (*history.claims, *recorded),
            (*history.revisions, revision),
            boundary=boundary,
            creating_operation=creating_operation,
        )
        if replacement is not None:
            recorded.append(replacement)
    return tuple(recorded)


def _baja_recomputed_claim(
    forecast: ActivityAssetForecastOperation,
    claim: AmortizationClaim,
    revision: ActivityAssetRevision,
    working: tuple[AmortizationClaim, ...],
    revisions: tuple[ActivityAssetRevision, ...],
    *,
    boundary: date | None,
    creating_operation: str,
) -> AmortizationClaim | None:
    """Replace one claim under the new boundary; a zero claim stays where the schedule also charges zero."""
    crossing = boundary is not None and claim.covered_until > boundary
    free = revision.amortization.method in FREE_AMOUNT_METHODS
    charge = forecast(
        revision,
        covered_from=claim.covered_from,
        covered_until=boundary if boundary is not None and crossing else claim.covered_until,
        history=asset_schedule_history(
            claims_through_year(working, claim.tax_year),
            revisions,
            asset_id=revision.asset_id,
            tax_year=claim.tax_year,
            excluding_claim_id=claim.claim_id,
        ),
        requested_free_amount=amount_before_baja_zeroed(claim, working) if free else None,
    )
    if not crossing and charge.amount <= Decimal("0"):
        return None
    return AmortizationClaim.from_schedule(
        charge,
        asset_kind=revision.asset_kind,
        creating_operation=creating_operation,
        supersedes_claim_id=claim.claim_id,
        disposal_revision_id=revision.revision_id if crossing else None,
    )


def _baja_zero_claims(
    claims: tuple[AmortizationClaim, ...], boundary: date | None, revision_id: str, creating_operation: str
) -> list[AmortizationClaim]:
    if boundary is None:
        return []
    return [
        claim.set_to_zero_by_baja(revision_id, creating_operation=creating_operation)
        for claim in claims
        if claim.covered_from >= boundary and claim.amount > Decimal("0")
    ]


def _baja_needs_recomputation(claim: AmortizationClaim, boundary: date | None) -> bool:
    crossing = boundary is not None and claim.covered_from < boundary < claim.covered_until
    restored = (
        claim.disposal_revision_id is not None
        and claim.amount == Decimal("0")
        and (boundary is None or claim.covered_until <= boundary)
    )
    return crossing or restored


def require_profile_modality(elected: DirectEstimationRegime, declared: DirectEstimationRegime) -> None:
    """Refuse an election whose modality the taxpayer profile does not declare (RIRPF art. 28.3)."""
    if declared is not elected:
        raise ActividadAssetValidationError(
            context={"elected": elected.value, "declared": declared.value},
            translated_message="ledger.actividad_asset.errors.profile_modality_mismatch",
        )
