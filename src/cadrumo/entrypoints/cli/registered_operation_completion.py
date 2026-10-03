"""Read exact settled registered CLI outcomes within the original result-read budget."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.frontend_projection import (
    OperationPublicProjectionV1,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationTerminalCondition
from .registered_operation_contracts import RegisteredOperationCompletion, RegisteredOperationProgress
from .registered_operation_deadlines import MIN_SETTLED_OPERATION_READ_SECONDS
from .registered_operation_errors import submitted_operation_error
from .registered_operation_exchange import require_registered_frontend_identity
from .registered_operation_projections import registered_result_projection, settled_registered_error_detail


def require_registered_settlement(
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    state: OperationPublicProjectionV1,
    progress: RegisteredOperationProgress,
    contract: OperationPublicDefinitionContractV1,
    allow_refusal_detail: bool,
    settled_read_deadline: Callable[[], float],
) -> None:
    """Retain recorded refusal details and diagnostics from the exact settled revision."""
    declared_refusal_detail = (
        allow_refusal_detail
        and progress.condition is OperationTerminalCondition.REFUSED
        and progress.refusal_code in contract.refusal_detail_codes
    )
    if progress.condition is not OperationTerminalCondition.SUCCEEDED and not declared_refusal_detail:
        raise submitted_operation_error(
            operation_id,
            state.refusal_ref
            or state.failure_error_code
            or (progress.condition.value if progress.condition is not None else "unknown"),
            terminal_condition=progress.condition,
            effect=progress.effect,
            refusal_code=progress.refusal_code,
            detail=settled_registered_error_detail(
                client,
                operation_id=operation_id,
                terminal_revision=state.revision,
                contract=contract,
                condition=progress.condition,
                deadline=settled_read_deadline(),
            ),
            diagnostic_ref=state.diagnostic_ref,
        )


def read_registered_completion[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    operation_id: OperationId,
    state: OperationPublicProjectionV1,
    progress: RegisteredOperationProgress,
    contract: OperationPublicDefinitionContractV1,
    expected_result: OperationSchemaIdentityV1,
    result_type: type[ResultT],
    profile_id: UUID,
    session_id: UUID,
    frontend: OperationFrontendProjection,
    settled_read_deadline: Callable[[], float],
) -> RegisteredOperationCompletion[ResultT]:
    """Read the settled result without recasting exhausted settlement waits as refusal."""
    read_deadline = settled_read_deadline()
    document = client.read_result_document(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=state.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=expected_result,
        ),
        timeout=max(read_deadline - time.monotonic(), MIN_SETTLED_OPERATION_READ_SECONDS),
        deadline=read_deadline,
    )
    projection = registered_result_projection(document, result_type=result_type, contract=contract)
    require_registered_frontend_identity(client, profile_id, session_id, frontend, RuntimeRefusalCode.INVALID_FRAME)
    if progress.condition is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return RegisteredOperationCompletion[ResultT](
        operation_id=operation_id,
        projection=projection,
        effect=state.effect,
        terminal_condition=progress.condition,
        refusal_code=progress.refusal_code,
    )
