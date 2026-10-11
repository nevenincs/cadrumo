"""Finding and describing operations with no session, from the contracts this package ships.

The contracts are the shipped ones and the surfaces are the declared ones.
Each answer is held to what a session's own answer is: the same pages, the
same order, the same refusals. The one connection double is a lease whose
runtime is gone, which is the condition under test.
"""

from __future__ import annotations

from typing import Any, NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurface, McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo_harness.mcp.operation_discovery import operation_summary
from cadrumo_harness.mcp.operation_search import rank_operations
from cadrumo_harness.mcp.protocol_contract import SEARCH_PAGE_DEFAULT, public_value
from cadrumo_harness.mcp.public_operation_discovery import discover_public_operations, shipped_public_descriptions
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FULL = MCP_SURFACES[McpSurfaceName.FULL]
_READ_ONLY_LOCAL = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
_READ = AUTH_READ_OPERATION_DEFINITION_ID


def _every_page(args: dict[str, Any], surface: McpSurface) -> list[dict[str, Any]]:
    """Follow the cursors to the end and return every row, asserting each page says it is under no session."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = discover_public_operations("search", args | ({} if cursor is None else {"cursor": cursor}), surface)
        assert (page["outcome"], page["session"]) == ("found", "none")
        assert "unavailable" not in page
        rows.extend(page["operations"])
        following = page.get("next_cursor")
        assert following is None or isinstance(following, str)
        cursor = following
        if cursor is None:
            return rows


def test_a_listing_pages_through_every_registered_operation_in_definition_id_order() -> None:
    shipped = shipped_public_descriptions()
    first = discover_public_operations("search", {}, _FULL)

    assert SEARCH_PAGE_DEFAULT == 10 and len(shipped) > SEARCH_PAGE_DEFAULT
    assert len(first["operations"]) == SEARCH_PAGE_DEFAULT
    assert first["next_cursor"] == first["operations"][-1]["definition_id"]
    rows = _every_page({"limit": 37}, _FULL)
    assert [row["definition_id"] for row in rows] == sorted(shipped)
    # A row is the operation's summary, as a session's listing gives it.
    assert rows == [operation_summary(shipped[definition_id]) for definition_id in sorted(shipped)]


def test_a_family_narrows_the_listing_to_that_family_and_its_own_id() -> None:
    shipped = shipped_public_descriptions()

    family = [row["definition_id"] for row in _every_page({"family": "auth"}, _FULL)]
    one = [row["definition_id"] for row in _every_page({"family": _READ}, _FULL)]

    assert family == sorted(definition_id for definition_id in shipped if definition_id.startswith("auth."))
    assert len(family) > 1 and one == [_READ]


def test_a_query_ranks_as_a_session_s_search_ranks_and_pages_by_position() -> None:
    query = "classify a ledger transaction"
    ranked = rank_operations(query, tuple(shipped_public_descriptions().values()))
    assert len(ranked) > 4

    whole = [row["definition_id"] for row in _every_page({"query": query, "limit": 200}, _FULL)]
    paged = [row["definition_id"] for row in _every_page({"query": query, "limit": 2}, _FULL)]

    assert whole == [description.contract.definition_id for description in ranked]
    assert paged == whole
    assert discover_public_operations("search", {"query": _READ, "limit": 1}, _FULL)["operations"] == [
        {
            "definition_id": _READ,
            "description": shipped_public_descriptions()[_READ].request_json_schema["description"],
            "subject_kind": "profile",
            "permitted_effects": ["none", "unknown", "updated"],
            "interaction_kinds": [],
            "ephemeral_secret_required": False,
        }
    ]


def test_a_cursor_of_the_other_kind_of_listing_is_refused_as_a_session_s_is() -> None:
    with pytest.raises(ValueError, match="unranked listing"):
        discover_public_operations("search", {"cursor": "3"}, _FULL)
    with pytest.raises(ValueError, match="ranked search"):
        discover_public_operations("search", {"query": "ledger", "cursor": _READ}, _FULL)


def test_a_narrowed_surface_finds_and_describes_only_what_it_keeps() -> None:
    shipped = shipped_public_descriptions()
    kept = sorted(definition_id for definition_id in shipped if _READ_ONLY_LOCAL.admits(definition_id))
    left_out = sorted(set(shipped) - set(kept))
    assert kept and left_out, "the narrowed surface keeps everything or nothing; nothing was judged"

    listed = [row["definition_id"] for row in _every_page({}, _READ_ONLY_LOCAL)]
    ranked = [row["definition_id"] for row in _every_page({"query": left_out[0], "limit": 200}, _READ_ONLY_LOCAL)]

    assert listed == kept
    assert set(ranked) <= set(kept)
    described = discover_public_operations("describe", {"definition_id": kept[0]}, _READ_ONLY_LOCAL)
    assert described["outcome"] == "described"
    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        discover_public_operations("describe", {"definition_id": left_out[0]}, _READ_ONLY_LOCAL)
    assert refused.value.reason == "frontend_denied"


def test_a_description_is_the_shipped_contract_and_schema_and_an_unregistered_id_is_refused() -> None:
    described = discover_public_operations("describe", {"definition_id": _READ}, _FULL)

    assert described == {
        "outcome": "described",
        "description": public_value(shipped_public_descriptions()[_READ]),
        "session": "none",
    }
    assert "profile_id" in described["description"]["request_json_schema"]["properties"]
    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        discover_public_operations("describe", {"definition_id": "auth.synthetic-unregistered"}, _FULL)
    assert refused.value.reason == "operation_denied"


class _LeaseOfAStoppedRuntime:
    """A lease still held after its runtime stopped: every exchange finds no runtime to answer."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.exchanges = 0
        self.close_count = 0

    def _gone(self) -> NoReturn:
        self.exchanges += 1
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    def status(self) -> NoReturn:
        self._gone()

    def describe(self, definition_id: str, *, deadline: float) -> NoReturn:
        self._gone()

    def subscribe_session_retirement(self, receive: object) -> None:
        """This double's runtime sends no notice: it is gone."""

    def subscribe_lifecycle_notices(self, receive: object) -> None:
        """This double's runtime sends no notice: it is gone."""

    def close(self) -> None:
        self.close_count += 1


@pytest.mark.anyio
async def test_a_lease_whose_runtime_is_gone_does_not_stop_operations_being_found_and_described() -> None:
    lease = _LeaseOfAStoppedRuntime(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=lease.profile_id, client=cast(RuntimeFrontendClient, lease))
    try:
        found = await adapter.call("search", {"family": _READ})
        described = await adapter.call("describe", {"definition_id": _READ})
        private = await adapter.call("execute", {"definition_id": _READ, "payload": {}})
    finally:
        await adapter.close()

    assert (found["outcome"], found["session"]) == ("found", "none")
    assert [row["definition_id"] for row in found["operations"]] == [_READ]
    assert (described["outcome"], described["session"]) == ("described", "none")
    # The runtime was asked first each time, and running an operation still needs it.
    assert lease.exchanges >= 2
    assert (private["outcome"], private["code"]) == ("refused", "runtime_unavailable")
