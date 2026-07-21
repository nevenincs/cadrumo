"""Structural gate for the concurrent packaging-lane campaign driver."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.packaging.campaign import _LANES, _PROFILES

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_JUSTFILE = Path(__file__).resolve().parents[3] / "justfile"


def test_profiles_reference_registered_lanes_only() -> None:
    """Every profile entry resolves to a registered lane."""
    for profile, lane_names in _PROFILES.items():
        unknown = set(lane_names) - set(_LANES)
        assert not unknown, f"profile {profile} references unknown lanes: {sorted(unknown)}"
        assert len(lane_names) == len(set(lane_names)), f"profile {profile} repeats a lane"


def test_quick_profile_is_exactly_the_single_core_probe() -> None:
    """The per-push quick profile proves one install surface and nothing else.

    The quick lane exists to keep the per-push wall inside the ten-minute
    budget; growing it must be a conscious decision against that budget, so
    the set is pinned to exactly the core probe.
    """
    assert _PROFILES["quick"] == ("core",)


def test_portable_profile_matches_the_host_portable_aggregate() -> None:
    """The portable profile carries the host-portable lane set, no host-specific lanes."""
    assert set(_PROFILES["portable"]) == {"core", "pip-core", "sdist-core", "extras", "split", "browser"}
    assert "docker-core" not in _PROFILES["portable"]
    assert "browser-linux" not in _PROFILES["portable"]


def test_ci_profile_is_the_ubuntu_superset() -> None:
    """The ci profile covers every portable proof plus the Linux-only lanes."""
    ci = set(_PROFILES["ci"])
    assert {"dev", "core", "pip-core", "sdist-core", "extras", "split"} <= ci
    assert "browser-linux" in ci
    assert {"docker-core", "docker-browser"} <= ci
    # The portable browser variant is replaced by the --with-deps variant.
    assert "browser" not in ci


def test_lane_commands_match_the_per_lane_just_recipes() -> None:
    """Each lane's module invocation stays in lock-step with its justfile recipe."""
    justfile = _JUSTFILE.read_text(encoding="utf-8")
    for lane in _LANES.values():
        assert f"dev.packaging.{lane.module.rsplit('.', 1)[-1]}" in justfile, lane.name
        command = lane.command()
        assert command[1:3] == ["-m", lane.module]
        if lane.takes_cohort:
            assert "--cohort-dir" in command
        for extra in lane.extra_args:
            assert extra in command


def test_aggregates_route_through_the_campaign_driver() -> None:
    """The two workflow aggregates invoke the driver with their profiles."""
    justfile = _JUSTFILE.read_text(encoding="utf-8")
    assert "dev.packaging.campaign --profile portable" in justfile
    assert "dev.packaging.campaign --profile ci" in justfile
    assert "dev.packaging.campaign --profile quick" in justfile
