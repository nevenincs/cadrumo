"""Read the canonical workbench generation through one authenticated runtime."""

from __future__ import annotations

from functools import cache

from pydantic import ValidationError

from ...application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from ...application.operations.registry import OperationPublicDefinitionContractV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import bounded_deadline_after, remaining_budget
from ...application.workbench_generation_contracts import WorkbenchGenerationV1
from ...application.workbench_generation_operation import (
    WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
    WorkbenchGenerationOperationRequest,
    build_workbench_generation_operation_definition,
    build_workbench_generation_operation_registration,
)
from ...application.workbench_generation_projection import (
    WorkbenchGenerationOperationProjection,
    restore_workbench_generation,
)
from ...core.external_constants import OutputLanguage
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient
from .frontend_client_contracts import RuntimeFrontendRefusedError
from .operation_settlement import (
    PinnedConnection,
    read_settled_result_bytes,
    start_and_await_terminal,
    submit_operation,
)


@cache
def _contract() -> OperationPublicDefinitionContractV1:
    definition = build_workbench_generation_operation_definition()
    return build_workbench_generation_operation_registration(definition).contract


def read_workbench_generation(
    client: RuntimeFrontendClient, *, output_language: OutputLanguage, timeout: float = 60
) -> WorkbenchGenerationV1:
    """Return one complete generation after exact contract and result validation.

    Every read is a separately recorded invocation. The caller owns the client;
    losing this observer never asserts cancellation of the canonical operation.
    """
    deadline = bounded_deadline_after(timeout, subject="workbench read")
    pinned = PinnedConnection.of(client)
    profile_id = pinned.profile_id
    contract = client.contract(WORKBENCH_GENERATION_OPERATION_DEFINITION_ID, deadline=deadline)
    if contract != _contract() or contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = submit_operation(
        client,
        pinned,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        payload_json=WorkbenchGenerationOperationRequest(
            profile_id=profile_id, output_language=output_language
        ).model_dump_json(),
        deadline=deadline,
    )
    if submitted.receipt.secret_requirement is not None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
    projection = start_and_await_terminal(
        client, pinned, operation_id, contract=contract, subject_ref=subject_ref, deadline=deadline
    )
    if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise RuntimeFrontendRefusedError(
            projection.refusal_ref or projection.failure_error_code or "operation_unavailable"
        )
    if projection.effect is not OperationEffect.NONE:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    encoded = read_settled_result_bytes(client, operation_id, projection, contract, deadline=deadline)
    generation = _restore_verified_generation(encoded, contract, client, pinned)
    remaining_budget(deadline)
    return generation


def _restore_verified_generation(
    encoded: bytes,
    contract: OperationPublicDefinitionContractV1,
    client: RuntimeFrontendClient,
    pinned: PinnedConnection,
) -> WorkbenchGenerationV1:
    """Restore typed meaning only after the complete result retains its exact identity."""
    try:
        result = OperationResultProjectionSuccessV1[WorkbenchGenerationOperationProjection].model_validate_json(encoded)
        if (
            result.result_schema != contract.result_schema
            or result.definition_contract_digest != contract.definition_contract_digest
            or result.projection.profile_id != pinned.profile_id
            or client.session_id != pinned.session_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        generation = restore_workbench_generation(result.projection)
    except (ValidationError, ValueError, TypeError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    return generation
