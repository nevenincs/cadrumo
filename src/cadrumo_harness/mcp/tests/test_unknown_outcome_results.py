"""A result whose effect is not known is a normal result that says so; a refusal is still an error.

A host or a model commonly repeats a call that came back as an error, and a
repeat of a write that may already have committed can commit it twice. So an
unknown outcome is answered without the error mark, and its document says that
the outcome is not known, that the call is not to be repeated, and what to read
instead. The transports here lose their replies on purpose; the classification
and the wording under test are the server's own.
"""

from __future__ import annotations

import json
from typing import cast, override
from uuid import uuid4

import pytest
from mcp.types import CallToolResult, TextContent

from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo_client.contracts.contracts import RefusalCode
from cadrumo_client.transport.frontend_client import FrontendClient

from ..protocol_contract import MCP_TOOL_CATALOGUE, UNKNOWN_OUTCOME_MEMBER, has_refusal, unknown_outcome_instruction
from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from .session import connected_server_and_client_session
from .test_result_page_tool import _auth_registry, _observed_operation_id, _ObservedClient

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DEADLINE = RefusalCode.DEADLINE_EXCEEDED.value


def _document(called: CallToolResult) -> dict[str, object]:
    """Return a result's document, having checked that its text block carries the same one."""
    assert called.structured_content is not None
    (block,) = called.content
    assert isinstance(block, TextContent) and json.loads(block.text) == called.structured_content
    return cast("dict[str, object]", called.structured_content)


class _UnsettledClient(_ObservedClient):
    """A lease whose runtime observes one operation in the state a test names."""

    lifecycle = OperationLifecycle.TERMINAL
    condition: OperationTerminalCondition | None = OperationTerminalCondition.SUCCEEDED
    effect = OperationEffect.NONE

    @override
    def _settled(self) -> OperationObservationSuccessV1:
        settled = super()._settled()
        succeeded = self.condition is OperationTerminalCondition.SUCCEEDED
        projection = OperationPublicProjectionV1.model_validate(
            settled.projection.model_dump()
            | {
                "lifecycle": self.lifecycle,
                "terminal_condition": self.condition,
                "effect": self.effect,
                "result_ref": settled.projection.result_ref if succeeded else None,
            }
        )
        return OperationObservationSuccessV1(projection=projection, event_page=settled.event_page)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("lifecycle", "condition", "effect", "told"),
    [
        (OperationLifecycle.SETTLING, None, OperationEffect.NONE, "is settling"),
        (OperationLifecycle.TERMINAL, OperationTerminalCondition.INTERRUPTED, OperationEffect.UNKNOWN, "is not known"),
        (OperationLifecycle.TERMINAL, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, None),
    ],
    ids=["settling", "effect-unknown", "settled"],
)
async def test_an_observation_of_an_unsettled_or_unknown_effect_says_so_and_is_no_error(
    lifecycle: OperationLifecycle,
    condition: OperationTerminalCondition | None,
    effect: OperationEffect,
    told: str | None,
) -> None:
    profile_id = uuid4()
    client = _UnsettledClient(profile_id, _auth_registry())
    client.lifecycle, client.condition, client.effect = lifecycle, condition, effect
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    request = OperationObservationRequestV1(operation_id=_observed_operation_id(), after_cursor=0, page_limit=10)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            observed = await sdk.call_tool("observe", {"observation": request.model_dump(mode="json")})
    finally:
        await adapter.close()

    document = _document(observed)
    assert observed.is_error is False and document["outcome"] == "reply"
    if told is None:
        assert UNKNOWN_OUTCOME_MEMBER not in document
    else:
        instruction = str(document[UNKNOWN_OUTCOME_MEMBER])
        assert told in instruction and "Do not submit it again" in instruction


@pytest.mark.parametrize(
    ("reply", "reads_with"),
    [
        ({"outcome": "unresolved", "code": _DEADLINE, "request_id": "r", "definition_id": "d"}, "idempotency_key"),
        ({"outcome": "unresolved", "code": "failed", "operation_id": "o"}, "operation_id with observe"),
        ({"outcome": "unresolved", "code": "unavailable", "request_id": "r"}, "tell the person"),
        (
            {"outcome": "submitted", "receipt": {"operation_id": "o"}, "start": {"outcome": "unresolved", "code": "c"}},
            "receipt.operation_id",
        ),
    ],
    ids=["lost-submission", "known-operation", "request-only", "lost-start"],
)
def test_every_unknown_outcome_is_no_refusal_and_says_not_to_repeat_and_what_to_read(
    reply: dict[str, object], reads_with: str
) -> None:
    instruction = unknown_outcome_instruction(reply)

    assert has_refusal(reply) is False
    assert instruction is not None and "not known" in instruction and "Do not repeat this call" in instruction
    assert reads_with in instruction


@pytest.mark.parametrize(
    "reply",
    [
        {"outcome": "refused", "code": "invalid_request"},
        {
            "outcome": "submitted",
            "receipt": {"operation_id": "o"},
            "start": {"outcome": "refused", "code": "c"},
        },
        {"outcome": "reply", "reply": {"kind": "access_refusal", "code": "operation_denied"}},
        {"outcome": "reply", "document": {"outcome": "refused", "code": "operation_not_successful"}},
    ],
    ids=["refused", "refused-step", "access-refusal", "refused-document"],
)
def test_a_refusal_is_still_an_error_and_carries_no_unknown_outcome(reply: dict[str, object]) -> None:
    assert has_refusal(reply) is True
    assert unknown_outcome_instruction(reply) is None


def test_the_tools_that_can_answer_unresolved_say_it_is_no_error_and_what_makes_a_repeat_safe() -> None:
    described = {name: description for name, description, _schema in MCP_TOOL_CATALOGUE}

    for name in ("execute",):
        assert "unresolved is not an error" in described[name], name
        assert "Do not repeat a call that answered so" in described[name], name
    assert "idempotency_key is optional, and giving one makes a repeat safe" in described["execute"]
    assert "two identical calls run twice" in described["execute"]
