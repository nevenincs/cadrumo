"""A terminal refused observation for transport tests that script the runtime's operation replies."""

from __future__ import annotations

from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationPublicContractSetV1, OperationPublicDefinitionContractV1
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.core.time.clock import now


def refused_observation(
    *, contract: OperationPublicDefinitionContractV1, operation_id: str, subject_ref: str, refusal_ref: str
) -> OperationObservationSuccessV1:
    instant = now()
    contract_set = OperationPublicContractSetV1.build((contract,))
    projection = OperationPublicProjectionV1(
        operation_id=operation_id,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        revision=3,
        anchor_cursor=3,
        definition_contract=contract,
        contract_set_digest=contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=instant,
        updated_at=instant,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref=refusal_ref,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    event_page = OperationPublicEventPageV1(
        operation_id=operation_id,
        anchor_cursor=3,
        requested_cursor=3,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=3,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=event_page)
