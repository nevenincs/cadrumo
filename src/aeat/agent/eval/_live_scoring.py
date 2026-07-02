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

from pydantic import BaseModel, ConfigDict, Field

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

__all__ = [
    "FaithfulnessCheckFn",
    "LiveScenarioScore",
    "ScoreLiveTrajectory",
    "score_live_trajectory",
]
