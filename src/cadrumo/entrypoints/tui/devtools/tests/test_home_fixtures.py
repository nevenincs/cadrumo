"""Focused contracts for deterministic Home candidate projections."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....application.overview.home import HomeAvailability, HomeDeclarationState, HomeSessionPosture
from ..home_fixtures import (
    HOME_FIXTURE_SCENARIOS,
    HomeFixtureScenario,
    build_home_projection_fixture,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_closed_mapping_covers_every_scenario() -> None:
    assert frozenset(HOME_FIXTURE_SCENARIOS) == frozenset(HomeFixtureScenario)
    assert all(callable(builder) for builder in HOME_FIXTURE_SCENARIOS.values())


@pytest.mark.parametrize("scenario", list(HomeFixtureScenario))
def test_every_fixture_is_fresh_frozen_and_valid(scenario: HomeFixtureScenario) -> None:
    first = build_home_projection_fixture(scenario)
    second = build_home_projection_fixture(scenario.value)

    assert first == second
    assert first is not second
    assert first.account is not second.account
    with pytest.raises(ValidationError):
        first.generated_at = second.generated_at


def test_ready_empty_and_blocked_projections_keep_distinct_typed_signals() -> None:
    ready = build_home_projection_fixture(HomeFixtureScenario.READY)
    empty = build_home_projection_fixture(HomeFixtureScenario.EMPTY)
    blocked = build_home_projection_fixture(HomeFixtureScenario.BLOCKED)

    assert ready.actions and ready.declarations and ready.ledger is not None
    assert empty.actions == () and empty.declarations == ()
    assert empty.ledger is not None and empty.ledger.entries == 0
    assert blocked.actions[0].reason_code == "fixture.blocked"
    assert blocked.declarations[0].state is HomeDeclarationState.NEEDS_REVIEW
    assert blocked.ledger is not None and blocked.ledger.requiring_review == 3


@pytest.mark.parametrize(
    ("scenario", "availability", "posture"),
    (
        (HomeFixtureScenario.LOCKED, HomeAvailability.LOCKED, HomeSessionPosture.LOCKED),
        (HomeFixtureScenario.STALE, HomeAvailability.STALE, HomeSessionPosture.ACTIVE),
        (HomeFixtureScenario.NEVER_CAPTURED, HomeAvailability.NEVER_CAPTURED, HomeSessionPosture.NO_PROFILE),
        (HomeFixtureScenario.UNAVAILABLE, HomeAvailability.UNAVAILABLE, HomeSessionPosture.ACTIVE),
    ),
)
def test_non_ready_scenarios_preserve_explicit_zone_and_session_states(
    scenario: HomeFixtureScenario,
    availability: HomeAvailability,
    posture: HomeSessionPosture,
) -> None:
    projection = build_home_projection_fixture(scenario)

    assert projection.actions_state.availability is availability
    assert projection.declarations_state.availability is availability
    assert projection.ledger_state.availability is availability
    assert projection.account.posture is posture
    assert projection.actions == ()
    assert projection.declarations == ()
    assert projection.ledger is None
    assert projection.messages_requiring_attention is None


def test_invalid_scenario_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown Home fixture scenario"):
        build_home_projection_fixture("fixture.not_declared")


def test_fixture_module_has_no_reader_network_or_secret_imports() -> None:
    source = ast.parse((Path(__file__).parent.parent / "home_fixtures.py").read_text(encoding="utf-8"))
    imported = {
        (node.module or "").split(".")[0]
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported & {"pathlib", "socket", "httpx", "requests", "secrets", "sqlite3"}
    assert "entrypoints.tui.secret" not in "".join(imported)
