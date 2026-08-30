"""A lawful 5 % food line in 2023 must classify, because the app grounds it.

RDL 20/2022 art. 72 put seed oils and pasta at 5 % and basic foods at 0 % from
2023-01-01, and three successive extensions carried that window to 2024-06-30
before RD-ley 4/2024 took over. The legal catalogue has carried the provision in
full since before this test existed -- bundled corpus file, BOE identity,
window, and discriminating ``required_text``.

What was missing was the RATE ROWS. So the app held the authority for a rate it
then refused to recognise: a taxpayer who bought oils at 5 % in 2023 had that
line fail to classify, while the identical line in August 2024 succeeded.

Only the 5 % arm was visible. The 0 % arm resolves on every date through the
deliberate zero-tier exemption, which masked half the gap -- one axis hiding the
absence on another, so a probe that looked only at zero would have reported the
window healthy.

These tests pin the window's boundaries rather than a sample inside it, because
the defect was an absent window and an absent window fails at its edges first.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..lookup import rate_kinds_for_declared_rate
from ..schema import EUMemberState, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FIVE = Decimal("0.05")


@pytest.mark.parametrize(
    "on_date",
    (
        pytest.param(date(2023, 1, 1), id="window-opens"),
        pytest.param(date(2023, 6, 1), id="mid-2023"),
        pytest.param(date(2024, 3, 1), id="first-half-2024"),
        pytest.param(date(2024, 6, 30), id="rdl-20-2022-last-day"),
        pytest.param(date(2024, 7, 1), id="rdl-4-2024-first-day"),
        pytest.param(date(2024, 9, 30), id="rdl-4-2024-last-day"),
    ),
)
def test_the_five_percent_food_rate_classifies_across_its_whole_grounded_span(on_date: date) -> None:
    """Every date the two bundled provisions jointly cover must classify 5 %."""
    assert rate_kinds_for_declared_rate(EUMemberState.ES, _FIVE, on_date) == (IvaRateKind.REDUCED,), (
        f"5 % is a lawful Spanish rate on {on_date.isoformat()} under the provisions this "
        "registry already grounds, so a line declaring it must classify"
    )


@pytest.mark.parametrize(
    "on_date",
    (
        pytest.param(date(2022, 12, 31), id="day-before-rdl-20-2022"),
        pytest.param(date(2024, 10, 1), id="day-after-rdl-4-2024-first-window"),
        pytest.param(date(2025, 6, 1), id="after-withdrawal"),
    ),
)
def test_the_five_percent_rate_stays_refused_outside_its_statutory_span(on_date: date) -> None:
    """The control. Widening must not become date-blindness.

    From 2024-10-01 the statute moved this arm to 7,5 %, and from 2025 the
    measure was withdrawn entirely. A 5 % line on those dates is not lawful, and
    admitting it would be an under-declaration -- the exact error the earlier
    tier-merge work closed.
    """
    assert rate_kinds_for_declared_rate(EUMemberState.ES, _FIVE, on_date) == (), (
        f"5 % was not a lawful Spanish rate on {on_date.isoformat()}; classifying it "
        "would accept a rate the statute did not provide"
    )


def test_the_successor_rate_still_holds_its_own_window() -> None:
    """Second control: adding the earlier window must not disturb the later one."""
    seven_five = Decimal("0.075")
    assert rate_kinds_for_declared_rate(EUMemberState.ES, seven_five, date(2024, 8, 1)) == ()
    assert rate_kinds_for_declared_rate(EUMemberState.ES, seven_five, date(2024, 11, 1)) == (IvaRateKind.REDUCED,)


def test_the_two_food_windows_abut_without_a_gap_or_an_overlap() -> None:
    """The join between the two provisions is where a boundary error would hide.

    RDL 20/2022's window ends 2024-06-30 and RD-ley 4/2024's opens 2024-07-01.
    A gap would silently refuse a lawful line for a day; an overlap on the zero
    tier would red registry load through the no-overlap rule. Assert the join
    directly so neither is discovered by a downstream symptom.
    """
    for on_date in (date(2024, 6, 29), date(2024, 6, 30), date(2024, 7, 1), date(2024, 7, 2)):
        assert rate_kinds_for_declared_rate(EUMemberState.ES, _FIVE, on_date) == (IvaRateKind.REDUCED,), (
            f"the join between the two food-rate provisions drops {on_date.isoformat()}"
        )
