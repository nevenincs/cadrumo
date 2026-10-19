"""Read-only continuation hints for already admitted operation replies."""

from __future__ import annotations

from typing import Any

from cadrumo.core.operations import OperationLifecycle


def operation_guidance(tool: str, value: dict[str, Any], *, compact: bool = False) -> dict[str, Any]:
    """Keep the exact operation handle and suggest only a read, never a repeated write.

    Compact observations omit the repeated definition and historical events.
    Current state, failure, effect and pending interaction stay intact. This is
    an MCP presentation; the runtime observation and its checks are unchanged.
    """
    if tool == "execute" and value.get("outcome") == "submitted":
        operation_id = value["receipt"]["operation_id"]
        return {**value, "next_call": _observe_call(operation_id)}
    if tool != "observe" or value.get("outcome") != "reply":
        return value
    reply = value.get("reply", {})
    observation = reply.get("observation", {})
    if observation.get("outcome") != "success":
        return value
    projection = observation.get("projection")
    if not isinstance(projection, dict) or "operation_id" not in projection:
        return value
    operation_id = projection["operation_id"]
    next_call = None
    if projection.get("lifecycle") == OperationLifecycle.TERMINAL.value:
        next_call = {"tool": "result", "arguments": {"result": {"operation_id": operation_id}}}
    elif projection.get("pending_interaction", {}).get("disposition") == "none":
        next_call = _observe_call(operation_id)
    if compact:
        projection = {
            key: item
            for key, item in projection.items()
            if key not in {"definition_contract", "contract_set_digest", "result_ref"}
        }
        observation = {key: item for key, item in observation.items() if key != "event_page"}
        observation = {**observation, "projection": projection}
        value = {**value, "reply": {**reply, "observation": observation}, "presentation": "compact"}
    return value if next_call is None else {**value, "next_call": next_call}


def _observe_call(operation_id: str) -> dict[str, Any]:
    return {
        "tool": "observe",
        "arguments": {
            "observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 1},
            "compact": True,
        },
    }
