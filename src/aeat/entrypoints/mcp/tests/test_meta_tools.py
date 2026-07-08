"""Tests for the search/execute meta-tools and server capability registration.

Exercised against the live descriptor set and the real MCP SDK - no mocks of the
CLI or the SDK. The injected ``run`` callable in the execute tests is the genuine
dependency-injection seam the server uses, so isolating meta-execute's control
flow from the subprocess is unit isolation, not a service double.
"""

from __future__ import annotations

import pytest

from .._annotations import McpAnnotations
from .._input_schema import VerbInputSchema
from .._meta_tools import gate_refusal, meta_execute, search_commands
from .._persona_scope import AgentPersona
from .._server import (
    _run_subprocess_tool,
    build_meta_sdk_tools,
    build_server,
    persona_scope_refusal,
)
from .._tools import McpToolDescriptor, build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _blocked_descriptor() -> McpToolDescriptor:
    """A synthetic descriptor whose leaf triggers the permanent live-write block."""
    return McpToolDescriptor(
        name="aeat_x_submit",
        command_key="x.submit",
        description="synthetic live-write",
        input_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        output_schema={"type": "object"},
        annotations=McpAnnotations(
            title="x submit", read_only_hint=False, destructive_hint=False, idempotent_hint=False
        ),
        verb_schema=VerbInputSchema(command_key="x.submit", cli_path=("app", "x", "submit"), parameters=()),
    )


def test_search_ranks_a_named_verb_above_a_mention() -> None:
    descriptors = build_tool_descriptors()
    results = search_commands("iva wallet balance", descriptors=descriptors, limit=5)
    assert results
    assert results[0].command_key == "modelo.iva_wallet.balance"
    # The mutability hints ride on the result so the caller sees them before execute.
    assert results[0].read_only is False
    # An empty query matches nothing rather than the whole surface.
    assert search_commands("", descriptors=descriptors) == ()


def test_search_results_carry_the_input_schema_so_they_are_actionable() -> None:
    # ADR P2: a search hit is self-sufficient - it carries the per-verb input
    # schema, so a model can call ``execute`` in one further round-trip without a
    # separate schema lookup.
    descriptors = build_tool_descriptors()
    results = search_commands("calculate modelo work", descriptors=descriptors, limit=5)
    assert results
    top = results[0]
    assert top.command_key == "modelo.work.calculate"
    by_key = {descriptor.command_key: descriptor for descriptor in descriptors}
    assert top.input_schema == by_key[top.command_key].input_schema
    assert top.input_schema.get("type") == "object"


def test_search_folds_plurals_and_diacritics_over_the_real_surface() -> None:
    # The index-backed search folds morphology over the real command corpus: a
    # query token in a different number/accent form than the command's own tokens
    # still ranks it (the deterministic cross-vocabulary proof over a controlled
    # corpus lives in the command_search unit tests).
    descriptors = build_tool_descriptors()
    results = search_commands("list the modelos", descriptors=descriptors, limit=8)
    keys = {result.command_key for result in results}
    assert "modelo.list" in keys


def test_gate_refusal_matches_the_direct_path_for_every_scoped_refusal() -> None:
    descriptors = build_tool_descriptors()
    persona = AgentPersona.RECONCILER
    refused = 0
    for descriptor in descriptors:
        direct = persona_scope_refusal(persona=persona, command_key=descriptor.command_key)
        meta = gate_refusal(persona=persona, descriptor=descriptor)
        if direct is not None:
            assert meta == direct
            refused += 1
    # The parity assertion is only meaningful if the persona actually refuses some.
    assert refused > 0


def test_gate_refusal_blocks_a_live_write_leaf() -> None:
    assert gate_refusal(persona=None, descriptor=_blocked_descriptor()) == (
        "refused: AEAT live-write is permanently forbidden"
    )


def test_meta_execute_never_reaches_the_runner_on_a_blocked_command() -> None:
    def boom(descriptor: McpToolDescriptor, arguments: dict[str, object]) -> tuple[dict[str, object], bool]:
        raise AssertionError("the runner must not be reached for a blocked command")

    blocked = _blocked_descriptor()
    outcome = meta_execute("x.submit", {}, descriptors=(blocked,), persona=None, run=boom)
    assert outcome.refused == "refused: AEAT live-write is permanently forbidden"
    assert outcome.envelope is None


def test_meta_execute_refuses_an_unknown_command() -> None:
    outcome = meta_execute("not.a.command", {}, descriptors=(), persona=None, run=_run_subprocess_tool)
    assert outcome.refused == "unknown command: not.a.command"


def test_gate_refusal_denies_the_handoff_boundary_to_a_non_verifier_persona() -> None:
    # MEDIUM-2 close-review finding: the per-verb handoff deny (verifier-only
    # export/record-marker) must be enforced STRUCTURALLY in gate_refusal, so the
    # meta-execute path cannot become a side door to it — not left masked by the
    # sync path's incidental no-elicitation fallback.
    descriptors = build_tool_descriptors()
    # modelo.export is IN the preparer/reconciler scope (modelo family) yet
    # handoff-denied, so it exercises the handoff rule rather than a scope
    # refusal masking it.
    export = next(d for d in descriptors if d.command_key == "modelo.export")
    for persona in (AgentPersona.MODELO_PREPARER, AgentPersona.RECONCILER):
        refusal = gate_refusal(persona=persona, descriptor=export)
        assert refusal is not None
        assert "verifier" in refusal
    # The verifier — the sole owner — is NOT denied it by the handoff rule.
    verifier_refusal = gate_refusal(persona=AgentPersona.VERIFIER, descriptor=export)
    assert verifier_refusal is None or "verifier" not in verifier_refusal


def test_meta_execute_never_reaches_the_runner_on_a_handoff_denied_command() -> None:
    def boom(descriptor: McpToolDescriptor, arguments: dict[str, object]) -> tuple[dict[str, object], bool]:
        raise AssertionError("the runner must not be reached for a handoff-denied command")

    descriptors = build_tool_descriptors()
    export = next(d for d in descriptors if d.command_key == "modelo.export")
    outcome = meta_execute(
        export.command_key,
        {},
        descriptors=descriptors,
        persona=AgentPersona.MODELO_PREPARER,
        run=boom,
    )
    assert outcome.refused is not None
    assert "verifier" in outcome.refused
    assert outcome.envelope is None


def test_meta_execute_dispatches_a_read_only_command_end_to_end() -> None:
    descriptors = build_tool_descriptors()
    outcome = meta_execute("contract", {}, descriptors=descriptors, persona=None, run=_run_subprocess_tool)
    assert outcome.refused is None
    assert outcome.envelope is not None
    assert outcome.envelope.get("command") == "contract"
    assert outcome.is_error is False


def test_build_meta_sdk_tools_exposes_search_execute_and_toolsets() -> None:
    tools = build_meta_sdk_tools()
    names = {tool.name for tool in tools}
    assert names == {"search", "execute", "toolsets"}
    for tool in tools:
        assert tool.inputSchema["type"] == "object"


def test_build_server_advertises_tools_prompts_and_resources() -> None:
    from mcp.server.lowlevel import NotificationOptions

    server = build_server(build_tool_descriptors(), persona=None)
    capabilities = server.get_capabilities(NotificationOptions(), {})
    assert capabilities.tools is not None
    assert capabilities.prompts is not None
    assert capabilities.resources is not None
