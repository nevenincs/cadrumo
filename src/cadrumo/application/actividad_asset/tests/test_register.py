"""The register's descriptor, event order, reads, atomic correction and one accrual route.

Figures are hand-worked from a fixed 26% linear charge on a 2,000.00 basis in service
from 1 January of the year before the support horizon: 520.00 a full year, so 2,000 / 520 = 3.85 years of charge.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    DISPOSAL_FINDING_FAMILY,
    NON_DEDUCTIBLE_IVA_STATE_FAMILY,
    PLAN_ADVISORY_FAMILY,
    TIMELINE_TOKEN_FAMILIES,
    ActivityAssetClaimStaleReason,
    ActivityAssetClaimState,
    ActivityAssetListRow,
    ActivityAssetNonDeductibleIvaState,
    ActivityAssetPlanAdvisoryKind,
    ActivityAssetRegisterState,
    activity_asset_label_key,
)
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations, SupersedingClaimRequest
from cadrumo.application.actividad_asset.register_reads import register_years
from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from cadrumo.core.period import Period
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    supported_authored_exercises,
)
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalFindingKind,
    ActivityAssetDisposalReason,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetPeriodElapsedError,
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
from cadrumo.domain.renta.actividad_asset.register_records import (
    ActivityAssetDescriptorFacts,
    ActivityAssetEventKind,
)
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    require_method_continuity,
    schedule_charge,
)

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


ACQUISITION = acquisition_transaction()
NAME = ActivityAssetDescriptorFacts(name="Office laptop", serial_number="SN-1")
FIRST_YEAR = filing_year_envelope().horizon - 1
_AT = datetime(FIRST_YEAR, 3, 1, 9, 0, tzinfo=UTC)


def register_revision(
    *,
    number: int = 1,
    supersedes: str | None = None,
    basis: str = "2000.00",
    in_service: date = date(FIRST_YEAR, 1, 1),
    method: AmortizationMethod = AmortizationMethod.LINEAR,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="laptop-1",
        revision_number=number,
        supersedes_revision_id=supersedes,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=ACQUISITION.transaction_id,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal(basis),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger allocation allocation-1",
        ),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=method,
            authority_class_key="equipo-informacion-software",
        ),
    )


def register_forecast(
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
            annual_rate=Decimal("0.26"),
            authority_generation="register-test-v1",
            source_reference="register test table",
            maximum_period_ends_on=date(FIRST_YEAR + 10, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def register_operations(
    *,
    today: date = date(FIRST_YEAR, 12, 31),
    consumers: dict[str, tuple[str, ...]] | None = None,
    last_admitted_year: int | None = None,
) -> tuple[ActivityAssetOperations, MemoryRepository]:
    repository = MemoryRepository()
    return (
        ActivityAssetOperations(
            repository=repository,
            ledger=MemoryLedger(ACQUISITION),
            forecast_operation=register_forecast,
            taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
            register_authority=memory_register_authority(
                today=today, consumers=consumers, last_admitted_year=last_admitted_year
            ),
        ),
        repository,
    )


def full_year(operations: ActivityAssetOperations, year: int) -> ScheduledAmortizationCharge:
    return operations.forecast(
        asset_id="laptop-1",
        covered_from=date(year, 1, 1),
        covered_until=date(year + 1, 1, 1),
    )


def test_a_descriptor_changes_no_revision_claim_or_fingerprint() -> None:
    operations, repository = register_operations()
    revision = register_revision()
    operations.create(revision, NAME, recorded_at=_AT, origin="test.create")
    charge = full_year(operations, FIRST_YEAR)
    operations.record_claim(charge, creating_operation="test.claim")
    before = repository.history

    after = operations.describe(
        "laptop-1",
        ActivityAssetDescriptorFacts(name="Renamed laptop", supplier_name="Proveedor"),
        origin="test.describe",
    )

    assert after.same_tax_facts(before)
    assert after.revisions[0].revision_id == revision.revision_id
    assert full_year(operations, FIRST_YEAR).schedule_fingerprint == charge.schedule_fingerprint
    descriptor = after.current_descriptor("laptop-1")
    assert descriptor is not None
    assert (descriptor.descriptor_number, descriptor.facts.name) == (2, "Renamed laptop")
    # A forecast taken before the rename still records: the rename moved no tax fact.
    assert operations.record_claim(charge, creating_operation="test.claim").reused_existing_claim is True


def test_restating_the_current_descriptor_writes_nothing_and_a_blank_name_is_refused() -> None:
    operations, repository = register_operations()
    operations.create(register_revision(), NAME)
    before = repository.history

    assert operations.describe("laptop-1", NAME) is before
    with pytest.raises(ValueError, match="must not be blank"):
        ActivityAssetDescriptorFacts(name="   ")


def test_describing_an_unknown_element_is_refused() -> None:
    operations, _ = register_operations()

    with pytest.raises(ActividadAssetValidationError, match="asset_not_found"):
        operations.describe("absent", NAME)


def test_events_keep_history_order_with_nullable_time_outside_identity() -> None:
    operations, repository = register_operations()
    revision = register_revision()
    operations.create(revision, NAME, recorded_at=_AT, origin="test.create")
    operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.claim")

    events = repository.history.ordered_events()

    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.kind for event in events] == [
        ActivityAssetEventKind.REVISION,
        ActivityAssetEventKind.DESCRIPTOR,
        ActivityAssetEventKind.CLAIM,
    ]
    assert [event.recorded_at for event in events] == [_AT, _AT, None]
    assert events[2].origin == "test.claim"
    assert revision.revision_id == register_revision().revision_id


def test_a_correction_and_its_superseding_claim_land_together() -> None:
    operations, repository = register_operations()
    first = register_revision()
    operations.create(first, NAME)
    claim = operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.claim").claim
    assert claim.amount == Decimal("520.00")
    corrected = register_revision(number=2, supersedes=first.revision_id, basis="400")
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="correction_below_effective_claims"):
        operations.correct(corrected)
    assert repository.history == before
    with pytest.raises(ActividadAssetValidationError, match="superseded_claim_not_effective"):
        operations.correct(corrected, (SupersedingClaimRequest(supersedes_claim_id="f" * 64),))
    assert repository.history == before

    after = operations.correct(
        corrected,
        (SupersedingClaimRequest(supersedes_claim_id=claim.claim_id),),
        origin="test.correct",
    )

    # 400.00 x 26% = 104.00 for the full year under the new revision.
    replacement = after.claims[-1]
    assert replacement.amount == Decimal("104.00")
    assert replacement.supersedes_claim_id == claim.claim_id
    assert replacement.asset_revision_id == corrected.revision_id
    assert [event.kind for event in after.events[-2:]] == [
        ActivityAssetEventKind.REVISION,
        ActivityAssetEventKind.CLAIM,
    ]


def test_a_correction_exactly_at_the_claimed_basis_needs_no_superseding_claim() -> None:
    operations, _ = register_operations()
    first = register_revision()
    operations.create(first, NAME)
    operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.claim")

    assert (
        operations.correct(register_revision(number=2, supersedes=first.revision_id, basis="520")).revisions[-1].basis
    )


def test_an_earlier_year_is_claimable_at_a_rate_method_up_to_its_maximum() -> None:
    operations, _ = register_operations(today=date(FIRST_YEAR + 1, 12, 31))
    operations.create(register_revision(), NAME)
    operations.record_claim(full_year(operations, FIRST_YEAR + 1), creating_operation="test.later")

    earlier = full_year(operations, FIRST_YEAR)

    assert earlier.amount == Decimal("520.00")
    assert operations.record_claim(earlier, creating_operation="test.earlier").claim.tax_year == FIRST_YEAR


@pytest.mark.parametrize(
    ("method", "key"),
    [
        (AmortizationMethod.CONSTANT_PERCENTAGE, "earlier_year_depends_on_pending_value"),
        (AmortizationMethod.SUM_OF_DIGITS, "earlier_year_depends_on_pending_value"),
        (AmortizationMethod.LOW_VALUE_FREE, "earlier_year_free_depreciation_not_taken"),
    ],
)
def test_an_earlier_year_behind_a_later_claim_is_refused_with_its_typed_reason(
    method: AmortizationMethod,
    key: str,
) -> None:
    with pytest.raises(ActividadAssetUnsupportedError, match=key):
        require_method_continuity(
            method,
            "a" * 64,
            AssetScheduleHistory(accumulated_after_tax_year=Decimal("100.00")),
        )


def test_the_plan_lists_each_year_until_the_basis_runs_out() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    claim = operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.claim").claim

    rows = operations.plan("laptop-1")

    assert [row.tax_year for row in rows] == list(range(FIRST_YEAR, FIRST_YEAR + 5))
    assert [None if row.planned is None else row.planned.decimal for row in rows] == [
        "520.00",
        "520.00",
        "520.00",
        "440.00",
        None,
    ]
    assert rows[0].claim_state is ActivityAssetClaimState.CLAIMED
    assert rows[0].claimed.decimal == "520.00"
    assert rows[0].claims[0].claim_id == claim.claim_id
    assert rows[1].claim_state is ActivityAssetClaimState.NOT_DUE
    assert rows[1].claimable_intervals[0].covered_from == date(FIRST_YEAR + 1, 1, 1)
    assert rows[4].absence is PlanFigureAbsence.BASIS_EXHAUSTED
    assert rows[0].edition is not None
    authored = supported_authored_exercises("100")
    for row in rows[:2]:
        assert row.edition is not None
        assert row.edition.projected is (row.tax_year not in authored)


def test_a_past_unclaimed_year_is_missing_and_a_partial_one_is_partial() -> None:
    operations, _ = register_operations(today=date(FIRST_YEAR + 1, 6, 30))
    operations.create(register_revision(), NAME)
    operations.record_claim(
        operations.forecast(
            asset_id="laptop-1", covered_from=date(FIRST_YEAR + 1, 1, 1), covered_until=date(FIRST_YEAR + 1, 4, 1)
        ),
        creating_operation="test.q1",
    )

    rows = {row.tax_year: row for row in operations.plan("laptop-1")}

    assert rows[FIRST_YEAR].claim_state is ActivityAssetClaimState.MISSING
    assert rows[FIRST_YEAR + 1].claim_state is ActivityAssetClaimState.PARTIAL
    assert rows[FIRST_YEAR + 1].claimable_intervals[0].covered_from == date(FIRST_YEAR + 1, 4, 1)


def test_the_list_row_reports_name_figures_and_findings() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.claim")

    row = operations.list_elements()[0]

    assert (row.name, row.serial_number) == ("Office laptop", "SN-1")
    assert row.state is ActivityAssetRegisterState.IN_SERVICE
    assert (row.basis.decimal, row.accumulated, row.pending) == (
        "2000.00",
        row.accumulated,
        row.pending,
    )
    assert row.accumulated is not None
    assert row.pending is not None
    assert Decimal(row.accumulated.decimal) == Decimal("520")
    assert Decimal(row.pending.decimal) == Decimal("1480")
    assert (row.findings.missing, row.findings.stale) == (0, 0)


def test_the_timeline_says_what_changed_what_used_a_claim_and_why_it_is_stale() -> None:
    claim_consumers: dict[str, tuple[str, ...]] = {}
    operations, _ = register_operations(consumers=claim_consumers)
    first = register_revision()
    operations.create(first, NAME, origin="test.create")
    claim = operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.claim").claim
    claim_consumers[claim.claim_id] = ("calculation-1",)

    current = operations.timeline("laptop-1")[-1]
    assert current.claim is not None
    assert current.claim.used_by == ("calculation-1",)
    assert current.claim.matches_current_schedule is True
    assert current.claim.stale_reason is None
    assert current.affects_calculation is True

    operations.correct(register_revision(number=2, supersedes=first.revision_id, basis="1000"), origin="test.correct")
    operations.describe("laptop-1", ActivityAssetDescriptorFacts(name="Renamed"), origin="test.describe")

    events = operations.timeline("laptop-1")
    assert [event.kind for event in events] == [
        ActivityAssetEventKind.REVISION,
        ActivityAssetEventKind.DESCRIPTOR,
        ActivityAssetEventKind.CLAIM,
        ActivityAssetEventKind.REVISION,
        ActivityAssetEventKind.DESCRIPTOR,
    ]
    stale = events[2].claim
    assert stale is not None
    assert stale.matches_current_schedule is False
    assert stale.stale_reason is ActivityAssetClaimStaleReason.REVISION_CHANGED
    assert events[3].origin == "test.correct"
    assert "basis.basis_amount" in {change.field for change in events[3].changes}
    assert events[4].affects_calculation is False
    assert [(item.field, item.before, item.after) for item in events[4].changes if item.field == "name"] == [
        ("name", "Office laptop", "Renamed"),
    ]


def test_a_candidate_states_unknown_non_deductible_iva_and_never_zero() -> None:
    operations, _ = register_operations()

    candidate = operations.acquisition_candidates()[0]

    assert candidate.transaction_id == ACQUISITION.transaction_id
    assert candidate.non_deductible_iva_state is ActivityAssetNonDeductibleIvaState.UNKNOWN
    assert candidate.non_deductible_iva is None
    assert candidate.taxable_base is not None
    assert candidate.taxable_base.decimal == "2000.00"


def test_an_acquisition_an_element_names_is_no_longer_a_candidate() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)

    assert operations.acquisition_candidates() == ()


def test_form_options_come_from_the_published_registry() -> None:
    operations, _ = register_operations()

    tax_year = newest_authored_edition("100")
    options = operations.form_options(asset_kind=AssetKind.MATERIAL, tax_year=tax_year)

    groups = {group.class_key: group for group in options.table_groups}
    computers = groups["equipo-informacion-software"]
    assert Decimal(computers.maximum_coefficient.decimal) == Decimal("0.26")
    assert AmortizationMethod.LINEAR in options.methods
    assert options.edition.authored_filing_year == tax_year
    assert set(options.acquisition_shapes) == {
        AcquisitionShape.PRIMARY_PURCHASE,
        AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER,
    }
    assert options.declared_activities == tuple(TipoActividad)


def test_the_handoff_reads_the_accrual_route_with_or_without_claims() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    period = Period.from_year_and_code(FIRST_YEAR, "2T")
    # 520.00 a full year, charged by calendar days through 30 June, with nothing recorded.
    year_days = 366 if calendar.isleap(FIRST_YEAR) else 365
    first_half = (Decimal("520.00") * (date(FIRST_YEAR, 7, 1) - date(FIRST_YEAR, 1, 1)).days / year_days).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    unclaimed = operations.filing_handoff(tax_year=FIRST_YEAR, m130_period=period)
    assert unclaimed.material_m130 is not None
    assert unclaimed.material_m130.amount == first_half
    assert unclaimed.material_m100 is not None
    assert unclaimed.material_m100.amount == Decimal("0.00")
    assert unclaimed.material_m100.claim_ids == ()

    claim = operations.record_claim(
        operations.forecast(
            asset_id="laptop-1", covered_from=date(FIRST_YEAR, 1, 1), covered_until=date(FIRST_YEAR, 7, 1)
        ),
        creating_operation="test.h1",
    ).claim
    claimed = operations.filing_handoff(tax_year=FIRST_YEAR, m130_period=period)

    assert claimed.material_m130 is not None
    assert claimed.material_m130.amount == first_half
    assert claimed.material_m100 is not None
    assert claimed.material_m100.claim_ids == (claim.claim_id,)
    assert claimed.material_m100.amount == first_half


def test_the_handoff_refuses_a_foral_profile() -> None:
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=register_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(territory=ResidenceTerritory.FORAL),
    )
    operations.create(register_revision(), NAME)

    with pytest.raises(ActividadAssetValidationError, match="foral_territory"):
        operations.filing_handoff(tax_year=FIRST_YEAR, m130_period=Period.from_year_and_code(FIRST_YEAR, "4T"))


def test_an_elapsed_period_counts_as_amortized_in_the_plan_and_m130() -> None:
    def elapsed_after_second_year(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        if covered_from.year > FIRST_YEAR + 1:
            raise ActividadAssetPeriodElapsedError(
                context={"ended_on": date(FIRST_YEAR + 2, 1, 1).isoformat()},
                translated_message="ledger.actividad_asset.errors.amortization_period_elapsed",
            )
        return register_forecast(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=elapsed_after_second_year,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(FIRST_YEAR + 3, 6, 30)),
    )
    operations.create(register_revision(), NAME)

    rows = {row.tax_year: row for row in operations.plan("laptop-1")}
    assert rows[FIRST_YEAR + 2].absence is PlanFigureAbsence.PERIOD_ELAPSED
    assert rows[FIRST_YEAR + 2].planned is None
    assert rows[FIRST_YEAR + 2].claim_state is ActivityAssetClaimState.NOT_DUE
    assert rows[FIRST_YEAR + 1].planned is not None

    within = operations.filing_handoff(
        tax_year=FIRST_YEAR + 1, m130_period=Period.from_year_and_code(FIRST_YEAR + 1, "4T")
    )
    beyond = operations.filing_handoff(
        tax_year=FIRST_YEAR + 2, m130_period=Period.from_year_and_code(FIRST_YEAR + 2, "4T")
    )
    assert within.material_m130 is not None
    assert within.material_m130.amount == Decimal("520.00")
    assert beyond.material_m130 is not None
    assert beyond.material_m130.amount == Decimal("0.00")
    assert beyond.material_m130.unavailable_asset_ids == ()

    # The first two years were never claimed, so nothing is amortized and the whole basis stays pending.
    row = operations.list_elements()[0]
    assert row.state is ActivityAssetRegisterState.IN_SERVICE
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("2000.00")


def _slow_rate_forecast(
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
            annual_rate=Decimal("0.02"),
            authority_generation="register-test-v1",
            source_reference="register test table",
            maximum_period_ends_on=date(FIRST_YEAR + 70, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_the_years_of_an_element_are_its_service_window_inside_the_registry_support() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)

    row = operations.list_elements()[0]

    assert (*row.years, *row.projected_years) == tuple(plan_row.tax_year for plan_row in operations.plan("laptop-1"))
    assert row.years == tuple(range(FIRST_YEAR, filing_year_envelope().horizon + 1))
    assert row.projected_years == tuple(range(filing_year_envelope().horizon + 1, FIRST_YEAR + 5))
    assert register_years([row]) == row.years


def test_a_decades_old_element_is_offered_only_the_years_the_registry_supports() -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=_slow_rate_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(FIRST_YEAR, 12, 31)),
    )
    decades_old = filing_year_envelope().floor - 21
    operations.create(register_revision(in_service=date(decades_old, 1, 1)), NAME)

    row = operations.list_elements()[0]

    # 2,000.00 at 2% charges 40.00 a year, so the charge runs 50 years from the year of today.
    floor = filing_year_envelope().floor
    horizon = filing_year_envelope().horizon
    assert min(plan_row.tax_year for plan_row in operations.plan("laptop-1")) == decades_old < floor
    assert row.years == tuple(range(floor, horizon + 1))
    assert row.projected_years == tuple(range(horizon + 1, FIRST_YEAR + 50 + 1))
    assert register_years([row]) == row.years


def test_the_register_years_merge_every_element_once_in_ascending_order() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    row = operations.list_elements()[0]
    other: ActivityAssetListRow = row.model_copy(update={"years": (FIRST_YEAR - 1, FIRST_YEAR)})

    assert register_years([other, row]) == (FIRST_YEAR - 1, FIRST_YEAR, FIRST_YEAR + 1)
    assert register_years([]) == ()


def _served_word_families() -> dict[str, type[StrEnum]]:
    return {
        DISPOSAL_FINDING_FAMILY: ActivityAssetDisposalFindingKind,
        NON_DEDUCTIBLE_IVA_STATE_FAMILY: ActivityAssetNonDeductibleIvaState,
        PLAN_ADVISORY_FAMILY: ActivityAssetPlanAdvisoryKind,
        **dict(TIMELINE_TOKEN_FAMILIES.values()),
    }


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_served_token_has_a_catalogue_word_in_every_locale(locale: str) -> None:
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        words = {
            activity_asset_label_key(family, member): tr(activity_asset_label_key(family, member), locale=locale)
            for family, enum in _served_word_families().items()
            for member in enum
        }
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    assert len(words) == sum(len(enum) for enum in _served_word_families().values())
    assert all(word.strip() for word in words.values())


def test_the_timeline_words_each_token_it_changes_and_leaves_other_values_bare() -> None:
    operations, _ = register_operations()
    first = register_revision()
    operations.create(first, NAME)
    operations.correct(register_revision(number=2, supersedes=first.revision_id, basis="1000"))

    created, corrected = [
        event for event in operations.timeline("laptop-1") if event.kind is ActivityAssetEventKind.REVISION
    ]

    keys = {change.field: (change.before_key, change.after_key) for change in created.changes}
    assert keys["acquired_condition"] == (None, "ledger.actividad_asset.acquired_condition.new")
    assert keys["acquisition_shape"] == (None, "ledger.actividad_asset.acquisition_shape.primary_purchase")
    assert keys["basis.stage"] == (None, "ledger.actividad_asset.basis_stage.business_allocated")
    assert keys["opening_history.status"] == (None, "ledger.actividad_asset.opening_history_status.known")
    assert keys["in_service_date"] == (None, None)
    assert {change.field for change in corrected.changes} == {"basis.basis_amount"}
    assert all(change.before_key is None and change.after_key is None for change in corrected.changes)


def test_a_candidate_serves_the_key_of_its_non_deductible_iva_state() -> None:
    operations, _ = register_operations()

    candidate = operations.acquisition_candidates()[0]

    assert candidate.non_deductible_iva_state_key == "ledger.actividad_asset.non_deductible_iva_state.unknown"


def _elapsed_after_second_year(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    if covered_from.year > FIRST_YEAR + 1:
        raise ActividadAssetPeriodElapsedError(
            context={"ended_on": date(FIRST_YEAR + 2, 1, 1).isoformat()},
            translated_message="ledger.actividad_asset.errors.amortization_period_elapsed",
        )
    return register_forecast(
        revision,
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def _elapsed_operations() -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=_elapsed_after_second_year,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(FIRST_YEAR + 3, 6, 30)),
    )
    operations.create(register_revision(), NAME)
    return operations


def test_a_period_that_ended_over_unclaimed_years_keeps_the_value_pending() -> None:
    operations = _elapsed_operations()
    operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.first")

    row = operations.list_elements()[0]

    # 2,000.00 basis less the 520.00 of the first year; the second was never claimed.
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("1480.00")
    assert row.state is ActivityAssetRegisterState.IN_SERVICE
    assert row.findings.missing == 1


def test_a_period_that_ended_with_every_year_claimed_is_fully_amortized_and_shows_the_rest() -> None:
    operations = _elapsed_operations()
    for year in range(FIRST_YEAR, FIRST_YEAR + 2):
        operations.record_claim(full_year(operations, year), creating_operation=f"test.{year}")

    row = operations.list_elements()[0]

    # 2,000.00 less two years at 520.00: the rest stays visible, though nothing more can be charged.
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("960.00")
    assert row.state is ActivityAssetRegisterState.FULLY_AMORTIZED


def test_a_baja_keeps_the_formula_value_pending() -> None:
    operations, _ = register_operations(today=date(FIRST_YEAR + 1, 12, 31))
    operations.create(register_revision(), NAME)
    operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.first")
    operations.dispose(
        "laptop-1",
        ActivityAssetDisposal(
            disposal_date=date(FIRST_YEAR, 12, 31),
            reason=ActivityAssetDisposalReason.SCRAPPING,
            proceeds=Decimal("0.00"),
            transmission_costs=Decimal("0.00"),
        ),
    )

    row = operations.list_elements()[0]

    assert row.state is ActivityAssetRegisterState.OUT_OF_SERVICE
    assert row.pending is not None
    assert Decimal(row.pending.decimal) == Decimal("1480.00")
