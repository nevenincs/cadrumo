"""Rule lookup by anchor is indexed, and the index answers what the scan did.

The renderer asks which rule covers a field's anchor once per FIELD. A scan
answered it by comparing that anchor against every anchor of every rule, and
anchors are frozen pydantic models whose equality walks their fields: one
modelo's export tree issued 32.5 million ``BaseModel.__eq__`` calls, 41% of its
runtime. Anchors are hashable, so the answer is one dict lookup.

An index that returned a DIFFERENT rule from the scan would be a correctness
regression the timing improvement would hide, so these gates pin the
equivalence and the first-wins tie-break, not just the speed-up.
"""

from __future__ import annotations

import pytest

from ..render_profile import RenderProfile, RenderProfileAnchor, SingletonNumericRule, Width17MembershipRule
from .test_render_profile import _anchor, _design_identity, _profile, _singleton, _width_rule

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _scanned_width_rule(profile: RenderProfile, anchor: RenderProfileAnchor) -> Width17MembershipRule | None:
    """The lookup the index replaced, kept here as the independent oracle."""
    return next((rule for rule in profile.width_17_rules if anchor in rule.anchors), None)


def _scanned_singleton_rule(profile: RenderProfile, anchor: RenderProfileAnchor) -> SingletonNumericRule | None:
    return next((rule for rule in profile.singleton_rules if rule.anchor == anchor), None)


@pytest.mark.parametrize("row", [10, 11, 12, 13])
def test_the_index_selects_exactly_what_the_scan_selected(row: int) -> None:
    """Covered anchors and an uncovered one both agree with the oracle."""
    profile = _profile()
    anchor = _anchor(row)

    assert profile.width_17_rule_by_anchor.get(anchor) == _scanned_width_rule(profile, anchor)
    assert profile.singleton_rule_by_anchor.get(anchor) == _scanned_singleton_rule(profile, anchor)


def test_an_uncovered_anchor_resolves_to_nothing() -> None:
    profile = _profile()

    assert profile.width_17_rule_by_anchor.get(_anchor(99)) is None
    assert profile.singleton_rule_by_anchor.get(_anchor(99)) is None


def test_two_rules_claiming_one_anchor_keep_the_first() -> None:
    """``next()`` returned the first match, so a later claimant was unreachable.

    The index must not silently promote it, which a last-wins fill would do.
    """
    shared = _anchor(10)
    first = _width_rule("Num", shared)
    second = _width_rule("N", shared)
    profile = RenderProfile(
        schema_version=1,
        design_identity=_design_identity(),
        fragment_ids=("width-17",),
        width_17_rules=(first, second),
        singleton_rules=(),
    )

    assert profile.width_17_rule_by_anchor[shared] == first
    assert profile.width_17_rule_by_anchor[shared] == _scanned_width_rule(profile, shared)


def test_a_rule_covering_several_anchors_is_reachable_from_each() -> None:
    """A membership rule carries a tuple of anchors; every one must index to it."""
    covered = (_anchor(10), _anchor(11), _anchor(12))
    rule = _width_rule("Num", covered[0]).model_copy(update={"anchors": covered})
    profile = RenderProfile(
        schema_version=1,
        design_identity=_design_identity(),
        fragment_ids=("width-17",),
        width_17_rules=(rule,),
        singleton_rules=(),
    )

    assert {anchor: profile.width_17_rule_by_anchor[anchor] for anchor in covered} == dict.fromkeys(covered, rule)


def test_the_index_is_built_once_per_profile() -> None:
    """Repeated lookups must not rebuild it; that would only move the cost."""
    profile = _profile()

    first = profile.width_17_rule_by_anchor
    second = profile.width_17_rule_by_anchor

    assert first is second, "the index must be cached on the profile, not recomputed per lookup"
    assert profile.singleton_rule_by_anchor is profile.singleton_rule_by_anchor


def test_two_profiles_index_separately() -> None:
    """The cache lives on the instance, so profiles cannot share one answer."""
    one = _profile()
    other = RenderProfile(
        schema_version=1,
        design_identity=_design_identity(),
        fragment_ids=("smaller-fields",),
        width_17_rules=(),
        singleton_rules=(_singleton(_anchor(20)),),
    )

    assert one.singleton_rule_by_anchor.keys() != other.singleton_rule_by_anchor.keys()
    assert other.width_17_rule_by_anchor == {}
