"""Focused contracts for deterministic Home candidate projections."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....application.overview.calendar_models import OverviewPeriodState
from .....application.overview.home import HomeAvailability, HomeDeclarationState, HomeSessionPosture
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

    assert len(ready.actions) == len(ready.declarations) == len(ready.agenda) == 3
    assert tuple(item.rank for item in ready.actions) == (0, 1, 2)
    assert len({item.action.action.action_id for item in ready.actions}) == 3
    assert len({item.reason_code for item in ready.actions}) == 3
    assert len({item.work_unit_id for item in ready.declarations}) == 3
    assert {item.state for item in ready.declarations} == {
        HomeDeclarationState.DRAFT,
        HomeDeclarationState.READY,
        HomeDeclarationState.FILED,
    }
    assert len({(item.modelo, item.period.registry_token) for item in ready.agenda}) == 3
    assert {item.period_state for item in ready.agenda} == {
        OverviewPeriodState.DUE,
        OverviewPeriodState.LATE,
        OverviewPeriodState.FILED,
    }
    assert ready.actions and ready.declarations and ready.ledger is not None
    assert empty.actions == () and empty.declarations == ()
    assert empty.ledger is not None and empty.ledger.entries == 0
    assert len(blocked.actions) == len(blocked.declarations) == len(blocked.agenda) == 3
    assert len({item.action.action.action_id for item in blocked.actions}) == 3
    assert len({item.reason_code for item in blocked.actions}) == 3
    assert len({item.work_unit_id for item in blocked.declarations}) == 3
    assert blocked.actions[0].reason_code == "fixture.blocked_dependency"
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


def test_every_serialized_fixture_has_no_pii_or_secret_like_values() -> None:
    forbidden = (
        re.compile(r"(?:password|passphrase|secret|bearer|api[_-]?key|private[_-]?key)", re.IGNORECASE),
        re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
        re.compile(r"\bES\d{22}\b", re.IGNORECASE),
        re.compile(r"\b\d{8}[A-Z]\b"),
        re.compile(r"https?://", re.IGNORECASE),
        re.compile(r"\bwork unit\b", re.IGNORECASE),
    )
    allowed_ids = {letter * 64 for letter in "abc"}
    for scenario in HomeFixtureScenario:
        serialized = build_home_projection_fixture(scenario).model_dump_json()
        assert all(pattern.search(serialized) is None for pattern in forbidden)
        assert set(re.findall(r"\b[0-9a-f]{64}\b", serialized)) <= allowed_ids


def test_fixture_module_ast_has_only_local_record_construction_and_no_io() -> None:
    source = ast.parse((Path(__file__).parent.parent / "home_fixtures.py").read_text(encoding="utf-8"))

    imported_modules = {
        alias.name
        for node in ast.walk(source)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module or ""
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom)
    )
    forbidden_modules = {"pathlib", "socket", "httpx", "requests", "secrets", "sqlite3", "subprocess"}
    assert all(module.split(".")[0] not in forbidden_modules for module in imported_modules)

    def call_path(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = call_path(node.value)
            return f"{parent}.{node.attr}"
        return ""

    called = {
        call_path(node.func)
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
    }
    forbidden_calls = {
        "open",
        "pathlib.Path",
        "socket.socket",
        "requests.get",
        "requests.post",
        "httpx.get",
        "httpx.post",
        "subprocess.run",
        "urlopen",
    }
    forbidden_suffixes = (".connect", ".request", ".read_text", ".write_text", ".mkdir")
    assert not called & forbidden_calls
    assert not any(path.endswith(forbidden) for path in called for forbidden in forbidden_suffixes)
