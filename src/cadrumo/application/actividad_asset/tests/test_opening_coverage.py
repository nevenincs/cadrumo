"""The schedule walk reads a non-zero opening amount as covering years through its stated tax year.

Figures are hand-worked from a 10,000.00 basis at 10% linear, in service from
1 January 2020, with an opening amount of 3,000.00: each uncovered full year charges 1,000.00.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetRegisterState
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence, WalkedYear, walk_element
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
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

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository, describing, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACQUISITION = acquisition_transaction(
    amount=Decimal("12100.00"),
    taxable_base=Decimal("10000.00"),
    iva_amount=Decimal("2100.00"),
)


def _revision(*, opening_through: int) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="machine-1",
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
            accumulated_amount=Decimal("3000"),
            covered_through_tax_year=opening_through,
        ),
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
            annual_rate=Decimal("0.10"),
            authority_generation="walk-test-v1",
            source_reference="walk test table",
            maximum_period_ends_on=date(2040, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def _walk(opening_through: int) -> dict[int, WalkedYear]:
    revision = _revision(opening_through=opening_through)
    rows = walk_element(
        revision,
        ActivityAssetHistory().append_revision(revision),
        forecast=_forecast,
        through_year=2025,
    )
    return {row.tax_year: row for row in rows}


def test_years_after_the_opening_year_are_missing_gaps_that_consume_nothing() -> None:
    rows = _walk(2022)

    covered = [year for year, row in rows.items() if row.absence is PlanFigureAbsence.COVERED_BY_OPENING]
    assert covered == [2020, 2021, 2022]
    for year in (2023, 2024):
        charge = rows[year].charge
        assert charge is not None
        assert charge.amount == Decimal("1000.00")
        assert len(rows[year].gaps) == 1
    assert rows[2024].consumed_before == Decimal("0")
    assert rows[2025].consumed_before == Decimal("0")


def _register(opening_through: int, *, today: date) -> tuple[ActivityAssetOperations, ActivityAssetRevision]:
    revision = _revision(opening_through=opening_through)
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=today),
    )
    operations.create(revision, describing(revision))
    return operations, revision


def test_the_read_model_shows_the_basis_less_the_opening_as_pending_whatever_years_are_missing() -> None:
    operations, _ = _register(2022, today=date(2025, 12, 31))

    (row,) = operations.list_elements()

    # 10,000.00 basis less the 3,000.00 opening; 2023 to 2025 are missing and take nothing.
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("7000.00")
    assert row.accumulated is not None
    assert Decimal(row.accumulated.decimal) == Decimal("3000.00")
    assert row.findings.missing == 3


def test_a_later_year_charges_its_full_figure_after_missing_years_and_a_claim_lowers_pending() -> None:
    operations, _ = _register(2022, today=date(2025, 12, 31))

    plan = {item.tax_year: item for item in operations.plan("machine-1")}
    for year in (2023, 2024, 2025, 2026):
        figure = plan[year].planned
        assert figure is not None
        assert Decimal(figure.decimal) == Decimal("1000.00")

    charge = operations.forecast(
        asset_id="machine-1",
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    assert charge.amount == Decimal("1000.00")
    operations.record_claim(charge, creating_operation="test.2025")

    (row,) = operations.list_elements()
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("6000.00")


def test_the_maximum_period_stops_the_plan_with_the_unclaimed_value_still_pending() -> None:
    operations, _ = _register(2022, today=date(2041, 6, 30))

    plan = {item.tax_year: item for item in operations.plan("machine-1")}

    # The table period ends on 1 January 2040, so 2039 is the last charge and 2040 has none.
    figure = plan[2039].planned
    assert figure is not None
    assert Decimal(figure.decimal) == Decimal("1000.00")
    assert plan[2040].planned is None
    assert plan[2040].absence is PlanFigureAbsence.PERIOD_ELAPSED
    (row,) = operations.list_elements()
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("7000.00")
    assert row.state is ActivityAssetRegisterState.IN_SERVICE


def test_an_opening_through_the_last_walked_year_leaves_no_gap_year() -> None:
    rows = _walk(2024)

    covered = [year for year, row in rows.items() if row.absence is PlanFigureAbsence.COVERED_BY_OPENING]
    assert covered == [2020, 2021, 2022, 2023, 2024]
    assert all(row.gaps == () and row.charge is None for year, row in rows.items() if year <= 2024)
    assert rows[2025].consumed_before == Decimal("0")
