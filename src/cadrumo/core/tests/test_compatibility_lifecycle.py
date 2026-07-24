"""Pure-predicate tests for the regime-switched compatibility policy.

The mechanism is DORMANT today (``COMPATIBILITY_REGIME`` is
``PRE_RELEASE``), yet its post-release teeth are proven now by feeding the
pure predicates synthetic ``RELEASED`` inputs — no global is mutated and no
monkeypatching is used, following the no-patching constraint for their
lineage gates. Every fact the predicates judge on is an
explicit parameter, so a released regime is exercisable without flipping the
one-way constant.
"""

from __future__ import annotations

import pytest

from ..compatibility_lifecycle import (
    CompatibilityRegime,
    expected_floor,
    lineage_obligations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRE = CompatibilityRegime.PRE_RELEASE
_REL = CompatibilityRegime.RELEASED


def test_pre_release_expected_floor_chases_the_current_version() -> None:
    assert expected_floor(_PRE, "bundle", 4, None) == 4


def test_released_expected_floor_is_frozen_not_chasing_current() -> None:
    assert expected_floor(_REL, "bundle", 5, {"bundle": 3}) == 3


def test_released_expected_floor_requires_a_frozen_floor_mapping() -> None:
    with pytest.raises(ValueError, match="RELEASED_FORMAT_FLOORS"):
        expected_floor(_REL, "bundle", 5, None)


def test_pre_release_normal_floor_raise_has_no_obligations() -> None:
    assert (
        lineage_obligations(
            _PRE,
            "bundle",
            current_version=4,
            floor=4,
            released_floors=None,
            has_registered_upgraders_for_gap=False,
            has_fixture_coverage=False,
        )
        == ()
    )


def test_pre_release_floor_above_current_is_incoherent() -> None:
    assert lineage_obligations(
        _PRE,
        "bundle",
        current_version=3,
        floor=4,
        released_floors=None,
        has_registered_upgraders_for_gap=False,
        has_fixture_coverage=False,
    ) == ("floor_exceeds_current",)


def test_released_version_bump_without_upgraders_or_fixtures_violates() -> None:
    obligations = lineage_obligations(
        _REL,
        "bundle",
        current_version=4,
        floor=3,
        released_floors={"bundle": 3},
        has_registered_upgraders_for_gap=False,
        has_fixture_coverage=False,
    )
    assert obligations
    assert "missing_upgraders" in obligations
    assert "missing_fixture_coverage" in obligations
    assert "floor_not_frozen" not in obligations


def test_released_version_bump_with_upgraders_and_fixtures_is_clean() -> None:
    assert (
        lineage_obligations(
            _REL,
            "bundle",
            current_version=4,
            floor=3,
            released_floors={"bundle": 3},
            has_registered_upgraders_for_gap=True,
            has_fixture_coverage=True,
        )
        == ()
    )


def test_released_floor_moved_above_the_frozen_value_is_flagged() -> None:
    obligations = lineage_obligations(
        _REL,
        "bundle",
        current_version=4,
        floor=4,
        released_floors={"bundle": 3},
        has_registered_upgraders_for_gap=True,
        has_fixture_coverage=True,
    )
    assert "floor_not_frozen" in obligations


def test_released_at_frozen_floor_with_no_gap_is_clean() -> None:
    assert (
        lineage_obligations(
            _REL,
            "bundle",
            current_version=3,
            floor=3,
            released_floors={"bundle": 3},
            has_registered_upgraders_for_gap=False,
            has_fixture_coverage=False,
        )
        == ()
    )
