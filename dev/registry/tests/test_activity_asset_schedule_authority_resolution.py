"""Real-source resolution of 2025 activity-asset schedule authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetAuthoritySelection,
    DirectEstimationRegime,
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision() -> ModeloRevision:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100")).revisions["2025"]


def test_exact_normal_and_simplified_class_keys_resolve_source_rates() -> None:
    normal = resolve_activity_asset_schedule_authority(
        _revision(),
        tax_year=2025,
        selection=ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.NORMAL,
            asset_kind=AssetKind.MATERIAL,
            authority_class_key="equipo-proceso-informacion",
        ),
        authority_generation="candidate-source",
    )
    simplified = resolve_activity_asset_schedule_authority(
        _revision(),
        tax_year=2025,
        selection=ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            asset_kind=AssetKind.INTANGIBLE,
            authority_class_key="equipo-informacion-software",
        ),
        authority_generation="candidate-source",
    )

    assert normal.annual_rate == Decimal("0.25")
    assert simplified.annual_rate == Decimal("0.26")
    assert "parameter:" in normal.source_reference


def test_missing_class_and_kind_mismatch_fail_closed() -> None:
    with pytest.raises(ActividadAssetUnsupportedError, match="not enrolled"):
        resolve_activity_asset_schedule_authority(
            _revision(),
            tax_year=2025,
            selection=ActivityAssetAuthoritySelection(
                regime=DirectEstimationRegime.NORMAL,
                asset_kind=AssetKind.MATERIAL,
                authority_class_key="caller-invented-class",
            ),
            authority_generation="candidate-source",
        )


def test_missing_regime_parameter_fails_before_class_lookup() -> None:
    revision = _revision()
    stripped = revision.model_copy(
        update={
            "parameters": tuple(
                parameter
                for parameter in revision.parameters
                if str(parameter.id)
                != "renta-actividad-inmovilizado-amortizacion-normal-coeficiente-lineal-maximo"
            ),
        },
    )

    with pytest.raises(ActividadAssetUnsupportedError, match="authority parameter"):
        resolve_activity_asset_schedule_authority(
            stripped,
            tax_year=2025,
            selection=ActivityAssetAuthoritySelection(
                regime=DirectEstimationRegime.NORMAL,
                asset_kind=AssetKind.MATERIAL,
                authority_class_key="mobiliario",
            ),
            authority_generation="candidate-source",
        )
    with pytest.raises(ActividadAssetUnsupportedError, match="intangible asset"):
        resolve_activity_asset_schedule_authority(
            _revision(),
            tax_year=2025,
            selection=ActivityAssetAuthoritySelection(
                regime=DirectEstimationRegime.NORMAL,
                asset_kind=AssetKind.INTANGIBLE,
                authority_class_key="mobiliario",
            ),
            authority_generation="candidate-source",
        )


def test_two_thousand_euro_computer_forecasts_permitted_charge_not_purchase_cost() -> None:
    asset = ActivityAssetRevision(
        asset_id="computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
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
    )

    charge = forecast_activity_asset_charge(
        asset,
        modelo_100_revision=_revision(),
        selection=ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.NORMAL,
            asset_kind=AssetKind.MATERIAL,
            authority_class_key="equipo-proceso-informacion",
        ),
        authority_generation="candidate-source",
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )

    assert charge.amount == Decimal("500.00")
    assert charge.amount != asset.basis.deductible_basis()
