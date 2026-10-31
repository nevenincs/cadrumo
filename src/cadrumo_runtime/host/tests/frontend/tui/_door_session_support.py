"""Shared fakes for TUI doors proved against a real registry and a scripted operation controller."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.error_detail import OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
OTHER_PROFILE_ID = UUID("6cc00000-0000-4000-8000-0000000000cc")
SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
OPERATION_ID = "a" * 64
NOW = datetime(2026, 10, 4, tzinfo=UTC)
RECORDED_CODE = "REFUSED_LEDGER_EVIDENCE_INPUT"
RECORDED_KEY = "errors.refused.refused_ledger_evidence_input"


class SessionClient:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = PROFILE_ID
        self.session_id = SESSION_ID
        self.session_read_threads: list[int] = []
        """The thread of each blocking session read: at composition, then around each operation."""


@dataclass
class ScriptedController:
    operation_id = OPERATION_ID
    observation: OperationObservationSuccessV1
    result: BaseModel | None
    detail: OperationErrorDetailV1 | None = None
    client: SessionClient = field(default_factory=SessionClient)
    deadline: float | None = None
    result_reads: list[tuple[type[BaseModel], int, bool]] = field(default_factory=list)
    detail_reads: int = 0

    @property
    def definition_contract(self) -> OperationPublicDefinitionContractV1:
        return self.observation.projection.definition_contract

    async def start(self) -> str:
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert after_cursor == 0
        assert page_limit == 1
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        assert projection.operation_id == self.operation_id
        self.result_reads.append((result_type, result_version, allow_refusal_detail))
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection.operation_id == self.operation_id
        self.detail_reads += 1
        return self.detail


def terminal_observation(
    registry: OperationRegistry,
    definition_id: str,
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
    refusal_ref: str | None = None,
) -> OperationObservationSuccessV1:
    contract = registry.lookup_public_contract(definition_id)
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=OPERATION_ID,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=registry.public_contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=effect,
        phase_code=None,
        started_at=NOW,
        updated_at=NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None if refused else "f" * 64,
        refusal_ref=refusal_ref if refused else None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def install_scripted_controller(
    monkeypatch: pytest.MonkeyPatch, client: SessionClient, controller: ScriptedController
) -> list[dict[str, object]]:
    """Route the session bridge and controller submission to the scripted fakes; return the submissions."""
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def read_session(
        _client: FrontendClient,
        *,
        profile_id: UUID,
        session_id: UUID,
        profile_label: str,
    ) -> object:
        assert profile_label == "Fixture profile"
        client.session_read_threads.append(threading.get_ident())
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []

    async def submit(
        _controller_type: type[OperationController],
        received_client: FrontendClient,
        **kwargs: object,
    ) -> ScriptedController:
        assert received_client is client
        submissions.append(kwargs)
        controller.client = client
        return controller

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions
