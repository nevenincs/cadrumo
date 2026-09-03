"""Real-behaviour tests for the condition-overlap report.

The report exists to find one screen condition saying what another already says.
Its two risks are opposite and both are held here: reporting a relationship that
is not there - which the empty-population trap produces in bulk - and losing the
distinction between an identity and a containment, which is the difference
between a duplicate and a special case.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis.condition_overlap import (
    RELATIONS,
    ConditionRelation,
    condition_populations,
    overlapping_conditions,
)
from ..analysis.corpus import bundled_modelo_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_A = ("303", "2025")
_B = ("200", "2024")
_C = ("165", "2023-2025")


def test_an_identical_population_is_reported_as_identical() -> None:
    """The relation the report was built to find, from input written here.

    The live corpus reports none, because the one real instance was found and
    retired by hand before this existed. A report whose strongest relation has
    no live instance and no constructed proof is one that could stop working
    without anybody noticing.
    """
    reported = overlapping_conditions({"screen_a.kind": frozenset({_A, _B}), "screen_b.kind": frozenset({_A, _B})})
    assert len(reported) == 1
    assert reported[0].relation == "identical"
    assert reported[0].shared == 2
    assert reported[0].left_size == reported[0].right_size == 2


def test_a_proper_subset_is_reported_as_contained_with_the_smaller_side_left() -> None:
    """Direction is part of the finding: the special case is named first."""
    reported = overlapping_conditions({"wide.kind": frozenset({_A, _B, _C}), "narrow.kind": frozenset({_A})})
    assert len(reported) == 1
    assert reported[0].relation == "contained"
    assert reported[0].left == "narrow.kind"
    assert reported[0].right == "wide.kind"
    assert (reported[0].left_size, reported[0].right_size) == (1, 3)


def test_a_partial_overlap_is_not_reported() -> None:
    """Sharing some revisions is the normal state of the corpus, not a finding.

    A few modelos carry most of the defects, so nearly every pair of conditions
    intersects. Reporting that would bury the two relations above in rows that
    mean nothing.
    """
    assert overlapping_conditions({"a.k": frozenset({_A, _B}), "b.k": frozenset({_B, _C})}) == ()


def test_disjoint_populations_are_not_reported() -> None:
    """Two conditions naming different revisions have no relationship to report."""
    assert overlapping_conditions({"a.k": frozenset({_A}), "b.k": frozenset({_B})}) == ()


def test_an_unordered_pair_yields_at_most_one_row() -> None:
    """``identical`` is symmetric and would otherwise be reported twice."""
    populations = {name: frozenset({_A, _B}) for name in ("a.k", "b.k", "c.k")}
    reported = overlapping_conditions(populations)
    pairs = {frozenset((item.left, item.right)) for item in reported}
    assert len(reported) == len(pairs) == 3


def test_density_separates_a_real_containment_from_a_large_container() -> None:
    """Containment in a big population is nearly free and must read as such.

    The provenance condition names 88 of 128 revisions, so a condition firing
    anywhere is likely inside it. That is a fact about its size, and the density
    is what lets a reader see the difference between it and the two-thirds
    containment that turned out to be a genuine special case.
    """
    real = ConditionRelation(left="a", right="b", relation="contained", shared=6, left_size=6, right_size=9)
    incidental = ConditionRelation(left="a", right="c", relation="contained", shared=6, left_size=6, right_size=88)
    assert real.density > 0.6
    assert incidental.density < 0.1
    assert (
        ConditionRelation(left="a", right="b", relation="identical", shared=0, left_size=0, right_size=0).density == 0.0
    )


def test_empty_populations_are_excluded_rather_than_compared() -> None:
    """Two conditions with nothing to compare are not thereby identical.

    Several screens report per modelo or per design and carry no revision, so
    their populations are empty. Comparing them would make every pair of them
    identical - the report inventing in bulk the exact defect it exists to find.
    """
    authority = bundled_authority()
    populations = condition_populations(authority, bundled_modelo_ids())
    assert populations, "no condition had a population, so this proves nothing"
    assert all(units for units in populations.values())
    # And the walk that builds them drops the empty ones rather than keeping a
    # key with an empty set, which would reintroduce the trap one layer down.
    assert not any(len(units) == 0 for units in populations.values())


def test_census_and_derived_screens_are_excluded_from_the_comparison() -> None:
    """One is too large to be informative, the other identical by construction.

    A census's population is every revision with fields, so it would contain
    almost every condition. A derived screen re-describes its source's findings,
    so reporting that pair would report a declared relationship as a discovery.
    """
    from ..analysis.screens import CORPUS_SCREENS, SCREENS

    excluded = {
        entry.name
        for entry in (*SCREENS, *CORPUS_SCREENS)
        if entry.entry_returns == "census" or entry.derives_from is not None
    }
    assert excluded, "no screen is census or derived, so this proves nothing"
    named = {key.split(".", 1)[0] for key in condition_populations(bundled_authority(), bundled_modelo_ids())}
    assert not (named & excluded)


def test_every_live_row_really_holds_the_relation_it_claims() -> None:
    """The report is checked against the populations it drew the rows from.

    Set relations are cheap to assert and easy to invert, and an inverted
    containment would name the wrong side as the special case - which is the
    only thing the row is for.
    """
    populations = condition_populations(bundled_authority(), bundled_modelo_ids())
    reported = overlapping_conditions(populations)
    assert reported, "no pair coincided, so this proves nothing"
    for item in reported:
        assert item.relation in RELATIONS
        left, right = populations[item.left], populations[item.right]
        if item.relation == "identical":
            assert left == right
        else:
            assert left < right, f"{item.left} is not a proper subset of {item.right}"
        assert item.shared == min(len(left), len(right))
        assert 0.0 < item.density <= 1.0


def test_the_live_report_is_ordered_with_the_densest_relationship_first() -> None:
    """The ordering is the report's whole output, so it is asserted."""
    reported = overlapping_conditions(condition_populations(bundled_authority(), bundled_modelo_ids()))
    assert reported, "no pair coincided, so this proves nothing"
    densities = [item.density for item in reported]
    assert densities == sorted(densities, reverse=True)
