"""Focused contracts for deterministic Home candidate projections."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from .....application.overview.calendar_models import OverviewPeriodState
from .....application.overview.home import HomeAvailability, HomeDeclarationState, HomeSessionPosture
from .....core.period import Period
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
    for first_rows, second_rows in (
        (first.actions, second.actions),
        (first.declarations, second.declarations),
        (first.agenda, second.agenda),
    ):
        if first_rows:
            assert first_rows is not second_rows
            assert all(
                first_row is not second_row for first_row, second_row in zip(first_rows, second_rows, strict=True)
            )
    if first.ledger is not None:
        assert second.ledger is not None
        assert first.ledger is not second.ledger
    with pytest.raises(ValidationError):
        first.generated_at = second.generated_at


def test_populated_declaration_identity_is_stable_across_fresh_builds() -> None:
    first = build_home_projection_fixture(HomeFixtureScenario.READY)
    second = build_home_projection_fixture(HomeFixtureScenario.READY)

    first_identity = tuple(
        (item.work_unit_id, item.modelo, item.filing_year, item.period.registry_token) for item in first.declarations
    )
    second_identity = tuple(
        (item.work_unit_id, item.modelo, item.filing_year, item.period.registry_token) for item in second.declarations
    )
    assert first_identity == second_identity


def _home_reason_keys(locale: str) -> frozenset[str]:
    """Every `tui.home.reason.*` key a locale actually declares.

    Read from the catalogue file rather than through `tr()`, because `tr()`
    HUMANISES a missing key into a plausible sentence: a resolution check
    routed through it can never observe an absence, which is the only thing
    this is trying to detect.
    """
    root = Path(__file__).resolve().parents[4] / "locales" / locale / "common.yml"
    raw = yaml.safe_load(root.read_text(encoding="utf-8"))

    def flatten(node: object, prefix: str = "") -> Iterator[str]:
        if isinstance(node, dict):
            for key, value in node.items():
                yield from flatten(value, f"{prefix}{key}.")
        else:
            yield prefix.rstrip(".")

    return frozenset(flatten(raw))


@pytest.mark.parametrize("scenario", (HomeFixtureScenario.READY, HomeFixtureScenario.BLOCKED))
def test_populated_actions_cover_declaration_addressed_and_cross_cutting_tasks(
    scenario: HomeFixtureScenario,
) -> None:
    """Both shapes of action are present: one bound to a declaration, one not.

    The cross-cutting action is found by the ABSENCE of an address, not by a
    pinned action id. The ids this once named -- `fixture.classify`,
    `fixture.review_blocker` -- no longer exist: the fixtures were moved onto
    the real `operator.*` ids so their copy resolves through the catalogue, and
    a gate pinning synthetic names then fails for a reason that has nothing to
    do with what it is checking. The property it actually cares about is that
    Home has to render both an addressed and an addressless action.
    """
    projection = build_home_projection_fixture(scenario)

    addressed = projection.actions[0]
    assert addressed.modelo == "303"
    assert addressed.filing_year == 2026
    assert addressed.period == Period.from_year_and_code(2026, "3T")
    addressless = [
        item
        for item in projection.actions
        if (item.modelo, item.filing_year, item.period) == (None, None, None)
    ]
    assert addressless, (
        f"{scenario} carries no cross-cutting action, so Home never renders one: "
        f"{[item.action.action.action_id for item in projection.actions]}"
    )


@pytest.mark.parametrize("scenario", (HomeFixtureScenario.READY, HomeFixtureScenario.BLOCKED))
def test_populated_agenda_period_state_agrees_with_generated_date(scenario: HomeFixtureScenario) -> None:
    projection = build_home_projection_fixture(scenario)
    generated_on = projection.generated_at.date()

    assert tuple(item.due_on for item in projection.agenda) == tuple(sorted(item.due_on for item in projection.agenda))
    assert all(
        item.due_on < generated_on for item in projection.agenda if item.period_state is OverviewPeriodState.LATE
    )
    assert all(
        item.due_on >= generated_on for item in projection.agenda if item.period_state is OverviewPeriodState.DUE
    )


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
    # Every reason code must reach real copy. A code is a transport token that
    # keys `tui.home.reason.<code>`, so pinning a literal name (this once
    # required `fixture.blocked_dependency`) proves nothing about whether the
    # operator sees a sentence or the degraded generic line -- and it broke the
    # moment the fixtures moved onto codes that actually resolve.
    catalogue = _home_reason_keys("es")
    for item in blocked.actions:
        assert f"tui.home.reason.{item.reason_code}" in catalogue, (
            f"reason code {item.reason_code!r} has no copy, so Home degrades to its generic line"
        )
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
    spanish_identifier = re.compile(
        r"\b(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z]|[KLM]\d{7}[A-Z]|[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J])\b",
        re.IGNORECASE,
    )
    forbidden = (
        re.compile(r"(?:password|passphrase|secret|bearer|api[_-]?key|private[_-]?key)", re.IGNORECASE),
        re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
        re.compile(r"\bES\d{22}\b", re.IGNORECASE),
        spanish_identifier,
        re.compile(r"https?://", re.IGNORECASE),
        re.compile(r"\bwork unit\b", re.IGNORECASE),
    )
    allowed_ids = {letter * 64 for letter in "abc"}
    for scenario in HomeFixtureScenario:
        serialized = build_home_projection_fixture(scenario).model_dump_json()
        assert all(pattern.search(serialized) is None for pattern in forbidden)
        assert set(re.findall(r"\b[0-9a-f]{64}\b", serialized)) <= allowed_ids
    assert all(spanish_identifier.fullmatch(value) for value in ("12345678Z", "X2482300W", "B12345678"))


def test_fixture_module_ast_has_only_local_record_construction_and_no_io() -> None:
    source = ast.parse((Path(__file__).parent.parent / "home_fixtures.py").read_text(encoding="utf-8"))

    imported_modules = {alias.name for node in ast.walk(source) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module or "" for node in ast.walk(source) if isinstance(node, ast.ImportFrom))
    forbidden_module_roots = {
        "os",
        "pathlib",
        "socket",
        "httpx",
        "requests",
        "secrets",
        "sqlite3",
        "subprocess",
    }
    forbidden_module_segments = {
        "adapter",
        "client",
        "network",
        "persistence",
        "reader",
        "repo",
        "repository",
        "secret",
    }
    assert all(module.split(".")[0] not in forbidden_module_roots for module in imported_modules)
    assert all(not forbidden_module_segments.intersection(module.casefold().split(".")) for module in imported_modules)

    def call_path(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = call_path(node.value)
            return f"{parent}.{node.attr}"
        return ""

    called = {call_path(node.func) for node in ast.walk(source) if isinstance(node, ast.Call)}
    forbidden_calls = {
        "open",
        "os.open",
        "os.system",
        "os.popen",
        "pathlib.Path",
        "pathlib.Path.open",
        "pathlib.Path.read_text",
        "pathlib.Path.write_text",
        "socket.socket",
        "requests.get",
        "requests.post",
        "httpx.get",
        "httpx.post",
        "subprocess.run",
        "urlopen",
    }
    forbidden_call_segments = {"adapter", "client", "network", "persistence", "reader", "repo", "repository"}
    forbidden_suffixes = (".connect", ".mkdir", ".open", ".read", ".read_text", ".request", ".write", ".write_text")
    assert not called & forbidden_calls
    assert all(not forbidden_call_segments.intersection(path.casefold().split(".")) for path in called)
    assert not any(path.endswith(forbidden) for path in called for forbidden in forbidden_suffixes)
