"""Hand-worked disposal calculations, each figure derived in its test."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalFacts,
    ActivityAssetDisposalFindingKind,
    ActivityAssetDisposalReason,
    ActivityAssetDisposalYearFacts,
    calculate_disposal,
    require_admissible_disposal,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _refusal(
    reason: ActivityAssetDisposalReason,
    *,
    proceeds: str = "0.00",
    market_value: str | None = None,
) -> str | None:
    """Return the registered refusal, having held the record itself to the same rule."""
    with pytest.raises(ValidationError):
        _disposal(reason, proceeds=proceeds, market_value=market_value)
    with pytest.raises(ActividadAssetError) as refused:
        require_admissible_disposal(
            reason,
            proceeds=Decimal(proceeds),
            transmission_costs=Decimal("0.00"),
            market_value=None if market_value is None else Decimal(market_value),
        )
    return refused.value.translated_message


def _disposal(
    reason: ActivityAssetDisposalReason = ActivityAssetDisposalReason.SALE,
    *,
    proceeds: str = "0.00",
    costs: str = "0.00",
    market_value: str | None = None,
    on: date = date(2025, 6, 30),
    later_affectation_on: date | None = None,
) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=on,
        reason=reason,
        proceeds=Decimal(proceeds),
        transmission_costs=Decimal(costs),
        market_value=None if market_value is None else Decimal(market_value),
        later_affectation_on=later_affectation_on,
    )


def _year(
    tax_year: int,
    claims: str = "0.00",
    minimum: str | None = "100.00",
    maximum: str | None = None,
    *,
    gap: bool = False,
) -> ActivityAssetDisposalYearFacts:
    return ActivityAssetDisposalYearFacts(
        tax_year=tax_year,
        claims=Decimal(claims),
        minimum=None if minimum is None else Decimal(minimum),
        maximum_charge=None if maximum is None else Decimal(maximum),
        claim_gap=gap,
    )


def _facts(
    disposal: ActivityAssetDisposal,
    years: tuple[ActivityAssetDisposalYearFacts, ...],
    *,
    acquisition: str = "1000.00",
    share: str = "1",
    amortizable: str = "1000.00",
    opening: str = "0",
    excess: bool = False,
) -> ActivityAssetDisposalFacts:
    return ActivityAssetDisposalFacts(
        disposal=disposal,
        acquisition_value=Decimal(acquisition),
        allocation_share=Decimal(share),
        amortizable_value=Decimal(amortizable),
        opening_amount=Decimal(opening),
        years=years,
        excess_applies=excess,
    )


def _excess_years() -> tuple[ActivityAssetDisposalYearFacts, ...]:
    return (
        _year(2024, "30000.00", minimum="2142.86", maximum="4800.00"),
        _year(2025, minimum="2142.86", maximum="4800.00"),
        _year(2026, minimum="1058.99", maximum="2380.27"),
    )


def test_the_disposal_date_is_the_last_service_day() -> None:
    assert _disposal(on=date(2025, 12, 31)).boundary == date(2026, 1, 1)


@pytest.mark.parametrize(
    "reason",
    [
        ActivityAssetDisposalReason.SALE,
        ActivityAssetDisposalReason.PART_EXCHANGE,
        ActivityAssetDisposalReason.THEFT,
        ActivityAssetDisposalReason.DESTRUCTION,
    ],
)
def test_each_reason_with_proceeds_nets_them_against_the_net_value(reason: ActivityAssetDisposalReason) -> None:
    # Reduction 300 on cost 1,000 leaves 700; 900 proceeds less 50 costs gives 150.
    calculation = calculate_disposal(
        _facts(_disposal(reason, proceeds="900.00", costs="50.00"), (_year(2024, "150.00"), _year(2025, "150.00"))),
    )
    assert calculation.reduction == Decimal("300.00")
    assert calculation.result == Decimal("150.00")


def test_scrapping_is_a_loss_of_the_net_value() -> None:
    calculation = calculate_disposal(_facts(_disposal(ActivityAssetDisposalReason.SCRAPPING), (_year(2025, "100.00"),)))
    assert calculation.result == Decimal("-900.00")


def test_scrapping_with_proceeds_is_refused() -> None:
    assert _refusal(ActivityAssetDisposalReason.SCRAPPING, proceeds="1.00") == (
        "ledger.actividad_asset.errors.disposal_scrapping_with_proceeds"
    )


def test_a_donation_is_refused() -> None:
    assert _refusal(ActivityAssetDisposalReason.DONATION) == "ledger.actividad_asset.errors.disposal_donation_refused"


def test_a_withdrawal_computes_no_gain() -> None:
    calculation = calculate_disposal(
        _facts(_disposal(ActivityAssetDisposalReason.WITHDRAWAL), (_year(2025, "100.00"),))
    )
    assert calculation.result is None
    assert calculation.transmission_value is None
    assert calculation.net_value == Decimal("900.00")


def test_a_withdrawal_states_no_amounts() -> None:
    assert _refusal(ActivityAssetDisposalReason.WITHDRAWAL, market_value="5.00") == (
        "ledger.actividad_asset.errors.disposal_withdrawal_with_amounts"
    )


def test_amounts_must_be_cents() -> None:
    with pytest.raises(ValidationError):
        _disposal(proceeds="1.001")


def test_the_reduction_follows_the_larger_of_claims_and_minimum_year_by_year() -> None:
    # M is 100 a year. 2022 is the opening span: max(0, 100) = 100.
    # 2023: max(100 + 50, 200) = 200. 2024: max(200 + 250, 300) = 450. 2025: max(450 + 0, 400) = 450.
    calculation = calculate_disposal(
        _facts(
            _disposal(proceeds="1000.00"),
            (_year(2022), _year(2023, "50.00"), _year(2024, "250.00"), _year(2025)),
        ),
    )
    assert [year.reduction_through for year in calculation.years] == [
        Decimal("100.00"),
        Decimal("200.00"),
        Decimal("450.00"),
        Decimal("450.00"),
    ]
    assert calculation.deducted == Decimal("300.00")
    assert calculation.result == Decimal("450.00")


def test_the_opening_span_is_one_maximum_of_the_opening_and_its_minimum() -> None:
    # Three unclaimed years with 500 opening: max(500, 300) = 500, then 2025 claims 50: max(550, 400) = 550.
    calculation = calculate_disposal(
        _facts(
            _disposal(proceeds="1000.00"),
            (_year(2022), _year(2023), _year(2024), _year(2025, "50.00")),
            opening="500.00",
        ),
    )
    assert calculation.reduction == Decimal("550.00")
    assert calculation.deducted == Decimal("550.00")
    assert ActivityAssetDisposalFindingKind.MINIMUM_EXCEEDED_DEDUCTION not in [f.kind for f in calculation.findings]


def test_a_minimum_above_the_opening_reduces_cost_with_a_finding_of_its_effect() -> None:
    # Opening 100, no claims, M 300 over the span: reduction 300, of which the minimum added 200.
    calculation = calculate_disposal(
        _facts(_disposal(proceeds="1000.00"), (_year(2023), _year(2024), _year(2025)), opening="100.00"),
    )
    assert calculation.reduction == Decimal("300.00")
    assert [
        (f.tax_year, f.effect_on_cost)
        for f in calculation.findings
        if f.kind is ActivityAssetDisposalFindingKind.MINIMUM_EXCEEDED_DEDUCTION
    ] == [(2025, Decimal("200.00"))]


def test_a_missing_claim_is_a_finding_and_never_a_refusal() -> None:
    calculation = calculate_disposal(_facts(_disposal(proceeds="1000.00"), (_year(2025, gap=True),)))
    assert calculation.reduction == Decimal("100.00")
    assert calculation.findings[0].kind is ActivityAssetDisposalFindingKind.CLAIM_GAP


def test_a_year_with_no_minimum_authority_counts_only_what_was_deducted() -> None:
    # 2015 claims 40 with no minimum; 2016 has M 100: max(40 + 0, 100) = 100.
    calculation = calculate_disposal(
        _facts(_disposal(proceeds="1000.00"), (_year(2015, "40.00", minimum=None), _year(2016))),
    )
    assert calculation.years[0].reduction_through == Decimal("40.00")
    assert calculation.reduction == Decimal("100.00")
    assert (ActivityAssetDisposalFindingKind.NO_MINIMUM_AUTHORITY, 2015) in [
        (f.kind, f.tax_year) for f in calculation.findings
    ]


def test_the_reduction_is_capped_at_the_amortizable_value() -> None:
    # 900 of claims, M 2,000 and an amortizable value of 900 (a residual of 100): 900 reduces cost of 1,000.
    calculation = calculate_disposal(
        _facts(_disposal(), (_year(2025, "900.00", minimum="2000.00"),), amortizable="900.00"),
    )
    assert calculation.reduction == Decimal("900.00")
    assert calculation.net_value == Decimal("100.00")


def test_excess_above_the_maximum_coefficient() -> None:
    # 30,000 charged in 2024; C = 4,800 + 4,800 + 2,380.27 = 11,980.27; E = 18,019.73.
    # M is 5,344.71, so R = max(min(30,000, 11,980.27), 5,344.71) and 20,000 - (30,000 - 11,980.27) = 1,980.27.
    calculation = calculate_disposal(
        _facts(
            _disposal(proceeds="20000.00", on=date(2026, 6, 30)),
            _excess_years(),
            acquisition="30000.00",
            amortizable="30000.00",
            excess=True,
        ),
    )
    assert calculation.excess == Decimal("18019.73")
    assert calculation.minimum == Decimal("5344.71")
    assert calculation.reduction == Decimal("11980.27")
    assert calculation.result == Decimal("1980.27")


def test_without_the_regime_no_excess_exists_on_the_same_figures() -> None:
    calculation = calculate_disposal(
        _facts(
            _disposal(proceeds="20000.00", on=date(2026, 6, 30)),
            _excess_years(),
            acquisition="30000.00",
            amortizable="30000.00",
        ),
    )
    assert calculation.excess == Decimal("0.00")
    assert calculation.reduction == Decimal("30000.00")
    assert calculation.result == Decimal("20000.00")


def test_a_required_counterfactual_without_a_table_class_is_refused() -> None:
    with pytest.raises(ActividadAssetError) as refused:
        calculate_disposal(_facts(_disposal(), (_year(2025, "500.00", maximum=None),), excess=True))
    assert refused.value.translated_message == "ledger.actividad_asset.errors.disposal_excess_without_table_class"


def test_a_withdrawal_has_no_excess_whatever_the_method() -> None:
    calculation = calculate_disposal(
        _facts(_disposal(ActivityAssetDisposalReason.WITHDRAWAL), (_year(2025, "500.00", maximum=None),), excess=True),
    )
    assert calculation.excess == Decimal("0.00")


def test_market_value_above_proceeds_is_the_value_of_transmission() -> None:
    # max(500, 800) - 0 - (1,000 - 100) = -100.
    calculation = calculate_disposal(
        _facts(_disposal(proceeds="500.00", market_value="800.00"), (_year(2025, "100.00"),)),
    )
    assert calculation.transmission_value == Decimal("800.00")
    assert calculation.result == Decimal("-100.00")


def test_market_value_below_proceeds_leaves_the_proceeds() -> None:
    calculation = calculate_disposal(
        _facts(_disposal(proceeds="500.00", market_value="300.00"), (_year(2025, "100.00"),)),
    )
    assert calculation.transmission_value == Decimal("500.00")


def test_whole_element_amounts_take_the_allocation_share() -> None:
    # Half the element is the activity's: 1,000 proceeds and 100 costs become 500 and 50; cost 500, reduction 50.
    calculation = calculate_disposal(
        _facts(
            _disposal(proceeds="1000.00", costs="100.00"),
            (_year(2025, "50.00", minimum=None),),
            acquisition="500.00",
            share="0.5",
            amortizable="500.00",
        ),
    )
    assert calculation.transmission_value == Decimal("500.00")
    assert calculation.transmission_costs == Decimal("50.00")
    assert calculation.result == Decimal("0.00")


def test_a_gain_reports_that_no_exemption_was_computed() -> None:
    calculation = calculate_disposal(_facts(_disposal(proceeds="2000.00"), (_year(2025, "100.00"),)))
    assert ActivityAssetDisposalFindingKind.EXEMPTION_NOT_COMPUTED in [f.kind for f in calculation.findings]


def test_a_sale_within_the_stated_period_of_a_later_affectation_changes_the_route() -> None:
    within = _disposal(proceeds="1.00", later_affectation_on=date(2022, 7, 1))
    after = _disposal(proceeds="1.00", later_affectation_on=date(2022, 6, 30))
    stated = {"later_affectation_period_years": 3}
    assert calculate_disposal(
        _facts(within, (_year(2025),)).model_copy(update=stated)
    ).route_changed_by_later_affectation
    assert not calculate_disposal(
        _facts(after, (_year(2025),)).model_copy(update=stated)
    ).route_changed_by_later_affectation
    # An edition stating no period leaves the route open rather than assuming the ordinary one.
    assert calculate_disposal(_facts(after, (_year(2025),))).route_changed_by_later_affectation


def test_manual_example_as_an_arithmetic_oracle() -> None:
    # Renta 2025 manual, part 1: 54,000 of which 40% is land, so 32,400 amortizable at 3% is 972 a year.
    # 1998 to 2024 is 27 years, 26,244. Half of 2025 by days is 972 x 181 / 365 = 482.01, against the
    # manual's 486 by months. 210,000 less 13,000 of costs, less (54,000 - 26,726.01), is 169,726.01.
    calculation = calculate_disposal(
        _facts(
            _disposal(proceeds="210000.00", costs="13000.00"),
            (
                *(_year(year, "972.00", minimum=None) for year in range(1998, 2025)),
                _year(2025, "482.01", minimum=None),
            ),
            acquisition="54000.00",
            amortizable="32400.00",
        ),
    )
    assert calculation.reduction == Decimal("26726.01")
    assert calculation.net_value == Decimal("27273.99")
    assert calculation.result == Decimal("169726.01")
