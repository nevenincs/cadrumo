"""Every tool is advertised with the protocol's annotations, and the read-only ones only read.

The annotations are hints a host may use for its own presentation and consent.
They are declared beside each tool in the catalogue and change nothing the
server or the runtime does. What a hint claims is held here to what the tool
sends: a tool marked read-only is driven through a lease that keeps every
exchange, and it sends nothing but reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurface
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.runtime.operation_access import RuntimeOperationObserve, RuntimeOperationReview
from cadrumo.application.runtime.projection_pages import ProjectionPageRequest
from cadrumo.core.hashing import sha256_hex
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE, MCP_TOOL_HINTS, MCP_TOOL_NAMES, ToolHints
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_harness.mcp.tests.test_operation_search_tool import _AdmittedClient, _registry
from cadrumo_harness.mcp.tests.test_result_page_tool import _observed_operation_id, _ObservedClient

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_READ_ONLY = {
    "status",
    "search",
    "describe",
    "authority",
    "corpus_search",
    "observe",
    "result",
    "result_page",
    "review",
}
"""The tools that cannot change a record or reach the network, written here apart from the catalogue."""

_READING_EXCHANGES = (RuntimeOperationObserve, RuntimeOperationReview)
"""The operation requests that only read; every other one submits, starts, resumes or manages."""

_READING_METHODS = {"status", "describe", "operation", "read_result_document", "read_result_page", "close"}


class _WatchedLease:
    """An admitted lease that answers reads and keeps what was asked of it, by method and by exchange."""

    def __init__(self, profile_id: UUID) -> None:
        registry = _registry()
        self._lease = _AdmittedClient(profile_id, registry)
        self._observed = _ObservedClient(profile_id, registry)
        self.profile_id, self.frontend, self.session_id = profile_id, self._lease.frontend, self._lease.session_id
        self.sent: list[type] = []
        self.unexpected: list[str] = []

    def __getattr__(self, name: str) -> Any:
        # Reached only for a method this lease does not serve, which a tool that only reads never asks for.
        self.unexpected.append(name)
        raise AttributeError(name)

    def status(self) -> SimpleNamespace:
        return self._lease.status()

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        return self._lease.describe(definition_id, deadline=deadline)

    def operation(self, request: object, *, deadline: float) -> object:
        self.sent.append(type(request))
        if not isinstance(request, RuntimeOperationObserve):
            # The reply's shape is not what is under test: the exchange was recorded.
            raise RuntimeFrontendRefusedError("operation_denied")
        return self._observed.operation(request, deadline=deadline)

    def read_result_document(self, result: Any, *, deadline: float) -> object:
        return self._observed.read_result_document(result, deadline=deadline)

    def read_result_page(self, result: Any, page: Any, *, deadline: float) -> object:
        return self._observed.read_result_page(result, page, deadline=deadline)

    def close(self) -> None:
        self._lease.close()


def _read_only_calls() -> dict[str, dict[str, object]]:
    """One representative call for each read-only tool that is served under a session."""
    operation_id = _observed_operation_id()
    digest = sha256_hex(b"synthetic review contract")
    review = OperationReviewProjectionRequestV1(
        reference=OperationReviewProjectionReferenceV1(
            operation_id=operation_id,
            interaction_id="f" * 64,
            revision=1,
            review_projection_schema=OperationSchemaIdentityV1(
                schema_id="test.mcp.review", schema_version=1, schema_fingerprint=digest
            ),
            definition_contract_digest=digest,
            expires_at=None,
        )
    )
    observation = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=10)
    return {
        "status": {},
        "search": {},
        "describe": {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID},
        "observe": {"observation": observation.model_dump(mode="json")},
        "result": {"result": {"operation_id": operation_id}},
        "result_page": {
            "result": {"operation_id": operation_id},
            "page": ProjectionPageRequest().model_dump(mode="json"),
        },
        "review": {"review": review.model_dump(mode="json")},
    }


def test_every_tool_in_the_catalogue_declares_its_hints_and_the_read_only_set_is_the_tools_that_only_read() -> None:
    assert set(MCP_TOOL_HINTS) == MCP_TOOL_NAMES == {name for name, _description, _schema in MCP_TOOL_CATALOGUE}
    titles = [hints.title for hints in MCP_TOOL_HINTS.values()]
    assert all(title.strip() for title in titles) and len(set(titles)) == len(titles)

    assert {name for name, hints in MCP_TOOL_HINTS.items() if hints.read_only} == _READ_ONLY
    for name, hints in MCP_TOOL_HINTS.items():
        if hints.read_only:
            # A tool that only reads destroys nothing, reaches nothing and is harmless to repeat.
            assert hints == ToolHints(hints.title, read_only=True, destructive=False, idempotent=True, open_world=False)
        else:
            assert hints.idempotent is False, name


def test_the_hints_of_the_tools_that_act_state_the_widest_thing_each_can_do() -> None:
    reaching = {name for name, hints in MCP_TOOL_HINTS.items() if hints.open_world}
    additive = {name for name, hints in MCP_TOOL_HINTS.items() if not hints.read_only and not hints.destructive}

    # Only a tool that runs or releases a registered operation can reach another host.
    assert reaching == {"execute", "control", "respond"}
    # Every tool that acts can overwrite or delete: none only adds, now that no tool admits a session.
    assert additive == set()


@pytest.mark.anyio
@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
async def test_the_server_advertises_each_tools_hints_as_the_protocols_annotations(surface: McpSurface) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None, surface=surface)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            tools = (await sdk.list_tools()).tools
    finally:
        await adapter.close()

    assert {tool.name for tool in tools} == surface.tools
    for tool in tools:
        hints, advertised = MCP_TOOL_HINTS[tool.name], tool.annotations
        assert advertised is not None, tool.name
        assert (
            advertised.title,
            advertised.read_only_hint,
            advertised.destructive_hint,
            advertised.idempotent_hint,
            advertised.open_world_hint,
        ) == (hints.title, hints.read_only, hints.destructive, hints.idempotent, hints.open_world)


@pytest.mark.anyio
async def test_a_tool_marked_read_only_sends_the_runtime_nothing_but_reads() -> None:
    calls = _read_only_calls()
    # The two reference tools are served with no session at all, so they have nothing to send.
    assert set(calls) == _READ_ONLY - {"authority", "corpus_search"}
    lease = _WatchedLease(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=lease.profile_id, client=cast(RuntimeFrontendClient, lease))
    sent_by: dict[str, list[type]] = {}
    try:
        for name, arguments in calls.items():
            before = len(lease.sent)
            reply = await adapter.call(name, arguments)
            assert reply["outcome"] != "refused" or name == "review", (name, reply)
            sent_by[name] = lease.sent[before:]
    finally:
        await adapter.close()

    assert lease.unexpected == []
    assert all(issubclass(kind, _READING_EXCHANGES) for kinds in sent_by.values() for kind in kinds), sent_by
    assert sent_by["observe"] == [RuntimeOperationObserve] and sent_by["review"] == [RuntimeOperationReview]
    # The lease itself serves nothing but reads, so a tool that asked for more would have been recorded above.
    assert {name for name in vars(_WatchedLease) if not name.startswith("_")} <= _READING_METHODS


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "arguments"),
    [("authority", {"query": "auth_providers"}), ("corpus_search", {"query": "synthetic"})],
)
async def test_the_reference_tools_marked_read_only_are_served_without_any_session(
    name: str, arguments: dict[str, object]
) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        await adapter.call(name, arguments)
        # Whatever the bundled data answered, no connection was opened and no session asked for.
        assert adapter.client is None and adapter.admission is None
    finally:
        await adapter.close()
