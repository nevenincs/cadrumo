"""HITL confirmation gate wiring for the operator golden-task eval.

Guards against a HITL / confirmation bypass: an autonomous
agent optimising for completion may pass ``--yes``, a failure mode no human
persona would reproduce (a human has no reason to bypass their own
confirmation). The ``PreToolUse`` gate is the operator-facing, granular half
of the defense-in-depth against that risk (the CLI's own ``--yes`` /
write-policy / ``LiveSubmitForbiddenError`` rails are the deterministic
backstop beneath it).

``src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_hitl_and_live_write.py`` already proves the
pure ``confirmation_for_tool`` function returns the right enum for a handful of
command keys in isolation. This module proves the stronger claim: the gate sits
IN FRONT of the dispatched call (it is evaluated,
and evaluated correctly, before the tool's own arguments are ever read - so an
auto-yes-equivalent argument riding along on the tool call cannot influence it),
and that claim is wired into a real golden-scenario run via the caller-injected
``ConfirmationGateCheck`` dimension, mirroring exactly how
``test_faithfulness_golden.py`` injects the faithfulness verdict and
``test_response_provenance_golden.py`` injects ``response_observations``.

No mocks: every decision is the real ``confirmation_for_tool`` called against
real ``McpAnnotations`` built by the real ``build_tool_descriptors`` /
``annotations_for_command``, and the argument-independence proof drives the real
MCP server over an in-memory client session instead of asserting a hand-rolled
boolean (``aeat-quality-gates``, ``aeat-quality-gates``).

See Also:
    :mod:`~cadrumo_harness.mcp._hitl`
        Human-in-the-loop confirmation policy projected onto MCP tool calls.
    :class:`~agent.eval.ConfirmationGateCheck`
        Caller-injected golden-eval verdict that records expected and actual
        confirmation tiers.
    :func:`~agent.eval.run_golden_scenario`
        Golden runner that fails a scenario when an injected confirmation tier
        mismatches.

The MCP harness wires confirmation gates into its serving behavior and
enforces the live-write prohibition at that same layer.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Coroutine, Mapping
from pathlib import Path

import mcp.types as mcp_types
import pytest
from cadrumo_harness.mcp import (
    ConfirmationPolicy,
    McpToolDescriptor,
    build_server,
    build_tool_descriptors,
    confirmation_for_tool,
)

from cadrumo.tests import connected_server_and_client_session as connect
from cadrumo.tests.declared_command_risk import declared_live_write

from .. import ConfirmationGateCheck, ConfirmationTier, load_scenario, run_golden_scenario
from ._real_cli_support import valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_SCENARIO_PATH = _SCENARIOS_DIR / "modelo_130.toml"

# The scenario's expected_trajectory carries a real filing-handoff step
# ("modelo.export") and a real routine calculate step ("modelo.work.calculate").
_EXPORT_STEP = "modelo.export"
_CALCULATE_STEP = "modelo.work.calculate"
# Not an exposed tool anywhere in the command set (the live tree is read-only and
# live submission is permanently forbidden) - a hypothetical live-write leaf, kept
# consistent with cadrumo_harness/mcp/tests/test_hitl_and_live_write.py's own
# defensive proof.
_HYPOTHETICAL_LIVE_WRITE_STEP = "modelo.work.submit"


def _descriptors_by_command_key() -> dict[str, McpToolDescriptor]:
    return {d.command_key: d for d in build_tool_descriptors()}


def _tier(policy: ConfirmationPolicy) -> ConfirmationTier:
    """Round-trip a real ``ConfirmationPolicy`` verdict into the local mirror enum."""
    return ConfirmationTier(policy.value)


def _run[T](coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(coro)


async def _call_tool(name: str, arguments: Mapping[str, object]) -> mcp_types.CallToolResult:
    server = build_server(build_tool_descriptors(), persona=None)
    async with connect(server) as session:
        # Clear the block-first-mutation identity gate through the public identity read.
        # I2) with a real whoami identity read, so this confirmation-gate proof reaches
        # the CONFIRM tier under test rather than the identity gate in front of it.
        await session.call_tool("cadrumo_whoami", {})
        return await session.call_tool(name, dict(arguments))


def _texts(result: mcp_types.CallToolResult) -> list[str]:
    return [block.text for block in result.content if isinstance(block, mcp_types.TextContent)]


def test_export_handoff_confirms_and_is_argument_independent() -> None:
    """The export handoff step resolves CONFIRM and cannot be bypassed by an auto-yes arg.

    Three independent proofs, not one:

    1. Behavioural: the real ``confirmation_for_tool`` returns CONFIRM for
       ``modelo.export``.
    2. Structural (signature): ``confirmation_for_tool`` accepts ``command_key``
       and nothing else - no ``arguments``/``args`` and no per-call annotations -
       so no call-supplied value can be threaded into the decision by construction.
    3. Serving behaviour: the real MCP server refuses an export handoff carrying
       an auto-yes-shaped argument when no elicitation channel is available,
       returning a refusal instead of a dispatched CLI envelope.
    """
    descriptor = _descriptors_by_command_key()[_EXPORT_STEP]

    # Two MCP call-tool `arguments` payloads an agent optimising for task
    # completion could plausibly send under the per-verb schema: a plain call, and
    # one carrying an auto-yes-equivalent named argument riding along (the CLI
    # exposes a confirmation flag for a human operator to skip a prompt; an
    # autonomous agent could supply it to itself just as easily).
    plain_arguments: dict[str, object] = {}
    auto_yes_arguments: dict[str, object] = {"actor": "--yes"}

    assert set(inspect.signature(confirmation_for_tool).parameters) == {"command_key"}, (
        "confirmation_for_tool must derive its decision from command identity "
        "alone; no call-arguments or per-call annotation parameter may be accepted"
    )

    decision_plain = confirmation_for_tool(command_key=descriptor.command_key)
    # The (unread) arguments payloads are irrelevant to the call above by
    # construction - demonstrated, not merely asserted, by resolving the SAME
    # decision a second time after "receiving" the auto-yes payload.
    assert plain_arguments != auto_yes_arguments
    decision_auto_yes = confirmation_for_tool(command_key=descriptor.command_key)

    assert decision_plain is ConfirmationPolicy.CONFIRM
    assert decision_auto_yes is ConfirmationPolicy.CONFIRM
    assert decision_plain is decision_auto_yes

    result = _run(_call_tool(descriptor.name, auto_yes_arguments))
    assert result.is_error
    text = "\n".join(_texts(result))
    assert _EXPORT_STEP in text
    assert len(result.content) == 1
    assert result.structured_content is None


def test_read_step_auto_approves() -> None:
    """A routine calculate step in the trajectory resolves AUTO_APPROVE.

    A non-destructive, non-handoff step must
    not be needlessly gated - over-gating trains operators to rubber-stamp
    confirmations, which is its own bypass risk.
    """
    descriptor = _descriptors_by_command_key()[_CALCULATE_STEP]
    decision = confirmation_for_tool(command_key=descriptor.command_key)
    assert decision is ConfirmationPolicy.AUTO_APPROVE


def test_hypothetical_live_write_leaf_blocks_unconditionally() -> None:
    """A declared live-write command resolves BLOCK regardless of its family mutability.

    If a live-write verb ever entered the
    exposed command set, the gate refuses it outright rather than falling through
    to CONFIRM - the strongest tier, requiring no human approval loop to bypass.
    The BLOCK derives from the DECLARED ``live_write`` axis, which forces the command non-read-only
    whatever its family mutability, so the outcome does not depend on getting the
    mutability classification right.
    """
    with declared_live_write(_HYPOTHETICAL_LIVE_WRITE_STEP):
        decision = confirmation_for_tool(command_key=_HYPOTHETICAL_LIVE_WRITE_STEP)
        assert decision is ConfirmationPolicy.BLOCK


def test_confirmation_gate_wired_into_golden_scenario_passes_when_tiers_match() -> None:
    """All three confirmation-gate checks wired into a real M130 golden run pass together.

    Mirrors ``test_faithfulness_golden.py``'s wiring pattern: the real
    ``confirmation_for_tool`` decisions are resolved here (the test), packaged as
    :class:`ConfirmationGateCheck` rows, and injected into
    ``run_golden_scenario`` via ``expected_confirmation_tiers`` - the runner
    itself never imports ``cadrumo_harness.mcp`` or resolves a tier.
    """
    export_descriptor = _descriptors_by_command_key()[_EXPORT_STEP]
    calculate_descriptor = _descriptors_by_command_key()[_CALCULATE_STEP]

    with declared_live_write(_HYPOTHETICAL_LIVE_WRITE_STEP):
        live_write_tier = _tier(confirmation_for_tool(command_key=_HYPOTHETICAL_LIVE_WRITE_STEP))

    checks = (
        ConfirmationGateCheck(
            step=_EXPORT_STEP,
            expected_tier=ConfirmationTier.CONFIRM,
            actual_tier=_tier(confirmation_for_tool(command_key=export_descriptor.command_key)),
        ),
        ConfirmationGateCheck(
            step=_CALCULATE_STEP,
            expected_tier=ConfirmationTier.AUTO_APPROVE,
            actual_tier=_tier(confirmation_for_tool(command_key=calculate_descriptor.command_key)),
        ),
        ConfirmationGateCheck(
            step=_HYPOTHETICAL_LIVE_WRITE_STEP,
            expected_tier=ConfirmationTier.BLOCK,
            actual_tier=live_write_tier,
        ),
    )
    for check in checks:
        assert check.matches, check

    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        expected_confirmation_tiers=checks,
    )

    assert result.passed, result.failures
    assert result.expected_confirmation_tiers == checks


def test_confirmation_gate_mismatch_fails_the_scenario() -> None:
    """Anti-tautology proof: a mismatched tier fails the scenario, not just the check.

    A confirmation-gate dimension that always reports ``matches=True`` regardless
    of the real decision would make ``ConfirmationGateCheck`` decorative. This
    proves a genuine mismatch (declaring the export handoff step AUTO_APPROVE
    when the real gate resolves CONFIRM) fails ``run_golden_scenario`` and names
    the offending step in ``failures``.
    """
    export_descriptor = _descriptors_by_command_key()[_EXPORT_STEP]
    actual = confirmation_for_tool(command_key=export_descriptor.command_key)
    assert actual is ConfirmationPolicy.CONFIRM, "fixture drift: the export step is expected to require confirmation"

    mismatched_check = ConfirmationGateCheck(
        step=_EXPORT_STEP,
        expected_tier=ConfirmationTier.AUTO_APPROVE,
        actual_tier=_tier(actual),
    )
    assert not mismatched_check.matches

    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        expected_confirmation_tiers=(mismatched_check,),
    )

    assert not result.passed
    assert any(_EXPORT_STEP in failure and "confirmation tier" in failure for failure in result.failures)


def test_confirmation_gate_dimension_holds_trivially_when_not_checked() -> None:
    """No injected checks -> the dimension holds trivially, no other check regresses.

    ``run_golden_scenario`` never resolves a confirmation tier itself (mirrors the
    ``narration_faithfulness_checks`` / ``response_observations`` injection
    pattern); this proves the new parameter's empty-tuple default does not
    silently fail every existing scenario run.
    """
    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert result.expected_confirmation_tiers == ()
    assert result.passed, result.failures
