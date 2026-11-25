"""Pure mechanics of dated intersections, independent of published authority."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.amendment_kind_regime import (
    AmendmentKindRestriction,
    AmendmentRegimePolicy,
    resolve_amendment_kind_regime,
)
from .....core.period import Period
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The mechanics are synthetic: three consecutive exercises stand for before, during and after the dated rows.
_YEAR = filing_year_envelope().horizon
_PREVIOUS_YEAR = _YEAR - 1
_NEXT_YEAR = _YEAR + 1


def _policy(*, adjustment: bool = False) -> AmendmentRegimePolicy:
    return AmendmentRegimePolicy(
        rectificativa_effective_from={"130": date(_NEXT_YEAR, 1, 1)},
        pre_rectificativa_kinds=frozenset({"complementaria", "sustitutiva"}),
        post_rectificativa_kinds=frozenset({"rectificativa", "sustitutiva"}),
        kind_restrictions={
            "130": AmendmentKindRestriction(
                effective_from=date(_YEAR, 4, 1),
                permitted_kinds=frozenset({"complementaria", "rectificativa"}),
            ),
        },
        later_period_adjustment_from={"130": date(_YEAR, 7, 1)} if adjustment else {},
    )


@pytest.mark.parametrize(
    ("year", "code", "expected", "effective"),
    [
        (_YEAR, "03", {"complementaria", "sustitutiva"}, False),
        (_YEAR, "1T", {"complementaria", "sustitutiva"}, False),
        (_YEAR, "04", {"complementaria"}, False),
        (_YEAR, "2T", {"complementaria"}, False),
        (_NEXT_YEAR, "1T", {"rectificativa"}, True),
        (_PREVIOUS_YEAR, "1P", {"complementaria", "sustitutiva"}, False),
        (_YEAR, "1P", {"complementaria"}, False),
    ],
)
def test_intersection_preserves_period_end_and_undated_year_boundaries(
    year: int, code: str, expected: set[str], effective: bool
) -> None:
    regime = resolve_amendment_kind_regime("130", Period.from_year_and_code(year, code), policy=_policy())
    assert regime.permitted_kinds == frozenset(expected)
    assert regime.rectificativa_effective is effective


def test_boundary_override_cannot_bypass_the_restriction() -> None:
    regime = resolve_amendment_kind_regime(
        "130",
        Period.from_year_and_code(_YEAR, "2T"),
        policy=_policy(),
        rectificativa_effective_from={"130": date(_YEAR, 1, 1)},
    )
    assert regime.permitted_kinds == frozenset({"rectificativa"})


def test_disjoint_restriction_grants_no_procedure() -> None:
    policy = AmendmentRegimePolicy(
        rectificativa_effective_from={},
        pre_rectificativa_kinds=frozenset({"complementaria"}),
        post_rectificativa_kinds=frozenset({"rectificativa"}),
        kind_restrictions={
            "131": AmendmentKindRestriction(date(_YEAR, 1, 1), frozenset({"rectificativa"})),
        },
    )
    regime = resolve_amendment_kind_regime("131", Period.from_year_and_code(_YEAR, "1T"), policy=policy)
    assert regime.permitted_kinds == frozenset()


def test_later_period_adjustment_takes_precedence_over_restrictions() -> None:
    regime = resolve_amendment_kind_regime(
        "130", Period.from_year_and_code(_NEXT_YEAR, "1T"), policy=_policy(adjustment=True)
    )
    assert regime.permitted_kinds == frozenset()
    assert regime.rectificativa_effective is False


def test_a_restriction_does_not_change_another_modelo() -> None:
    regime = resolve_amendment_kind_regime("349", Period.from_year_and_code(_NEXT_YEAR, "1T"), policy=_policy())
    assert regime.permitted_kinds == frozenset({"complementaria", "sustitutiva"})
