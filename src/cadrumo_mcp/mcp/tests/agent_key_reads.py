"""An agent's own reads and profile edits through MCP tools, as a connected client issues them.

Shared by the tests that prove an agent session inside the profile reads its
values back and edits them: every step is a tool call on the real server,
``execute`` then ``observe`` until terminal, then ``result``. Each edit is
written against the revision the agent has just read, and read back.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol
from uuid import UUID

from mcp.types import CallToolResult

from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

__all__ = ["ToolCaller", "edit_profile_and_read_back", "profile_facts", "settled_result", "tool_document"]

_ROW_SECTION = "activities"
_ROW_FIELD = "description"


class ToolCaller(Protocol):
    """The one MCP client method these calls use."""

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None, /) -> CallToolResult: ...


def tool_document(reply: CallToolResult) -> dict[str, Any]:
    """Return an admitted tool reply's structured document."""
    document = reply.structured_content
    assert isinstance(document, dict), reply
    assert reply.is_error is False, document
    return document


async def settled_result(
    sdk: ToolCaller, profile_id: UUID, definition_id: str, payload: dict[str, Any], *, timeout: float = 60
) -> CallToolResult:
    """Run one operation to a succeeded terminal and return the agent's ``result`` call, admitted or refused."""
    submitted = tool_document(
        await sdk.call_tool(
            "execute",
            {
                "definition_id": definition_id,
                "subject_ref": profile_operation_subject(str(profile_id)),
                "payload": payload,
            },
        )
    )
    operation_id = submitted["receipt"]["operation_id"]
    deadline = time.monotonic() + timeout
    while True:
        observed = tool_document(
            await sdk.call_tool(
                "observe", {"observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}}
            )
        )
        projection = observed["reply"]["observation"]["projection"]
        if projection["lifecycle"] == "terminal":
            break
        assert time.monotonic() < deadline, f"{definition_id} did not settle"
        await asyncio.sleep(0.05)
    assert projection["terminal_condition"] == "succeeded", projection
    return await sdk.call_tool("result", {"result": {"operation_id": operation_id}})


async def _projection(sdk: ToolCaller, profile_id: UUID, definition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    released = tool_document(await settled_result(sdk, profile_id, definition_id, payload))
    assert released["outcome"] == "reply", released
    document = released["document"]
    assert document["outcome"] == "success", document
    return document["projection"]


async def profile_facts(sdk: ToolCaller, profile_id: UUID) -> tuple[dict[str, Any], dict[str, str]]:
    """Read the current revision and every stored fact, page by page."""
    facts: dict[str, str] = {}
    cursor = 0
    while True:
        page = await _projection(
            sdk,
            profile_id,
            "user-profile.view",
            {"profile_id": str(profile_id), "page_kind": "facts", "cursor": cursor},
        )
        assert page["outcome"] == "page", page
        facts.update({item["path"]: item["value"] for item in page["items"]})
        if page["next_cursor"] is None:
            return page, facts
        cursor = page["next_cursor"]


async def _edit(sdk: ToolCaller, profile_id: UUID, definition_id: str, change: dict[str, Any]) -> dict[str, Any]:
    baseline, _ = await profile_facts(sdk, profile_id)
    return await _projection(
        sdk,
        profile_id,
        definition_id,
        {
            "profile_id": str(profile_id),
            "expected_revision": baseline["record_revision"],
            "expected_content_digest": baseline["content_digest"],
            **change,
        },
    )


async def edit_profile_and_read_back(sdk: ToolCaller, profile_id: UUID) -> None:
    """Patch, mutate a field and add, update and remove a row, reading each value back."""
    _, before = await profile_facts(sdk, profile_id)
    await _edit(sdk, profile_id, "user-profile.patch", {"values": [{"question_id": "name", "value": "Agente"}]})
    _, patched = await profile_facts(sdk, profile_id)
    assert "Agente" in patched.values() and "Agente" not in before.values(), patched

    language = "ca" if before.get(PROFILE_OUTPUT_LANGUAGE_PATH) != "ca" else "hu"
    await _edit(
        sdk, profile_id, "user-profile.field-mutation", {"path": PROFILE_OUTPUT_LANGUAGE_PATH, "value": language}
    )
    _, mutated = await profile_facts(sdk, profile_id)
    assert mutated[PROFILE_OUTPUT_LANGUAGE_PATH] == language

    added = await _edit(
        sdk,
        profile_id,
        "user-profile.repeatable-row-mutation",
        {"section_key": _ROW_SECTION, "values": [{"field_key": _ROW_FIELD, "value": "Agent row"}]},
    )
    path = f"{_ROW_SECTION}.{added['row_index']}.{_ROW_FIELD}"
    _, rows = await profile_facts(sdk, profile_id)
    assert rows[path] == "Agent row"

    row = {"section_key": _ROW_SECTION, "row_key": str(added["row_index"])}
    updated = await _edit(
        sdk,
        profile_id,
        "user-profile.repeatable-row-update",
        {**row, "values": [{"field_key": _ROW_FIELD, "value": "Agent row, edited"}]},
    )
    assert updated["changed"] is True
    _, rows = await profile_facts(sdk, profile_id)
    assert rows[path] == "Agent row, edited"

    removed = await _edit(sdk, profile_id, "user-profile.repeatable-row-remove", row)
    assert removed["changed"] is True
    _, rows = await profile_facts(sdk, profile_id)
    assert path not in rows
