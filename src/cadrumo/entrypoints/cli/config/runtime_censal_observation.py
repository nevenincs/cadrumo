"""Censal lifecycle observations and pending review identity."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ....application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from ....application.operations.models import OperationId
from ....application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.deadline_budget import remaining_budget
from ....application.runtime.operation_access import (
    RuntimeOperationObserve,
    RuntimeOperationObserved,
)
from ....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
)
from ....core.operations import OperationLifecycle
from .runtime_censal_exchange import _exchange

_OBSERVATION_PAGE_LIMIT = 1


def _observe(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    deadline: float,
) -> OperationObservationSuccessV1:
    request = RuntimeOperationObserve(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        observation=OperationObservationRequestV1(
            operation_id=operation_id,
            after_cursor=0,
            page_limit=_OBSERVATION_PAGE_LIMIT,
        ),
    )
    reply = _exchange(client, session_id, request, deadline=deadline)
    if not isinstance(reply, RuntimeOperationObserved):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if isinstance(reply.observation, OperationObservationRefusalV1):
        raise RuntimeFrontendRefusedError(reply.observation.code.value)
    if not isinstance(reply.observation, OperationObservationSuccessV1):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reply.observation


def _validate_observation(
    observed: OperationObservationSuccessV1,
    *,
    operation_id: OperationId,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    projection = observed.projection
    if (
        projection.operation_id != operation_id
        or projection.definition_id != CENSAL_OPERATION_DEFINITION_ID
        or projection.subject_ref != subject_ref
        or projection.definition_contract != contract
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _review_interaction(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
    deadline: float,
) -> tuple[OperationObservationSuccessV1, OperationReviewAvailableInteractionV1 | None]:
    while True:
        remaining_budget(deadline)
        observed = _observe(
            client,
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
            deadline=deadline,
        )
        _validate_observation(
            observed,
            operation_id=operation_id,
            subject_ref=subject_ref,
            contract=contract,
        )
        projection = observed.projection
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            return observed, None
        pending = projection.pending_interaction
        if isinstance(pending, OperationReviewAvailableInteractionV1):
            reference = pending.review_reference
            if (
                pending.operation_id != operation_id
                or pending.response_schema != CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity
                or reference.operation_id != operation_id
                or reference.review_projection_schema != CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity
                or reference.definition_contract_digest != contract.definition_contract_digest
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return observed, pending
        if projection.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        time.sleep(min(0.02, remaining_budget(deadline)))
