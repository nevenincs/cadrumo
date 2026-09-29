"""Runtime-backed Modelo actions retain canonical refusal identity and effect."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    build_modelo_work_m303_attestation_definition,
    build_modelo_work_m303_attestation_registration,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.tui.modelo import runtime_lifecycle
from cadrumo.entrypoints.tui.modelo.lifecycle import (
    ModeloLifecycleActionUnavailableError,
    ModeloWorkspaceLifecycleDoor,
)
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_REFUSAL_CODE = "REFUSED_MODELO_M303_EXONERADO_390_ATTESTATION_UNADMISSIBLE"
_NOW = datetime(2026, 9, 28, tzinfo=UTC)


class _StartFailureController:
    operation_id = _OPERATION_ID

    async def start(self) -> None:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def test_lifecycle_start_transport_failure_keeps_submitted_identity_and_unknown_effect() -> None:
    controller = _StartFailureController()

    async def submit(_request: object) -> _StartFailureController:
        return controller

    door = ModeloWorkspaceLifecycleDoor(
        work_unit_id=_WORK_UNIT_ID,
        submit_operation=cast(Any, submit),
    )

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        asyncio.run(door.calculate())

    assert str(raised.value) == RuntimeRefusalCode.CONNECTION_CLOSED.value
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "effect": OperationEffect.UNKNOWN.value,
    }


@lru_cache(maxsize=1)
def _attestation_contract_set():
    definition = build_modelo_work_m303_attestation_definition(
        work_lifecycle_ports_factory=cast(Any, lambda _profile_id: None),
        attachment_store_factory=cast(Any, lambda _profile_id: None),
    )
    registration = build_modelo_work_m303_attestation_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)).public_contract_set


def _terminal_refused_observation() -> OperationObservationSuccessV1:
    contracts = _attestation_contract_set()
    contract = contracts.definitions[0]
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        subject_ref=_WORK_UNIT_ID,
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
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
        refusal_ref=_REFUSAL_CODE,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    event_page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=0,
        requested_cursor=0,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=event_page)


class _AttestationController:
    operation_id = _OPERATION_ID

    def __init__(self, *, start_error: RuntimeRefusalError | None = None) -> None:
        self.start_error = start_error
        self.started = False
        self.observation = _terminal_refused_observation()

    async def start(self) -> None:
        self.started = True
        if self.start_error is not None:
            raise self.start_error

    async def observe(self, _after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert page_limit == 1
        return self.observation


def _attestation_inputs(session_id: UUID) -> tuple[Any, Any]:
    client = SimpleNamespace(profile_id=uuid4(), session_id=session_id)
    lifecycle = SimpleNamespace(target=SimpleNamespace(work_unit_id=_WORK_UNIT_ID))
    return client, lifecycle


def _bind_controller_submit(monkeypatch: pytest.MonkeyPatch, controller: _AttestationController) -> None:
    async def submit(client: SimpleNamespace, **kwargs: object) -> _AttestationController:
        assert kwargs["definition_id"] == MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == _WORK_UNIT_ID
        assert kwargs["expected_session_id"] == client.session_id
        return controller

    monkeypatch.setattr(RuntimeOperationController, "submit", submit)


def test_attestation_start_transport_failure_retains_canonical_reason_and_unknown_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid4()
    client, lifecycle = _attestation_inputs(session_id)
    controller = _AttestationController(start_error=RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED))
    _bind_controller_submit(monkeypatch, controller)

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        asyncio.run(
            runtime_lifecycle._admit_attestation(
                cast(RuntimeFrontendClient, client),
                lifecycle,
                _NOW,
                session_id,
            )
        )

    assert controller.started
    assert str(raised.value) == RuntimeRefusalCode.CONNECTION_CLOSED.value
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "effect": OperationEffect.UNKNOWN.value,
    }


def test_attestation_terminal_refusal_uses_registered_refusal_code_and_observed_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid4()
    client, lifecycle = _attestation_inputs(session_id)
    controller = _AttestationController()
    _bind_controller_submit(monkeypatch, controller)

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        asyncio.run(
            runtime_lifecycle._admit_attestation(
                cast(RuntimeFrontendClient, client),
                lifecycle,
                _NOW,
                session_id,
            )
        )

    assert controller.started
    assert str(raised.value) == _REFUSAL_CODE
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
        "effect": OperationEffect.NONE.value,
    }
