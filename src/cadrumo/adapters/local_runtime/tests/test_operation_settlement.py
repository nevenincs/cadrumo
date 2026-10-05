"""Operation settlement polls one pinned connection and refuses once that connection is lost."""

from __future__ import annotations

from typing import override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.operation_settlement import (
    PinnedConnection,
    start_and_await_terminal,
    submit_operation,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.deadline_budget import deadline_after
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.time.clock import now

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_OPERATION_ID = "e" * 64


def _contract() -> OperationPublicDefinitionContractV1:
    definition = next(
        item
        for item in build_automation_operation_definitions()
        if item.definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    )
    return build_automation_operation_registrations((definition,))[0].contract


def _observation(
    contract: OperationPublicDefinitionContractV1, subject_ref: str, *, lifecycle: OperationLifecycle
) -> OperationObservationSuccessV1:
    instant = now()
    terminal = lifecycle is OperationLifecycle.TERMINAL
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        revision=3,
        anchor_cursor=3,
        definition_contract=contract,
        contract_set_digest=OperationPublicContractSetV1.build((contract,)).contract_set_digest,
        lifecycle=lifecycle,
        terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
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
        result_ref="result:example" if terminal else None,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=projection,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=3,
            requested_cursor=3,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=3,
            restart_cursor=None,
        ),
    )


class _Client(RuntimeFrontendClient):
    """Admit a submission, then report a running operation before it settles."""

    def __init__(self, *, running_observations: int, replace_session_after_first_observation: bool = False) -> None:
        self._profile_id = uuid4()
        self._frontend = OperationFrontendProjection.CLI
        self._session_id = uuid4()
        self.requests: list[RuntimeOperationRequest] = []
        self._running_left = running_observations
        self._replace_session = replace_session_after_first_observation

    @override
    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
        self.requests.append(request)
        request_id, boot_id, connection_id = request.request_id, UUID(int=1), UUID(int=2)
        if isinstance(request, RuntimeOperationSubmit):
            return RuntimeOperationSubmitted(
                request_id=request_id,
                runtime_boot_id=boot_id,
                connection_id=connection_id,
                receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION_ID, secret_requirement=None),
            )
        if isinstance(request, RuntimeOperationControl):
            return RuntimeOperationAcknowledged(
                request_id=request_id, runtime_boot_id=boot_id, connection_id=connection_id, operation_id=_OPERATION_ID
            )
        assert isinstance(request, RuntimeOperationObserve)
        lifecycle = OperationLifecycle.RUNNING if self._running_left > 0 else OperationLifecycle.TERMINAL
        self._running_left -= 1
        if self._replace_session:
            self._session_id = uuid4()
        return RuntimeOperationObserved(
            request_id=request_id,
            runtime_boot_id=boot_id,
            connection_id=connection_id,
            observation=_observation(
                _contract(), profile_operation_subject(str(self._profile_id)), lifecycle=lifecycle
            ),
        )


def _settle(client: _Client) -> OperationPublicProjectionV1:
    pinned = PinnedConnection.of(client)
    return start_and_await_terminal(
        client,
        pinned,
        _OPERATION_ID,
        contract=_contract(),
        subject_ref=profile_operation_subject(str(client.profile_id)),
        deadline=deadline_after(30),
    )


def test_polling_continues_through_running_states_until_the_operation_is_terminal() -> None:
    client = _Client(running_observations=2)

    state = _settle(client)

    assert state.lifecycle is OperationLifecycle.TERMINAL
    assert [type(request) for request in client.requests] == [
        RuntimeOperationControl,
        RuntimeOperationObserve,
        RuntimeOperationObserve,
        RuntimeOperationObserve,
    ]


def test_a_session_replaced_while_polling_names_the_lost_connection_instead_of_polling_on() -> None:
    client = _Client(running_observations=5, replace_session_after_first_observation=True)

    with pytest.raises(RuntimeRefusalError) as lost:
        _settle(client)

    assert lost.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert sum(isinstance(request, RuntimeOperationObserve) for request in client.requests) == 1


def test_the_pinned_identity_is_exactly_profile_session_and_frontend() -> None:
    client = _Client(running_observations=0)
    pinned = PinnedConnection.of(client)

    assert pinned.holds(client)
    pinned.require_held(client)
    client._session_id = uuid4()
    assert not pinned.holds(client)
    with pytest.raises(RuntimeRefusalError) as lost:
        pinned.require_held(client)
    assert lost.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED


def test_a_submission_is_sent_under_the_pinned_session_with_its_optional_idempotency_key() -> None:
    client = _Client(running_observations=0)
    pinned = PinnedConnection.of(client)

    submitted = submit_operation(
        client,
        pinned,
        definition_id="user-profile.example",
        subject_ref="subject",
        payload_json="{}",
        deadline=deadline_after(30),
        idempotency_key="key-1",
    )

    assert submitted.receipt.operation_id == _OPERATION_ID
    (request,) = client.requests
    assert isinstance(request, RuntimeOperationSubmit)
    assert (request.profile_id, request.session_id) == (pinned.profile_id, pinned.session_id)
    assert request.idempotency_key == "key-1"


def test_a_refused_observation_surfaces_the_runtime_refusal_rather_than_polling() -> None:
    class _Refusing(_Client):
        @override
        def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationReply:
            if isinstance(request, RuntimeOperationObserve):
                raise RuntimeFrontendRefusedError("operation_denied")
            return super().operation(request, deadline=deadline)

    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        _settle(_Refusing(running_observations=1))

    assert refused.value.reason == "operation_denied"
