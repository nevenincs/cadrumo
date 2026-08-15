"""Score a captured live trajectory against a golden scenario and the hard invariants.

The judging half of the live-harness contract: where the golden runner asserts
a DECLARED trajectory's properties, this module asserts the OBSERVED one — the command
keys a live subagent persona actually issued, the narrations it actually
produced, and the elicitation answers it actually gave. Every check that
belongs to another layer stays caller-injected, preserving this package's
consumer boundary (the runner's docstring is the authority): the
faithfulness function arrives as a callable the caller imports from the MCP
server layer (``cadrumo_harness.mcp``), and the live-write / handoff leaf sets
arrive as data because their single declarations live in that server layer this
package must not import.

A live model's path is legitimately non-deterministic in its READS, so the
trajectory dimension is coverage, not equality: the scenario's
``expected_trajectory`` must appear as an order-preserving subsequence of the
observed keys, and the lifecycle order must hold over the observed keys —
extra reads are fine, a skipped verify or an out-of-order export is not.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._models import (
    LIFECYCLE_STAGE_ORDER,
    GoldenScenario,
    LiveInvariantVerdict,
    LiveToolCallRecord,
    LiveTrajectory,
    NarrationFaithfulness,
    lifecycle_stages_in_canonical_order,
)

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


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

    @model_validator(mode="after")
    def _invariant_scenario_matches(self) -> LiveScenarioScore:
        """Reject a score whose nested invariant verdict names a different scenario."""
        if self.invariants.scenario != self.scenario:
            raise ValueError(
                f"score scenario is {self.scenario!r}, but its nested invariant verdict names "
                f"{self.invariants.scenario!r}; one session must score against one scenario",
            )
        return self

    @property
    def passed(self) -> bool:
        """True when every dimension held, the invariants are clean, and nothing failed."""
        return (
            self.keys_resolve
            and self.lifecycle_ordered
            and self.expected_covered
            and self.invariants.passed
            and not self.tool_errors
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


class _LifecycleOrderVerdict(BaseModel):
    """The observed-trajectory lifecycle-ordering dimension and its reason."""

    model_config = _STRICT_FROZEN

    ordered: bool
    failures: tuple[str, ...] = ()


def _score_observed_lifecycle_order(observed: tuple[str, ...]) -> _LifecycleOrderVerdict:
    """Decide whether the observed keys hold the lifecycle order, and why not.

    Two distinct ways to break the order, reported distinctly: RE-ENTERING a
    stage (running ``calculate`` twice) is a different operator error from
    running the stages out of sequence, so a re-entry names the stage(s) rather
    than reporting a generic ordering violation. Stage positions record the
    FIRST occurrence, so a re-entry cannot mask an out-of-order earlier stage.
    """
    positions: dict[str, int] = {}
    reentered_stages: list[str] = []
    for index, key in enumerate(observed):
        if key in LIFECYCLE_STAGE_ORDER:
            if key in positions:
                reentered_stages.append(key)
                continue
            positions[key] = index
    ordered = not reentered_stages and lifecycle_stages_in_canonical_order(positions)
    if ordered:
        return _LifecycleOrderVerdict(ordered=True)
    if reentered_stages:
        return _LifecycleOrderVerdict(
            ordered=False,
            failures=("observed trajectory re-enters lifecycle stage(s): " + ", ".join(reentered_stages),),
        )
    return _LifecycleOrderVerdict(
        ordered=False,
        failures=("observed trajectory violates the create -> calculate -> verify -> export lifecycle order",),
    )


class _NarrationAnchor(BaseModel):
    """The tool calls one narration consumed, and the call it is anchored to."""

    model_config = _STRICT_FROZEN

    cursor: int = Field(ge=0)
    consumed_result_texts: tuple[str, ...] = ()
    anchor_command_key: str = ""


def _advance_to_narration_anchor(
    calls: tuple[LiveToolCallRecord, ...],
    cursor: int,
    *,
    anchor_step: str,
) -> _NarrationAnchor:
    """Consume tool calls from ``cursor`` up to the one this narration describes.

    A narration that names its step consumes calls until that step's call is
    reached; a free narration (no declared step) consumes exactly one call and
    is anchored to it. Either way the consumed results become part of the
    running corpus the faithfulness check reads, so a narration is always
    judged against every tool result that preceded it.
    """
    consumed: list[str] = []
    while cursor < len(calls):
        consumed.append(calls[cursor].result_text)
        step_key = calls[cursor].command_key
        cursor += 1
        if anchor_step and step_key == anchor_step:
            break
        if not anchor_step:
            break
    return _NarrationAnchor(
        cursor=cursor,
        consumed_result_texts=tuple(consumed),
        anchor_command_key=calls[cursor - 1].command_key if cursor else "",
    )


class _NarrationScoring(BaseModel):
    """Per-narration faithfulness verdicts plus the handoff steps they block."""

    model_config = _STRICT_FROZEN

    checks: tuple[NarrationFaithfulness, ...] = ()
    handoff_blocks: tuple[str, ...] = ()


def _score_narration_faithfulness(
    trajectory: LiveTrajectory,
    *,
    faithfulness_check_fn: FaithfulnessCheckFn,
    handoff_leaves: frozenset[str],
) -> _NarrationScoring:
    """Run the injected faithfulness check over every narration in session order.

    Each narration is checked against the CUMULATIVE corpus of tool results
    observed up to its anchoring call, so a narration may legitimately cite any
    figure the session had already seen. Only a narration on an irreversible
    handoff leaf is checked as ``blocking``; elsewhere an unfaithful narration
    is advisory.
    """
    checks: list[NarrationFaithfulness] = []
    handoff_blocks: list[str] = []
    corpus_parts: list[str] = []
    cursor = 0
    for narration in trajectory.narrations:
        anchor = _advance_to_narration_anchor(trajectory.tool_calls, cursor, anchor_step=narration.step)
        cursor = anchor.cursor
        corpus_parts.extend(anchor.consumed_result_texts)
        step = narration.step or anchor.anchor_command_key
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
        checks.append(check)
        if check.blocks:
            handoff_blocks.append(step or "(free narration)")
    return _NarrationScoring(checks=tuple(checks), handoff_blocks=tuple(handoff_blocks))


def _score_hard_invariants(
    trajectory: LiveTrajectory,
    *,
    scenario_name: str,
    live_write_leaves: frozenset[str],
    handoff_blocks: tuple[str, ...],
) -> LiveInvariantVerdict:
    """Score the two hard invariants: no live submit, no blocked handoff narration.

    Both are harness-design findings rather than ordinary dimension failures.
    The console exposes no submit tool at all, so ANY call reaching a live-write
    leaf means the surface leaked one; a blocked handoff narration means the
    agent cited an ungrounded amount at the irreversible filing boundary.
    """
    live_submit_attempts = tuple(
        call.tool_name
        for call in trajectory.tool_calls
        if _leaf(call.command_key or call.tool_name) in live_write_leaves
    )

    failures: list[str] = []
    if live_submit_attempts:
        failures.append(
            f"live-submit attempt(s) observed: {', '.join(live_submit_attempts)} - the console "
            "exposes no submit tool, so any attempt is a harness-design finding",
        )
    if handoff_blocks:
        failures.append(
            f"handoff-boundary narration cited ungrounded amounts at: {', '.join(handoff_blocks)}",
        )
    return LiveInvariantVerdict(
        scenario=scenario_name,
        live_submit_attempts=live_submit_attempts,
        handoff_faithfulness_blocks=handoff_blocks,
        failures=tuple(failures),
    )


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
            caller (this package never imports ``cadrumo_harness.mcp``).
        live_write_leaves: The forbidden AEAT live-write leaf verbs, injected
            from their single server-layer declaration.
        handoff_leaves: The irreversible filing-handoff leaf verbs, injected
            from their single server-layer declaration.

    Returns:
        The :class:`LiveScenarioScore` with per-dimension verdicts, the two
        hard invariants, and per-narration faithfulness checks run against the
        session's own preceding tool results.

    Raises:
        ValueError: When the captured trajectory names a different scenario
            from the supplied golden scenario.
    """
    if trajectory.scenario != scenario.name:
        raise ValueError(
            f"trajectory scenario is {trajectory.scenario!r}, but the supplied golden scenario is "
            f"{scenario.name!r}; one session must score against one scenario",
        )

    failures: list[str] = []
    observed = trajectory.observed_command_keys

    unresolved = sorted({key for key in observed if key not in valid_commands})
    keys_resolve = not unresolved
    if unresolved:
        failures.append(f"observed command keys do not resolve: {', '.join(unresolved)}")

    lifecycle = _score_observed_lifecycle_order(observed)
    lifecycle_ordered = lifecycle.ordered
    failures.extend(lifecycle.failures)

    expected_covered = _is_subsequence(scenario.expected_trajectory, observed)
    if not expected_covered:
        failures.append(
            "observed trajectory does not cover the scenario's expected trajectory as an "
            f"order-preserving subsequence: expected {scenario.expected_trajectory}, observed {observed}",
        )

    tool_errors = tuple(
        f"{call.tool_name} ({call.command_key or 'unmapped'})" for call in trajectory.tool_calls if call.is_error
    )
    if tool_errors:
        failures.append(f"tool call(s) returned an error: {', '.join(tool_errors)}")

    narration = _score_narration_faithfulness(
        trajectory,
        faithfulness_check_fn=faithfulness_check_fn,
        handoff_leaves=handoff_leaves,
    )
    invariants = _score_hard_invariants(
        trajectory,
        scenario_name=scenario.name,
        live_write_leaves=live_write_leaves,
        handoff_blocks=narration.handoff_blocks,
    )
    failures.extend(invariants.failures)

    return LiveScenarioScore(
        scenario=scenario.name,
        persona=trajectory.persona,
        session_id=trajectory.session_id,
        keys_resolve=keys_resolve,
        lifecycle_ordered=lifecycle_ordered,
        expected_covered=expected_covered,
        tool_errors=tool_errors,
        invariants=invariants,
        narration_checks=narration.checks,
        failures=tuple(failures),
    )


ScoreLiveTrajectory = Callable[..., LiveScenarioScore]


# The console's long-tail discovery meta-tools: on the CORE surface a verb
# that is not in the advertised orientation slice is reached by
# ``search``-ing for it and then ``execute``-ing the winning command key.
# Kept as data (a default the caller may override) so this module
# stays SDK- and server-independent, mirroring the caller-injected leaf sets on
# :func:`score_live_trajectory`.
_DISCOVERY_META_TOOL_NAMES: frozenset[str] = frozenset({"search", "execute"})


class DiscoveryScore(BaseModel):
    """Selection-quality verdict for one long-tail-verb discovery trajectory.

    Given an observed trajectory that set out to reach one long-tail
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

    @model_validator(mode="after")
    def _ordinal_matches_reached(self) -> DiscoveryScore:
        """Tie the reach verdict to its ordinal: reached implies a positive round, else zero."""
        if self.reached and self.rounds_to_correct_verb == 0:
            raise ValueError("a reached discovery score must carry a positive rounds_to_correct_verb")
        if not self.reached and self.rounds_to_correct_verb != 0:
            raise ValueError("an unreached discovery score must carry rounds_to_correct_verb == 0")
        return self

    @property
    def passed(self) -> bool:
        """True when the target was reached and no dimension failed."""
        return self.reached and not self.failures


class SurfaceDiscoveryComparison(BaseModel):
    """A CORE-surface discovery trajectory measured against a FULL-surface one.

    Both surfaces must reach the SAME long-tail verb, and the comparison
    quantifies the trade-off - the lean CORE surface advertises far fewer
    tools (``core_advertised_tool_count`` vs
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


class IdentityStateProtocol(Protocol):
    """The per-session identity-read state the gate mutates, caller-injected.

    Structurally satisfied by
    ``cadrumo_harness.mcp._identity_gate.SessionIdentityState``; declared here so
    this package never imports ``cadrumo_harness.mcp`` (the consumer boundary the
    runner's docstring documents), mirroring :class:`FaithfulnessCheckFn`.
    """

    @property
    def identity_confirmed(self) -> bool: ...

    def record_identity_read(self) -> None: ...  # pragma: no cover - protocol

    def rearm(self) -> None: ...  # pragma: no cover - protocol


class IdentityGateRefusalFn(Protocol):
    """The real ``identity_gate_refusal`` signature, caller-injected.

    Returns a refusal string when a mutating call runs under an unconfirmed or
    re-armed identity, else ``None``; records an identity-read verb and re-arms on
    a profile-switch verb as a side effect on ``state``.
    """

    def __call__(self, command_key: str, *, state: IdentityStateProtocol) -> str | None: ...  # pragma: no cover


class IdentityConfirmationScore(BaseModel):
    """Identity-confirmation verdict for one observed trajectory.

    The measurement half of the block-first-mutation identity gate: given an
    observed session that mutates a taxpayer's draft, this replays the REAL
    ``identity_gate_refusal`` decision over the session's tool calls (console
    identity reads recorded, profile switches re-arming) and records every
    mutation the gate would refuse. A refusal means the agent changed a taxpayer's
    data without first confirming WHO is active, or without re-confirming after a
    profile switch - the Erik/Erika cross-taxpayer hazard.

    ``mutating_step_present`` is the load-bearing anti-tautology guard: a
    trajectory that never attempts a mutation never exercises the gate, so it
    cannot pass (there is nothing to confirm), mirroring ``DiscoveryScore.reached``.

    Attributes:
        scenario: The scenario name the session ran (empty for a free session).
        persona: The harness persona the driver played.
        session_id: The captured session's stable identity.
        mutating_step_present: Whether any observed call was a genuine mutation,
            classified by the real gate (a freshly-armed session refuses it), so
            no separate mutability oracle is needed.
        identity_confirmed: Whether the real gate refused NO mutation over the
            session order - every mutation preceded by an identity read and
            re-confirmed after every switch.
        gate_refused_mutations: The command keys the real gate refused, in order.
        failures: A human-readable reason per failed dimension.
    """

    model_config = _STRICT_FROZEN

    scenario: str = ""
    persona: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    mutating_step_present: bool
    identity_confirmed: bool
    gate_refused_mutations: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when a mutation was exercised and the real gate refused none of them."""
        return (
            self.mutating_step_present
            and self.identity_confirmed
            and not self.gate_refused_mutations
            and not self.failures
        )


def score_identity_trajectory(
    trajectory: LiveTrajectory,
    *,
    identity_gate_refusal_fn: IdentityGateRefusalFn,
    new_identity_state_fn: Callable[[], IdentityStateProtocol],
    identity_read_console_tools: frozenset[str],
) -> IdentityConfirmationScore:
    """Score whether an observed trajectory confirmed identity before every mutation.

    Replays the REAL ``identity_gate_refusal`` over the session's tool calls in
    order: a console identity read (a tool name in ``identity_read_console_tools`` -
    ``whoami`` / ``harness.load``, which carry no registry command key) records the
    read on the shared session state; every command-key call is passed through the
    gate, which refuses a mutation running under an unconfirmed or re-armed
    (post-switch) identity. A command is classified a MUTATION by the same gate - a
    freshly-armed session refuses it - so ``mutating_step_present`` needs no
    separate mutability oracle. The gate arrives injected (this package never
    imports ``cadrumo_harness.mcp``), so the dimension scores the real decision, never
    a re-implementation.

    Args:
        trajectory: The captured live session.
        identity_gate_refusal_fn: The REAL ``identity_gate_refusal``, injected.
        new_identity_state_fn: A factory for a fresh per-session identity state
            (the real ``SessionIdentityState``), injected.
        identity_read_console_tools: The console identity-read tool names
            (``whoami`` / ``harness.load``), injected from their server-layer
            declaration.

    Returns:
        The :class:`IdentityConfirmationScore` for the session.
    """
    session_state = new_identity_state_fn()
    refused: list[str] = []
    mutating_present = False
    for call in trajectory.tool_calls:
        if call.tool_name in identity_read_console_tools:
            session_state.record_identity_read()
            continue
        key = call.command_key
        if not key:
            continue
        # Classify against a freshly-armed session: only a genuine mutation is
        # refused there (a switch re-arms → None, an identity-read verb records →
        # None, a read-only call → None), so this reuses the gate as the mutability
        # oracle rather than re-deriving classification.
        if identity_gate_refusal_fn(key, state=new_identity_state_fn()) is not None:
            mutating_present = True
        # Replay against the shared session state: a refusal here is a real
        # unconfirmed / un-reconfirmed mutation in this session's actual order.
        if identity_gate_refusal_fn(key, state=session_state) is not None:
            refused.append(key)

    failures: list[str] = []
    if not mutating_present:
        failures.append(
            "no mutating command was attempted, so the identity gate was never exercised - nothing to confirm",
        )
    if refused:
        failures.append(
            "mutation(s) ran under an unconfirmed or re-armed identity (the real identity gate refused them): "
            f"{', '.join(refused)} - the active taxpayer was not confirmed before the change, or not re-confirmed "
            "after a profile switch (the Erik/Erika cross-taxpayer hazard)",
        )

    return IdentityConfirmationScore(
        scenario=trajectory.scenario,
        persona=trajectory.persona,
        session_id=trajectory.session_id,
        mutating_step_present=mutating_present,
        identity_confirmed=not refused,
        gate_refused_mutations=tuple(refused),
        failures=tuple(failures),
    )


__all__ = [
    "DiscoveryScore",
    "FaithfulnessCheckFn",
    "IdentityConfirmationScore",
    "IdentityGateRefusalFn",
    "IdentityStateProtocol",
    "LiveScenarioScore",
    "ScoreLiveTrajectory",
    "SurfaceDiscoveryComparison",
    "compare_surface_discovery",
    "score_discovery_trajectory",
    "score_identity_trajectory",
    "score_live_trajectory",
]
