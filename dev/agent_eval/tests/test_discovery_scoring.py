"""Discovery selection-quality gate for the operator evaluation.

Scores how efficiently an OBSERVED trajectory reaches a long-tail verb through the
console's CORE surface (``search`` + ``execute``) versus the FULL surface (a direct
per-verb call). The metrics under test - ``rounds_to_correct_verb`` selection
quality and the CORE-vs-FULL surface comparison - are pure over a constructed
:class:`LiveTrajectory`, so no live model is driven here; the deterministic
core-vs-full advantage (a dozen-odd advertised tools
vs ~300, the same long-tail verb still reachable) is measured from the live surface
policy and asserted directly.

The advertised-tool counts are measured from the live descriptor set via the public
``build_tool_descriptors`` facade; the CORE orientation predicate (the ``contract``
verb plus the ``overview.*`` family) mirrors ``cadrumo_harness.mcp._surface`` and is
reproduced locally rather than imported to keep this test off the cross-package
private-import ratchet. Every trajectory is hand-constructed from the real
``LiveTrajectory`` / ``LiveToolCallRecord`` models - no mocks of the scoring code
under test (``aeat-quality-gates``, ``aeat-quality-gates``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, Unpack

import pytest

from cadrumo_harness.mcp import build_tool_descriptors

from .. import (
    LiveToolCallRecord,
    LiveTrajectory,
    load_scenario,
    run_golden_scenario,
)
from .._live_scoring import (
    DiscoveryScore,
    SurfaceDiscoveryComparison,
    compare_surface_discovery,
    score_discovery_trajectory,
)
from ._real_cli_support import valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_DISCOVERY_SCENARIO = _SCENARIOS_DIR / "descubrimiento_verbo.toml"

# The long-tail discovery target the scenario declares: a genuine modelo-130 verb
# that resolves against the live CLI surface but is NOT in the advertised CORE
# orientation slice, so it must be reached through search + execute.
_TARGET = "modelo.work.calculate"

# The always-on advertised tools that are NOT per-verb descriptors: the
# `harness.load` floor (1), the two grounding tools (2), and the search/execute/
# toolsets meta trio (3). The CORE and FULL advertised totals both add this
# constant to their per-verb slice (mirrors `cadrumo_harness.mcp._server`'s list_tools
# assembly: `[floor_tool, *grounding_tools, *advertised, *meta_tools]`).
_ALWAYS_ON_NON_VERB_TOOLS = 1 + 2 + 3


def _is_orientation(command_key: str) -> bool:
    # Mirrors `cadrumo_harness.mcp._surface.is_orientation_command`: the `contract`
    # capability verb plus the `overview.*` obligation-derivation family.
    return command_key == "contract" or command_key.startswith("overview.")


def _target_tool_name() -> str:
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    assert _TARGET in by_key, f"{_TARGET!r} is not an exposed MCP tool"
    return by_key[_TARGET].name


def _core_trajectory(tool_calls: tuple[LiveToolCallRecord, ...], *, session_id: str) -> LiveTrajectory:
    return LiveTrajectory(
        scenario="descubrimiento-verbo-long-tail",
        persona="cadrumo-modelo-preparer",
        session_id=session_id,
        tool_calls=tool_calls,
    )


def _search_call(query: str = "calculate the modelo draft casillas") -> LiveToolCallRecord:
    # A CORE-surface discovery round-trip: the meta `search` tool carries no
    # registry command key (it maps a query onto candidates; it executes nothing).
    return LiveToolCallRecord(tool_name="search", command_key="", arguments_json=f'{{"query": "{query}"}}')


def _execute_call(command_key: str, *, is_error: bool = False) -> LiveToolCallRecord:
    # A CORE-surface `execute` of one command key (the meta invoke path).
    return LiveToolCallRecord(
        tool_name="execute",
        command_key=command_key,
        arguments_json='{"modelo": "130", "year": "2024", "period": "1T"}',
        is_error=is_error,
    )


def _direct_call(command_key: str) -> LiveToolCallRecord:
    # A FULL-surface direct per-verb tool call: the advertised tool IS the verb, so
    # there is no meta round-trip and the tool name is the verb's own tool name.
    return LiveToolCallRecord(
        tool_name=_target_tool_name(),
        command_key=command_key,
        arguments_json='{"modelo": "130", "year": "2024", "period": "1T"}',
    )


# --------------------------------------------------------------------------- #
# The discovery scenario is valid, runnable, and targets a long-tail verb.
# --------------------------------------------------------------------------- #


def test_discovery_scenario_loads_and_targets_a_resolvable_long_tail_verb() -> None:
    """The scenario is valid, and its long-tail target resolves without being orientation."""
    scenario = load_scenario(_DISCOVERY_SCENARIO)
    assert scenario.name == "descubrimiento-verbo-long-tail"
    assert _TARGET in scenario.expected_trajectory
    assert _TARGET in valid_cli_commands(), f"{_TARGET!r} must resolve against the live CLI surface"
    assert not _is_orientation(_TARGET), f"{_TARGET!r} must be a long-tail verb, not part of the CORE orientation slice"


def test_discovery_scenario_passes_the_shared_golden_dimensions() -> None:
    """The scenario is minimal-but-valid: it passes the trajectory/lifecycle/skill/provenance gate."""
    result = run_golden_scenario(load_scenario(_DISCOVERY_SCENARIO), valid_commands=valid_cli_commands())
    assert result.passed, result.failures


# --------------------------------------------------------------------------- #
# Measure rounds-to-correct-verb selection quality over an observed trajectory.
# --------------------------------------------------------------------------- #


def test_core_search_then_execute_reaches_in_two_rounds() -> None:
    """A minimal CORE trajectory (search -> execute target) scores two rounds, both discovery calls."""
    trajectory = _core_trajectory((_search_call(), _execute_call(_TARGET)), session_id="core-minimal")

    score = score_discovery_trajectory(trajectory, target_command_key=_TARGET)

    assert score.passed
    assert score.reached
    assert score.rounds_to_correct_verb == 2
    assert score.discovery_calls == 2
    assert score.misselections == 0


def test_full_direct_call_reaches_in_one_round_with_no_discovery_calls() -> None:
    """A FULL trajectory calls the verb's own advertised tool directly: one round, zero meta calls."""
    trajectory = _core_trajectory((_direct_call(_TARGET),), session_id="full-direct")

    score = score_discovery_trajectory(trajectory, target_command_key=_TARGET)

    assert score.reached
    assert score.rounds_to_correct_verb == 1
    assert score.discovery_calls == 0
    assert score.misselections == 0


def test_wasted_search_before_the_correct_execute_costs_extra_rounds() -> None:
    """Two searches before the execute score three rounds and three discovery calls - selection cost is visible."""
    trajectory = _core_trajectory(
        (_search_call("how do I compute the quarter"), _search_call(), _execute_call(_TARGET)),
        session_id="core-wasted-search",
    )

    score = score_discovery_trajectory(trajectory, target_command_key=_TARGET)

    assert score.reached
    assert score.rounds_to_correct_verb == 3
    assert score.discovery_calls == 3
    assert score.misselections == 0


def test_executing_a_wrong_verb_before_the_target_counts_as_a_misselection() -> None:
    """A wrong non-target verb executed before the target is counted; the target still reached at round three."""
    trajectory = _core_trajectory(
        (_search_call(), _execute_call("modelo.work.verify"), _execute_call(_TARGET)),
        session_id="core-misselection",
    )

    score = score_discovery_trajectory(trajectory, target_command_key=_TARGET)

    assert score.reached
    assert score.rounds_to_correct_verb == 3
    assert score.discovery_calls == 3
    assert score.misselections == 1


def test_an_errored_target_execution_does_not_count_as_reached() -> None:
    """An `isError` execute of the target is not a reach; a later clean execute is the reach point."""
    trajectory = _core_trajectory(
        (_search_call(), _execute_call(_TARGET, is_error=True), _execute_call(_TARGET)),
        session_id="core-error-then-retry",
    )

    score = score_discovery_trajectory(trajectory, target_command_key=_TARGET)

    assert score.reached
    # The errored attempt at index 1 is skipped; the clean execute at index 2 is round 3.
    assert score.rounds_to_correct_verb == 3


def test_a_trajectory_that_never_executes_the_target_does_not_pass() -> None:
    """FAIL-catch (anti-tautology): a trajectory that only searches never reaches the verb and must fail."""
    trajectory = _core_trajectory((_search_call(), _search_call()), session_id="core-never-reached")

    score = score_discovery_trajectory(trajectory, target_command_key=_TARGET)

    assert not score.passed
    assert not score.reached
    assert score.rounds_to_correct_verb == 0
    assert any(_TARGET in failure and "never" in failure for failure in score.failures)


# --------------------------------------------------------------------------- #
# Compare the deterministic CORE and FULL surfaces.
# --------------------------------------------------------------------------- #


def _measure_surface_tool_counts() -> tuple[int, int]:
    """Return ``(core_advertised, full_advertised)`` from the live descriptor set."""
    descriptors = build_tool_descriptors()
    orientation = sum(1 for descriptor in descriptors if _is_orientation(descriptor.command_key))
    core = orientation + _ALWAYS_ON_NON_VERB_TOOLS
    full = len(descriptors) + _ALWAYS_ON_NON_VERB_TOOLS
    return core, full


def test_core_surface_is_dramatically_leaner_than_full_yet_reaches_the_same_verb() -> None:
    """The core-vs-full A/B: CORE advertises far fewer tools, both surfaces reach the same long-tail verb."""
    core_count, full_count = _measure_surface_tool_counts()

    # The lean CORE surface is a dozen-odd tools; FULL is the whole verb universe.
    assert core_count <= 20, core_count
    assert full_count >= 250, full_count
    assert full_count - core_count >= 200

    core_score = score_discovery_trajectory(
        _core_trajectory((_search_call(), _execute_call(_TARGET)), session_id="cmp-core"),
        target_command_key=_TARGET,
    )
    full_score = score_discovery_trajectory(
        _core_trajectory((_direct_call(_TARGET),), session_id="cmp-full"),
        target_command_key=_TARGET,
    )

    comparison = compare_surface_discovery(
        core=core_score,
        full=full_score,
        core_advertised_tool_count=core_count,
        full_advertised_tool_count=full_count,
    )

    assert comparison.passed
    assert comparison.both_reached_same_target
    assert comparison.full_surface_advertises_more
    # CORE pays exactly one extra discovery round-trip (search) for the lean surface.
    assert comparison.rounds_delta == 1
    assert comparison.target_command_key == _TARGET


def test_comparison_fails_when_a_surface_loses_the_verb() -> None:
    """FAIL-catch: if either surface never reaches the target the comparison must not pass."""
    reached = score_discovery_trajectory(
        _core_trajectory((_search_call(), _execute_call(_TARGET)), session_id="cmp-core-ok"),
        target_command_key=_TARGET,
    )
    lost = score_discovery_trajectory(
        _core_trajectory((_search_call(),), session_id="cmp-full-lost"),
        target_command_key=_TARGET,
    )

    comparison = compare_surface_discovery(core=reached, full=lost)

    assert not comparison.passed
    assert not comparison.both_reached_same_target
    assert any(_TARGET in failure for failure in comparison.failures)


def test_comparison_rejects_two_scores_targeting_different_verbs() -> None:
    """Anti-tautology: a core-vs-full comparison must measure ONE verb; mismatched targets raise."""
    core_score = score_discovery_trajectory(
        _core_trajectory((_search_call(), _execute_call(_TARGET)), session_id="cmp-core-a"),
        target_command_key=_TARGET,
    )
    other_target = "modelo.work.verify"
    full_score = score_discovery_trajectory(
        _core_trajectory((_direct_call(other_target),), session_id="cmp-full-b"),
        target_command_key=other_target,
    )

    with pytest.raises(ValueError, match="must measure one verb"):
        SurfaceDiscoveryComparison(
            target_command_key=_TARGET,
            core=core_score,
            full=full_score,
        )


class _DiscoveryScoreKwargs(TypedDict):
    persona: str
    session_id: str
    target_command_key: str
    reached: bool
    rounds_to_correct_verb: int
    discovery_calls: int
    misselections: int
    failures: tuple[str, ...]


class _DiscoveryScoreOverrides(TypedDict, total=False):
    persona: str
    session_id: str
    target_command_key: str
    reached: bool
    rounds_to_correct_verb: int
    discovery_calls: int
    misselections: int
    failures: tuple[str, ...]


def _reached_kwargs(**overrides: Unpack[_DiscoveryScoreOverrides]) -> _DiscoveryScoreKwargs:
    kwargs: _DiscoveryScoreKwargs = {
        "persona": "cadrumo-modelo-preparer",
        "session_id": "s-1",
        "target_command_key": _TARGET,
        "reached": True,
        "rounds_to_correct_verb": 1,
        "discovery_calls": 0,
        "misselections": 0,
        "failures": (),
    }
    kwargs.update(overrides)
    return kwargs


def test_reached_score_with_a_zero_ordinal_is_refused() -> None:
    """Anti-tautology: a reached target must carry a positive rounds_to_correct_verb."""
    with pytest.raises(ValueError, match="positive rounds_to_correct_verb"):
        DiscoveryScore(**_reached_kwargs(rounds_to_correct_verb=0))


def test_unreached_score_with_a_nonzero_ordinal_is_refused() -> None:
    with pytest.raises(ValueError, match="rounds_to_correct_verb == 0"):
        DiscoveryScore(**_reached_kwargs(reached=False, rounds_to_correct_verb=1))


def test_direct_construction_with_valid_reached_and_unreached_ordinals_round_trips() -> None:
    reached = DiscoveryScore(**_reached_kwargs())
    assert reached.passed

    unreached = DiscoveryScore(**_reached_kwargs(reached=False, rounds_to_correct_verb=0, failures=("never reached",)))
    assert not unreached.passed


def test_discovery_score_is_a_frozen_strict_model() -> None:
    """The verdict is immutable (the eval's strict-frozen contract), so a score cannot be mutated after the fact."""
    score = score_discovery_trajectory(
        _core_trajectory((_search_call(), _execute_call(_TARGET)), session_id="frozen"),
        target_command_key=_TARGET,
    )
    assert isinstance(score, DiscoveryScore)
    with pytest.raises(ValueError, match="frozen"):
        score.__setattr__("reached", False)
