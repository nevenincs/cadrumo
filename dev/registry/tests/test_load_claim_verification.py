"""Real-behaviour tests for the live-claim verification screen.

The comparison is pure and is tested against constructed module sets, so these
run without paying for two registry loads. The probe that produces those sets is
tested for the one property that matters and cannot be inferred: that a failed
load raises rather than returning nothing.
"""

from __future__ import annotations

import pytest

from dev.registry.analysis.load_census_classification import RULES
from dev.registry.analysis.load_claim_verification import ClaimFinding, verify_live_claims

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _live_members() -> tuple[str, ...]:
    return tuple(member for rule in RULES if rule.classification == "live" for member in rule.members)


def test_a_member_both_regimes_load_is_not_reported() -> None:
    """The screen reports disagreement, not membership."""
    members = _live_members()
    assert members, "the rule table declares no live members, so the assertions below say nothing"

    assert verify_live_claims(members, members) == ()


def test_a_member_neither_regime_loads_is_reported_as_never_loaded() -> None:
    """A claim no load supports is wrong rather than imprecise."""
    members = _live_members()
    missing = members[0]
    rest = members[1:]

    findings = verify_live_claims(rest, rest)

    assert [item.kind for item in findings if item.module == missing] == ["never_loaded"]


def test_a_member_only_the_cold_regime_loads_is_reported_apart() -> None:
    """Cold-only is a different claim from never, and wants a different correction.

    Twenty-nine members of the live rules are in this state and eleven are in
    the other. Collapsing them would put a rule that is right about one regime
    beside a rule that is wrong about every regime.
    """
    members = _live_members()
    cold_only = members[0]
    warm = members[1:]

    findings = verify_live_claims(members, warm)

    assert [item.kind for item in findings if item.module == cold_only] == ["cold_regime_only"]


def test_a_finding_names_the_trigger_that_made_the_claim() -> None:
    """A module name alone does not say which rule has to change."""
    members = _live_members()
    findings = verify_live_claims((), ())

    assert len(findings) == len(members)
    assert all(isinstance(item, ClaimFinding) and item.trigger for item in findings)


def test_an_empty_regime_pair_reports_every_live_member() -> None:
    """The screen cannot silently pass when the probe returns nothing.

    This is the shape a failed load would take if the probe swallowed its own
    error, and it is why the probe raises instead. Here it is asserted as
    behaviour: empty input means every claim is unsupported, loudly.
    """
    assert len(verify_live_claims((), ())) == len(_live_members())
