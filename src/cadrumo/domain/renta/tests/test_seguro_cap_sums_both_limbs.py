"""The seguro cap is a SUM over two populations, not one amount times one count.

LIRPF art. 30.2.5.a allows 500 euros per insured person *o de 1.500 euros por cada una
de ellas con discapacidad*. Both limbs apply in the same return, to their own share of
the persons, so the lawful cap is ``500 x general + 1.500 x discapacidad``.

The previous shape multiplied one amount by one count, which applies the LOWER limb to
everybody. For a filer insuring themselves, a spouse and a child where one of the three
has discapacidad, that is 1.500 against a lawful 2.500 -- a thousand euros of allowance
lost, in the over-payment direction, landing on the population the higher limb exists
to protect.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...categories.registry import load_category_profiles
from ...categories.spending_category import SpendingCategory
from ..errors import RentaValidationError
from ..ledger_expenses import RentaDeductibilityContext, _resolve_statutory_cap

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _rule():
    return load_category_profiles()[SpendingCategory.SEGUROS_SALUD_AUTONOMO].proportionality


def _cap(**counts: int) -> Decimal | None:
    return _resolve_statutory_cap(
        rule=_rule(),
        context=RentaDeductibilityContext(
            profile_year=2025,
            statutory_cap_variant_person_counts=counts,
        ),
    )


@pytest.mark.parametrize(
    ("counts", "expected", "note"),
    [
        pytest.param({"general": 1}, Decimal("500"), "contribuyente alone", id="one-ordinary-person"),
        pytest.param({"general": 3}, Decimal("1500"), "three ordinary persons", id="three-ordinary"),
        pytest.param({"discapacidad": 1}, Decimal("1500"), "one person with discapacidad", id="one-disabled"),
        pytest.param(
            {"general": 2, "discapacidad": 1},
            Decimal("2500"),
            "the mixed household the old shape got wrong",
            id="mixed-household",
        ),
    ],
)
def test_the_cap_sums_each_limb_over_its_own_population(
    counts: dict[str, int],
    expected: Decimal,
    note: str,
) -> None:
    assert _cap(**counts) == expected, note


def test_the_mixed_household_is_a_thousand_euros_above_the_old_flat_shape() -> None:
    """The defect quantified, so a regression to one-amount-times-one-count is visible.

    Three insured persons, one with discapacidad. The retired shape computed
    ``500 x 3``; the article allows ``500 x 2 + 1.500 x 1``.
    """
    lawful = _cap(general=2, discapacidad=1)
    retired_flat_shape = Decimal("500") * 3

    assert lawful is not None
    assert lawful - retired_flat_shape == Decimal("1000")


def test_uncounted_populations_fall_back_to_the_ordinary_limb_not_to_zero() -> None:
    """Absence of counts is unknown, and the ordinary limit is what applies then.

    The higher limb requires a condition to be met; with nothing declared about it,
    the article grants the ordinary limit. Two wrong answers are avoided here. Zero
    would cap the deduction at nothing -- the same silent detriment in another
    disguise. The HIGHER limb would hand out an allowance nobody proved.

    This also keeps the caller that knows nothing exactly where it was before the
    second limb existed, so widening the rule regressed no one.
    """
    assert _resolve_statutory_cap(
        rule=_rule(),
        context=RentaDeductibilityContext(profile_year=2025, statutory_cap_person_count=1),
    ) == Decimal("500")

    assert _resolve_statutory_cap(
        rule=_rule(),
        context=RentaDeductibilityContext(profile_year=2025, statutory_cap_person_count=3),
    ) == Decimal("1500")


def test_a_count_naming_a_variant_the_rule_does_not_declare_is_refused() -> None:
    """DISCRIMINATING: a typo'd variant id would otherwise be silently counted as zero."""
    with pytest.raises(RentaValidationError, match="variants the rule does not declare"):
        _resolve_statutory_cap(
            rule=_rule(),
            context=RentaDeductibilityContext(
                profile_year=2025,
                statutory_cap_variant_person_counts={"discapacidadd": 1},
            ),
        )
