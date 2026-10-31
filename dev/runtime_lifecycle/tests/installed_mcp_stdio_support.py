"""Shared MCP stdio driving for the installed-runtime query tests."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import UUID

from mcp import ClientSession
from pydantic import BaseModel

from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)


def structured_object(value: object) -> dict[str, Any]:
    """Require a decoded MCP structured-content object."""
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


async def release_query_result[ProjectionT: BaseModel](
    client: ClientSession,
    *,
    definition_id: str,
    profile_id: UUID,
    request: BaseModel,
    contract: OperationPublicDefinitionContractV1,
    result_model: type[OperationResultProjectionSuccessV1[ProjectionT]],
    label: str,
) -> tuple[OperationResultProjectionSuccessV1[ProjectionT], dict[str, Any]]:
    """Execute a read-only query over MCP, wait for it to settle and release its typed result.

    Returns the validated result and the raw released document so callers can
    check what the wire carried as well as what the typed projection holds.
    """
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = await client.call_tool(
        "execute",
        {
            "definition_id": definition_id,
            "subject_ref": subject_ref,
            "payload": request.model_dump(mode="json"),
        },
    )
    assert submitted.is_error is False
    receipt = OperationSubmissionReceiptV1.model_validate_json(
        canonical_json_bytes(structured_object(submitted.structured_content)["receipt"]),
    )
    observation_request = OperationObservationRequestV1(
        operation_id=receipt.operation_id,
        after_cursor=0,
        page_limit=32,
    )
    terminal: OperationObservationSuccessV1 | None = None
    for _attempt in range(100):
        observed = await client.call_tool(
            "observe",
            {"observation": observation_request.model_dump(mode="json")},
        )
        assert observed.is_error is False
        candidate = OperationObservationSuccessV1.model_validate_json(
            canonical_json_bytes(
                structured_object(structured_object(observed.structured_content)["reply"])["observation"]
            ),
        )
        state = candidate.projection
        assert state.operation_id == receipt.operation_id
        assert state.definition_id == definition_id
        assert state.subject_ref == subject_ref
        if state.lifecycle is OperationLifecycle.TERMINAL:
            terminal = candidate
            break
        await asyncio.sleep(0.05)
    assert terminal is not None, f"{label} did not settle"
    state = terminal.projection
    assert state.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert state.effect is OperationEffect.NONE

    result_schema = contract.result_schema
    assert result_schema is not None
    result_request = OperationResultProjectionRequestV1(
        operation_id=receipt.operation_id,
        terminal_revision=state.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=result_schema,
    )
    released = await client.call_tool("result", {"result": result_request.model_dump(mode="json")})
    assert released.is_error is False
    document = structured_object(released.structured_content)
    result = result_model.model_validate_json(canonical_json_bytes(document["document"]))
    assert result.result_schema == result_schema
    assert result.definition_contract_digest == contract.definition_contract_digest
    return result, document


async def assert_human_operation_refused(
    client: ClientSession,
    *,
    definition_id: str,
    profile_id: UUID,
    request: BaseModel,
) -> None:
    """Require the typed MCP refusal before a human-only request is admitted."""
    refusal = await client.call_tool(
        "execute",
        {
            "definition_id": definition_id,
            "subject_ref": profile_operation_subject(str(profile_id)),
            "payload": request.model_dump(mode="json"),
        },
    )
    assert refusal.is_error is True
    assert refusal.structured_content == {"outcome": "refused", "code": "operation_denied"}
