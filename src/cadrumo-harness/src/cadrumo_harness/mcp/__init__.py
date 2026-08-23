"""MCP server entrypoint for the operator agent-harness.

Exposes the deterministic ``aeat`` CLI to an LLM operator as Model Context
Protocol tools, sourcing the tool list, output schemas, and mutability
annotations from the Layer 0 capability manifest. The manifest itself is served
to the operator by the MCP-native ``contract`` meta-tool
(:func:`~cadrumo_harness.mcp._meta_tools.build_capability_manifest`), which
composes the application-layer manifest builder with the CLI's registered
result-schema references. The human-in-the-loop confirmation tiers and the
faithfulness check live here too.

The protocol runtime (the MCP SDK) is an optional dependency gated behind the
``cadrumo[agent]`` extra and imported lazily by :func:`main`; the tool-building,
annotation, HITL, faithfulness, and dispatch logic in this package is
SDK-independent and fully unit-tested. A bare-core invocation of the ``cadrumo-mcp``
console script refuses with the install hint rather than crashing - the same
graceful-degradation contract every optional integration follows.

Live AEAT submission is permanently forbidden: no live-write tool is ever exposed
(enforced by test), and the CLI rails remain the deterministic backstop.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ._annotations import McpAnnotations, annotations_for_command
from ._dispatch import command_key_for_tool, tool_name_for_command, tool_request_argv
from ._faithfulness import FaithfulnessResult, faithfulness_check
from ._hitl import ConfirmationPolicy, confirmation_for_tool
from ._identity_gate import (
    IDENTITY_READ_CONSOLE_TOOLS,
    SessionIdentityState,
    identity_gate_refusal,
)
from ._persona_scope import (
    PERSONA_TOOL_SCOPES,
    AgentPersona,
    PersonaToolScope,
    is_tool_in_persona_scope,
    live_family_mutability,
    scope_for_persona,
)
from ._server import build_server
from ._tools import McpToolDescriptor, build_tool_descriptors

__all__ = [
    "IDENTITY_READ_CONSOLE_TOOLS",
    "PERSONA_TOOL_SCOPES",
    "AgentPersona",
    "ConfirmationPolicy",
    "FaithfulnessResult",
    "McpAnnotations",
    "McpToolDescriptor",
    "PersonaToolScope",
    "SessionIdentityState",
    "annotations_for_command",
    "build_server",
    "build_tool_descriptors",
    "command_key_for_tool",
    "confirmation_for_tool",
    "faithfulness_check",
    "identity_gate_refusal",
    "is_tool_in_persona_scope",
    "live_family_mutability",
    "main",
    "scope_for_persona",
    "tool_name_for_command",
    "tool_request_argv",
]


def main() -> None:
    """Console-script entry point for the ``cadrumo-mcp`` server.

    Lazily imports the MCP SDK runtime. If the ``cadrumo[agent]`` extra is not
    installed, it refuses with the install hint and a non-zero exit rather than
    raising a raw ``ModuleNotFoundError``.
    """
    from ._server import serve

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-secrets-file", type=Path)
    args = parser.parse_args()
    serve(profile_secrets_file=args.profile_secrets_file)
