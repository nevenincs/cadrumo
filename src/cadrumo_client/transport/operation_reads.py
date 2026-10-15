"""Settle one registered read through the shared operation client API."""

from __future__ import annotations

import time
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition

from ..contracts.contracts import RefusalCode, RefusalError
from .frontend_client import FrontendClient
from .frontend_client_contracts import FrontendRefusedError
from .operation_controller import OperationController, await_terminal_projection


async def read_operation[ResultT: BaseModel](
    client: FrontendClient,
    *,
    definition_id: str,
    subject_ref: str,
    payload: BaseModel,
    result_type: type[ResultT],
    session_id: UUID,
    deadline: float | None = None,
    financial_input: bool = False,
    request_model: type[BaseModel] | None = None,
    request_version: int = 1,
    result_version: int = 1,
) -> ResultT:
    """Run one recorded read-only worker operation to its terminal state and return its typed result."""
    if deadline is None:
        deadline = time.monotonic() + 120.0
    controller = await OperationController.submit(
        client,
        definition_id=definition_id,
        subject_ref=subject_ref,
        payload=payload,
        financial_input=financial_input,
        deadline=deadline,
        expected_session_id=session_id,
    )
    await controller.start()
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=definition_id + ".request", schema_version=request_version, model_type=request_model or type(payload)
    )
    state = await await_terminal_projection(
        controller,
        definition_id=definition_id,
        subject_ref=subject_ref,
        request_schema=expected_request,
        deadline=deadline,
        poll_seconds=0.02,
    )
    if state.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise FrontendRefusedError(
            state.refusal_ref
            or state.failure_error_code
            or (state.terminal_condition.value if state.terminal_condition is not None else "operation_unavailable")
        )
    if state.effect is not OperationEffect.NONE:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return await controller.read_settled_result(state, result_type, result_version=result_version)
