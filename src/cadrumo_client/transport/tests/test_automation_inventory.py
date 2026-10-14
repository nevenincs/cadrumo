"""The inventory client preserves canonical identity when the wire is lost."""

from __future__ import annotations

from datetime import timedelta
from typing import override
from uuid import UUID, uuid4

import pytest

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
from cadrumo.application.user_profile.access_contracts import AuthorityState
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationKeyProjection,
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

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationObserve,
    OperationObserved,
    OperationReply,
    OperationRequest,
    OperationSubmit,
    OperationSubmitted,
)
from ..automation_inventory import AutomationInventoryReadError, _exact_profile, read_automation_inventory
from ..frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _canonical_contract() -> OperationPublicDefinitionContractV1:
    definition = next(
        item
        for item in build_automation_operation_definitions()
        if item.definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    )
    return build_automation_operation_registrations((definition,))[0].contract


def _refused_observation(
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


class _InterruptedClient(FrontendClient):
    """Stop only after an actual typed submission receipt has been delivered."""

    def __init__(
        self,
        *,
        frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
        refusal_ref: str | None = None,
    ) -> None:
        self._profile_id = uuid4()
        self._frontend = frontend
        self._session_id = uuid4()
        self.operation_id = "a" * 64
        self.requests: list[OperationRequest] = []
        self.return_wrong_contract = False
        self.refusal_ref = refusal_ref

    @override
    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        assert definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID and deadline > 0
        contract = _canonical_contract()
        if self.return_wrong_contract:
            return contract.model_copy(update={"definition_id": "user-profile.other"})
        return contract

    @override
    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        assert deadline > 0
        self.requests.append(request)
        if isinstance(request, OperationSubmit):
            assert request.profile_id == self.profile_id and request.session_id == self.session_id
            return OperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=UUID(int=1),
                connection_id=UUID(int=2),
                receipt=OperationSubmissionReceiptV1(operation_id=self.operation_id, secret_requirement=None),
            )
        if isinstance(request, OperationControl) and self.refusal_ref is not None:
            return OperationAcknowledged(
                request_id=request.request_id,
                runtime_boot_id=UUID(int=1),
                connection_id=UUID(int=2),
                operation_id=self.operation_id,
            )
        if isinstance(request, OperationObserve) and self.refusal_ref is not None:
            contract = _canonical_contract()
            observation = _refused_observation(
                contract=contract,
                operation_id=self.operation_id,
                subject_ref=profile_operation_subject(str(self.profile_id)),
                refusal_ref=self.refusal_ref,
            )
            return OperationObserved(
                request_id=request.request_id,
                runtime_boot_id=UUID(int=1),
                connection_id=UUID(int=2),
                observation=observation,
            )
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)


@pytest.mark.parametrize("frontend", list(OperationFrontendProjection))
def test_post_submit_connection_loss_retains_id_and_unknown_effect_on_every_frontend(
    frontend: OperationFrontendProjection,
) -> None:
    client = _InterruptedClient(frontend=frontend)
    with pytest.raises(AutomationInventoryReadError) as failed:
        read_automation_inventory(client)
    assert isinstance(client.requests[0], OperationSubmit)
    assert failed.value.operation_id == client.operation_id
    assert failed.value.reason == RefusalCode.CONNECTION_CLOSED.value
    assert failed.value.terminal_condition is None and failed.value.effect is None
    assert failed.value.context == {
        "reason": RefusalCode.CONNECTION_CLOSED.value,
        "operation_id": client.operation_id,
        "effect": "unknown",
    }


def test_terminal_refusal_uses_public_refusal_reference_and_observed_context() -> None:
    refusal_ref = "refusal:inventory.denied"
    client = _InterruptedClient(refusal_ref=refusal_ref)

    with pytest.raises(AutomationInventoryReadError) as failed:
        read_automation_inventory(client)

    assert failed.value.reason == refusal_ref
    assert failed.value.context == {
        "reason": refusal_ref,
        "operation_id": client.operation_id,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
    }


def test_a_mismatched_contract_refuses_before_submission() -> None:
    client = _InterruptedClient()
    client.return_wrong_contract = True
    with pytest.raises(RefusalError, match=RefusalCode.INVALID_FRAME.value):
        read_automation_inventory(client)
    assert client.requests == []


def test_a_foreign_key_row_cannot_join_the_bound_profile_inventory() -> None:
    selected, foreign = uuid4(), uuid4()
    instant = now()
    projection = AutomationInventoryProjection(
        grants=(),
        keys=(
            AutomationKeyProjection(
                key_id=uuid4(),
                grant_id=uuid4(),
                profile_id=foreign,
                state=AuthorityState.ACTIVE,
                valid_from=instant,
                expires_at=instant + timedelta(days=1),
                last_used_at=None,
            ),
        ),
        requests=(),
    )
    assert not _exact_profile(projection, selected)
    assert _exact_profile(projection, foreign)
