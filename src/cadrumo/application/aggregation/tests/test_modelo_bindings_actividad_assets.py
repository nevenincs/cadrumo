"""Read-only activity-asset filing composition and collision tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.renta.actividad_asset.claims import AmortizationClaim
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ..modelo_bindings_actividad_assets import (
    CompetingDepreciationTreatment,
    activity_asset_expense_observations,
    refuse_competing_depreciation_treatments,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


def _claim(
    year: int,
    *,
    kind: AssetKind = AssetKind.MATERIAL,
    amount: Decimal = Decimal("500.00"),
    covered_until: date | None = None,
) -> AmortizationClaim:
    """A claim covering the first quarter of ``year`` unless told otherwise."""
    return AmortizationClaim(
        asset_id="computer",
        asset_revision_id="a" * 64,
        asset_kind=kind,
        tax_year=year,
        covered_from=date(year, 1, 1),
        covered_until=covered_until or date(year, 4, 1),
        amount=amount,
        schedule_fingerprint="b" * 64,
        authority_generation="published-test-generation",
        source_reference=f"modelo-100:{year}:parameter:test",
        creating_operation="record-amortization",
    )


def _asset(year: int) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="c" * 64,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="d" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000.00"),
            prior_allocation_provenance="canonical-ledger-allocation",
        ),
        in_service_date=date(year, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


@pytest.mark.parametrize("year", _supported_years())
def test_m130_projects_each_claim_to_the_sole_expense_casilla(year: int) -> None:
    """A claim reaches Modelo 130 as its own observation, never a replaced total."""
    period = Period.from_year_and_code(year, "1T")
    claim = _claim(year)

    observations = activity_asset_expense_observations((claim,), modelo="130", period=period)

    assert [observation.claim_id for observation in observations] == [claim.claim_id]
    assert observations[0].target_casilla_id == validated_casilla_id("02", surface="test M130 target")
    assert observations[0].deductible_amount == Decimal("500.00")


@pytest.mark.parametrize("year", _supported_years())
def test_m130_excludes_a_claim_covered_beyond_the_period_cutoff(year: int) -> None:
    """The year-to-date cutoff is the period end, so a later claim is not declared yet."""
    period = Period.from_year_and_code(year, "1T")

    within = activity_asset_expense_observations((_claim(year),), modelo="130", period=period)
    beyond = activity_asset_expense_observations(
        (_claim(year, covered_until=date(year, 7, 1)),),
        modelo="130",
        period=period,
    )

    assert len(within) == 1
    assert beyond == ()


@pytest.mark.parametrize("year", _supported_years())
def test_m100_keeps_material_and_intangible_destinations_distinct(year: int) -> None:
    """Material and intangible amortization reach distinct Modelo 100 casillas."""
    period = Period.from_year_and_code(year, "0A")
    material = _claim(year)
    intangible = _claim(year, kind=AssetKind.INTANGIBLE, amount=Decimal("125.00"))

    observations = activity_asset_expense_observations((material, intangible), modelo="100", period=period)

    by_claim = {observation.claim_id: observation for observation in observations}
    assert by_claim[material.claim_id].target_casilla_id == validated_casilla_id("0208", surface="test")
    assert by_claim[material.claim_id].deductible_amount == Decimal("500.00")
    assert by_claim[intangible.claim_id].target_casilla_id == validated_casilla_id("0227", surface="test")
    assert by_claim[intangible.claim_id].deductible_amount == Decimal("125.00")


@pytest.mark.parametrize("year", _supported_years())
def test_acquisition_evidence_is_valid_but_competing_depreciation_refuses(year: int) -> None:
    asset = _asset(year)
    claim = _claim(year)

    refuse_competing_depreciation_treatments((asset,), (claim,), ())
    with pytest.raises(ActividadAssetClaimConflictError, match="retain acquisition evidence"):
        refuse_competing_depreciation_treatments(
            (asset,),
            (claim,),
            (
                CompetingDepreciationTreatment(
                    asset_id=asset.asset_id,
                    transaction_id=asset.acquisition.observed_transaction_id,
                    category="hardware_depreciation",
                    tax_year=year,
                ),
            ),
        )
