"""Identity-confirmation scoring gate for the operator evaluation.

Scores whether an OBSERVED trajectory confirmed the active taxpayer identity before
every mutation, and RE-confirmed after a profile switch - the Erik/Erika hazard the
block-first-mutation gate exists to close. The dimension replays the REAL
``identity_gate_refusal`` decision over a hand-constructed :class:`LiveTrajectory`
(the injection point: this test imports the gate from the ``cadrumo_harness.mcp`` facade
and hands it to the SDK-independent scorer, which never imports ``cadrumo_harness.mcp``),
so it scores the real gate, never a re-implementation.

No mocks: every trajectory is built from the real ``LiveTrajectory`` /
``LiveToolCallRecord`` models and every decision is the real ``identity_gate_refusal``
run over a real ``SessionIdentityState`` (``aeat-quality-gates``,
``aeat-quality-gates``). The anti-tautology proof (a switch-then-mutate-without-reconfirm
trajectory MUST fail the scenario) mirrors ``test_discovery_scoring.py``'s never-reached
guard and ``test_active_profile_confirmation_golden.py``'s missing-confirmation guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo_harness.mcp import (
    IDENTITY_READ_CONSOLE_TOOLS,
    SessionIdentityState,
    build_tool_descriptors,
    identity_gate_refusal,
    tool_name_for_command,
)

from .._live_scoring import IdentityConfirmationScore, score_identity_trajectory
from .._models import LiveToolCallRecord, LiveTrajectory
from .._runner import load_scenario, run_golden_scenario
from ._real_cli_support import valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_IDENTITY_SCENARIO = _SCENARIOS_DIR / "identidad_perfil.toml"

# A genuine modelo-130 mutating verb, a profile-switching verb (re-arms the gate),
# and an identity-read verb - all resolvable registry command keys.
_MUTATING = "modelo.work.create"
_SWITCH = "config.login"
_IDENTITY_READ_VERB = "config.profile.status"

# The two console identity-read tool names (they carry no registry command key).
_WHOAMI = "cadrumo_whoami"
_HARNESS_LOAD = "cadrumo_harness_load"


def _score(trajectory: LiveTrajectory) -> IdentityConfirmationScore:
    """Score a trajectory against the REAL injected identity gate."""
    return score_identity_trajectory(
        trajectory,
        identity_gate_refusal_fn=identity_gate_refusal,
        new_identity_state_fn=SessionIdentityState,
        identity_read_console_tools=IDENTITY_READ_CONSOLE_TOOLS,
    )


def _console_read(tool_name: str) -> LiveToolCallRecord:
    # whoami / harness.load: an identity read carrying no registry command key.
    return LiveToolCallRecord(tool_name=tool_name, command_key="")


def _verb(command_key: str, *, is_error: bool = False) -> LiveToolCallRecord:
    # A per-verb tool call: the tool name is the verb's own name, the command key
    # is what the gate classifies.
    return LiveToolCallRecord(tool_name=tool_name_for_command(command_key), command_key=command_key, is_error=is_error)


def _trajectory(*calls: LiveToolCallRecord, session_id: str) -> LiveTrajectory:
    return LiveTrajectory(
        scenario="identidad-perfil-switch-reconfirm",
        persona="cadrumo-modelo-preparer",
        session_id=session_id,
        tool_calls=calls,
    )


# --------------------------------------------------------------------------- #
# The scenario is a valid, minimal GoldenScenario.
# --------------------------------------------------------------------------- #


def test_identity_scenario_loads_and_passes_the_shared_golden_dimensions() -> None:
    """The scenario is valid and passes the shared trajectory, skill, and provenance gate."""
    scenario = load_scenario(_IDENTITY_SCENARIO)
    assert scenario.name == "identidad-perfil-switch-reconfirm"
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert result.passed, result.failures


def test_scenario_constants_are_real_and_correctly_shaped() -> None:
    """Ground the test's command keys against the live descriptor policy."""
    valid = valid_cli_commands()
    assert _MUTATING in valid and _SWITCH in valid and _IDENTITY_READ_VERB in valid
    # The mutating verb is genuinely non-read-only; the switch and identity-read verbs exist.
    descriptors_by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    assert _MUTATING in descriptors_by_key
    assert not descriptors_by_key[_MUTATING].annotations.read_only_hint
    # The two console reads are the declared console identity tools.
    assert _WHOAMI in IDENTITY_READ_CONSOLE_TOOLS
    assert _HARNESS_LOAD in IDENTITY_READ_CONSOLE_TOOLS


# --------------------------------------------------------------------------- #
# Measure identity confirmation over an observed trajectory.
# --------------------------------------------------------------------------- #


def test_confirm_then_mutate_then_switch_then_reconfirm_passes() -> None:
    """PASS: confirm identity, mutate, switch profile, RE-confirm, mutate again - no gate refusal."""
    trajectory = _trajectory(
        _console_read(_WHOAMI),
        _verb(_MUTATING),
        _verb(_SWITCH),
        _console_read(_WHOAMI),
        _verb(_MUTATING),
        session_id="confirmed-switch-reconfirmed",
    )

    score = _score(trajectory)

    assert score.passed, score.failures
    assert score.mutating_step_present
    assert score.identity_confirmed
    assert score.gate_refused_mutations == ()


def test_mutation_after_switch_without_reconfirm_fails_the_scenario() -> None:
    """FAIL-catch (the Erik/Erika hazard): a mutation after a switch with no re-confirmation is refused.

    Confirm identity, mutate under the first taxpayer, switch to another taxpayer,
    then mutate WITHOUT re-confirming - the real gate (re-armed by the switch)
    refuses the post-switch mutation, so the scenario must fail and name it.
    """
    trajectory = _trajectory(
        _console_read(_WHOAMI),
        _verb(_MUTATING),
        _verb(_SWITCH),
        _verb(_MUTATING),  # under the WRONG (unconfirmed) active profile
        session_id="switch-then-mutate-unconfirmed",
    )

    score = _score(trajectory)

    assert not score.passed
    assert score.mutating_step_present
    assert not score.identity_confirmed
    assert _MUTATING in score.gate_refused_mutations
    assert any(_MUTATING in failure and "re-armed" in failure and "Erik/Erika" in failure for failure in score.failures)


def test_first_mutation_without_any_identity_read_fails() -> None:
    """FAIL-catch: a mutation with no prior identity read is refused by the real gate."""
    trajectory = _trajectory(_verb(_MUTATING), session_id="unconfirmed-first-mutation")

    score = _score(trajectory)

    assert not score.passed
    assert score.mutating_step_present
    assert not score.identity_confirmed
    assert _MUTATING in score.gate_refused_mutations


def test_identity_read_verb_also_confirms_before_a_mutation() -> None:
    """PASS: an identity-read VERB (config profile status) clears the gate just like a console read."""
    trajectory = _trajectory(
        _verb(_IDENTITY_READ_VERB),
        _verb(_MUTATING),
        session_id="verb-read-then-mutate",
    )

    score = _score(trajectory)

    assert score.passed, score.failures
    assert score.gate_refused_mutations == ()


def test_harness_load_read_also_clears_the_gate() -> None:
    """PASS: the harness.load floor read confirms identity."""
    trajectory = _trajectory(
        _console_read(_HARNESS_LOAD),
        _verb(_MUTATING),
        session_id="harness-load-then-mutate",
    )

    score = _score(trajectory)

    assert score.passed, score.failures


def test_trajectory_that_never_mutates_does_not_pass() -> None:
    """FAIL-catch (anti-tautology): a read-only trajectory never exercises the gate, so it cannot pass."""
    trajectory = _trajectory(
        _console_read(_WHOAMI),
        _verb(_IDENTITY_READ_VERB),
        session_id="never-mutates",
    )

    score = _score(trajectory)

    assert not score.passed
    assert not score.mutating_step_present
    assert any("nothing to confirm" in failure for failure in score.failures)


def test_identity_confirmation_score_is_a_frozen_strict_model() -> None:
    """The verdict is immutable (the eval's strict-frozen contract), so a score cannot be mutated after the fact."""
    score = _score(_trajectory(_console_read(_WHOAMI), _verb(_MUTATING), session_id="frozen"))
    assert isinstance(score, IdentityConfirmationScore)
    with pytest.raises(ValueError, match="frozen"):
        score.identity_confirmed = False  # type: ignore[misc]
