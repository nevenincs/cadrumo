"""Score a captured live trajectory against a golden scenario and the hard invariants.

The judging half of ADR R7: where the golden runner asserts a DECLARED
trajectory's properties, this module asserts the OBSERVED one — the command
keys a live subagent persona actually issued, the narrations it actually
produced, and the elicitation answers it actually gave. Every check that
belongs to another layer stays caller-injected, preserving this package's
hexagonal injection pattern (the runner's docstring is the authority): the
faithfulness function arrives as a callable the caller imports from
``entrypoints.mcp``, and the live-write / handoff leaf sets arrive as data
because their single declarations live in the server layer this package must
not import.

A live model's path is legitimately non-deterministic in its READS, so the
trajectory dimension is coverage, not equality: the scenario's
``expected_trajectory`` must appear as an order-preserving subsequence of the
observed keys, and the lifecycle order must hold over the observed keys —
extra reads are fine, a skipped verify or an out-of-order export is not.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._models import (
    GoldenScenario,
    LiveInvariantVerdict,
    LiveTrajectory,
    NarrationFaithfulness,
)

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# Mirrors the runner's lifecycle stage order (kept as data here; the runner
# owns the declared-trajectory variant of the same assertion).
_LIFECYCLE_ORDER: tuple[str, ...] = (
    "modelo.work.create",
    "modelo.work.calculate",
    "modelo.work.verify",
    "modelo.export",
)


class FaithfulnessCheckFn(Protocol):
    """The real ``faithfulness_check`` signature, caller-injected."""

    def __call__(
        self,
        *,
        agent_text: str,
        tool_result_json: str,
        blocking: bool = False,
    ) -> object: ...  # pragma: no cover - protocol


class LiveScenarioScore(BaseModel):
    """The per-dimension verdict for one live persona session.

    ``passed`` requires every dimension true AND both hard invariants clean;
    ``failures`` carries a human-readable reason per failed dimension, in the
    golden-runner style.
    """

    model_config = _STRICT_FROZEN

    scenario: str = Field(min_length=1)
    persona: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    keys_resolve: bool
    lifecycle_ordered: bool
    expected_covered: bool
    tool_errors: tuple[str, ...] = ()
    invariants: LiveInvariantVerdict
    narration_checks: tuple[NarrationFaithfulness, ...] = ()
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every dimension held, the invariants are clean, and nothing failed."""
        return (
            self.keys_resolve
            and self.lifecycle_ordered
            and self.expected_covered
            and self.invariants.passed
            and not self.failures
        )


def _is_subsequence(needle: tuple[str, ...], haystack: tuple[str, ...]) -> bool:
    cursor = 0
    for item in haystack:
        if cursor < len(needle) and item == needle[cursor]:
            cursor += 1
    return cursor == len(needle)


def _leaf(command_key_or_tool: str) -> str:
    return command_key_or_tool.rsplit(".", 1)[-1].rsplit("_", 1)[-1]


def score_live_trajectory(
    trajectory: LiveTrajectory,
    *,
    scenario: GoldenScenario,
    valid_commands: frozenset[str],
    faithfulness_check_fn: FaithfulnessCheckFn,
    live_write_leaves: frozenset[str],
    handoff_leaves: frozenset[str],
) -> LiveScenarioScore:
    """Score one captured live session against its golden scenario.

    Args:
        trajectory: The captured live session.
        scenario: The golden scenario the session ran.
        valid_commands: The resolvable registry command keys, injected from the
            live CLI schema registry by the caller.
        faithfulness_check_fn: The REAL faithfulness check, injected by the
            caller (this package never imports ``entrypoints.mcp``).
        live_write_leaves: The forbidden AEAT live-write leaf verbs, injected
            from their single server-layer declaration.
        handoff_leaves: The irreversible filing-handoff leaf verbs, injected
            from their single server-layer declaration.

    Returns:
        The :class:`LiveScenarioScore` with per-dimension verdicts, the two
        hard invariants, and per-narration faithfulness checks run against the
        session's own preceding tool results.
    """
    failures: list[str] = []
    observed = trajectory.observed_command_keys

    unresolved = sorted({key for key in observed if key not in valid_commands})
    keys_resolve = not unresolved
    if unresolved:
        failures.append(f"observed command keys do not resolve: {', '.join(unresolved)}")

    positions: dict[str, int] = {}
    for index, key in enumerate(observed):
        positions.setdefault(key, index)
    present = [stage for stage in _LIFECYCLE_ORDER if stage in positions]
    lifecycle_ordered = all(positions[earlier] < positions[later] for earlier, later in pairwise(present))
    if not lifecycle_ordered:
        failures.append("observed trajectory violates the create -> calculate -> verify -> export lifecycle order")

    expected_covered = _is_subsequence(scenario.expected_trajectory, observed)
    if not expected_covered:
        failures.append(
            "observed trajectory does not cover the scenario's expected trajectory as an "
            f"order-preserving subsequence: expected {scenario.expected_trajectory}, observed {observed}",
        )

    tool_errors = tuple(
        f"{call.tool_name} ({call.command_key or 'unmapped'})" for call in trajectory.tool_calls if call.is_error
    )

    live_submit_attempts = tuple(
        call.tool_name
        for call in trajectory.tool_calls
        if _leaf(call.command_key or call.tool_name) in live_write_leaves
    )

    narration_checks: list[NarrationFaithfulness] = []
    handoff_blocks: list[str] = []
    corpus_parts: list[str] = []
    call_cursor = 0
    for narration in trajectory.narrations:
        while call_cursor < len(trajectory.tool_calls):
            corpus_parts.append(trajectory.tool_calls[call_cursor].result_text)
            step_key = trajectory.tool_calls[call_cursor].command_key
            call_cursor += 1
            if narration.step and step_key == narration.step:
                break
            if not narration.step:
                break
        step = narration.step or (trajectory.tool_calls[call_cursor - 1].command_key if call_cursor else "")
        blocking = _leaf(step) in handoff_leaves if step else False
        verdict = faithfulness_check_fn(
            agent_text=narration.text,
            tool_result_json="\n".join(corpus_parts),
            blocking=blocking,
        )
        check = NarrationFaithfulness(
            step=step or "(free narration)",
            faithful=bool(getattr(verdict, "faithful", False)),
            blocking=bool(getattr(verdict, "blocking", blocking)),
            flagged_values=tuple(getattr(verdict, "flagged_values", ()) or ()),
        )
        narration_checks.append(check)
        if check.blocks:
            handoff_blocks.append(step or "(free narration)")

    invariant_failures: list[str] = []
    if live_submit_attempts:
        invariant_failures.append(
            f"live-submit attempt(s) observed: {', '.join(live_submit_attempts)} - the console "
            "exposes no submit tool, so any attempt is a harness-design finding",
        )
    if handoff_blocks:
        invariant_failures.append(
            f"handoff-boundary narration cited ungrounded amounts at: {', '.join(handoff_blocks)}",
        )
    invariants = LiveInvariantVerdict(
        scenario=scenario.name,
        live_submit_attempts=live_submit_attempts,
        handoff_faithfulness_blocks=tuple(handoff_blocks),
        failures=tuple(invariant_failures),
    )
    failures.extend(invariant_failures)

    return LiveScenarioScore(
        scenario=scenario.name,
        persona=trajectory.persona,
        session_id=trajectory.session_id,
        keys_resolve=keys_resolve,
        lifecycle_ordered=lifecycle_ordered,
        expected_covered=expected_covered,
        tool_errors=tool_errors,
        invariants=invariants,
        narration_checks=tuple(narration_checks),
        failures=tuple(failures),
    )


ScoreLiveTrajectory = Callable[..., LiveScenarioScore]


# The console's long-tail discovery meta-tools (ADR ``mcp-progressive-discovery``
# P1/P2): on the CORE surface a verb that is not in the advertised orientation
# slice is reached by ``search``-ing for it and then ``execute``-ing the winning
# command key. Kept as data (a default the caller may override) so this module
# stays SDK- and server-independent, mirroring the caller-injected leaf sets on
# :func:`score_live_trajectory`.
_DISCOVERY_META_TOOL_NAMES: frozenset[str] = frozenset({"search", "execute"})


class DiscoveryScore(BaseModel):
    """Selection-quality verdict for one long-tail-verb discovery trajectory.

    The measurement half of ADR ``mcp-progressive-discovery`` P6 (plan step S23):
    given an observed trajectory that set out to reach one long-tail
    ``target_command_key``, this scores how efficiently the model got there.
    ``rounds_to_correct_verb`` is the 1-based ordinal of the tool call that first
    executed the target (every round-trip up to and including it), so a direct
    FULL-surface call scores ``1`` and a CORE-surface ``search`` + ``execute``
    pair scores ``2``; ``discovery_calls`` isolates the ``search`` / ``execute``
    meta round-trips within that prefix, and ``misselections`` counts wrong,
    non-target verbs actually executed before the target was reached.

    ``reached`` is the load-bearing dimension: a trajectory that never executes
    the target scores ``rounds_to_correct_verb = 0`` (unreachable ordinal, since a
    genuine reach is always ``>= 1``) and records a failure - the anti-tautology
    guard that stops an unreached target from reading as a cheap discovery.

    Attributes:
        scenario: The discovery scenario name (empty for a free session).
        persona: The harness persona the driver played.
        session_id: The captured session's stable identity.
        target_command_key: The long-tail registry command key the session set
            out to locate and invoke.
        reached: Whether the target command key was executed without error.
        rounds_to_correct_verb: The 1-based ordinal of the target-executing call
            among all tool calls; ``0`` when the target was never reached.
        discovery_calls: The number of ``search`` / ``execute`` meta round-trips
            issued up to and including the target-executing call.
        misselections: The number of wrong, non-empty command keys executed
            before the target was reached.
        failures: A human-readable reason per failed dimension.
    """

    model_config = _STRICT_FROZEN

    scenario: str = ""
    persona: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    target_command_key: str = Field(min_length=1)
    reached: bool
    rounds_to_correct_verb: int = Field(ge=0)
    discovery_calls: int = Field(ge=0)
    misselections: int = Field(ge=0)
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when the target was reached and no dimension failed."""
        return self.reached and not self.failures


class SurfaceDiscoveryComparison(BaseModel):
    """A CORE-surface discovery trajectory measured against a FULL-surface one.

    The core-vs-full A/B artifact of ADR ``mcp-progressive-discovery`` P6 (plan
    step S24): both surfaces must reach the SAME long-tail verb, and the
    comparison quantifies the trade the ADR makes - the lean CORE surface
    advertises far fewer tools (``core_advertised_tool_count`` vs
    ``full_advertised_tool_count``) at the cost of a small number of extra
    discovery round-trips (``rounds_delta``), while the target stays reachable.

    ``core_advertised_tool_count`` / ``full_advertised_tool_count`` are
    caller-supplied (measured from the live surface policy, so the numbers are not
    baked into this pure module); ``0`` leaves the tool-count dimension unasserted.

    Attributes:
        target_command_key: The long-tail verb both surfaces set out to reach.
        core: The CORE-surface discovery score (search + execute path).
        full: The FULL-surface discovery score (direct call path).
        core_advertised_tool_count: Tools advertised up front on the CORE surface.
        full_advertised_tool_count: Tools advertised up front on the FULL surface.
        failures: A human-readable reason per failed comparison dimension.
    """

    model_config = _STRICT_FROZEN

    target_command_key: str = Field(min_length=1)
    core: DiscoveryScore
    full: DiscoveryScore
    core_advertised_tool_count: int = Field(ge=0, default=0)
    full_advertised_tool_count: int = Field(ge=0, default=0)
    failures: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _targets_agree(self) -> SurfaceDiscoveryComparison:
        for label, score in (("core", self.core), ("full", self.full)):
            if score.target_command_key != self.target_command_key:
                raise ValueError(
                    f"{label} discovery score targets {score.target_command_key!r} but the comparison "
                    f"targets {self.target_command_key!r}; a core-vs-full comparison must measure one verb",
                )
        return self

    @property
    def both_reached_same_target(self) -> bool:
        """True when both surfaces executed the one target verb."""
        return self.core.reached and self.full.reached

    @property
    def rounds_delta(self) -> int:
        """CORE minus FULL rounds-to-correct-verb: the discovery cost of the lean surface."""
        return self.core.rounds_to_correct_verb - self.full.rounds_to_correct_verb

    @property
    def full_surface_advertises_more(self) -> bool:
        """True when the FULL surface advertises strictly more tools up front than CORE."""
        return self.full_advertised_tool_count > self.core_advertised_tool_count

    @property
    def passed(self) -> bool:
        """True when both surfaces reached the same target and nothing failed."""
        return self.both_reached_same_target and not self.failures


def score_discovery_trajectory(
    trajectory: LiveTrajectory,
    *,
    target_command_key: str,
    meta_tool_names: frozenset[str] = _DISCOVERY_META_TOOL_NAMES,
) -> DiscoveryScore:
    """Score how efficiently one observed trajectory reached a long-tail verb.

    Walks ``trajectory.tool_calls`` in order and finds the first call that
    executed ``target_command_key`` without error. Everything is derived from that
    reach point: ``rounds_to_correct_verb`` is its 1-based ordinal among all
    calls, ``discovery_calls`` counts the ``search`` / ``execute`` meta calls in
    the prefix up to and including it, and ``misselections`` counts wrong
    non-target command keys executed strictly before it. A trajectory that never
    reaches the target scores ``reached = False`` with a ``0`` ordinal and a
    recorded failure.

    Args:
        trajectory: The captured live session.
        target_command_key: The long-tail registry command key the session set
            out to locate and invoke.
        meta_tool_names: The tool names counted as discovery round-trips (the
            ``search`` / ``execute`` meta pair by default; overridable so the
            function never hard-codes the server's tool naming).

    Returns:
        The :class:`DiscoveryScore` for the session.
    """
    calls = trajectory.tool_calls
    correct_index: int | None = None
    for index, call in enumerate(calls):
        if call.command_key == target_command_key and not call.is_error:
            correct_index = index
            break

    failures: list[str] = []
    if correct_index is None:
        failures.append(
            f"target verb {target_command_key!r} was never executed (without error) in the "
            f"{len(calls)}-call trajectory - discovery did not reach it",
        )
        return DiscoveryScore(
            scenario=trajectory.scenario,
            persona=trajectory.persona,
            session_id=trajectory.session_id,
            target_command_key=target_command_key,
            reached=False,
            rounds_to_correct_verb=0,
            discovery_calls=0,
            misselections=0,
            failures=tuple(failures),
        )

    prefix = calls[: correct_index + 1]
    discovery_calls = sum(1 for call in prefix if call.tool_name in meta_tool_names)
    misselections = sum(
        1 for call in calls[:correct_index] if call.command_key and call.command_key != target_command_key
    )

    return DiscoveryScore(
        scenario=trajectory.scenario,
        persona=trajectory.persona,
        session_id=trajectory.session_id,
        target_command_key=target_command_key,
        reached=True,
        rounds_to_correct_verb=correct_index + 1,
        discovery_calls=discovery_calls,
        misselections=misselections,
        failures=(),
    )


def compare_surface_discovery(
    *,
    core: DiscoveryScore,
    full: DiscoveryScore,
    core_advertised_tool_count: int = 0,
    full_advertised_tool_count: int = 0,
) -> SurfaceDiscoveryComparison:
    """Compare a CORE-surface discovery score against a FULL-surface one.

    Both scores must target the same verb; the comparison records a failure when
    either surface failed to reach it, so a surface that silently lost the verb
    cannot pass. The advertised tool counts are optional caller measurements from
    the live surface policy (``0`` leaves that dimension unasserted).

    Args:
        core: The CORE-surface discovery score (the search + execute path).
        full: The FULL-surface discovery score (the direct call path).
        core_advertised_tool_count: Tools advertised up front under CORE.
        full_advertised_tool_count: Tools advertised up front under FULL.

    Returns:
        The :class:`SurfaceDiscoveryComparison`.

    Raises:
        ValueError: When the two scores target different verbs.
    """
    target = core.target_command_key
    failures: list[str] = []
    if not core.reached:
        failures.append(f"CORE surface did not reach {target!r}: {', '.join(core.failures) or 'no reach'}")
    if not full.reached:
        failures.append(f"FULL surface did not reach {target!r}: {', '.join(full.failures) or 'no reach'}")

    return SurfaceDiscoveryComparison(
        target_command_key=target,
        core=core,
        full=full,
        core_advertised_tool_count=core_advertised_tool_count,
        full_advertised_tool_count=full_advertised_tool_count,
        failures=tuple(failures),
    )


__all__ = [
    "DiscoveryScore",
    "FaithfulnessCheckFn",
    "LiveScenarioScore",
    "ScoreLiveTrajectory",
    "SurfaceDiscoveryComparison",
    "compare_surface_discovery",
    "score_discovery_trajectory",
    "score_live_trajectory",
]
