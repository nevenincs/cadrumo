from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetAmortizationMethod,
    ActivityAssetAuthoritySelection,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError, ActividadAssetValidationError
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
    ScheduleAuthority,
    schedule_charge,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _MemoryRepository:
    def __init__(self) -> None:
        self.history = ActivityAssetHistory()

    def load(self) -> ActivityAssetHistory:
        return self.history

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        self.history = self.history.append_revision(revision)
        return self.history

    def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
        result = self.history.record_claim(claim)
        self.history = result.history
        return result


def _revision(
    *,
    asset_id: str = "laptop-1",
    basis_amount: Decimal = Decimal("2000"),
    number: int = 1,
    supersedes: str | None = None,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=number,
        supersedes_revision_id=supersedes,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=basis_amount,
            prior_allocation_provenance="ledger allocation allocation-1",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
    )


def _authority() -> ScheduleAuthority:
    return ScheduleAuthority(
        asset_kind=AssetKind.MATERIAL,
        annual_rate=Decimal("0.26"),
        authority_generation="irpf-2025-assets-test-v1",
        source_reference="AEAT simplified direct-estimation table 2025",
    )


def _selection() -> ActivityAssetAuthoritySelection:
    return ActivityAssetAuthoritySelection(
        regime=DirectEstimationRegime.SIMPLIFIED,
        asset_kind=AssetKind.MATERIAL,
        authority_class_key="equipment-test-class",
    )


def _forecast(
    revision,
    *,
    selection,
    covered_from,
    covered_until,
    accumulated_effective_claims,
    accumulated_effective_free_depreciation_claims,
):
    assert selection == _selection()
    return schedule_charge(
        revision,
        _authority(),
        covered_from=covered_from,
        covered_until=covered_until,
        accumulated_effective_claims=accumulated_effective_claims,
        accumulated_effective_free_depreciation_claims=accumulated_effective_free_depreciation_claims,
    )


def test_frontend_operations_share_one_create_forecast_claim_and_projection_path() -> None:
    repository = _MemoryRepository()
    operations = ActivityAssetOperations(repository=repository, forecast_operation=_forecast)
    revision = _revision()

    operations.create(revision)
    forecast = operations.forecast(
        asset_id=revision.asset_id,
        selection=_selection(),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    assert forecast.amount == Decimal("520.00")
    assert repository.history.claims == ()

    first = operations.record_claim(forecast, creating_operation="actividad_asset.claim")
    retry = operations.record_claim(forecast, creating_operation="actividad_asset.claim")
    assert retry.reused_existing_claim is True
    assert retry.claim.claim_id == first.claim.claim_id
    assert len(repository.history.claims) == 1

    handoff = operations.filing_handoff(
        tax_year=2025,
        m130_period=Period.from_year_and_code(2025, "4T"),
    )
    assert handoff.material_m100.amount == Decimal("520.00")
    assert handoff.material_m130.amount == Decimal("520.00")
    assert handoff.material_m100.claim_ids == handoff.material_m130.claim_ids
    assert handoff.intangible_m100.amount == Decimal("0.00")


def test_correction_must_supersede_the_current_revision() -> None:
    operations = ActivityAssetOperations(repository=_MemoryRepository(), forecast_operation=_forecast)
    first = _revision()
    operations.create(first)

    with pytest.raises(ActividadAssetValidationError, match="current revision"):
        operations.correct(_revision(number=2, supersedes="c" * 64))

    corrected = _revision(number=2, supersedes=first.revision_id)
    history = operations.correct(corrected)
    assert operations.inspect(first.asset_id) == (first, corrected)
    assert history.revisions[-1] == corrected


def test_operations_use_effective_profile_history_for_the_free_depreciation_cap_without_forecast_consumption() -> None:
    repository = _MemoryRepository()

    def free_forecast(
        revision,
        *,
        selection,
        covered_from,
        covered_until,
        accumulated_effective_claims,
        accumulated_effective_free_depreciation_claims,
    ):
        election = selection.free_depreciation_election
        assert election is not None
        return schedule_charge(
            revision,
            ScheduleAuthority(
                asset_kind=AssetKind.MATERIAL,
                authority_generation="irpf-2025-published-test",
                source_reference="modelo-100:2025:low-value-free",
                method=AmortizationMethod.LOW_VALUE_FREE,
                free_depreciation_unit_threshold=Decimal("300.00"),
                free_depreciation_annual_cap=Decimal("500.00"),
                free_depreciation_election=election,
            ),
            covered_from=covered_from,
            covered_until=covered_until,
            accumulated_effective_claims=accumulated_effective_claims,
            accumulated_effective_free_depreciation_claims=accumulated_effective_free_depreciation_claims,
        )

    operations = ActivityAssetOperations(repository=repository, forecast_operation=free_forecast)
    first_asset = _revision(asset_id="low-value-first", basis_amount=Decimal("300.00"))
    second_asset = _revision(asset_id="low-value-second", basis_amount=Decimal("300.00"))
    operations.create(first_asset)
    operations.create(second_asset)

    def selection(*, requested_amount: Decimal) -> ActivityAssetAuthoritySelection:
        return ActivityAssetAuthoritySelection(
            regime=DirectEstimationRegime.NORMAL,
            asset_kind=AssetKind.MATERIAL,
            authority_class_key="mobiliario",
            method=ActivityAssetAmortizationMethod.LOW_VALUE_FREE,
            free_depreciation_election=FreeDepreciationElection(
                election_reference=f"election-{requested_amount}",
                new_material_evidence_reference="canonical-new-material-evidence",
                unit_acquisition_value=Decimal("300.00"),
                requested_amount=requested_amount,
            ),
        )

    forecast = operations.forecast(
        asset_id=first_asset.asset_id,
        selection=selection(requested_amount=Decimal("300.00")),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    assert repository.history.claims == ()
    operations.record_claim(forecast, creating_operation="test.free-depreciation")

    with pytest.raises(ActividadAssetUnsupportedError, match="annual cap"):
        operations.forecast(
            asset_id=second_asset.asset_id,
            selection=selection(requested_amount=Decimal("300.00")),
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
        )
    exact_cap_forecast = operations.forecast(
        asset_id=second_asset.asset_id,
        selection=selection(requested_amount=Decimal("200.00")),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    operations.record_claim(exact_cap_forecast, creating_operation="test.free-depreciation")
    assert sum((claim.amount for claim in repository.history.claims), Decimal("0")) == Decimal("500.00")
