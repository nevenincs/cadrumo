"""The standard rates must keep classifying when a temporary rate joins their tier.

Spain's 2024 anti-inflation measures put a SECOND rate on a tier that already had
one: certain foodstuffs moved to 2 % while everything else stayed at 4 %, and
seed oils moved to 7,5 % while everything else stayed at 10 % (RDL 4/2024 art. 1,
BOE-A-2024-12944, grounded at ``real-decreto-ley-4-2024:art-1``).

``lookup_rate`` returns the FIRST record whose tier matches and whose window
covers the date, so it can hold only one rate per tier per moment. A 2 %
super-reducido record for Oct-Dec 2024 overlaps the existing 4 % record for all
of 2024, and first-match-wins would then make one of the two unreachable.

The registry already refuses that, loudly: the loader raises
``IvaRateOverlapError`` naming both windows, so the whole rate table fails to
load rather than silently resolving a 4 % November sale to 2 % and rejecting it.
Measured by inserting the naive record and reading the failure, not assumed --
the first reading of this looked like a silent-regression hazard and it is not
one.

So these tests are defence in depth over a gate that already holds, not the
only warning. What they add is the direction the loader cannot express: that
the ordinary rates must keep CLASSIFYING, which is a property of
``iva_rate_kind_for`` rather than of the table's shape. Whoever settles the
concurrency question will change how rates are represented, and the loader's
overlap rule may move or go with it; these assertions outlive that, because
they name the outcome rather than the mechanism.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..iva_ledger import iva_rate_kind_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Inside the 1 Oct - 31 Dec 2024 window, when the temporary rates were in force
# alongside the standard ones.
_IN_WINDOW = date(2024, 11, 15)
# Inside the 1 Jul - 30 Sep 2024 window, the measure's other step.
_EARLIER_WINDOW = date(2024, 8, 1)


@pytest.mark.parametrize("on_date", [_IN_WINDOW, _EARLIER_WINDOW])
@pytest.mark.parametrize(
    ("rate", "expected_tier"),
    [
        (Decimal("0.21"), "general"),
        (Decimal("0.10"), "reduced"),
        (Decimal("0.04"), "super_reduced"),
        (Decimal("0"), "zero"),
    ],
)
def test_a_standard_rate_still_classifies_inside_the_temporary_windows(
    on_date: date,
    rate: Decimal,
    expected_tier: str,
) -> None:
    """The ordinary rates are what most transactions carry, even in these windows.

    The temporary measure was goods-specific: it moved certain foodstuffs and
    oils, and left every other supply on its usual rate. So a November 2024 sale
    at 4 % is the common case, not an edge case, and it must not become
    unclassifiable as a side effect of teaching the table about 2 %.
    """
    resolved = iva_rate_kind_for(rate, on_date=on_date)

    assert resolved is not None, f"{rate} on {on_date} must classify -- it is an ordinary Spanish rate"
    assert resolved.value == expected_tier


@pytest.mark.parametrize(
    ("rate", "expected_tier"),
    [(Decimal("0.02"), "super_reduced"), (Decimal("0.075"), "reduced")],
)
def test_the_temporary_rates_now_classify_in_their_own_window(rate: Decimal, expected_tier: str) -> None:
    """The gap closed: these rates were legally correct and are now representable.

    This assertion is the INVERTED form of the one this module shipped with,
    which asserted the same rates resolved to ``None``. Flipping it is the
    deliberate signal that the concurrency question was settled -- they coexist
    with their tier's ordinary rate rather than replacing it -- rather than a
    test quietly relaxed to match new behaviour.
    """
    resolved = iva_rate_kind_for(rate, on_date=_IN_WINDOW)

    assert resolved is not None
    assert resolved.value == expected_tier


@pytest.mark.parametrize(
    ("rate", "on_date"),
    [
        # The Oct-Dec step, asked inside the Jul-Sep window.
        (Decimal("0.02"), _EARLIER_WINDOW),
        # Both steps, asked after the measure expired on 2025-01-01.
        (Decimal("0.02"), date(2025, 6, 1)),
        (Decimal("0.075"), date(2025, 6, 1)),
        (Decimal("0.05"), date(2025, 6, 1)),
    ],
)
def test_a_temporary_rate_does_not_leak_outside_its_window(rate: Decimal, on_date: date) -> None:
    """Each step is confined to the dates its article fixes.

    Without this the records could be dated wrongly -- or open-ended -- and every
    test above would still pass, because they only ever ask inside the windows.
    A 2 % sale dated June 2025 is not a legitimate Spanish rate and must refuse.
    """
    assert iva_rate_kind_for(rate, on_date=on_date) is None


def test_zero_is_already_representable_so_the_gap_is_three_rates_not_four() -> None:
    """The 0 % arm of the measure needs no new record.

    ``ZERO`` is a distinct tier with its own record, so a 0 % foodstuff sale in
    2024 classifies correctly today. Stating it here keeps a later reader from
    scoping the remediation one rate wider than it is.
    """
    assert iva_rate_kind_for(Decimal("0"), on_date=_IN_WINDOW) is not None
