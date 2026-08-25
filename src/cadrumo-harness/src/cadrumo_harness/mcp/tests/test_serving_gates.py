"""Serving-path gate tests over the real ``build_server`` handlers.

Drives the real MCP server in-process through the SDK's memory transport
(:func:`cadrumo_harness.mcp.tests.session.connected_server_and_client_session`) - a real client, a
real server, no mocks - for the gates that short-circuit before the CLI subprocess: the
persona handoff-deny boundary, the handoff faithfulness block, the meta-execute
fail-close, and payload-free telemetry. The post-dispatch advisory and the
grounding-window pass are exercised against the exact serving-path gate functions
``build_server`` calls (``SessionGroundingWindow`` / ``arguments_faithfulness``),
because a successful CLI dispatch needs a provisioned profile + secret store the
spawned ``aeat`` subprocess cannot reach in a focused gate test.

Amount tokens use the ``NNN.NN`` shape the faithfulness matcher recognises (a
four-digit undelimited integer like ``1234.56`` is deliberately NOT amount-shaped).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine, Mapping
from pathlib import Path

import mcp.types as mcp_types
import pytest
from mcp.client.session import ElicitationFnT

from .._dispatch import tool_name_for_command
from .._faithfulness import SessionGroundingWindow, arguments_faithfulness
from .._persona_scope import AgentPersona
from .._server import build_server
from .._surface import SurfaceMode
from .._telemetry import SessionTelemetryWriter, read_session_records
from .._tools import build_tool_descriptors
from .session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UNGROUNDED_AMOUNT = "500.00"
_EXPORT_TOOL = tool_name_for_command("modelo.export")
_FILE_TOOL = tool_name_for_command("modelo.work.file")
_DESCRIBE_TOOL = tool_name_for_command("modelo.describe")


def _run[T](coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(coro)


async def _accept_confirmation(
    context: object,
    params: object,
) -> mcp_types.ElicitResult:
    return mcp_types.ElicitResult(action="accept", content={"confirm": True})


async def _decline_confirmation(
    context: object,
    params: object,
) -> mcp_types.ElicitResult:
    return mcp_types.ElicitResult(action="decline", content=None)


async def _cancel_confirmation(
    context: object,
    params: object,
) -> mcp_types.ElicitResult:
    return mcp_types.ElicitResult(action="cancel", content=None)


async def _accept_but_unconfirmed(
    context: object,
    params: object,
) -> mcp_types.ElicitResult:
    # An "accept" whose confirm flag is false: the malformed / half-hearted
    # confirmation the degradation matrix must still treat as a refusal.
    return mcp_types.ElicitResult(action="accept", content={"confirm": False})


async def _list_tool_names(persona: AgentPersona | None) -> set[str]:
    # FULL surface: this helper asserts the persona-scope and handoff-deny
    # filtering of the per-verb tool list, a property that only manifests when
    # the per-verb tools are actually advertised. The default-surface policy
    # (CORE advertises only the orientation slice) is owned by
    # ``test_surface_policy.py``; here it must not hide the verbs under test.
    server = build_server(build_tool_descriptors(), persona=persona, surface_mode=SurfaceMode.FULL)
    async with connect(server) as session:
        listed = await session.list_tools()
        return {tool.name for tool in listed.tools}


async def _call(
    persona: AgentPersona | None,
    name: str,
    arguments: Mapping[str, object],
    *,
    elicit: ElicitationFnT | None = None,
    telemetry: SessionTelemetryWriter | None = None,
) -> mcp_types.CallToolResult:
    server = build_server(build_tool_descriptors(), persona=persona, telemetry=telemetry)
    async with connect(server, elicitation_callback=elicit) as session:
        # Clear the block-first-mutation identity gate with a real
        # whoami identity read so these serving-path gate tests reach the
        # confirm / faithfulness gate under test rather than the identity gate.
        # whoami is a read-only console tool that emits no telemetry, so record
        # counts are unaffected.
        await session.call_tool("cadrumo_whoami", {})
        return await session.call_tool(name, dict(arguments))


def _texts(result: mcp_types.CallToolResult) -> list[str]:
    return [block.text for block in result.content if isinstance(block, mcp_types.TextContent)]


def test_handoff_leaves_are_denied_to_preparer_and_reconciler_but_not_verifier() -> None:
    preparer = _run(_list_tool_names(AgentPersona.MODELO_PREPARER))
    reconciler = _run(_list_tool_names(AgentPersona.RECONCILER))
    verifier = _run(_list_tool_names(AgentPersona.VERIFIER))
    for denied in (preparer, reconciler):
        assert _EXPORT_TOOL not in denied
        assert _FILE_TOOL not in denied
    assert _EXPORT_TOOL in verifier
    assert _FILE_TOOL in verifier


def test_direct_denied_handoff_call_refuses_with_the_denial_message() -> None:
    result = _run(_call(AgentPersona.MODELO_PREPARER, _EXPORT_TOOL, {}))
    assert result.is_error
    text = "\n".join(_texts(result))
    # The denial names the command and the owning verifier persona (interpolated).
    assert "modelo.export" in text
    assert AgentPersona.VERIFIER.value in text


def test_faithfulness_blocks_an_ungrounded_amount_at_a_handoff_verb() -> None:
    # A handoff verb (leaf ``file``) reached with an accepting elicitation, whose
    # arguments cite an amount no tool result in this session produced, is blocked
    # BEFORE dispatch - the block returns the advisory and never runs the CLI.
    result = _run(
        _call(None, _FILE_TOOL, {"notes": _UNGROUNDED_AMOUNT}, elicit=_accept_confirmation),
    )
    assert result.is_error
    text = "\n".join(_texts(result))
    assert _UNGROUNDED_AMOUNT in text
    # A block returns a single advisory content block, not a dispatched envelope.
    assert len(result.content) == 1


def test_faithfulness_advises_without_blocking_on_a_non_handoff_verb() -> None:
    # A non-handoff read carrying an ungrounded amount proceeds PAST the gate to
    # dispatch (two content blocks: the advisory, then the CLI envelope), rather
    # than being blocked - the advisory is a warning, not a refusal.
    result = _run(_call(None, _DESCRIBE_TOOL, {"modelo": "130", "as_of": _UNGROUNDED_AMOUNT}))
    text = "\n".join(_texts(result))
    assert _UNGROUNDED_AMOUNT in text
    assert len(result.content) == 2
    # The gate itself never blocks a non-handoff mismatch (advisory, isError false).
    window = SessionGroundingWindow()
    verdict = arguments_faithfulness(
        arguments_json=json.dumps({"as_of": _UNGROUNDED_AMOUNT}),
        window=window,
        blocking=False,
    )
    assert verdict.faithful is False
    assert verdict.blocks is False


def test_grounding_window_makes_a_previously_returned_figure_pass() -> None:
    # The serving-path grounding gate build_server calls: a figure a prior tool
    # result produced grounds a later call's arguments; an empty window blocks it
    # at the handoff boundary.
    window = SessionGroundingWindow()
    empty = arguments_faithfulness(
        arguments_json=json.dumps({"notes": _UNGROUNDED_AMOUNT}),
        window=window,
        blocking=True,
    )
    assert empty.blocks is True
    window.record(json.dumps({"casilla_07": _UNGROUNDED_AMOUNT}))
    grounded = arguments_faithfulness(
        arguments_json=json.dumps({"notes": _UNGROUNDED_AMOUNT}),
        window=window,
        blocking=True,
    )
    assert grounded.faithful is True
    assert grounded.blocks is False


def test_telemetry_records_payload_free_rows(tmp_path: Path) -> None:
    writer = SessionTelemetryWriter(session_id="serving-gates-test", directory=tmp_path)
    # A successful read-only dispatch (contract needs no storage) plus a
    # faithfulness-blocked handoff whose arguments carry a real amount.
    _run(_call(None, tool_name_for_command("registry.inspect"), {}, telemetry=writer))
    _run(_call(None, _FILE_TOOL, {"notes": _UNGROUNDED_AMOUNT}, elicit=_accept_confirmation, telemetry=writer))

    raw = writer.path.read_text(encoding="utf-8")
    records = read_session_records(writer.path)
    assert len(records) == 2
    assert any(len(record.executable_sha256) == 64 for record in records)
    # A content hash is present ...
    assert any(len(record.arguments_sha256) == 64 for record in records)
    # ... but neither the raw amount argument nor the contract result payload is.
    assert _UNGROUNDED_AMOUNT not in raw
    assert "command_families" not in raw
    assert "manifest_version" not in raw


@pytest.mark.parametrize(
    ("elicit", "outcome_token"),
    [
        (_decline_confirmation, "refused_declined"),
        (_cancel_confirmation, "refused_cancelled"),
        (_accept_but_unconfirmed, "refused_not_confirmed"),
    ],
)
def test_confirm_elicitation_refuses_over_the_wire_when_not_confirmed(
    elicit: ElicitationFnT,
    outcome_token: str,
) -> None:
    # e2e over the memory-transport wire: a handoff verb (leaf ``export``) routes
    # to the CONFIRM elicitation tier, the server elicits the client, and the
    # client answers with a non-proceed action. The gate must refuse BEFORE any
    # dispatch — decline, cancel, and accept-without-confirm all fail closed.
    result = _run(_call(None, _EXPORT_TOOL, {}, elicit=elicit))
    assert result.is_error
    text = "\n".join(_texts(result))
    assert "modelo.export" in text
    # The refusal is the not-confirmed message carrying the concrete decision,
    # not a dispatched CLI envelope (a refusal is a single content block).
    assert outcome_token in text
    assert len(result.content) == 1


def test_confirm_elicitation_records_the_declined_route_in_telemetry(tmp_path: Path) -> None:
    # The declined round-trip is telemetered payload-free with the route label
    # carrying the decision, proving the gate fired (not a silent pass).
    writer = SessionTelemetryWriter(session_id="confirm-decline-test", directory=tmp_path)
    _run(_call(None, _EXPORT_TOOL, {}, elicit=_decline_confirmation, telemetry=writer))
    records = read_session_records(writer.path)
    assert len(records) == 1
    assert records[0].is_error is True
    assert "refused_declined" in records[0].route


def test_meta_execute_fail_closes_a_handoff_tier_confirm() -> None:
    # The meta path runs synchronously (no elicitation channel), so a handoff-tier
    # CONFIRM fails closed with the no-channel refusal rather than proceeding.
    result = _run(_call(None, "execute", {"command_key": "modelo.export", "arguments": {}}))
    assert result.is_error
    assert "modelo.export" in "\n".join(_texts(result))
