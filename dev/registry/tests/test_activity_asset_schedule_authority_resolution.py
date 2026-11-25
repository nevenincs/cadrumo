"""Real-source resolution of activity-asset amortization elections.

Every expected amount is an independent hand calculation from the cited
provision, written out beside the assertion; none is copied from a run of the
code under test.  Proration follows the accepted day-count contract (service
days over 365 for the tax year).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

import pytest

from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    AmortizationMethod,
    ApprovedAmortizationPlan,
    DefiniteUsefulLife,
    DigitOrder,
    DirectEstimationRegime,
    OriginalPriceDetermination,
    PlanAnnualAmount,
    PlanApprovalKind,
    UsedAssetOriginalPrice,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    ActivityAssetRevision,
    AssetKind,
)
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
)

from .activity_asset_schedule_support import (
    TAX_YEAR,
    YEAR_START,
    activity_asset_schedule_asset,
    activity_asset_schedule_charge,
    activity_asset_schedule_constant,
    activity_asset_schedule_election,
    activity_asset_schedule_linear,
    activity_asset_schedule_refused,
    legal_reference,
    modelo_100,
    small_enterprise,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_linear_table_resolves_each_modality_maximum_from_source() -> None:
    normal = resolve_activity_asset_schedule_authority(
        modelo_100(),
        tax_year=TAX_YEAR,
        asset_revision=activity_asset_schedule_asset(
            activity_asset_schedule_linear("equipo-proceso-informacion"), basis="2000.00"
        ),
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=legal_reference,
    )
    simplified = resolve_activity_asset_schedule_authority(
        modelo_100(),
        tax_year=TAX_YEAR,
        asset_revision=activity_asset_schedule_asset(
            activity_asset_schedule_linear("equipo-informacion-software", DirectEstimationRegime.SIMPLIFIED),
            basis="2000.00",
            kind=AssetKind.INTANGIBLE,
        ),
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=legal_reference,
    )

    assert normal.annual_rate == Decimal("0.25")
    assert simplified.annual_rate == Decimal("0.26")
    assert "metodo-admitido:key:material:linear" in normal.source_reference
    assert "coeficiente-lineal-maximo:key:equipo-proceso-informacion" in normal.source_reference


def test_two_thousand_euro_computer_forecasts_permitted_charge_not_purchase_cost() -> None:
    charge = activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_linear("equipo-proceso-informacion"), basis="2000.00")
    )

    # 2,000 x 25% for a full service year.
    assert charge.amount == Decimal("500.00")


def test_elected_linear_coefficient_is_bounded_by_the_maximum_and_the_maximum_period() -> None:
    # Processing equipment: maximum 25%, maximum period 8 years, so the floor is 1/8 = 12.5%.
    elected = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("equipo-proceso-informacion", linear_coefficient=Decimal("0.20")),
            basis="2000.00",
        )
    )
    floor = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("equipo-proceso-informacion", linear_coefficient=Decimal("0.125")),
            basis="2000.00",
        )
    )

    assert elected.amount == Decimal("400.00")  # 2,000 x 20%
    assert floor.amount == Decimal("250.00")  # 2,000 x 12.5%
    for outside in ("0.12", "0.26"):
        with activity_asset_schedule_refused(ActividadAssetValidationError, "elected_coefficient_out_of_range"):
            activity_asset_schedule_charge(
                activity_asset_schedule_asset(
                    activity_asset_schedule_linear("equipo-proceso-informacion", linear_coefficient=Decimal(outside)),
                    basis="2000.00",
                )
            )


def test_first_partial_year_and_residual_value_use_the_amortizable_basis() -> None:
    partial = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("equipo-proceso-informacion"),
            basis="2000.00",
            in_service=date(TAX_YEAR, 7, 1),
        )
    )
    residual = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("equipo-proceso-informacion"), basis="2000.00", residual="400"
        )
    )

    assert partial.service_days == 184
    assert partial.amount == Decimal("252.05")  # 2,000 x 25% x 184/365 = 252.0548
    assert residual.amount == Decimal("400.00")  # (2,000 - 400) x 25%


def test_used_asset_may_double_the_maximum_only_in_the_normal_modality() -> None:
    used_machine = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("maquinaria"), basis="10000", condition=AcquiredCondition.USED
        )
    )
    simplified_used = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("maquinaria", DirectEstimationRegime.SIMPLIFIED),
            basis="10000",
            condition=AcquiredCondition.USED,
        ),
    )

    assert used_machine.amount == Decimal("2400.00")  # 10,000 x (2 x 12%)
    assert simplified_used.amount == Decimal("1200.00")  # 10,000 x 12%, no doubling enrolled


def test_a_building_under_ten_years_old_is_not_a_used_asset() -> None:
    young = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("edificio-industrial"),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=date(TAX_YEAR - 5, 1, 1),
        ),
    )
    old = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("edificio-industrial"),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=date(TAX_YEAR - 10, 1, 1),
        ),
    )

    assert young.amount == Decimal("3000.00")  # five years old: 100,000 x 3%
    assert old.amount == Decimal("6000.00")  # exactly ten years old: 100,000 x (2 x 3%)
    with activity_asset_schedule_refused(ActividadAssetIncompleteError, "used_building_requires_construction_date"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear("edificio-industrial"), basis="100000", condition=AcquiredCondition.USED
            )
        )


def _original(
    price: str,
    determination: OriginalPriceDetermination = OriginalPriceDetermination.KNOWN,
    evidence: str | None = None,
) -> UsedAssetOriginalPrice:
    return UsedAssetOriginalPrice(
        determination=determination,
        original_price=Decimal(price),
        evidence_reference=evidence,
    )


def _used_machine(*, price: str = "30000.00", basis: str = "10000", **facts: object) -> ActivityAssetRevision:
    return activity_asset_schedule_asset(
        activity_asset_schedule_election(
            AmortizationMethod.LINEAR,
            DirectEstimationRegime.NORMAL,
            authority_class_key="maquinaria",
            used_original_price=_original(price),
            **facts,
        ),
        basis=basis,
        condition=AcquiredCondition.USED,
    )


def test_a_known_original_price_is_the_base_of_the_single_maximum_coefficient() -> None:
    asset = _used_machine()
    authority = resolve_activity_asset_schedule_authority(
        modelo_100(),
        tax_year=TAX_YEAR,
        asset_revision=asset,
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=legal_reference,
    )

    assert authority.annual_rate == Decimal("0.12")  # the table maximum, not twice it
    assert authority.original_price_basis == Decimal("30000.00")
    assert activity_asset_schedule_charge(asset).amount == Decimal(
        "3600.00"
    )  # 30,000 x 12%, against 2,400 on the doubled acquisition price
    assert activity_asset_schedule_charge(_used_machine(linear_coefficient=Decimal("0.10"))).amount == Decimal(
        "3000.00"
    )  # 30,000 x 10%


def test_the_original_price_route_is_limited_to_the_undoubled_maximum() -> None:
    at_maximum = activity_asset_schedule_charge(_used_machine(linear_coefficient=Decimal("0.12")))

    assert at_maximum.amount == Decimal("3600.00")
    for above in ("0.1201", "0.24"):
        with activity_asset_schedule_refused(
            ActividadAssetValidationError, "elected_coefficient_out_of_range", maximum=Decimal("0.12")
        ):
            activity_asset_schedule_charge(_used_machine(linear_coefficient=Decimal(above)))


def test_the_original_price_route_never_charges_beyond_the_elements_own_basis() -> None:
    # 100,000 x 12% = 12,000 would exceed the 10,000 the element cost, so only the cost remains.
    assert activity_asset_schedule_charge(_used_machine(price="100000.00")).amount == Decimal("10000.00")


def test_an_expert_valuation_of_the_original_price_proceeds_as_a_known_price() -> None:
    valuation = _original("25000.00", OriginalPriceDetermination.EXPERT_VALUATION, "valuation-report-2025-001")
    asset = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria", used_original_price=valuation),
        basis="10000",
        condition=AcquiredCondition.USED,
    )

    assert activity_asset_schedule_charge(asset).amount == Decimal("3000.00")  # 25,000 x 12%
    with activity_asset_schedule_refused(
        ActividadAssetValidationError, "original_price_expert_requires_evidence", field="evidence_reference"
    ):
        _original("25000.00", OriginalPriceDetermination.EXPERT_VALUATION)


def test_a_change_of_original_price_is_a_change_of_election() -> None:
    plain = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="10000", condition=AcquiredCondition.USED
    )

    assert _used_machine(price="30000.00").amortization.fingerprint != (
        _used_machine(price="31000.00").amortization.fingerprint
    )
    assert _used_machine().amortization.fingerprint != plain.amortization.fingerprint


def test_an_original_price_is_a_fact_of_the_linear_method_only() -> None:
    with activity_asset_schedule_refused(
        ActividadAssetValidationError,
        "election_fact_not_of_method",
        method=AmortizationMethod.CONSTANT_PERCENTAGE.value,
        field="used_original_price",
    ):
        activity_asset_schedule_election(
            AmortizationMethod.CONSTANT_PERCENTAGE,
            authority_class_key="maquinaria",
            used_original_price=_original("30000.00"),
        )


def test_the_original_price_route_refuses_an_element_that_is_not_used() -> None:
    new_machine = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria", used_original_price=_original("30000.00")),
        basis="10000",
        condition=AcquiredCondition.NEW,
    )

    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "used_original_price_requires_used_asset", asset_id="asset"
    ):
        activity_asset_schedule_charge(new_machine)


def test_the_original_price_route_refuses_a_modality_without_a_used_asset_rule() -> None:
    simplified = activity_asset_schedule_asset(
        activity_asset_schedule_linear(
            "maquinaria", DirectEstimationRegime.SIMPLIFIED, used_original_price=_original("30000.00")
        ),
        basis="10000",
        condition=AcquiredCondition.USED,
    )

    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "used_original_price_not_enrolled", regime="simplified"
    ):
        activity_asset_schedule_charge(simplified)


def test_the_original_price_route_follows_the_ten_year_building_rule() -> None:
    def building(built: date | None) -> ActivityAssetRevision:
        return activity_asset_schedule_asset(
            activity_asset_schedule_linear("edificio-industrial", used_original_price=_original("150000.00")),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=built,
        )

    # Exactly ten years old on the in-service date: used, so 150,000 x 3%.
    assert activity_asset_schedule_charge(building(date(TAX_YEAR - 10, 1, 1))).amount == Decimal("4500.00")
    # One day short of ten years: not a used element, so the route does not apply.
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "used_original_price_requires_used_asset"):
        activity_asset_schedule_charge(building(date(TAX_YEAR - 10, 1, 2)))
    with activity_asset_schedule_refused(ActividadAssetIncompleteError, "used_building_requires_construction_date"):
        activity_asset_schedule_charge(building(None))


def test_the_original_price_route_does_not_combine_with_multi_shift_use() -> None:
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "multi_shift_with_used_asset_unsupported"):
        activity_asset_schedule_charge(_used_machine(shift_hours_per_day=Decimal("16")))


def test_multi_shift_coefficient_follows_the_hours_formula() -> None:
    # Machinery: max 12%, period-implied 1/18. 16 hours: 1/18 + (12% - 1/18) x 16/8 = 24% - 1/18.
    charge = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("maquinaria", shift_hours_per_day=Decimal("16")), basis="18000"
        )
    )

    assert charge.amount == Decimal("3320.00")  # 18,000 x 24% - 18,000/18 = 4,320 - 1,000
    with activity_asset_schedule_refused(ActividadAssetValidationError, "multi_shift_requires_extra_shift"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear("maquinaria", shift_hours_per_day=Decimal("8")), basis="18000"
            )
        )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "multi_shift_not_enrolled", regime="simplified"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear(
                    "maquinaria", DirectEstimationRegime.SIMPLIFIED, shift_hours_per_day=Decimal("16")
                ),
                basis="18000",
            )
        )


def test_reduced_size_acceleration_doubles_the_maximum_for_a_new_element() -> None:
    # The AEAT manual's LIS art. 103 example: a EUR 36,000 machine in service on
    # 1 December. The manual illustrates with a month fraction (x 1/12 = EUR 720); the
    # only official unit, binding DGT consulta V1978-24, prorates by days in service over
    # the days of the year: 36,000 x 24% x 31/365 = 733.8082.
    charge = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("maquinaria", small_enterprise=small_enterprise("2800000")),
            basis="36000",
            in_service=date(TAX_YEAR, 12, 1),
        ),
    )

    assert charge.amount == Decimal("733.81")
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "reduced_size_turnover_reached"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear(
                    "maquinaria", small_enterprise=small_enterprise("10000000", made_available=YEAR_START)
                ),
                basis="36000",
            )
        )
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear(
                "maquinaria", small_enterprise=small_enterprise("9999999.99", made_available=YEAR_START)
            ),
            basis="36000",
        ),
    ).amount == Decimal("8640.00")  # 36,000 x 24%
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "reduced_size_acceleration_new_only"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear(
                    "maquinaria", small_enterprise=small_enterprise("100", made_available=YEAR_START)
                ),
                basis="36000",
                condition=AcquiredCondition.USED,
            ),
        )


def test_used_doubling_is_limited_to_material_assets_where_it_is_enrolled() -> None:
    used_software = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("intangible-software"),
            basis="3000",
            kind=AssetKind.INTANGIBLE,
            condition=AcquiredCondition.USED,
        ),
    )
    simplified_used_building = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("edificio-otra-construccion", DirectEstimationRegime.SIMPLIFIED),
            basis="100000",
            condition=AcquiredCondition.USED,
        ),
    )

    # RIS art. 4.3 covers material assets only: 3,000 x 33%, not 66%.
    assert used_software.amount == Decimal("990.00")
    # The simplified table applies no used multiplier, so no construction date is needed: 100,000 x 3%.
    assert simplified_used_building.amount == Decimal("3000.00")


def test_constant_percentage_weights_the_elected_coefficient_by_period_band() -> None:
    long_band = activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_constant("maquinaria"), basis="10000")
    )
    medium_band = activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_constant("equipo-electronico", "0.20"), basis="1000")
    )
    short_band = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_constant("equipo-proceso-informacion", "0.25"), basis="1000"
        )
    )
    floored = activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_constant("obra-civil-general", "0.02"), basis="100000")
    )

    assert long_band.amount == Decimal("3000.00")  # 12% -> 8.33 years -> x2.5 = 30%
    assert medium_band.amount == Decimal("400.00")  # 20% -> exactly 5 years -> x2 = 40%
    assert short_band.amount == Decimal("375.00")  # 25% -> 4 years -> x1.5 = 37.5%
    assert floored.amount == Decimal("11000.00")  # 2% -> 50 years -> x2.5 = 5%, floored at 11%


def test_constant_percentage_applies_to_the_value_pending_at_the_start_of_the_year() -> None:
    first_partial = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_constant("maquinaria"), basis="10000", in_service=date(TAX_YEAR, 7, 1)
        )
    )
    second_year = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_constant("maquinaria"),
            basis="10000",
            in_service=date(TAX_YEAR - 1, 1, 1),
            opening="3000",
            opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
        ),
    )
    with_residual = activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_constant("maquinaria"), basis="10000", residual="1000")
    )
    quarter_after_claim = activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_constant("maquinaria"), basis="10000"),
        covered_from=date(TAX_YEAR, 4, 1),
        covered_until=date(TAX_YEAR, 7, 1),
        history=AssetScheduleHistory(accumulated_in_tax_year=Decimal("739.73")),
    )

    assert first_partial.amount == Decimal("1512.33")  # 10,000 x 30% x 184/365 = 1,512.3288
    assert second_year.amount == Decimal("2100.00")  # (10,000 - 3,000) x 30%
    assert with_residual.amount == Decimal("2700.00")  # (10,000 - 1,000) x 30%
    # In-year claims do not change the start-of-year pending value: 10,000 x 30% accrues
    # 739.726 by 1 April and 1,487.671 by 1 July, so the quarter is 1,487.67 - 739.73.
    assert quarter_after_claim.amount == Decimal("747.94")


def test_constant_percentage_amortizes_everything_pending_in_the_final_year() -> None:
    # 25% elected -> 4-year life from 1 July four years earlier, concluding on 1 July of the tax year.
    asset = activity_asset_schedule_asset(
        activity_asset_schedule_constant("equipo-proceso-informacion", "0.25"),
        basis="10000",
        in_service=date(TAX_YEAR - 4, 7, 1),
        opening="8000",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )

    whole_year = activity_asset_schedule_charge(asset)
    first_quarter = activity_asset_schedule_charge(asset, covered_until=date(TAX_YEAR, 4, 1))

    assert whole_year.covered_until == date(TAX_YEAR, 7, 1)
    assert whole_year.amount == Decimal("2000.00")  # the whole pending value
    assert first_quarter.amount == Decimal("994.48")  # 2,000 x 90/181 = 994.4751
    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed"):
        activity_asset_schedule_charge(asset, covered_from=date(TAX_YEAR, 8, 1))


def test_constant_percentage_final_year_intervals_telescope_to_the_pending_value() -> None:
    asset = activity_asset_schedule_asset(
        activity_asset_schedule_constant("equipo-proceso-informacion", "0.25"),
        basis="10000",
        in_service=date(TAX_YEAR - 4, 7, 1),
        opening="9000",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )
    boundaries = (date(TAX_YEAR, 1, 1), date(TAX_YEAR, 1, 2), date(TAX_YEAR, 1, 3), date(TAX_YEAR, 7, 1))

    amounts = [
        activity_asset_schedule_charge(asset, covered_from=start, covered_until=end).amount
        for start, end in pairwise(boundaries)
    ]

    # 1,000 pending over 181 final-year days: 5.52 + 5.53 + 988.95, no stranded cent.
    assert amounts == [Decimal("5.52"), Decimal("5.53"), Decimal("988.95")]
    assert sum(amounts, Decimal("0")) == Decimal("1000.00")


def test_a_from_start_method_refuses_an_unattested_opening_amount() -> None:
    unattested = activity_asset_schedule_asset(
        activity_asset_schedule_constant("maquinaria"),
        basis="10000",
        in_service=date(TAX_YEAR - 1, 1, 1),
        opening="3000",
    )
    other_method = activity_asset_schedule_asset(
        activity_asset_schedule_constant("maquinaria"),
        basis="10000",
        in_service=date(TAX_YEAR - 1, 1, 1),
        opening="1200",
        opening_method=AmortizationMethod.LINEAR,
    )

    for asset in (unattested, other_method):
        with pytest.raises(ActividadAssetUnsupportedError, match="opening_amount_must_attest_from_start_method"):
            activity_asset_schedule_charge(asset)


def test_constant_percentage_excludes_buildings_furniture_and_the_simplified_modality() -> None:
    for class_key in ("mobiliario", "edificio-industrial", "almacen-deposito", "util-herramienta"):
        with activity_asset_schedule_refused(
            ActividadAssetUnsupportedError, "method_excludes_buildings_and_furniture", provision="RIS art. 5.2"
        ):
            activity_asset_schedule_charge(
                activity_asset_schedule_asset(activity_asset_schedule_constant(class_key), basis="1000")
            )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "method_excluded_by_law", rendered=r"excluded by law.*rd-439-2007:art-30"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_constant("maquinaria", regime=DirectEstimationRegime.SIMPLIFIED), basis="1000"
            )
        )


def test_constant_percentage_and_sum_of_digits_admit_the_intangibles_the_table_lists() -> None:
    constant = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_constant("intangible-software"), basis="3000", kind=AssetKind.INTANGIBLE
        )
    )
    digits = activity_asset_schedule_charge(
        activity_asset_schedule_asset(_digits("intangible-software", 4), basis="3000", kind=AssetKind.INTANGIBLE)
    )

    # LIS art. 12.1.a lists software at 33%: 3.03 years is under 5, so RIS art. 5.1.a weights it
    # 1.5 to 49.5%, and 3,000 x 49.5% = 1,485.00.
    assert constant.amount == Decimal("1485.00")
    # Whole-year periods run from ceil(1 / 0.33) = 4 to the 6-year maximum; four years descending
    # gives the first year 4 of 10 digits: 3,000 x 4/10 = 1,200.00.
    assert digits.amount == Decimal("1200.00")


def test_simplified_intangible_table_methods_refuse_with_the_sources_that_leave_them_open() -> None:
    for election in (
        activity_asset_schedule_constant("equipo-informacion-software", regime=DirectEstimationRegime.SIMPLIFIED),
        activity_asset_schedule_election(
            AmortizationMethod.SUM_OF_DIGITS,
            DirectEstimationRegime.SIMPLIFIED,
            authority_class_key="equipo-informacion-software",
            sum_of_digits_period_years=4,
            digit_order=DigitOrder.DESCENDING,
        ),
    ):
        with activity_asset_schedule_refused(
            ActividadAssetUnsupportedError,
            "simplified_intangible_table_method",
            rendered=r"RIRPF art\. 30\.1a.*Order of 27 March 1998",
        ):
            activity_asset_schedule_charge(
                activity_asset_schedule_asset(election, basis="3000", kind=AssetKind.INTANGIBLE)
            )


def _digits(class_key: str, period: int, order: DigitOrder = DigitOrder.DESCENDING):
    return activity_asset_schedule_election(
        AmortizationMethod.SUM_OF_DIGITS,
        authority_class_key=class_key,
        sum_of_digits_period_years=period,
        digit_order=order,
    )


def test_sum_of_digits_allocates_quota_per_digit_in_either_order() -> None:
    # Machinery, 9 years: digit sum 45, quota 45,000 / 45 = 1,000 per digit.
    descending = activity_asset_schedule_charge(activity_asset_schedule_asset(_digits("maquinaria", 9), basis="45000"))
    ascending = activity_asset_schedule_charge(
        activity_asset_schedule_asset(_digits("maquinaria", 9, DigitOrder.ASCENDING), basis="45000")
    )
    mid_year = activity_asset_schedule_charge(
        activity_asset_schedule_asset(_digits("maquinaria", 9), basis="45000", in_service=date(TAX_YEAR, 7, 1))
    )

    assert descending.amount == Decimal("9000.00")  # digit 9
    assert ascending.amount == Decimal("1000.00")  # digit 1
    assert mid_year.amount == Decimal("4536.99")  # first life year 9,000 x 184/365 = 4,536.9863


def test_sum_of_digits_period_lies_between_the_coefficient_and_the_maximum_period() -> None:
    # Machinery: 12% implies 8.33 years, so whole-year periods run from 9 to the 18-year maximum.
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(_digits("maquinaria", 18), basis="171000")
    ).amount == Decimal("18000.00")  # 171,000 x 18/171
    for period in (8, 19):
        with activity_asset_schedule_refused(ActividadAssetValidationError, "sum_of_digits_period_out_of_range"):
            activity_asset_schedule_charge(activity_asset_schedule_asset(_digits("maquinaria", period), basis="45000"))


def test_sum_of_digits_final_life_year_reaches_exactly_the_basis() -> None:
    asset = activity_asset_schedule_asset(
        _digits("maquinaria", 9),
        basis="45000",
        in_service=date(TAX_YEAR - 8, 1, 1),
        opening="44000",
        opening_method=AmortizationMethod.SUM_OF_DIGITS,
    )

    # The tax year is the ninth life year, digit 1: 1,000, which leaves nothing pending.
    assert activity_asset_schedule_charge(asset).amount == Decimal("1000.00")


def test_sum_of_digits_excludes_buildings_and_furniture() -> None:
    for class_key in ("edificio-comercial-administrativo-servicios-vivienda", "enseres-otros"):
        with activity_asset_schedule_refused(
            ActividadAssetUnsupportedError, "method_excludes_buildings_and_furniture", provision="RIS art. 6.2"
        ):
            activity_asset_schedule_charge(activity_asset_schedule_asset(_digits(class_key, 20), basis="1000"))


def _plan(submitted: date = date(TAX_YEAR - 1, 11, 1), amounts: tuple[tuple[int, str], ...] = ((TAX_YEAR, "5000"),)):
    return activity_asset_schedule_election(
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
    plan = _plan(amounts=((TAX_YEAR, "5000"), (TAX_YEAR + 1, "4000"), (TAX_YEAR + 2, "3000")))

    assert activity_asset_schedule_charge(activity_asset_schedule_asset(plan, basis="12000")).amount == Decimal(
        "5000.00"
    )
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(plan, basis="12000"), covered_until=date(TAX_YEAR, 4, 1)
    ).amount == Decimal(
        "1232.88",
    )  # 5,000 x 90/365 = 1,232.8767


def test_approved_plan_refusals() -> None:
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "approved_plan_not_yet_effective", rendered=re.escape("RIS art. 7.8")
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(_plan(submitted=date(TAX_YEAR + 1, 1, 10)), basis="12000")
        )
    with pytest.raises(ActividadAssetValidationError, match="approved_plan_exceeds_basis"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(_plan(amounts=((TAX_YEAR, "5000"), (TAX_YEAR + 1, "8000"))), basis="12000")
        )
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "approved_plan_without_distribution"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(_plan(amounts=((TAX_YEAR + 1, "5000"),)), basis="12000")
        )
    simplified_plan = _plan().model_copy(update={"regime": DirectEstimationRegime.SIMPLIFIED})
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "method_excluded_by_law"):
        activity_asset_schedule_charge(activity_asset_schedule_asset(simplified_plan, basis="12000"))


def test_definite_life_intangible_amortizes_over_its_evidenced_life() -> None:
    licence = activity_asset_schedule_election(
        AmortizationMethod.INTANGIBLE_USEFUL_LIFE,
        useful_life=DefiniteUsefulLife(ends_on=date(TAX_YEAR + 2, 1, 1), evidence_reference="licence-term"),
    )
    asset = activity_asset_schedule_asset(licence, basis="3650", kind=AssetKind.INTANGIBLE)

    assert activity_asset_schedule_charge(asset).amount == Decimal("1825.00")  # 3,650 x 365/730
    assert activity_asset_schedule_charge(asset, covered_until=date(TAX_YEAR, 4, 1)).amount == Decimal(
        "450.00"
    )  # 3,650 x 90/730
    with activity_asset_schedule_refused(ActividadAssetValidationError, "useful_life_must_end_after_service"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_election(
                    AmortizationMethod.INTANGIBLE_USEFUL_LIFE,
                    useful_life=DefiniteUsefulLife(ends_on=YEAR_START, evidence_reference="bad"),
                ),
                basis="3650",
                kind=AssetKind.INTANGIBLE,
            ),
        )


def test_reduced_size_goodwill_and_indefinite_life_intangibles_deduct_150_percent_of_the_twentieth() -> None:
    evidence = small_enterprise("2800000", made_available=YEAR_START)
    goodwill = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_election(AmortizationMethod.GOODWILL, small_enterprise=evidence),
            basis="40000",
            kind=AssetKind.INTANGIBLE,
            condition=AcquiredCondition.USED,
        ),
    )
    indefinite = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_election(
                AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE,
                DirectEstimationRegime.SIMPLIFIED,
                small_enterprise=evidence,
            ),
            basis="20000",
            kind=AssetKind.INTANGIBLE,
        ),
    )

    # LIS art. 103.5 as the AEAT manual and DGT V0976-24 read it: 150% of the 5% art. 12.2
    # amount is 7.5%, so 40,000 x 7.5% = 3,000.00 and 20,000 x 7.5% = 1,500.00. Unlike
    # art. 103.1, the element need not be new, so acquired goodwill qualifies.
    assert goodwill.amount == Decimal("3000.00")
    assert indefinite.amount == Decimal("1500.00")
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "reduced_size_turnover_reached"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_election(
                    AmortizationMethod.GOODWILL,
                    small_enterprise=small_enterprise("10000000", made_available=YEAR_START),
                ),
                basis="40000",
                kind=AssetKind.INTANGIBLE,
            ),
        )
