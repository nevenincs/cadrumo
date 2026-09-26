from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.modality import direct_estimation_modality
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    LowValueElection,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
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
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LINEAR = ActivityAssetAmortizationElection(
    regime=DirectEstimationRegime.SIMPLIFIED,
    method=AmortizationMethod.LINEAR,
    authority_class_key="equipo-informacion-software",
)


def _simplified() -> DirectEstimationRegime:
    return DirectEstimationRegime.SIMPLIFIED


def _normal() -> DirectEstimationRegime:
    return DirectEstimationRegime.NORMAL


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
    election: ActivityAssetAmortizationElection = _LINEAR,
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
        acquired_condition=AcquiredCondition.NEW,
        amortization=election,
    )


def _linear_forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None,
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=2025,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="irpf-2025-assets-test-v1",
            source_reference="AEAT simplified direct-estimation table 2025",
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_frontend_operations_share_one_create_forecast_claim_and_projection_path() -> None:
    repository = _MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository, forecast_operation=_linear_forecast, taxpayer_modality=_simplified
    )
    revision = _revision()

    operations.create(revision)
    forecast = operations.forecast(
        asset_id=revision.asset_id,
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


def test_forecast_passes_effective_history_split_at_the_tax_year() -> None:
    repository = _MemoryRepository()
    seen: list[AssetScheduleHistory] = []

    def recording_forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None,
    ) -> ScheduledAmortizationCharge:
        seen.append(history)
        return _linear_forecast(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    operations = ActivityAssetOperations(
        repository=repository, forecast_operation=recording_forecast, taxpayer_modality=_simplified
    )
    revision = _revision()
    operations.create(revision)
    first_quarter = operations.forecast(
        asset_id=revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2025, 4, 1)
    )
    operations.record_claim(first_quarter, creating_operation="test.q1")
    operations.forecast(asset_id=revision.asset_id, covered_from=date(2025, 4, 1), covered_until=date(2025, 7, 1))

    assert seen[-1].accumulated_in_tax_year == first_quarter.amount
    assert seen[-1].accumulated_before_tax_year == Decimal("0")
    assert seen[-1].election_fingerprints_in_tax_year == (revision.amortization.fingerprint,)


def test_correction_must_supersede_the_current_revision() -> None:
    operations = ActivityAssetOperations(
        repository=_MemoryRepository(), forecast_operation=_linear_forecast, taxpayer_modality=_simplified
    )
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
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None,
    ) -> ScheduledAmortizationCharge:
        return schedule_charge(
            revision,
            ScheduleAuthority(
                tax_year=2025,
                asset_kind=AssetKind.MATERIAL,
                method=AmortizationMethod.LOW_VALUE_FREE,
                election_fingerprint=revision.amortization.fingerprint,
                authority_generation="irpf-2025-published-test",
                source_reference="modelo-100:2025:low-value-free",
                free_depreciation_unit_threshold=Decimal("300.00"),
                free_depreciation_annual_cap=Decimal("500.00"),
                low_value=revision.amortization.low_value,
            ),
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    def low_value(asset_id: str) -> ActivityAssetRevision:
        return _revision(
            asset_id=asset_id,
            basis_amount=Decimal("300.00"),
            election=ActivityAssetAmortizationElection(
                regime=DirectEstimationRegime.NORMAL,
                method=AmortizationMethod.LOW_VALUE_FREE,
                authority_class_key="mobiliario",
                low_value=LowValueElection(
                    election_reference=f"election-{asset_id}",
                    new_material_evidence_reference="canonical-new-material-evidence",
                    unit_acquisition_value=Decimal("300.00"),
                ),
            ),
        )

    operations = ActivityAssetOperations(
        repository=repository, forecast_operation=free_forecast, taxpayer_modality=_normal
    )
    first_asset = low_value("low-value-first")
    second_asset = low_value("low-value-second")
    operations.create(first_asset)
    operations.create(second_asset)

    forecast = operations.forecast(
        asset_id=first_asset.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        requested_free_amount=Decimal("300.00"),
    )
    assert repository.history.claims == ()
    operations.record_claim(forecast, creating_operation="test.free-depreciation")

    with pytest.raises(ActividadAssetUnsupportedError, match="annual cap"):
        operations.forecast(
            asset_id=second_asset.asset_id,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            requested_free_amount=Decimal("300.00"),
        )
    exact_cap_forecast = operations.forecast(
        asset_id=second_asset.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        requested_free_amount=Decimal("200.00"),
    )
    operations.record_claim(exact_cap_forecast, creating_operation="test.free-depreciation")
    assert sum((claim.amount for claim in repository.history.claims), Decimal("0")) == Decimal("500.00")


def test_forecast_refuses_an_election_the_taxpayer_modality_does_not_declare() -> None:
    operations = ActivityAssetOperations(
        repository=_MemoryRepository(),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_normal,
    )
    revision = _revision()
    operations.create(revision)

    with pytest.raises(ActividadAssetValidationError, match="profile declares normal"):
        operations.forecast(asset_id=revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1))


@pytest.mark.parametrize(
    ("profile_token", "expected"),
    [("directa_normal", DirectEstimationRegime.NORMAL), ("directa_simplificada", DirectEstimationRegime.SIMPLIFIED)],
)
def test_profile_direct_estimation_tokens_resolve_through_governed_authority(
    profile_token: str,
    expected: DirectEstimationRegime,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    assert direct_estimation_modality(profile_token, authority=authority_operation) is expected


@pytest.mark.parametrize(
    ("profile_token", "error", "message"),
    [
        (None, ActividadAssetIncompleteError, "declares no IRPF estimation regime"),
        ("objetiva", ActividadAssetUnsupportedError, "only for direct estimation"),
    ],
)
def test_absent_or_objective_profile_regime_refuses(
    profile_token: str | None,
    error: type[Exception],
    message: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(error, match=message):
        direct_estimation_modality(profile_token, authority=authority_operation)
