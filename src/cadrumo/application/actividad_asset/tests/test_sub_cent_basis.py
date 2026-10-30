"""A basis with sub-cent precision has one ceiling, whichever route compares against it.

Hand-worked: 1,234.57 at a 35% business share is an amortizable basis of 432.0995.  At
50% a full year charges 216.04975, emitted as 216.05.  Two years total 432.10, which is
the basis in cents, so nothing remains and the third year charges 0.00.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import (
    M130ElementOutcome,
    PlanFigureAbsence,
    free_base_remains,
    m130_register_accruals,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
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
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACQUISITION = acquisition_transaction()
_ASSET = "tablet-1"


def _revision() -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=_ASSET,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=_ACQUISITION.transaction_id,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.TAXPAYER_OWNED,
            basis_amount=Decimal("1234.57"),
            non_deductible_iva=Decimal("0"),
            business_use_share=Decimal("0.35"),
        ),
        in_service_date=date(2020, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key="maquinaria",
        ),
    )


def _forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=covered_from.year,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.50"),
            authority_generation="sub-cent-test",
            source_reference="sub-cent test table",
            maximum_period_ends_on=date(2040, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def _claimed_two_years() -> tuple[ActivityAssetOperations, MemoryRepository]:
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2023, 12, 31)),
    )
    operations.create(_revision(), ActivityAssetDescriptorFacts(name="Tablet"))
    for year in (2020, 2021):
        charge = operations.forecast(asset_id=_ASSET, covered_from=date(year, 1, 1), covered_until=date(year + 1, 1, 1))
        assert charge.amount == Decimal("216.05")
        operations.record_claim(charge, creating_operation=f"test.{year}")
    return operations, repository


def test_the_year_after_charges_totalling_the_basis_in_cents_forecasts_zero() -> None:
    operations, _ = _claimed_two_years()

    charge = operations.forecast(asset_id=_ASSET, covered_from=date(2022, 1, 1), covered_until=date(2023, 1, 1))

    assert charge.amount == Decimal("0.00")
    assert {row.tax_year: row.absence for row in operations.plan(_ASSET)}[2022] is PlanFigureAbsence.BASIS_EXHAUSTED
    (listed,) = operations.list_elements()
    assert listed.pending is not None
    assert Decimal(listed.pending.decimal) == Decimal("0")


def test_the_later_modelo_130_has_nothing_to_accrue_and_is_not_unavailable() -> None:
    _, repository = _claimed_two_years()

    (accrual,) = m130_register_accruals(
        repository.history,
        forecast=_forecast,
        period_end=date(2023, 12, 31),
        activities={_ASSET: None},
        agrarian=frozenset(),
    )

    assert accrual.outcome is M130ElementOutcome.NOTHING
    assert accrual.error is None


def test_claims_above_the_basis_in_cents_are_still_refused() -> None:
    history = AssetScheduleHistory(accumulated_before_tax_year=Decimal("432.11"))

    with pytest.raises(ActividadAssetValidationError, match="claims_exceed_amortizable_basis"):
        _forecast(_revision(), covered_from=date(2022, 1, 1), covered_until=date(2023, 1, 1), history=history)


def test_the_history_write_refuses_one_cent_past_the_ceiling() -> None:
    _, repository = _claimed_two_years()
    (first, *_) = repository.history.claims
    excess = first.model_copy(
        update={
            "tax_year": 2022,
            "covered_from": date(2022, 1, 1),
            "covered_until": date(2023, 1, 1),
            "amount": Decimal("0.01"),
        },
    )

    with pytest.raises(ActividadAssetClaimConflictError, match="claims_exceed_amortizable_basis"):
        repository.history.record_claim(excess)


def test_a_free_method_test_of_remaining_base_uses_the_same_ceiling() -> None:
    _, repository = _claimed_two_years()
    history = repository.history

    assert free_base_remains(history.revisions[0], history, tax_year=2022) is False
