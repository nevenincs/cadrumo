"""Real-source resolution of 2025 activity-asset schedule authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetAmortizationMethod,
    ActivityAssetAuthoritySelection,
    DirectEstimationRegime,
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
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
from cadrumo.domain.renta.actividad_asset.schedule import (
    AmortizationMethod,
    FreeDepreciationElection,
    ScheduledAmortizationCharge,
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


def test_low_value_free_authority_resolves_published_threshold_and_cap_with_explicit_election() -> None:
    authority = resolve_activity_asset_schedule_authority(
        _revision(),
        tax_year=2025,
        selection=ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.NORMAL,
            asset_kind=AssetKind.MATERIAL,
            authority_class_key="mobiliario",
            method=ActivityAssetAmortizationMethod.LOW_VALUE_FREE,
            free_depreciation_election=FreeDepreciationElection(
                election_reference="operator-low-value-election",
                new_material_evidence_reference="canonical-invoice-new-item-attestation",
                unit_acquisition_value=Decimal("300.00"),
                requested_amount=Decimal("300.00"),
            ),
        ),
        authority_generation="candidate-source",
    )

    assert authority.method is AmortizationMethod.LOW_VALUE_FREE
    assert authority.free_depreciation_unit_threshold == Decimal("300")
    assert authority.free_depreciation_annual_cap == Decimal("25000")
    assert "libertad-amortizacion-umbral-unitario" in authority.source_reference
    assert "libertad-amortizacion-limite-anual" in authority.source_reference


def test_low_value_free_refuses_intangible_and_missing_explicit_election() -> None:
    with pytest.raises(ValueError, match="material assets"):
        ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.NORMAL,
            asset_kind=AssetKind.INTANGIBLE,
            authority_class_key="intangible-software",
            method=ActivityAssetAmortizationMethod.LOW_VALUE_FREE,
            free_depreciation_election=FreeDepreciationElection(
                election_reference="bad-kind",
                new_material_evidence_reference="evidence",
                unit_acquisition_value=Decimal("300.00"),
                requested_amount=Decimal("300.00"),
            ),
        )


def test_low_value_free_real_authority_forecast_records_one_idempotent_encrypted_history_claim() -> None:
    class MemoryHistoryRepository:
        def __init__(self) -> None:
            self.history = ActivityAssetHistory()

        def load(self) -> ActivityAssetHistory:
            return self.history

        def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
            self.history = self.history.append_revision(revision)
            return self.history

        def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
            recorded = self.history.record_claim(claim)
            self.history = recorded.history
            return recorded

    asset = ActivityAssetRevision(
        asset_id="published-free-depreciation-tool",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="canonical-new-material-invoice",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("300.00"),
            prior_allocation_provenance="reviewed allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
    )
    selection = ActivityAssetAuthoritySelection(
        regime=DirectEstimationRegime.NORMAL,
        asset_kind=AssetKind.MATERIAL,
        authority_class_key="mobiliario",
        method=ActivityAssetAmortizationMethod.LOW_VALUE_FREE,
        free_depreciation_election=FreeDepreciationElection(
            election_reference="operator-elected-full-amount",
            new_material_evidence_reference="canonical-new-material-invoice",
            unit_acquisition_value=Decimal("300.00"),
            requested_amount=Decimal("300.00"),
        ),
    )
    repository = MemoryHistoryRepository()

    def forecast(
        revision: ActivityAssetRevision,
        *,
        selection: ActivityAssetAuthoritySelection,
        covered_from: date,
        covered_until: date,
        accumulated_effective_claims: Decimal,
        accumulated_effective_free_depreciation_claims: Decimal,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=_revision(),
            authority_generation="published-registry-test-generation",
            selection=selection,
            covered_from=covered_from,
            covered_until=covered_until,
            accumulated_effective_claims=accumulated_effective_claims,
            accumulated_effective_free_depreciation_claims=accumulated_effective_free_depreciation_claims,
        )

    operations = ActivityAssetOperations(repository=repository, forecast_operation=forecast)
    operations.create(asset)
    forecast_charge = operations.forecast(
        asset_id=asset.asset_id,
        selection=selection,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    first = operations.record_claim(forecast_charge, creating_operation="test.real-authority-free-depreciation")
    retry = operations.record_claim(forecast_charge, creating_operation="test.real-authority-free-depreciation")

    assert forecast_charge.amount == Decimal("300.00")
    assert first.claim.method is AmortizationMethod.LOW_VALUE_FREE
    assert "libertad-amortizacion-umbral-unitario" in first.claim.source_reference
    assert retry.reused_existing_claim is True
    with pytest.raises(ValueError, match="explicit election"):
        ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            asset_kind=AssetKind.MATERIAL,
            authority_class_key="util-herramienta",
            method=ActivityAssetAmortizationMethod.LOW_VALUE_FREE,
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
