"""Read-only activity-asset filing composition and collision tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
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
from .._models import CasillaAggregation
from ..modelo_bindings_actividad_assets import (
    CompetingDepreciationTreatment,
    add_activity_assets_to_m130_expenses,
    project_activity_assets_to_m100,
    refuse_competing_depreciation_treatments,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _claim(*, kind: AssetKind = AssetKind.MATERIAL, amount: Decimal = Decimal("500.00")) -> AmortizationClaim:
    return AmortizationClaim(
        asset_id="computer",
        asset_revision_id="a" * 64,
        asset_kind=kind,
        tax_year=2025,
        covered_from=date(2025, 1, 1),
        covered_until=date(2025, 4, 1),
        amount=amount,
        schedule_fingerprint="b" * 64,
        authority_generation="published-test-generation",
        source_reference="modelo-100:2025:parameter:test",
        creating_operation="record-amortization",
    )


def _asset() -> ActivityAssetRevision:
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
        in_service_date=date(2025, 1, 1),
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


def test_m130_adds_claim_to_ordinary_expenses_without_replacing_them() -> None:
    period = Period.from_year_and_code(2025, "1T")
    target = validated_casilla_id("02", surface="test M130 target")
    ordinary = CasillaAggregation(modelo="130", period=period, casilla_values={target: Decimal("300.00")})
    claim = _claim()

    result = add_activity_assets_to_m130_expenses(ordinary, (claim,))

    assert result.casilla_values[target] == Decimal("800.00")
    assert result.claim_ids == (claim.claim_id,)
    assert ordinary.casilla_values[target] == Decimal("300.00")


def test_m100_keeps_material_and_intangible_destinations_distinct() -> None:
    period = Period.from_year_and_code(2025, "0A")
    material = _claim()
    intangible = _claim(kind=AssetKind.INTANGIBLE, amount=Decimal("125.00"))

    result = project_activity_assets_to_m100((material, intangible), period=period)

    assert result.casilla_values[validated_casilla_id("0208", surface="test")] == Decimal("500.00")
    assert result.casilla_values[validated_casilla_id("0227", surface="test")] == Decimal("125.00")
    assert set(result.claim_ids) == {material.claim_id, intangible.claim_id}


def test_acquisition_evidence_is_valid_but_competing_depreciation_refuses() -> None:
    asset = _asset()
    claim = _claim()

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
                    tax_year=2025,
                ),
            ),
        )
