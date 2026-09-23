"""Real-source resolution of 2025 activity-asset amortization elections.

Every expected amount is an independent hand calculation from the cited
provision, written out beside the assertion; none is copied from a run of the
code under test.  Proration follows the accepted day-count contract (service
days over 365 for 2025).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.actividad_asset_bindings import resolve_activity_asset_schedule_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    ApprovedAmortizationPlan,
    ChargingInfrastructureEvidence,
    DefiniteUsefulLife,
    DigitOrder,
    DirectEstimationRegime,
    LowValueElection,
    PlanAnnualAmount,
    PlanApprovalKind,
    SmallEnterpriseEvidence,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
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
from cadrumo.domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import (
    ElectricPropulsion,
    VehicleAffectation,
    VehicleCategory,
    VehicleListedUse,
    VehiclePrivateUse,
)

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR_START = date(2025, 1, 1)
_YEAR_END = date(2026, 1, 1)
_NORMAL = DirectEstimationRegime.NORMAL
_SIMPLIFIED = DirectEstimationRegime.SIMPLIFIED


def _modelo_100() -> ModeloRevision:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100")).revisions["2025"]


def _election(method: AmortizationMethod, regime: DirectEstimationRegime = _NORMAL, **facts: object):
    return ActivityAssetAmortizationElection.model_validate({"regime": regime, "method": method, **facts})


def _asset(
    election: ActivityAssetAmortizationElection,
    *,
    basis: str,
    kind: AssetKind = AssetKind.MATERIAL,
    in_service: date = _YEAR_START,
    condition: AcquiredCondition = AcquiredCondition.NEW,
    residual: str = "0",
    opening: str = "0",
    opening_method: AmortizationMethod | None = None,
    built: date | None = None,
    asset_id: str = "asset",
    vehicle: VehicleAffectation | None = None,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=kind,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal(basis),
            prior_allocation_provenance="reviewed business allocation",
        ),
        residual_value=Decimal(residual),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal(opening),
            amortization_method=opening_method,
        ),
        acquired_condition=condition,
        building_construction_date=built,
        amortization=election,
        vehicle_affectation=vehicle,
    )


def _charge(
    asset: ActivityAssetRevision,
    *,
    covered_from: date = _YEAR_START,
    covered_until: date = _YEAR_END,
    history: AssetScheduleHistory | None = None,
    free_amount: str | None = None,
) -> ScheduledAmortizationCharge:
    return forecast_activity_asset_charge(
        asset,
        modelo_100_revision=_modelo_100(),
        authority_generation="candidate-source",
        covered_from=covered_from,
        covered_until=covered_until,
        history=history or AssetScheduleHistory(),
        requested_free_amount=Decimal(free_amount) if free_amount is not None else None,
    )


def _linear(class_key: str, regime: DirectEstimationRegime = _NORMAL, **facts: object):
    return _election(AmortizationMethod.LINEAR, regime, authority_class_key=class_key, **facts)


# --- Linear table (LIS art. 12.1.a; RIS art. 4) ---------------------------------------------


def test_linear_table_resolves_each_modality_maximum_from_source() -> None:
    normal = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=_asset(_linear("equipo-proceso-informacion"), basis="2000"),
        authority_generation="candidate-source",
    )
    simplified = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=_asset(
            _linear("equipo-informacion-software", _SIMPLIFIED),
            basis="2000",
            kind=AssetKind.INTANGIBLE,
        ),
        authority_generation="candidate-source",
    )

    assert normal.annual_rate == Decimal("0.25")
    assert simplified.annual_rate == Decimal("0.26")
    assert "metodo-admitido:key:material:linear" in normal.source_reference
    assert "coeficiente-lineal-maximo:key:equipo-proceso-informacion" in normal.source_reference


def test_two_thousand_euro_computer_forecasts_permitted_charge_not_purchase_cost() -> None:
    charge = _charge(_asset(_linear("equipo-proceso-informacion"), basis="2000.00"))

    # 2,000 x 25% for a full 2025 service year.
    assert charge.amount == Decimal("500.00")


def test_elected_linear_coefficient_is_bounded_by_the_maximum_and_the_maximum_period() -> None:
    # Processing equipment: maximum 25%, maximum period 8 years, so the floor is 1/8 = 12.5%.
    elected = _charge(_asset(_linear("equipo-proceso-informacion", linear_coefficient=Decimal("0.20")), basis="2000"))
    floor = _charge(_asset(_linear("equipo-proceso-informacion", linear_coefficient=Decimal("0.125")), basis="2000"))

    assert elected.amount == Decimal("400.00")  # 2,000 x 20%
    assert floor.amount == Decimal("250.00")  # 2,000 x 12.5%
    for outside in ("0.12", "0.26"):
        with pytest.raises(ActividadAssetValidationError, match="admissible range"):
            _charge(_asset(_linear("equipo-proceso-informacion", linear_coefficient=Decimal(outside)), basis="2000"))


def test_first_partial_year_and_residual_value_use_the_amortizable_basis() -> None:
    partial = _charge(_asset(_linear("equipo-proceso-informacion"), basis="2000", in_service=date(2025, 7, 1)))
    residual = _charge(_asset(_linear("equipo-proceso-informacion"), basis="2000", residual="400"))

    assert partial.service_days == 184
    assert partial.amount == Decimal("252.05")  # 2,000 x 25% x 184/365 = 252.0548
    assert residual.amount == Decimal("400.00")  # (2,000 - 400) x 25%


def test_used_asset_may_double_the_maximum_only_in_the_normal_modality() -> None:
    used_machine = _charge(_asset(_linear("maquinaria"), basis="10000", condition=AcquiredCondition.USED))
    simplified_used = _charge(
        _asset(_linear("maquinaria", _SIMPLIFIED), basis="10000", condition=AcquiredCondition.USED),
    )

    assert used_machine.amount == Decimal("2400.00")  # 10,000 x (2 x 12%)
    assert simplified_used.amount == Decimal("1200.00")  # 10,000 x 12%, no doubling enrolled


def test_a_building_under_ten_years_old_is_not_a_used_asset() -> None:
    young = _charge(
        _asset(
            _linear("edificio-industrial"),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=date(2020, 1, 1),
        ),
    )
    old = _charge(
        _asset(
            _linear("edificio-industrial"),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=date(2015, 1, 1),
        ),
    )

    assert young.amount == Decimal("3000.00")  # five years old: 100,000 x 3%
    assert old.amount == Decimal("6000.00")  # exactly ten years old: 100,000 x (2 x 3%)
    with pytest.raises(ActividadAssetIncompleteError, match="construction date"):
        _charge(_asset(_linear("edificio-industrial"), basis="100000", condition=AcquiredCondition.USED))


def test_multi_shift_coefficient_follows_the_hours_formula() -> None:
    # Machinery: max 12%, period-implied 1/18. 16 hours: 1/18 + (12% - 1/18) x 16/8 = 24% - 1/18.
    charge = _charge(_asset(_linear("maquinaria", shift_hours_per_day=Decimal("16")), basis="18000"))

    assert charge.amount == Decimal("3320.00")  # 18,000 x 24% - 18,000/18 = 4,320 - 1,000
    with pytest.raises(ActividadAssetValidationError, match="more than one normal shift"):
        _charge(_asset(_linear("maquinaria", shift_hours_per_day=Decimal("8")), basis="18000"))
    with pytest.raises(ActividadAssetUnsupportedError, match="not enrolled for the simplified modality"):
        _charge(_asset(_linear("maquinaria", _SIMPLIFIED, shift_hours_per_day=Decimal("16")), basis="18000"))


def _small_enterprise(turnover: str, made_available: date = date(2025, 11, 15)) -> SmallEnterpriseEvidence:
    return SmallEnterpriseEvidence(
        evidence_reference="prior-year-accounts",
        made_available_on=made_available,
        prior_period_net_turnover=Decimal(turnover),
    )


def test_reduced_size_acceleration_doubles_the_maximum_for_a_new_element() -> None:
    # The AEAT 2025 manual's LIS art. 103 example: a EUR 36,000 machine in service on
    # 1 December. The manual illustrates with a month fraction (x 1/12 = EUR 720); the
    # only official unit, binding DGT consulta V1978-24, prorates by days in service over
    # the days of the year: 36,000 x 24% x 31/365 = 733.8082.
    charge = _charge(
        _asset(
            _linear("maquinaria", small_enterprise=_small_enterprise("2800000")),
            basis="36000",
            in_service=date(2025, 12, 1),
        ),
    )

    assert charge.amount == Decimal("733.81")
    with pytest.raises(ActividadAssetUnsupportedError, match="reduced-size threshold"):
        _charge(
            _asset(
                _linear("maquinaria", small_enterprise=_small_enterprise("10000000", made_available=_YEAR_START)),
                basis="36000",
            )
        )
    assert _charge(
        _asset(
            _linear("maquinaria", small_enterprise=_small_enterprise("9999999.99", made_available=_YEAR_START)),
            basis="36000",
        ),
    ).amount == Decimal("8640.00")  # 36,000 x 24%
    with pytest.raises(ActividadAssetUnsupportedError, match="new elements"):
        _charge(
            _asset(
                _linear("maquinaria", small_enterprise=_small_enterprise("100", made_available=_YEAR_START)),
                basis="36000",
                condition=AcquiredCondition.USED,
            ),
        )


def test_used_doubling_is_limited_to_material_assets_where_it_is_enrolled() -> None:
    used_software = _charge(
        _asset(
            _linear("intangible-software"),
            basis="3000",
            kind=AssetKind.INTANGIBLE,
            condition=AcquiredCondition.USED,
        ),
    )
    simplified_used_building = _charge(
        _asset(
            _linear("edificio-otra-construccion", _SIMPLIFIED),
            basis="100000",
            condition=AcquiredCondition.USED,
        ),
    )

    # RIS art. 4.3 covers material assets only: 3,000 x 33%, not 66%.
    assert used_software.amount == Decimal("990.00")
    # The simplified table applies no used multiplier, so no construction date is needed: 100,000 x 3%.
    assert simplified_used_building.amount == Decimal("3000.00")


# --- Constant percentage (LIS art. 12.1.b; RIS art. 5) ---------------------------------------


def _constant(class_key: str, coefficient: str | None = None, regime: DirectEstimationRegime = _NORMAL):
    facts: dict[str, object] = {"authority_class_key": class_key}
    if coefficient is not None:
        facts["linear_coefficient"] = Decimal(coefficient)
    return _election(AmortizationMethod.CONSTANT_PERCENTAGE, regime, **facts)


def test_constant_percentage_weights_the_elected_coefficient_by_period_band() -> None:
    long_band = _charge(_asset(_constant("maquinaria"), basis="10000"))
    medium_band = _charge(_asset(_constant("equipo-electronico", "0.20"), basis="1000"))
    short_band = _charge(_asset(_constant("equipo-proceso-informacion", "0.25"), basis="1000"))
    floored = _charge(_asset(_constant("obra-civil-general", "0.02"), basis="100000"))

    assert long_band.amount == Decimal("3000.00")  # 12% -> 8.33 years -> x2.5 = 30%
    assert medium_band.amount == Decimal("400.00")  # 20% -> exactly 5 years -> x2 = 40%
    assert short_band.amount == Decimal("375.00")  # 25% -> 4 years -> x1.5 = 37.5%
    assert floored.amount == Decimal("11000.00")  # 2% -> 50 years -> x2.5 = 5%, floored at 11%


def test_constant_percentage_applies_to_the_value_pending_at_the_start_of_the_year() -> None:
    first_partial = _charge(_asset(_constant("maquinaria"), basis="10000", in_service=date(2025, 7, 1)))
    second_year = _charge(
        _asset(
            _constant("maquinaria"),
            basis="10000",
            in_service=date(2024, 1, 1),
            opening="3000",
            opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
        ),
    )
    with_residual = _charge(_asset(_constant("maquinaria"), basis="10000", residual="1000"))
    quarter_after_claim = _charge(
        _asset(_constant("maquinaria"), basis="10000"),
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
        history=AssetScheduleHistory(accumulated_in_tax_year=Decimal("739.73")),
    )

    assert first_partial.amount == Decimal("1512.33")  # 10,000 x 30% x 184/365 = 1,512.3288
    assert second_year.amount == Decimal("2100.00")  # (10,000 - 3,000) x 30%
    assert with_residual.amount == Decimal("2700.00")  # (10,000 - 1,000) x 30%
    # In-year claims do not change the start-of-year pending value: 10,000 x 30% x 91/365.
    assert quarter_after_claim.amount == Decimal("747.95")


def test_constant_percentage_amortizes_everything_pending_in_the_final_year() -> None:
    # 25% elected -> 4-year life from 1 July 2021, concluding on 1 July 2025.
    asset = _asset(
        _constant("equipo-proceso-informacion", "0.25"),
        basis="10000",
        in_service=date(2021, 7, 1),
        opening="8000",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )

    whole_year = _charge(asset)
    first_quarter = _charge(asset, covered_until=date(2025, 4, 1))

    assert whole_year.covered_until == date(2025, 7, 1)
    assert whole_year.amount == Decimal("2000.00")  # the whole pending value
    assert first_quarter.amount == Decimal("994.48")  # 2,000 x 90/181 = 994.4751
    with pytest.raises(ActividadAssetUnsupportedError, match="no amortizable"):
        _charge(asset, covered_from=date(2025, 8, 1))


def test_constant_percentage_final_year_intervals_telescope_to_the_pending_value() -> None:
    asset = _asset(
        _constant("equipo-proceso-informacion", "0.25"),
        basis="10000",
        in_service=date(2021, 7, 1),
        opening="9000",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )
    boundaries = (date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3), date(2025, 7, 1))

    amounts = [_charge(asset, covered_from=start, covered_until=end).amount for start, end in pairwise(boundaries)]

    # 1,000 pending over 181 final-year days: 5.52 + 5.53 + 988.95, no stranded cent.
    assert amounts == [Decimal("5.52"), Decimal("5.53"), Decimal("988.95")]
    assert sum(amounts, Decimal("0")) == Decimal("1000.00")


def test_a_from_start_method_refuses_an_unattested_opening_amount() -> None:
    unattested = _asset(_constant("maquinaria"), basis="10000", in_service=date(2024, 1, 1), opening="3000")
    other_method = _asset(
        _constant("maquinaria"),
        basis="10000",
        in_service=date(2024, 1, 1),
        opening="1200",
        opening_method=AmortizationMethod.LINEAR,
    )

    for asset in (unattested, other_method):
        with pytest.raises(ActividadAssetUnsupportedError, match="attest the same from-start method"):
            _charge(asset)


def test_constant_percentage_excludes_buildings_furniture_and_the_simplified_modality() -> None:
    for class_key in ("mobiliario", "edificio-industrial", "almacen-deposito", "util-herramienta"):
        with pytest.raises(ActividadAssetUnsupportedError, match=re.escape("RIS art. 5.2")):
            _charge(_asset(_constant(class_key), basis="1000"))
    with pytest.raises(ActividadAssetUnsupportedError, match=r"excluded by law.*rd-439-2007:art-30"):
        _charge(_asset(_constant("maquinaria", regime=_SIMPLIFIED), basis="1000"))


def test_constant_percentage_and_sum_of_digits_admit_the_intangibles_the_table_lists() -> None:
    constant = _charge(_asset(_constant("intangible-software"), basis="3000", kind=AssetKind.INTANGIBLE))
    digits = _charge(_asset(_digits("intangible-software", 4), basis="3000", kind=AssetKind.INTANGIBLE))

    # LIS art. 12.1.a lists software at 33%: 3.03 years is under 5, so RIS art. 5.1.a weights it
    # 1.5 to 49.5%, and 3,000 x 49.5% = 1,485.00.
    assert constant.amount == Decimal("1485.00")
    # Whole-year periods run from ceil(1 / 0.33) = 4 to the 6-year maximum; four years descending
    # gives the first year 4 of 10 digits: 3,000 x 4/10 = 1,200.00.
    assert digits.amount == Decimal("1200.00")


def test_simplified_intangible_table_methods_refuse_with_the_sources_that_leave_them_open() -> None:
    for election in (
        _constant("equipo-informacion-software", regime=_SIMPLIFIED),
        _election(
            AmortizationMethod.SUM_OF_DIGITS,
            _SIMPLIFIED,
            authority_class_key="equipo-informacion-software",
            sum_of_digits_period_years=4,
            digit_order=DigitOrder.DESCENDING,
        ),
    ):
        with pytest.raises(ActividadAssetUnsupportedError, match=r"RIRPF art\. 30\.1a.*Orden of 27 March 1998"):
            _charge(_asset(election, basis="3000", kind=AssetKind.INTANGIBLE))


# --- Sum of digits (LIS art. 12.1.c; RIS art. 6) ---------------------------------------------


def _digits(class_key: str, period: int, order: DigitOrder = DigitOrder.DESCENDING):
    return _election(
        AmortizationMethod.SUM_OF_DIGITS,
        authority_class_key=class_key,
        sum_of_digits_period_years=period,
        digit_order=order,
    )


def test_sum_of_digits_allocates_quota_per_digit_in_either_order() -> None:
    # Machinery, 9 years: digit sum 45, quota 45,000 / 45 = 1,000 per digit.
    descending = _charge(_asset(_digits("maquinaria", 9), basis="45000"))
    ascending = _charge(_asset(_digits("maquinaria", 9, DigitOrder.ASCENDING), basis="45000"))
    mid_year = _charge(_asset(_digits("maquinaria", 9), basis="45000", in_service=date(2025, 7, 1)))

    assert descending.amount == Decimal("9000.00")  # digit 9
    assert ascending.amount == Decimal("1000.00")  # digit 1
    assert mid_year.amount == Decimal("4536.99")  # first life year 9,000 x 184/365 = 4,536.9863


def test_sum_of_digits_period_lies_between_the_coefficient_and_the_maximum_period() -> None:
    # Machinery: 12% implies 8.33 years, so whole-year periods run from 9 to the 18-year maximum.
    assert _charge(_asset(_digits("maquinaria", 18), basis="171000")).amount == Decimal("18000.00")  # 171,000 x 18/171
    for period in (8, 19):
        with pytest.raises(ActividadAssetValidationError, match="whole-year range"):
            _charge(_asset(_digits("maquinaria", period), basis="45000"))


def test_sum_of_digits_final_life_year_reaches_exactly_the_basis() -> None:
    asset = _asset(
        _digits("maquinaria", 9),
        basis="45000",
        in_service=date(2017, 1, 1),
        opening="44000",
        opening_method=AmortizationMethod.SUM_OF_DIGITS,
    )

    # 2025 is the ninth life year, digit 1: 1,000, which leaves nothing pending.
    assert _charge(asset).amount == Decimal("1000.00")


def test_sum_of_digits_excludes_buildings_and_furniture() -> None:
    for class_key in ("edificio-comercial-administrativo-servicios-vivienda", "enseres-otros"):
        with pytest.raises(ActividadAssetUnsupportedError, match=re.escape("RIS art. 6.2")):
            _charge(_asset(_digits(class_key, 20), basis="1000"))


# --- Approved plan (LIS art. 12.1.d; RIS art. 7) ---------------------------------------------


def _plan(submitted: date = date(2024, 11, 1), amounts: tuple[tuple[int, str], ...] = ((2025, "5000"),)):
    return _election(
        AmortizationMethod.APPROVED_PLAN,
        approved_plan=ApprovedAmortizationPlan(
            approval_reference="resolution-2025-0001",
            approval_kind=PlanApprovalKind.EXPRESS,
            submitted_on=submitted,
            resolved_on=submitted + timedelta(days=60),
            annual_amounts=tuple(PlanAnnualAmount(tax_year=year, amount=Decimal(amount)) for year, amount in amounts),
        ),
    )


def test_approved_plan_charges_its_annual_distribution_over_service_days() -> None:
    plan = _plan(amounts=((2025, "5000"), (2026, "4000"), (2027, "3000")))

    assert _charge(_asset(plan, basis="12000")).amount == Decimal("5000.00")
    assert _charge(_asset(plan, basis="12000"), covered_until=date(2025, 4, 1)).amount == Decimal(
        "1232.88",
    )  # 5,000 x 90/365 = 1,232.8767


def test_approved_plan_refusals() -> None:
    with pytest.raises(ActividadAssetUnsupportedError, match=re.escape("RIS art. 7.8")):
        _charge(_asset(_plan(submitted=date(2026, 1, 10)), basis="12000"))
    with pytest.raises(ActividadAssetValidationError, match="more than the amortizable basis"):
        _charge(_asset(_plan(amounts=((2025, "5000"), (2026, "8000"))), basis="12000"))
    with pytest.raises(ActividadAssetUnsupportedError, match="no amortization to this tax year"):
        _charge(_asset(_plan(amounts=((2026, "5000"),)), basis="12000"))
    simplified_plan = _plan().model_copy(update={"regime": _SIMPLIFIED})
    with pytest.raises(ActividadAssetUnsupportedError, match="excluded by law"):
        _charge(_asset(simplified_plan, basis="12000"))


# --- Intangibles (LIS art. 12.2) --------------------------------------------------------------


def test_definite_life_intangible_amortizes_over_its_evidenced_life() -> None:
    licence = _election(
        AmortizationMethod.INTANGIBLE_USEFUL_LIFE,
        useful_life=DefiniteUsefulLife(ends_on=date(2027, 1, 1), evidence_reference="licence-term"),
    )
    asset = _asset(licence, basis="3650", kind=AssetKind.INTANGIBLE)

    assert _charge(asset).amount == Decimal("1825.00")  # 3,650 x 365/730
    assert _charge(asset, covered_until=date(2025, 4, 1)).amount == Decimal("450.00")  # 3,650 x 90/730
    with pytest.raises(ActividadAssetValidationError, match="must end after"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.INTANGIBLE_USEFUL_LIFE,
                    useful_life=DefiniteUsefulLife(ends_on=_YEAR_START, evidence_reference="bad"),
                ),
                basis="3650",
                kind=AssetKind.INTANGIBLE,
            ),
        )


def test_reduced_size_goodwill_and_indefinite_life_intangibles_deduct_150_percent_of_the_twentieth() -> None:
    evidence = _small_enterprise("2800000", made_available=_YEAR_START)
    goodwill = _charge(
        _asset(
            _election(AmortizationMethod.GOODWILL, small_enterprise=evidence),
            basis="40000",
            kind=AssetKind.INTANGIBLE,
            condition=AcquiredCondition.USED,
        ),
    )
    indefinite = _charge(
        _asset(
            _election(AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE, _SIMPLIFIED, small_enterprise=evidence),
            basis="20000",
            kind=AssetKind.INTANGIBLE,
        ),
    )

    # LIS art. 103.5 as the AEAT manual and DGT V0976-24 read it: 150% of the 5% art. 12.2
    # amount is 7.5%, so 40,000 x 7.5% = 3,000.00 and 20,000 x 7.5% = 1,500.00. Unlike
    # art. 103.1, the element need not be new, so acquired goodwill qualifies.
    assert goodwill.amount == Decimal("3000.00")
    assert indefinite.amount == Decimal("1500.00")
    with pytest.raises(ActividadAssetUnsupportedError, match="reduced-size threshold"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.GOODWILL,
                    small_enterprise=_small_enterprise("10000000", made_available=_YEAR_START),
                ),
                basis="40000",
                kind=AssetKind.INTANGIBLE,
            ),
        )


def test_indefinite_life_and_goodwill_are_limited_to_one_twentieth_in_both_modalities() -> None:
    indefinite = _charge(
        _asset(_election(AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE), basis="20000", kind=AssetKind.INTANGIBLE),
    )
    goodwill = _charge(
        _asset(_election(AmortizationMethod.GOODWILL, _SIMPLIFIED), basis="40000", kind=AssetKind.INTANGIBLE),
    )

    assert indefinite.amount == Decimal("1000.00")  # 20,000 / 20
    assert goodwill.amount == Decimal("2000.00")  # 40,000 / 20
    with pytest.raises(ActividadAssetUnsupportedError, match="not enrolled for material"):
        _charge(_asset(_election(AmortizationMethod.GOODWILL), basis="40000"))


# --- Free depreciation (LIS art. 12.3; DA 18a) -------------------------------------------------


def test_low_value_free_resolves_published_threshold_and_cap() -> None:
    authority = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=_asset(
            _election(
                AmortizationMethod.LOW_VALUE_FREE,
                authority_class_key="mobiliario",
                low_value=LowValueElection(
                    election_reference="operator-low-value-election",
                    new_material_evidence_reference="canonical-invoice-new-item-attestation",
                    unit_acquisition_value=Decimal("300.00"),
                ),
            ),
            basis="300",
        ),
        authority_generation="candidate-source",
    )

    assert authority.free_depreciation_unit_threshold == Decimal("300")
    assert authority.free_depreciation_annual_cap == Decimal("25000")
    assert "libertad-amortizacion-umbral-unitario" in authority.source_reference


def test_research_development_free_and_building_methods() -> None:
    machine = _asset(
        _election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            authority_class_key="maquinaria",
            research_development_evidence_reference="rnd-project-affectation",
        ),
        basis="10000",
    )
    building = _asset(
        _election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
            authority_class_key="edificio-industrial",
            research_development_evidence_reference="rnd-building-affectation",
        ),
        basis="100000",
    )

    assert _charge(machine, free_amount="7000").amount == Decimal("7000.00")
    assert _charge(building).amount == Decimal("10000.00")  # 100,000 / 10 years
    with pytest.raises(ActividadAssetValidationError, match="remaining lawful basis"):
        _charge(machine, free_amount="10000.01")
    with pytest.raises(ActividadAssetUnsupportedError, match="excludes buildings"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
                    authority_class_key="edificio-industrial",
                    research_development_evidence_reference="rnd",
                ),
                basis="100000",
            ),
            free_amount="1",
        )
    with pytest.raises(ActividadAssetValidationError, match="building table class"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
                    authority_class_key="maquinaria",
                    research_development_evidence_reference="rnd",
                ),
                basis="100000",
            ),
        )


def test_charging_infrastructure_free_depreciation_window() -> None:
    def charger(in_service: date, condition: AcquiredCondition = AcquiredCondition.NEW) -> ActivityAssetRevision:
        return _asset(
            _election(
                AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE,
                authority_class_key="instalacion-resto",
                charging_infrastructure=ChargingInfrastructureEvidence(
                    technical_documentation_reference="rebt-memoria",
                    installation_certificate_reference="ccaa-certificate",
                ),
            ),
            basis="2500",
            in_service=in_service,
            condition=condition,
        )

    assert _charge(charger(date(2025, 3, 1)), free_amount="2500").amount == Decimal("2500.00")
    assert _charge(charger(date(2024, 6, 1)), free_amount="1500").amount == Decimal("1500.00")
    with pytest.raises(ActividadAssetUnsupportedError, match=re.escape("DA 18a.2")):
        _charge(charger(date(2023, 6, 1)), free_amount="1500")
    with pytest.raises(ActividadAssetUnsupportedError, match="new elements"):
        _charge(charger(date(2025, 3, 1), AcquiredCondition.USED), free_amount="100")


@pytest.mark.parametrize(
    ("method", "provision"),
    [
        (AmortizationMethod.JUSTIFIED_AMOUNT, "LIS art. 12.1.e"),
        (AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE, "LIS art. 102"),
        (AmortizationMethod.RENEWABLE_SELF_CONSUMPTION_FREE, "LIS DA 17a"),
        (AmortizationMethod.ENTITY_REGIME_FREE, "LIS art. 12.3.a and 12.3.d"),
    ],
)
def test_statutory_methods_the_product_cannot_validate_refuse_with_their_provision(
    method: AmortizationMethod,
    provision: str,
) -> None:
    with pytest.raises(ActividadAssetUnsupportedError, match=provision):
        _charge(_asset(_election(method), basis="1000"))


# --- Vehicles (LIRPF art. 29; RIRPF art. 22; LIS DA 18a.1) ------------------------------------


def _vehicle(
    category: VehicleCategory = VehicleCategory.PASSENGER_CAR,
    private_use: VehiclePrivateUse = VehiclePrivateUse.NONE,
    listed_use: VehicleListedUse | None = None,
    *,
    in_books: bool = True,
    propulsion: ElectricPropulsion | None = None,
) -> VehicleAffectation:
    return VehicleAffectation(
        category=category,
        private_use=private_use,
        listed_use=listed_use,
        recorded_in_activity_books=in_books,
        evidence_reference="vehicle-use-log",
        electric_propulsion=propulsion,
    )


def test_a_vehicle_class_charges_only_on_a_declaration_that_proves_affectation() -> None:
    car = _linear("transporte-externo")

    with pytest.raises(ActividadAssetIncompleteError, match="requires a vehicle affectation declaration"):
        _charge(_asset(car, basis="20000"))
    # External transport is 16%: 20,000 x 16% = 3,200.00 for a car used only for the activity.
    assert _charge(_asset(car, basis="20000", vehicle=_vehicle())).amount == Decimal("3200.00")
    # A taxi keeps its accessory rest-day use under RIRPF art. 22.4 (b).
    taxi = _vehicle(
        private_use=VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME, listed_use=VehicleListedUse.PAID_PASSENGER_TRANSPORT
    )
    assert _charge(_asset(car, basis="20000", vehicle=taxi)).amount == Decimal("3200.00")
    # A delivery van outside the restricted categories keeps the general accessory-use allowance.
    van = _vehicle(VehicleCategory.OTHER_VEHICLE, VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME)
    assert _charge(_asset(car, basis="20000", vehicle=van)).amount == Decimal("3200.00")
    # A truck's table class cannot hold a restricted vehicle, so no declaration is needed: 20,000 x 20%.
    assert _charge(_asset(_linear("transporte-autocamion"), basis="20000")).amount == Decimal("4000.00")


def test_a_vehicle_not_proven_affected_refuses_with_its_provision() -> None:
    car = _linear("transporte-externo")
    refusals = (
        (_vehicle(private_use=VehiclePrivateUse.SHARED), "22.2.1"),
        (_vehicle(private_use=VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME), "22.4"),
        (_vehicle(VehicleCategory.MOTORCYCLE, VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME), "22.4"),
        (_vehicle(in_books=False), "22.2.2"),
    )
    for declaration, provision in refusals:
        with pytest.raises(ActividadAssetUnsupportedError, match=re.escape(provision)):
            _charge(_asset(car, basis="20000", vehicle=declaration))
    # Simplified modality: the transport group is flagged too.
    with pytest.raises(ActividadAssetIncompleteError, match="requires a vehicle affectation declaration"):
        _charge(_asset(_linear("transporte", _SIMPLIFIED), basis="20000"))


def test_the_goods_transport_use_belongs_to_a_mixed_vehicle_only() -> None:
    with pytest.raises(ValueError, match="mixed vehicle"):
        _vehicle(listed_use=VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT)
    assert (
        _vehicle(
            VehicleCategory.MIXED_VEHICLE,
            VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME,
            VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT,
        ).listed_use
        is VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT
    )


def test_electric_vehicle_free_depreciation_needs_an_affected_new_vehicle_in_the_window() -> None:
    election = _election(AmortizationMethod.ELECTRIC_VEHICLE_FREE, authority_class_key="transporte-externo")
    electric = _vehicle(propulsion=ElectricPropulsion.BEV)

    charged = _charge(_asset(election, basis="30000", vehicle=electric), free_amount="30000")

    assert charged.amount == Decimal("30000.00")
    with pytest.raises(ActividadAssetIncompleteError, match="annex II propulsion"):
        _charge(_asset(election, basis="30000", vehicle=_vehicle()), free_amount="100")
    with pytest.raises(ActividadAssetUnsupportedError, match="new vehicles"):
        _charge(
            _asset(election, basis="30000", vehicle=electric, condition=AcquiredCondition.USED),
            free_amount="100",
        )
    with pytest.raises(ActividadAssetUnsupportedError, match=re.escape("DA 18a.1")):
        _charge(_asset(election, basis="30000", vehicle=electric, in_service=date(2023, 6, 1)), free_amount="100")
    with pytest.raises(ActividadAssetUnsupportedError, match=re.escape("22.2.1")):
        shared = _vehicle(private_use=VehiclePrivateUse.SHARED, propulsion=ElectricPropulsion.BEV)
        _charge(_asset(election, basis="30000", vehicle=shared), free_amount="100")


def test_unknown_class_and_kind_mismatch_fail_closed() -> None:
    with pytest.raises(ActividadAssetUnsupportedError, match="no enrolled group classification"):
        _charge(_asset(_linear("caller-invented-class"), basis="1000"))
    with pytest.raises(ActividadAssetUnsupportedError, match="does not classify intangible assets"):
        _charge(_asset(_linear("mobiliario"), basis="1000", kind=AssetKind.INTANGIBLE))


def test_an_absent_admission_parameter_fails_closed() -> None:
    revision = _modelo_100()
    stripped = revision.model_copy(
        update={
            "parameters": tuple(
                parameter
                for parameter in revision.parameters
                if parameter.id != "renta-actividad-inmovilizado-amortizacion-normal-metodo-admitido"
            ),
        },
    )

    with pytest.raises(ActividadAssetUnsupportedError, match="authority parameter"):
        resolve_activity_asset_schedule_authority(
            stripped,
            tax_year=2025,
            asset_revision=_asset(_linear("mobiliario"), basis="1000"),
            authority_generation="candidate-source",
        )


# --- Change of method and shared operations -------------------------------------------------


class _MemoryHistoryRepository:
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


def _operations() -> tuple[ActivityAssetOperations, _MemoryHistoryRepository]:
    def forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=_modelo_100(),
            authority_generation="published-registry-test-generation",
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    repository = _MemoryHistoryRepository()
    return (
        ActivityAssetOperations(
            repository=repository,
            forecast_operation=forecast,
            taxpayer_modality=lambda: DirectEstimationRegime.NORMAL,
        ),
        repository,
    )


def test_a_change_of_method_inside_a_claimed_tax_year_refuses() -> None:
    operations, _ = _operations()
    linear = _asset(_linear("maquinaria"), basis="10000", asset_id="switching-machine")
    operations.create(linear)
    first_quarter = operations.forecast(
        asset_id=linear.asset_id,
        covered_from=_YEAR_START,
        covered_until=date(2025, 4, 1),
    )
    operations.record_claim(first_quarter, creating_operation="test.linear-q1")
    switched = linear.model_copy(
        update={
            "revision_number": 2,
            "supersedes_revision_id": linear.revision_id,
            "amortization": _constant("maquinaria"),
        },
    )
    operations.correct(switched)

    assert first_quarter.amount == Decimal("295.89")  # 10,000 x 12% x 90/365 = 295.8904
    with pytest.raises(ActividadAssetValidationError, match="tax-year boundary"):
        operations.forecast(asset_id=linear.asset_id, covered_from=date(2025, 4, 1), covered_until=date(2025, 7, 1))


def test_constant_percentage_and_sum_of_digits_cannot_be_adopted_after_another_method() -> None:
    constant = _asset(
        _constant("maquinaria"),
        basis="10000",
        in_service=date(2024, 1, 1),
        opening="1200",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )
    earlier_linear = AssetScheduleHistory(election_fingerprints_before_tax_year=(_linear("maquinaria").fingerprint,))
    earlier_same = AssetScheduleHistory(election_fingerprints_before_tax_year=(constant.amortization.fingerprint,))

    with pytest.raises(ActividadAssetUnsupportedError, match="start of amortization"):
        _charge(constant, history=earlier_linear)
    assert _charge(constant, history=earlier_same).amount == Decimal("2640.00")  # (10,000 - 1,200) x 30%
    # A move to linear from a tax-year boundary is admitted and runs on the remaining basis.
    linear = _asset(_linear("maquinaria"), basis="10000", in_service=date(2024, 1, 1), opening="3000")
    after_constant = AssetScheduleHistory(election_fingerprints_before_tax_year=(constant.amortization.fingerprint,))
    assert _charge(linear, history=after_constant).amount == Decimal("1200.00")  # 10,000 x 12%


def test_an_undeclared_vehicle_refuses_with_its_correction_action_until_corrected() -> None:
    operations, _ = _operations()
    car = _asset(_linear("transporte-externo"), basis="20000", asset_id="undeclared-car")
    operations.create(car)

    with pytest.raises(ActividadAssetIncompleteError) as refused:
        operations.forecast(asset_id=car.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)

    verdict = refused.value.terminal_precondition_verdict
    assert isinstance(verdict, PreconditionVerdict)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.ledger.actividad_asset.correct_revision"
    assert verdict.missing_argument_names == ("revision_json",)
    assert verdict.evidence[0].values["asset_id"] == "undeclared-car"
    assert verdict.evidence[0].values["revision_id"] == car.revision_id
    assert "undeclared-car" in str(refused.value)
    assert "aeat " not in str(refused.value)
    corrected = car.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": car.revision_id, "vehicle_affectation": _vehicle()},
    )
    operations.correct(corrected)
    # The corrected car is used only for the activity: 20,000 x 16% = 3,200.00.
    forecast = operations.forecast(asset_id=car.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)
    assert forecast.amount == Decimal("3200.00")


def test_a_superseding_claim_is_forecast_without_the_claim_it_replaces() -> None:
    operations, repository = _operations()
    machine = _asset(
        _linear("maquinaria"),
        basis="1000",
        in_service=date(2017, 1, 1),
        opening="950",
        asset_id="nearly-amortized-machine",
    )
    operations.create(machine)
    first = operations.forecast(asset_id=machine.asset_id, covered_from=_YEAR_START, covered_until=date(2025, 4, 1))
    operations.record_claim(first, creating_operation="test.q1")
    second = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
    )
    second_claim = operations.record_claim(second, creating_operation="test.q2").claim
    corrected = machine.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": machine.revision_id, "residual_value": Decimal("10")},
    )
    operations.correct(corrected)

    # Counting the claim it would replace, 950 + 29.59 + 20.41 already exceeds the corrected 990 basis.
    with pytest.raises(ActividadAssetValidationError, match="exceed the lawful amortizable basis"):
        operations.forecast(asset_id=machine.asset_id, covered_from=date(2025, 4, 1), covered_until=date(2025, 7, 1))
    replacement = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
        supersedes_claim_id=second_claim.claim_id,
    )
    operations.record_claim(
        replacement,
        creating_operation="test.q2-corrected",
        supersedes_claim_id=second_claim.claim_id,
    )

    # 1,000 x 12% x 90/365 = 29.59; the second quarter is capped at the 20.41 left of the 50.00 pending.
    assert (first.amount, second.amount) == (Decimal("29.59"), Decimal("20.41"))
    # Without it, the corrected 990 basis leaves 990 - 950 - 29.59 = 10.41.
    assert replacement.amount == Decimal("10.41")
    effective = {claim.claim_id: claim.amount for claim in effective_claims(repository.history.claims)}
    assert second_claim.claim_id not in effective
    assert sum(effective.values(), Decimal("0")) == Decimal("40.00")


def test_a_forecast_cannot_supersede_a_claim_the_asset_does_not_have() -> None:
    operations, _ = _operations()
    machine = _asset(_linear("maquinaria"), basis="1000", asset_id="no-claims-machine")
    operations.create(machine)

    with pytest.raises(ActividadAssetValidationError, match="not an effective claim of this asset"):
        operations.forecast(
            asset_id=machine.asset_id,
            covered_from=_YEAR_START,
            covered_until=_YEAR_END,
            supersedes_claim_id="c" * 64,
        )


def test_the_history_write_refuses_a_claim_under_a_superseded_revision() -> None:
    machine = _asset(_linear("maquinaria"), basis="1000", asset_id="corrected-before-write")
    corrected = machine.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": machine.revision_id, "residual_value": Decimal("10")},
    )
    history = ActivityAssetHistory(revisions=(machine, corrected))
    stale = AmortizationClaim.from_schedule(
        _charge(machine, covered_until=date(2025, 7, 1)),
        asset_kind=machine.asset_kind,
        creating_operation="test.stale-revision",
    )

    with pytest.raises(ActividadAssetClaimConflictError, match="current revision"):
        history.record_claim(stale)


def test_two_forecasts_taken_before_recording_cannot_both_consume_the_basis() -> None:
    operations, repository = _operations()
    machine = _asset(
        _election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            authority_class_key="maquinaria",
            research_development_evidence_reference="rnd-project-affectation",
        ),
        basis="10000",
        asset_id="rnd-machine",
    )
    operations.create(machine)
    first_half = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=_YEAR_START,
        covered_until=date(2025, 7, 1),
        requested_free_amount=Decimal("10000"),
    )
    second_half = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(2025, 7, 1),
        covered_until=_YEAR_END,
        requested_free_amount=Decimal("10000"),
    )

    operations.record_claim(first_half, creating_operation="test.rnd-first-half")
    with pytest.raises(ActividadAssetValidationError, match="remaining lawful basis"):
        operations.record_claim(second_half, creating_operation="test.rnd-second-half")
    assert sum((claim.amount for claim in repository.history.claims), Decimal("0")) == Decimal("10000")


def test_a_hand_edited_forecast_is_refused_at_record_time() -> None:
    operations, _ = _operations()
    machine = _asset(_linear("maquinaria"), basis="10000", asset_id="edited-machine")
    operations.create(machine)
    forecast = operations.forecast(asset_id=machine.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)
    inflated = forecast.model_copy(update={"amount": Decimal("5000.00")})

    with pytest.raises(ActividadAssetValidationError, match="no longer matches"):
        operations.record_claim(inflated, creating_operation="test.inflated")


def test_the_history_write_refuses_a_claim_beyond_the_basis_even_without_operations() -> None:
    machine = _asset(_linear("maquinaria"), basis="1000", asset_id="direct-write-machine")
    first_half = _charge(machine, covered_until=date(2025, 7, 1))
    second_half = _charge(machine, covered_from=date(2025, 7, 1))
    history = ActivityAssetHistory(revisions=(machine,))
    after_first = history.record_claim(
        AmortizationClaim.from_schedule(first_half, asset_kind=machine.asset_kind, creating_operation="test.first"),
    ).history
    beyond = AmortizationClaim.from_schedule(
        second_half.model_copy(update={"amount": Decimal("950.00")}),
        asset_kind=machine.asset_kind,
        creating_operation="test.beyond",
    )

    # First half: 1,000 x 12% x 181/365 = 59.51; adding 950.00 would reach 1,009.51 of a 1,000 basis.
    assert first_half.amount == Decimal("59.51")
    with pytest.raises(ActividadAssetClaimConflictError, match="lawful amortizable basis"):
        after_first.record_claim(beyond)


def test_low_value_free_real_authority_forecast_records_one_idempotent_claim() -> None:
    operations, _ = _operations()
    asset = _asset(
        _election(
            AmortizationMethod.LOW_VALUE_FREE,
            authority_class_key="mobiliario",
            low_value=LowValueElection(
                election_reference="operator-elected-full-amount",
                new_material_evidence_reference="canonical-new-material-invoice",
                unit_acquisition_value=Decimal("300.00"),
            ),
        ),
        basis="300.00",
        asset_id="published-free-depreciation-tool",
    )
    operations.create(asset)
    forecast = operations.forecast(
        asset_id=asset.asset_id,
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        requested_free_amount=Decimal("300.00"),
    )
    first = operations.record_claim(forecast, creating_operation="test.real-authority-free-depreciation")
    retry = operations.record_claim(forecast, creating_operation="test.real-authority-free-depreciation")

    assert forecast.amount == Decimal("300.00")
    assert first.claim.method is AmortizationMethod.LOW_VALUE_FREE
    assert retry.reused_existing_claim is True
    with pytest.raises(ActividadAssetIncompleteError, match="elected amount"):
        operations.forecast(asset_id=asset.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)
