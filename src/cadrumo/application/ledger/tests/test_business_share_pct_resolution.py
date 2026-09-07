"""Which business share a row is stamped with is decided once, and says why.

The legal arithmetic — the censo afectación ratio times the category's
statutory multiplier — was already here, in ``censo_business_pct_for``. The
PRECEDENCE around it was not: a chain of early returns at a command boundary,
so a second frontend stamping a share had to reproduce four rules and would
most plausibly reproduce none of them.

It also returned one ``None`` for four different situations. An operator whose
row got no share could not tell whether they had set no category, applied no
censo, or chosen a category that is never apportioned — three different next
actions, and only two of them are anything they can do. The outcome now names
which, which is the half a caller cannot recompute from a bare ``None``.

Everything here drives the real resolver with real categories and the real
year-versioned registry; nothing is stubbed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.categories.spending_category import HOME_OFFICE_FAMILIES, SpendingCategory, family_for
from ..ratios import (
    BusinessSharePctOutcome,
    BusinessSharePctResolution,
    resolve_business_share_pct,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025
_A_RATIO = Decimal("0.25")


def _home_office_category() -> SpendingCategory:
    """One category the censo actually apportions, taken from the real families."""
    return next(category for category in SpendingCategory if family_for(category) in HOME_OFFICE_FAMILIES)


def _non_apportioned_category() -> SpendingCategory:
    """One category outside those families, so the censo never applies to it."""
    return next(category for category in SpendingCategory if family_for(category) not in HOME_OFFICE_FAMILIES)


def test_an_operator_statement_outranks_the_censo() -> None:
    """The specific claim beats the default, and is not silently re-derived.

    Parametrised nowhere on purpose: this must hold even for a category the
    censo WOULD have apportioned, which is exactly the case where a
    re-derivation would look plausible.
    """
    resolution = resolve_business_share_pct(
        operator_supplied=Decimal("0.60"),
        category=_home_office_category(),
        censo_afectacion_ratio=_A_RATIO,
        year=_YEAR,
    )

    assert resolution.outcome is BusinessSharePctOutcome.STATED
    assert resolution.business_pct == Decimal("0.60")


def test_a_home_office_category_with_a_censo_derives_a_share() -> None:
    """The positive control: the resolver produces a share, not only refusals.

    Without it every "no share" outcome below would be satisfied by a resolver
    that never derives anything, which is the one behaviour that would silently
    stop stamping.
    """
    resolution = resolve_business_share_pct(
        operator_supplied=None,
        category=_home_office_category(),
        censo_afectacion_ratio=_A_RATIO,
        year=_YEAR,
    )

    assert resolution.outcome is BusinessSharePctOutcome.DERIVED_FROM_CENSO
    assert resolution.business_pct is not None


def test_a_row_with_no_category_reports_the_category_not_the_censo() -> None:
    """Order is the rule: absence of a category is asked before absence of a censo.

    Both are missing here. Reporting the censo would send the operator to
    apply one and watch the row still take no share, because a row with
    nothing to apportion takes none either way.
    """
    resolution = resolve_business_share_pct(
        operator_supplied=None,
        category=None,
        censo_afectacion_ratio=None,
        year=_YEAR,
    )

    assert resolution.outcome is BusinessSharePctOutcome.NO_CATEGORY
    assert resolution.business_pct is None


def test_an_unapplied_censo_is_reported_as_the_missing_fact() -> None:
    """The one outcome that names something the operator can go and fix."""
    resolution = resolve_business_share_pct(
        operator_supplied=None,
        category=_home_office_category(),
        censo_afectacion_ratio=None,
        year=_YEAR,
    )

    assert resolution.outcome is BusinessSharePctOutcome.NO_CENSO_APPLIED
    assert resolution.business_pct is None


def test_a_category_outside_the_home_office_families_is_never_apportioned() -> None:
    """Distinct from an unapplied censo, and the distinction is actionable.

    A censo IS applied here. Collapsing this into ``NO_CENSO_APPLIED`` would
    tell an operator to apply one they already have; collapsing it into a bare
    ``None`` told them nothing at all.
    """
    resolution = resolve_business_share_pct(
        operator_supplied=None,
        category=_non_apportioned_category(),
        censo_afectacion_ratio=_A_RATIO,
        year=_YEAR,
    )

    assert resolution.outcome is BusinessSharePctOutcome.CATEGORY_NOT_APPORTIONED
    assert resolution.business_pct is None


def test_every_outcome_the_enum_declares_is_reachable() -> None:
    """A member no input produces is a state a consumer handles for nothing.

    Driven across the real input space rather than asserted from a list, so a
    member added without a path here shows as a gap instead of as unreachable
    code nobody notices.
    """
    home_office = _home_office_category()
    conditions = [
        (Decimal("0.6"), home_office, _A_RATIO),
        (None, home_office, _A_RATIO),
        (None, None, None),
        (None, home_office, None),
        (None, _non_apportioned_category(), _A_RATIO),
    ]

    produced = {
        resolve_business_share_pct(
            operator_supplied=supplied,
            category=category,
            censo_afectacion_ratio=ratio,
            year=_YEAR,
        ).outcome
        for supplied, category, ratio in conditions
    }

    assert produced == set(BusinessSharePctOutcome)


@pytest.mark.parametrize(
    "outcome",
    [
        BusinessSharePctOutcome.NO_CATEGORY,
        BusinessSharePctOutcome.NO_CENSO_APPLIED,
        BusinessSharePctOutcome.CATEGORY_NOT_APPORTIONED,
    ],
    ids=lambda outcome: outcome.value,
)
def test_an_outcome_that_derived_nothing_may_not_carry_a_share(
    outcome: BusinessSharePctOutcome,
) -> None:
    """A number beside "no share" invites a caller to stamp a proportion nothing derived."""
    with pytest.raises(ValidationError, match="disagrees with its own outcome"):
        BusinessSharePctResolution(outcome=outcome, business_pct=_A_RATIO)


@pytest.mark.parametrize(
    "outcome",
    [BusinessSharePctOutcome.STATED, BusinessSharePctOutcome.DERIVED_FROM_CENSO],
    ids=lambda outcome: outcome.value,
)
def test_an_outcome_that_derived_a_share_must_carry_it(
    outcome: BusinessSharePctOutcome,
) -> None:
    """The other direction, so the invariant reads as an agreement between the fields.

    Paired with the test above rather than written alone: one of them on its
    own states a ban, and the two together state the rule.
    """
    with pytest.raises(ValidationError, match="disagrees with its own outcome"):
        BusinessSharePctResolution(outcome=outcome)
