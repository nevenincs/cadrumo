"""The direct dispatch path composes a gate refusal exactly once.

The ``_call_tool`` direct per-verb path and the ``execute`` meta-path
share ONE persona-scope / handoff / permanent-live-write gate,
:func:`~cadrumo_harness.mcp._meta_tools.gate_refusal`. Previously the
direct path re-derived that decision inline (a second ``persona_scope_refusal``
plus ``is_handoff_denied`` composition running alongside the shared
``gate_refusal`` the meta-path already used), so the same refusal was composed in
two places and could silently diverge. These tests drive the REAL server call
handler (never a mock) and prove a refused direct-dispatch call carries exactly
one refusal - the plain shared-gate string, not a doubly-wrapped envelope - and
that the direct and execute paths return byte-identical refusals from the single
composition site.
"""

from __future__ import annotations

from typing import Any, cast

import anyio
import pytest

from .._dispatch import tool_name_for_command
from .._meta_tools import gate_refusal
from .._persona_scope import AgentPersona
from .._tools import build_tool_descriptors
from ._session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

try:  # the SDK-gated build path, exercised without a skip either way
    import mcp.server  # noqa: F401

    _SDK_PRESENT = True
except ModuleNotFoundError:
    _SDK_PRESENT = False

# A verb OUTSIDE the coordinator persona's scope (a scope refusal) and a verb
# INSIDE the preparer's modelo scope yet handoff-denied to it (a handoff
# refusal) - the two distinct gate_refusal branches the direct path must route
# through the shared composition.
_SCOPE_PERSONA = AgentPersona.COORDINATOR
_SCOPE_KEY = "ledger.add"
_HANDOFF_PERSONA = AgentPersona.MODELO_PREPARER
_HANDOFF_KEY = "modelo.export"


def _descriptor(command_key: str) -> Any:
    return next(d for d in build_tool_descriptors() if d.command_key == command_key)


def _direct_call(server: Any, command_key: str) -> Any:
    """Invoke the real ``tools/call`` path for one verb; return the CallToolResult."""

    async def _drive() -> Any:
        async with connect(server) as session:
            return await session.call_tool(tool_name_for_command(command_key), {})

    return anyio.run(_drive)


def _execute_call(server: Any, command_key: str) -> Any:
    """Invoke the ``execute`` meta-tool for one verb; return the CallToolResult."""

    async def _drive() -> Any:
        async with connect(server) as session:
            return await session.call_tool("execute", {"command_key": command_key, "arguments": {}})

    return anyio.run(_drive)


def _sole_text(result: Any) -> str:
    texts: list[str] = []
    for block in result.content:
        if block.type != "text":
            continue
        text = block.text
        if not isinstance(text, str):
            raise TypeError("text result blocks must contain strings")
        texts.append(text)
    return " ".join(texts)


@pytest.mark.parametrize(
    ("persona", "command_key"),
    [(_SCOPE_PERSONA, _SCOPE_KEY), (_HANDOFF_PERSONA, _HANDOFF_KEY)],
)
def test_direct_refusal_is_composed_once_by_the_shared_gate(persona: AgentPersona, command_key: str) -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    # The single composition site: the shared gate the meta-path also runs.
    expected = gate_refusal(persona=persona, descriptor=_descriptor(command_key))
    assert expected is not None, "the persona must refuse the chosen verb for this test to be meaningful"

    result = _direct_call(cast("Any", build_server(descriptors, persona=persona)), command_key)

    assert result.is_error is True
    # Exactly one refusal, byte-identical to the sole shared-gate composition.
    assert _sole_text(result) == expected
    # Not doubly-wrapped: the scope/handoff refusal is the plain gate string, not
    # an error envelope nesting another refusal. A single text block, no
    # structured envelope, and the refusal token appears exactly once.
    assert result.structured_content is None
    text_blocks = [block for block in result.content if block.type == "text"]
    assert len(text_blocks) == 1
    assert text_blocks[0].text.count(expected) == 1


@pytest.mark.parametrize(
    ("persona", "command_key"),
    [(_SCOPE_PERSONA, _SCOPE_KEY), (_HANDOFF_PERSONA, _HANDOFF_KEY)],
)
def test_direct_and_execute_paths_share_one_refusal(persona: AgentPersona, command_key: str) -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    expected = gate_refusal(persona=persona, descriptor=_descriptor(command_key))
    assert expected is not None

    # A fresh server per path so no prior identity read or toolset state leaks.
    direct = _direct_call(cast("Any", build_server(descriptors, persona=persona)), command_key)
    execute = _execute_call(cast("Any", build_server(descriptors, persona=persona)), command_key)

    assert direct.is_error is True
    assert execute.is_error is True
    # Both entry points resolve the refusal from the same gate_refusal call, so
    # the operator-facing text is byte-identical across the two surfaces.
    assert _sole_text(direct) == expected
    assert _sole_text(execute) == expected
    assert _sole_text(direct) == _sole_text(execute)
