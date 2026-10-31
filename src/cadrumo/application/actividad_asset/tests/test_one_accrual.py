"""Plan, forecast, Modelo 130 accrual and claim read one deductible pending value.

Hand-worked: a 10,000.00 basis at 10%, in service 1 January 2020, no opening amount and
no claim until 2025.  Each full year charges 1,000.00.  The value pending on 1 January
2025 is 10,000.00, because a year nobody claimed takes nothing from later years.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimState
from cadrumo.application.actividad_asset.disposal_calculation import DisposalBoundsReader
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import (
    M130ElementOutcome,
    PlanFigureAbsence,
    m130_register_accruals,
)
from cadrumo.domain.calculations.registry.actividad_asset_bindings import ActivityAssetDisposalBounds
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetPeriodElapsedError, ActividadAssetUnsupportedError
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

_ACQUISITION = acquisition_transaction(
    amount=Decimal("12100.00"), taxable_base=Decimal("10000.00"), iva_amount=Decimal("2100.00")
)
_ASSET = "machine-1"


def _revision(*, method: AmortizationMethod = AmortizationMethod.LINEAR, opening: str = "0") -> ActivityAssetRevision:
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
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("10000"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger allocation allocation-1",
        ),
        in_service_date=date(2020, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal(opening),
            covered_through_tax_year=2022 if opening != "0" else None,
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=method,
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
    constant = revision.amortization.method is AmortizationMethod.CONSTANT_PERCENTAGE
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=covered_from.year,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.10"),
            authority_generation="accrual-test-v1",
            source_reference="accrual test table",
            useful_life_ends_on=date(2050, 1, 1) if constant else None,
            maximum_period_ends_on=None if constant else date(2038, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def _one_eighteenth(_revision: ActivityAssetRevision, _tax_year: int) -> ActivityAssetDisposalBounds:
    return ActivityAssetDisposalBounds(minimum_coefficient=Decimal(1) / Decimal(18))


def _operations(
    *,
    revision: ActivityAssetRevision,
    today: date = date(2025, 6, 30),
    bounds: DisposalBoundsReader = _one_eighteenth,
    last_admitted_year: int | None = None,
) -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=replace(
            memory_register_authority(today=today, last_admitted_year=last_admitted_year), disposal_bounds=bounds
        ),
    )
    operations.create(revision, ActivityAssetDescriptorFacts(name="Machine"))
    return operations


def _year(operations: ActivityAssetOperations, year: int) -> ScheduledAmortizationCharge:
    return operations.forecast(asset_id=_ASSET, covered_from=date(year, 1, 1), covered_until=date(year + 1, 1, 1))


def _claim(operations: ActivityAssetOperations, year: int) -> None:
    operations.record_claim(_year(operations, year), creating_operation=f"test.{year}")


def test_plan_and_forecast_agree_on_the_charge_and_pending_value_after_unclaimed_years() -> None:
    operations = _operations(revision=_revision())

    rows = {row.tax_year: row for row in operations.plan(_ASSET)}
    forecast = _year(operations, 2025)
    (listed,) = operations.list_elements()

    assert forecast.amount == Decimal("1000.00")
    planned = rows[2025].planned
    assert planned is not None
    assert planned.decimal == "1000.00"
    assert listed.pending is not None
    assert listed.pending.decimal == "10000.00"


def test_the_minimum_to_date_is_shown_apart_and_never_lowers_the_value_pending() -> None:
    operations = _operations(revision=_revision())

    rows = {row.tax_year: row for row in operations.plan(_ASSET)}
    (listed,) = operations.list_elements()

    # 10,000 / 18 = 555.5555 a full year; five years sum to 2,777.78, rounded once.
    assert rows[2024].minimum_through is not None
    assert rows[2024].minimum_through.decimal == "2777.78"
    assert rows[2024].minimum_complete is True
    assert listed.pending is not None
    assert listed.pending.decimal == "10000.00"
    assert _year(operations, 2025).amount == Decimal("1000.00")


def test_a_year_without_minimum_authority_says_the_figure_leaves_it_out() -> None:
    def from_2022(revision: ActivityAssetRevision, tax_year: int) -> ActivityAssetDisposalBounds:
        return _one_eighteenth(revision, tax_year) if tax_year >= 2022 else ActivityAssetDisposalBounds()

    rows = {row.tax_year: row for row in _operations(revision=_revision(), bounds=from_2022).plan(_ASSET)}

    assert rows[2024].minimum_through is not None
    assert rows[2024].minimum_through.decimal == "1666.67"
    assert rows[2024].minimum_complete is False


def test_the_minimum_to_date_stops_at_the_basis() -> None:
    rows = _operations(revision=_revision(), today=date(2039, 1, 1)).plan(_ASSET)

    figures = {row.tax_year: row.minimum_through for row in rows}
    assert figures[2038] is not None
    assert figures[2038].decimal == "10000.00"


def test_an_unclaimed_past_year_shows_as_missing_with_its_figure_and_takes_nothing() -> None:
    rows = {row.tax_year: row for row in _operations(revision=_revision()).plan(_ASSET)}

    for year in range(2020, 2025):
        planned = rows[year].planned
        assert planned is not None
        assert planned.decimal == "1000.00"
        assert rows[year].claim_state is ActivityAssetClaimState.MISSING
        assert rows[year].claimed.decimal == "0"


def test_the_charge_of_a_pending_value_method_ignores_unclaimed_years() -> None:
    """Constant percentage charges on the value pending, so this figure proves what pending is."""
    operations = _operations(revision=_revision(method=AmortizationMethod.CONSTANT_PERCENTAGE))

    rows = {row.tax_year: row for row in operations.plan(_ASSET)}
    forecast = _year(operations, 2025)

    assert forecast.amount == Decimal("1000.00")
    planned = rows[2025].planned
    assert planned is not None
    assert planned.decimal == forecast.amount.to_eng_string()


def test_opening_and_claims_lower_the_pending_value_in_every_view() -> None:
    operations = _operations(revision=_revision(opening="3000"))
    _claim(operations, 2023)

    (listed,) = operations.list_elements()

    assert listed.pending is not None
    assert listed.pending.decimal == "6000.00"
    assert _year(operations, 2025).amount == Decimal("1000.00")


def test_claims_and_plan_never_exceed_the_basis_and_stop_when_it_is_exhausted() -> None:
    operations = _operations(revision=_revision(), today=date(2034, 12, 31), last_admitted_year=2034)
    for year in range(2025, 2035):
        _claim(operations, year)

    assert _year(operations, 2035).amount == Decimal("0.00")
    rows = operations.plan(_ASSET)
    claimed = sum((Decimal(row.claimed.decimal) for row in rows), Decimal("0"))
    assert claimed == Decimal("10000.00")
    (listed,) = operations.list_elements()
    assert listed.pending is not None
    assert Decimal(listed.pending.decimal) == Decimal("0")


def test_the_future_plan_projects_within_the_value_pending() -> None:
    rows = _operations(revision=_revision()).plan(_ASSET)

    future = [Decimal(row.planned.decimal) for row in rows if row.tax_year >= 2025 and row.planned is not None]

    assert sum(future, Decimal("0")) == Decimal("10000.00")
    assert rows[-1].planned is None


def test_the_maximum_period_stops_the_charge_with_value_still_pending() -> None:
    operations = _operations(revision=_revision(), today=date(2039, 1, 1))

    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed"):
        _year(operations, 2038)

    assert _year(operations, 2037).amount == Decimal("1000.00")


def test_the_modelo_130_accrual_reads_the_same_figure() -> None:
    revision = _revision()
    repository = MemoryRepository()
    history = repository.append_revision(revision)

    (accrual,) = m130_register_accruals(
        history,
        forecast=_forecast,
        period_end=date(2025, 12, 31),
        activities={_ASSET: None},
        agrarian=frozenset(),
    )

    assert accrual.outcome is M130ElementOutcome.ACCRUED
    assert [item.amount for item in accrual.contributions] == [Decimal("1000.00")]


def test_the_plan_projection_is_display_only_and_forecast_and_claim_never_read_it() -> None:
    """The plan projects 2025 to 2034 onto later rows; 2035 still forecasts on the real pending value."""
    operations = _operations(revision=_revision())

    rows = {row.tax_year: row for row in operations.plan(_ASSET)}

    assert rows[2035].planned is None
    assert rows[2035].absence is PlanFigureAbsence.BASIS_EXHAUSTED
    late = _year(operations, 2035)
    assert late.amount == Decimal("1000.00")
    with pytest.raises(ActividadAssetUnsupportedError, match="claim_year_beyond_registry"):
        operations.record_claim(late, creating_operation="test.2035")
    (listed,) = operations.list_elements()
    assert listed.pending is not None
    assert listed.pending.decimal == "10000.00"
