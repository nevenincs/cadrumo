"""A client of the newest protocol revision, which performs no handshake, is served what a legacy client is.

The newest revision the installed SDK speaks has no ``initialize``: each
request carries its own protocol version, and a client may ask
``server/discover`` first or ask nothing. The server here is the real one,
reached over framed streams as a stdio connection is. Nothing the server keeps
for a connection is set up by the handshake, so the same tools answer the same
way whichever revision the client speaks, and these cases hold it to that.
"""

from __future__ import annotations

from typing import Any, Literal, cast
from uuid import UUID, uuid4

import pytest
from mcp.types import LATEST_PROTOCOL_VERSION, CallToolResult, Tool

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.runtime.operation_access import RuntimeOperationControl, RuntimeOperationSubmit
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE, SIGN_IN_REMEDY
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_handshake_free_client, connected_server_and_client_session
from cadrumo_harness.mcp.tests.test_execute_typed_input_tool import _AnsweringClient

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_Negotiation = Literal["discover", "pinned"]
_READ = {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID, "payload": {"kind": "status"}}


def _advertised(tools: list[Tool]) -> list[tuple[str, str | None, dict[str, Any], dict[str, Any] | None]]:
    return [
        (
            tool.name,
            tool.description,
            tool.input_schema,
            None if tool.annotations is None else tool.annotations.model_dump(),
        )
        for tool in tools
    ]


def _answered(called: CallToolResult) -> tuple[bool, Any, list[str]]:
    """Return what a caller can read of a result: its error mark, its document and its text blocks."""
    return called.is_error, called.structured_content, [getattr(block, "text", "") for block in called.content]


def _without_identities(document: Any) -> Any:
    """Drop the identifiers the runtime mints for each submission, which no two calls share."""
    receipt = dict(document["receipt"]) | {"operation_id": None}
    start = {key: value for key, value in document["start"].items() if not key.endswith("_id")}
    return dict(document) | {"receipt": receipt, "start": start}


@pytest.mark.anyio
@pytest.mark.parametrize("negotiation", ["discover", "pinned"])
async def test_a_client_that_never_initializes_speaks_the_newest_revision_and_lists_the_same_tools(
    negotiation: _Negotiation,
) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        server = build_server(adapter)
        async with connected_handshake_free_client(server, negotiation=negotiation) as modern:
            session = modern.session
            assert session.initialize_result is None and session.discover_result is not None
            assert session.protocol_version == LATEST_PROTOCOL_VERSION
            assert LATEST_PROTOCOL_VERSION in session.discover_result.supported_versions
            listed = (await modern.list_tools()).tools
        async with connected_server_and_client_session(server) as legacy:
            assert legacy.initialize_result is not None
            assert legacy.protocol_version != LATEST_PROTOCOL_VERSION
            listed_after_handshake = (await legacy.list_tools()).tools
    finally:
        await adapter.close()

    assert [tool.name for tool in listed] == [name for name, _description, _schema in MCP_TOOL_CATALOGUE]
    assert all(tool.annotations is not None for tool in listed)
    assert _advertised(listed) == _advertised(listed_after_handshake)


@pytest.mark.anyio
async def test_the_server_tells_a_discovering_client_that_it_serves_tools() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        async with connected_handshake_free_client(build_server(adapter)) as modern:
            discovered = modern.session.discover_result
    finally:
        await adapter.close()

    assert discovered is not None and discovered.capabilities.tools is not None
    # It offers no resources and no prompts, and a client is told as much instead of finding out by error.
    assert discovered.capabilities.resources is None and discovered.capabilities.prompts is None


async def _read_calls(
    profile_id: UUID, *, handshake_free: _Negotiation | None
) -> dict[str, tuple[bool, Any, list[str]]]:
    """Make the same calls with no session held: status, two refusals, and an argument the contract refuses."""
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        server = build_server(adapter)
        if handshake_free is None:
            async with connected_server_and_client_session(server) as legacy:
                return {
                    "status": _answered(await legacy.call_tool("status", {})),
                    "search": _answered(await legacy.call_tool("search", {"family": "auth", "limit": 2})),
                    "observe": _answered(await legacy.call_tool("observe", {"observation": {}})),
                    "mistyped": _answered(await legacy.call_tool("search", {"limit": "many"})),
                }
        async with connected_handshake_free_client(server, negotiation=handshake_free) as modern:
            return {
                "status": _answered(await modern.call_tool("status", {})),
                "search": _answered(await modern.call_tool("search", {"family": "auth", "limit": 2})),
                "observe": _answered(await modern.call_tool("observe", {"observation": {}})),
                "mistyped": _answered(await modern.call_tool("search", {"limit": "many"})),
            }
    finally:
        await adapter.close()


@pytest.mark.anyio
@pytest.mark.parametrize("negotiation", ["discover", "pinned"])
async def test_a_read_tool_and_a_refusal_answer_a_handshake_free_client_as_they_answer_a_legacy_one(
    negotiation: _Negotiation,
) -> None:
    profile_id = uuid4()

    modern = await _read_calls(profile_id, handshake_free=negotiation)
    legacy = await _read_calls(profile_id, handshake_free=None)

    assert modern == legacy
    is_error, status, text = modern["status"]
    assert is_error is False and status["outcome"] == "status" and status["profile_id"] == str(profile_id)
    assert status["session"] == "none" and len(text) == 1
    # A refusal is an error result on this revision too, and so is an argument the wire contract refuses.
    # With no session, search is refused as observe is: only status answers.
    refused = {"outcome": "refused", "code": "authentication_required", "remedy": SIGN_IN_REMEDY}
    assert modern["search"][:2] == (True, refused)
    assert modern["observe"][:2] == (True, refused)
    assert modern["mistyped"][:2] == (True, {"outcome": "refused", "code": "invalid_request"})


@pytest.mark.anyio
@pytest.mark.parametrize("negotiation", ["discover", "pinned"])
async def test_execute_on_a_read_operation_is_submitted_and_started_for_a_handshake_free_client(
    negotiation: _Negotiation,
) -> None:
    modern_lease, legacy_lease = _AnsweringClient(uuid4()), _AnsweringClient(uuid4())
    modern_adapter = RuntimeMcpAdapter(
        profile_id=modern_lease.profile_id, client=cast(RuntimeFrontendClient, modern_lease)
    )
    legacy_adapter = RuntimeMcpAdapter(
        profile_id=legacy_lease.profile_id, client=cast(RuntimeFrontendClient, legacy_lease)
    )
    try:
        async with connected_handshake_free_client(build_server(modern_adapter), negotiation=negotiation) as modern:
            executed = await modern.call_tool("execute", dict(_READ))
            described = await modern.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
            unfit = await modern.call_tool("execute", dict(_READ) | {"secret": "synthetic-unasked-text"})
        async with connected_server_and_client_session(build_server(legacy_adapter)) as legacy:
            executed_after_handshake = await legacy.call_tool("execute", dict(_READ))
    finally:
        await modern_adapter.close()
        await legacy_adapter.close()

    assert executed.is_error is False and described.is_error is False
    document = executed.structured_content
    assert document["outcome"] == "submitted" and document["start"]["kind"] == "operation_acknowledged"
    # The runtime was sent the same two exchanges it is sent for a client that shook hands.
    submitted, started = modern_lease.exchanges
    assert isinstance(submitted, RuntimeOperationSubmit) and isinstance(started, RuntimeOperationControl)
    assert submitted.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
    assert submitted.subject_ref == f"profile:{modern_lease.profile_id}"
    assert [type(item) for item in legacy_lease.exchanges] == [RuntimeOperationSubmit, RuntimeOperationControl]
    assert _without_identities(document) == _without_identities(executed_after_handshake.structured_content)
    assert unfit.is_error is True
    # No tool takes a secret, so a call that gives one is refused at the wire, before anything is sent.
    assert unfit.structured_content == {"outcome": "refused", "code": "invalid_request"}
