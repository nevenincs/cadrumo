"""Tests for the search/execute meta-tools and server capability registration.

Exercised against the live descriptor set and the real MCP SDK - no mocks of the
CLI or the SDK. The injected ``run`` callable in the execute tests is the genuine
dependency-injection seam the server uses, so isolating meta-execute's control
flow from the subprocess is unit isolation, not a service double.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import pytest

from ....application.operator_surface import COMMAND_RISK, CommandRiskDeclaration
from ....core import PRODUCT_IDENTITY
from .._annotations import McpAnnotations
from .._input_schema import VerbInputSchema
from .._meta_tools import (
    MetaDescribeResult,
    ToolRunOutcome,
    describe_command,
    gate_refusal,
    meta_execute,
    search_commands,
    search_commands_response,
)
from .._persona_scope import AgentPersona
from .._server import (
    build_meta_sdk_tools,
    build_server,
    persona_scope_refusal,
)
from .._tools import McpToolDescriptor, build_tool_descriptors
from .._transport import _run_subprocess_tool

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _blocked_descriptor() -> McpToolDescriptor:
    """A synthetic descriptor whose leaf triggers the permanent live-write block."""
    return McpToolDescriptor(
        name="cadrumo_x_submit",
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
    # A search hit is self-sufficient: it carries the per-verb input
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


@contextlib.contextmanager
def _declared_live_write(command_key: str) -> Iterator[None]:
    """Declare ``command_key`` a live-write in the risk table for the test body.

    A live-write BLOCK now fires from the DECLARED risk table, not a leaf-name
    heuristic: no real command declares live_write
    (never-submit is enforced as "no such tool exists"), so a test that exercises
    the defensive BLOCK branch must supply a declared live-write row and restore
    the table after - test data, not a mocked behaviour.
    """
    previous = COMMAND_RISK.get(command_key)
    COMMAND_RISK[command_key] = CommandRiskDeclaration(live_write=True)
    try:
        yield
    finally:
        if previous is None:
            COMMAND_RISK.pop(command_key, None)
        else:
            COMMAND_RISK[command_key] = previous


def test_gate_refusal_blocks_a_declared_live_write_command() -> None:
    with _declared_live_write("x.submit"):
        assert gate_refusal(persona=None, descriptor=_blocked_descriptor()) == (
            "refused: AEAT live-write is permanently forbidden"
        )


def test_meta_execute_never_reaches_the_runner_on_a_blocked_command() -> None:
    def boom(descriptor: McpToolDescriptor, arguments: dict[str, object]) -> ToolRunOutcome:
        raise AssertionError("the runner must not be reached for a blocked command")

    blocked = _blocked_descriptor()
    with _declared_live_write("x.submit"):
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
    def boom(descriptor: McpToolDescriptor, arguments: dict[str, object]) -> ToolRunOutcome:
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


def test_build_meta_sdk_tools_exposes_search_execute_toolsets_and_describe() -> None:
    tools = build_meta_sdk_tools()
    names = {tool.name for tool in tools}
    assert names == {"search", "execute", "toolsets", "describe"}
    for tool in tools:
        assert tool.inputSchema["type"] == "object"
    product_descriptions = [tool.description for tool in tools if tool.name in {"search", "execute", "describe"}]
    for description in product_descriptions:
        assert description is not None
        assert "Cadrumo command" in description
        assert "aeat command" not in description.lower()


def test_server_uses_the_canonical_cadrumo_identity() -> None:
    server = build_server(())
    assert server.name == PRODUCT_IDENTITY.mcp_server


def test_describe_command_returns_the_full_descriptor_for_a_known_key() -> None:
    descriptors = build_tool_descriptors()
    described = describe_command("modelo.export", descriptors=descriptors)
    assert isinstance(described, MetaDescribeResult)
    assert described.command_key == "modelo.export"
    # modelo.export is a filing handoff: it carries the handoff risk, sits in the
    # modelo-lifecycle toolset, and confirms rather than auto-approves.
    assert described.owning_toolset == "modelo-lifecycle"
    assert described.confirmation_tier == "confirm"
    assert described.risk_handoff is True
    assert described.risk_live_write is False
    # The schema rides along so the caller can build the argument form in one hop.
    by_key = {descriptor.command_key: descriptor for descriptor in descriptors}
    assert described.input_schema == by_key["modelo.export"].input_schema
    # The verifier owns the handoff; the preparer and reconciler are structurally
    # denied it, so they are absent from the reachable set while the verifier is in.
    assert "verifier" in described.reachable_personas
    assert "modelo-preparer" not in described.reachable_personas
    assert "reconciler" not in described.reachable_personas


def test_describe_command_returns_none_for_an_unknown_key() -> None:
    descriptors = build_tool_descriptors()
    assert describe_command("not.a.command", descriptors=descriptors) is None


def test_search_commands_response_flags_a_truncated_broad_query() -> None:
    descriptors = build_tool_descriptors()
    broad = search_commands_response("modelo", descriptors=descriptors, limit=5)
    assert broad.truncated is True
    assert broad.total_matches >= len(broad.results)
    assert broad.total_matches > len(broad.results)
    assert broad.hint
    assert "describe" in broad.hint


def test_search_commands_response_does_not_flag_a_specific_query() -> None:
    descriptors = build_tool_descriptors()
    specific = search_commands_response("iva wallet balance", descriptors=descriptors, limit=20)
    assert specific.results
    assert specific.truncated is False
    assert specific.hint == ""
    assert specific.total_matches == len(specific.results)


def test_search_commands_response_returns_the_empty_response_for_a_blank_query() -> None:
    descriptors = build_tool_descriptors()
    empty = search_commands_response("   ", descriptors=descriptors)
    assert empty.results == ()
    assert empty.total_matches == 0
    assert empty.truncated is False
    assert empty.hint == ""


def test_build_server_advertises_tools_prompts_and_resources() -> None:
    from mcp.server.lowlevel import NotificationOptions

    server = build_server(build_tool_descriptors(), persona=None)
    capabilities = server.get_capabilities(NotificationOptions(), {})
    assert capabilities.tools is not None
    assert capabilities.prompts is not None
    assert capabilities.resources is not None
