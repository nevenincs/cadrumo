"""A domestic category is derived from the rate, but only once domesticity is established.

`iva_category` is load-bearing on the income path and no CLI surface could set a
domestic one, so every domestic invoice arrived ungrounded. The closed
rate-to-category mapping can supply it -- but that mapping is DOMESTIC-ONLY, so
deriving from the rate slot alone would stamp a domestic category on an export
or an intra-community supply.

A wrong category is worse than an absent one, because the absent one is refused
downstream and the wrong one is believed. Everything here therefore turns on the
order of the two questions: domesticity first, on `counterparty_country`, and
only then the tier.

`counterparty_country` is the discriminator because production already decides
this fact that way for Modelo 303 settlement. Adopting the incumbent leaves ONE
discriminator; either alternative would create a second that has to agree with
it, which is how two answers to one question start diverging.

THE SILENCES ARE THE POINT. Each returns None deliberately, and each is asserted
below, because a later reader will find three early returns and be tempted to
"complete" them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.iva.schema import IvaCategory
from ..creation_wizard import _derived_domestic_category

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DAY = date(2025, 6, 15)


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (Decimal("21"), IvaCategory.DOMESTIC_GENERAL),
        (Decimal("10"), IvaCategory.DOMESTIC_REDUCED),
        (Decimal("4"), IvaCategory.DOMESTIC_SUPER_REDUCED),
    ],
)
def test_a_domestic_rate_derives_its_category(rate: Decimal, expected: IvaCategory) -> None:
    """Each in-force tier reaches its own category, so the income path is grounded."""
    assert _derived_domestic_category(country_code="ES", iva_rate=rate, on_date=_DAY) is expected


def test_a_non_domestic_counterparty_derives_nothing() -> None:
    """The guard that stops an export being labelled a domestic supply.

    21 % is a real Spanish rate and the mapping would happily answer for it. The
    country is what refuses, and it must refuse BEFORE the rate is consulted --
    this is the single assertion standing between a French counterparty and a
    DOMESTIC_GENERAL_21 stamp on an operation that is not domestic at all.
    """
    assert _derived_domestic_category(country_code="FR", iva_rate=Decimal("21"), on_date=_DAY) is None


def test_an_unstated_rate_derives_nothing() -> None:
    """No rate, no tier, no category. Absence is not a tier of its own."""
    assert _derived_domestic_category(country_code="ES", iva_rate=None, on_date=_DAY) is None


def test_a_rate_outside_its_force_window_derives_nothing() -> None:
    """The silence most likely to be mistaken for an unhandled case.

    5 % was a real Spanish rate inside the 2023 to September 2024 food window
    and is not one in June 2025, so it resolves to no tier at all. Deriving
    anyway would ground an invoice on a rate that did not exist on its date.

    A rate resolving to MORE than one tier is refused by the same condition, for
    the same reason: collapsing an ambiguity by taking the first answer is a
    guess wearing a derivation's clothes. No rate is currently ambiguous, so
    that half is defensive rather than exercised, and saying so is more honest
    than implying the branch is covered.
    """
    assert _derived_domestic_category(country_code="ES", iva_rate=Decimal("5"), on_date=_DAY) is None


def test_the_same_rate_derives_again_once_its_window_reopens() -> None:
    """Anti-vacuity for the window check: 5 % is not simply unknown to the table.

    Without this, the refusal above would pass just as well against a derivation
    that had never heard of 5 % at all, and the test would be asserting
    ignorance rather than a date judgement.
    """
    inside_the_window = date(2024, 3, 1)

    assert (
        _derived_domestic_category(country_code="ES", iva_rate=Decimal("5"), on_date=inside_the_window)
        is IvaCategory.DOMESTIC_REDUCED
    )
