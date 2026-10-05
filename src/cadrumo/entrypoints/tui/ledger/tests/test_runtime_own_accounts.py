"""Exact-session dispatch and receipt correlation for the installed own-account TUI door."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.ledger.own_account_operation import (
    LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    OwnAccountProjection,
    build_ledger_own_account_definition,
    build_ledger_own_account_registration,
)
from cadrumo.application.ledger.own_account_ports import OwnAccountRepositoryFactory
from cadrumo.application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.runtime_own_accounts import RuntimeOwnAccountTuiDoorV1
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 4, tzinfo=UTC)
_ES_IBAN = "ES9121000418450200051332"
_REFUSAL_CODE = "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
_REFUSAL_KEY = "errors.refused.refused_ledger_own_account_register_validation"


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID


class _Controller:
    operation_id = _OPERATION_ID

    def __init__(
        self,
        *,
        observation: OperationObservationSuccessV1,
        result: LedgerOwnAccountResult | None,
        detail: OperationErrorDetailV1 | None = None,
    ) -> None:
        self.observation = observation
        self.result = result
        self.detail = detail
        self.result_reads: list[tuple[type[BaseModel], int, bool]] = []
        self.detail_reads = 0

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
    ) -> LedgerOwnAccountResult:
        assert projection.operation_id == self.operation_id
        self.result_reads.append((result_type, result_version, allow_refusal_detail))
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection.operation_id == self.operation_id
        self.detail_reads += 1
        return self.detail


def _observation(
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
) -> OperationObservationSuccessV1:
    factory = cast(OwnAccountRepositoryFactory, cast(object, lambda **_kwargs: None))
    definition = build_ledger_own_account_definition(factory)
    registry = OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_ledger_own_account_registration(definition),),
    )
    contract = registry.lookup_public_contract(LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID)
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=registry.public_contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=effect,
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
        result_ref=None if refused else "f" * 64,
        refusal_ref=_REFUSAL_CODE if refused else None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def _account() -> OwnAccountProjection:
    return OwnAccountProjection(
        own_account_id="acc-01",
        label="main",
        holding=OwnAccountHolding.TITULAR,
        masked_iban="ES ···· 1332",
        country_code="ES",
        sepa_marca="1",
        has_swift_bic=False,
        has_bank_block=False,
        currency="EUR",
    )


def _install(monkeypatch: pytest.MonkeyPatch, client: _Client, controller: _Controller) -> list[dict[str, object]]:
    from cadrumo.entrypoints.tui.operations import runtime_profile_session as bridge

    def read_session(
        _client: RuntimeFrontendClient,
        *,
        profile_id: UUID,
        session_id: UUID,
        profile_label: str,
    ) -> object:
        assert profile_label == "Fixture profile"
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        return controller

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    return submissions


def _door(client: _Client) -> RuntimeOwnAccountTuiDoorV1:
    return RuntimeOwnAccountTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")


def _add_request() -> LedgerOwnAccountRequest:
    return LedgerOwnAccountRequest(
        profile_id=_PROFILE_ID,
        action="add",
        label="main",
        holding=OwnAccountHolding.TITULAR,
        iban=_ES_IBAN,
    )


def test_own_account_door_submits_the_exact_request_and_reads_its_masked_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    result = LedgerOwnAccountResult(
        profile_id=_PROFILE_ID, action="add", own_account_id="acc-01", accounts=(_account(),), changed=True
    )
    controller = _Controller(observation=_observation(effect=OperationEffect.UPDATED), result=result)
    submissions = _install(monkeypatch, client, controller)
    door = _door(client)

    assert door.profile_id == _PROFILE_ID
    assert asyncio.run(door(_add_request())) == result
    assert submissions[0]["definition_id"] == LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID
    assert submissions[0]["payload"] == _add_request()
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert controller.result_reads == [(LedgerOwnAccountResult, 1, False)]


@pytest.mark.parametrize(
    ("result", "effect"),
    [
        # A change that the receipt reports as having no effect.
        (
            LedgerOwnAccountResult(
                profile_id=_PROFILE_ID, action="add", own_account_id="acc-01", accounts=(_account(),), changed=True
            ),
            OperationEffect.NONE,
        ),
        # A result answering a different action.
        (
            LedgerOwnAccountResult(
                profile_id=_PROFILE_ID, action="list", own_account_id="acc-01", accounts=(_account(),), changed=True
            ),
            OperationEffect.UPDATED,
        ),
        # An add that names no account.
        (
            LedgerOwnAccountResult(profile_id=_PROFILE_ID, action="add", changed=True),
            OperationEffect.UPDATED,
        ),
    ],
)
def test_own_account_door_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch,
    result: LedgerOwnAccountResult,
    effect: OperationEffect,
) -> None:
    client = _Client()
    _install(monkeypatch, client, _Controller(observation=_observation(effect=effect), result=result))

    with pytest.raises(RuntimeRefusalError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.reason is RuntimeRefusalCode.INVALID_FRAME


def test_own_account_door_raises_the_recorded_refusal_of_a_refused_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key=_REFUSAL_KEY,
        context=(),
    )
    controller = _Controller(
        observation=_observation(condition=OperationTerminalCondition.REFUSED),
        result=None,
        detail=detail,
    )
    _install(monkeypatch, client, controller)
    request = LedgerOwnAccountRequest(profile_id=_PROFILE_ID, action="remove", own_account_id="acc-01")

    with pytest.raises(RecordedRegisteredError) as raised:
        asyncio.run(_door(client)(request))

    assert raised.value.recorded_code == _REFUSAL_CODE
    assert controller.detail_reads == 1
    assert controller.result_reads == []


def test_own_account_door_keeps_the_bare_code_when_no_detail_was_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(observation=_observation(condition=OperationTerminalCondition.REFUSED), result=None)
    _install(monkeypatch, client, controller)
    request = LedgerOwnAccountRequest(profile_id=_PROFILE_ID, action="remove", own_account_id="acc-01")

    with pytest.raises(RuntimeFrontendRefusedError) as raised:
        asyncio.run(_door(client)(request))

    assert raised.value.reason == _REFUSAL_CODE


def test_own_account_door_fails_closed_when_its_session_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    submissions = _install(monkeypatch, client, _Controller(observation=_observation(), result=None))
    door = _door(client)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door(LedgerOwnAccountRequest(profile_id=_PROFILE_ID, action="list")))

    assert submissions == []
