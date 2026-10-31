"""Exact-session dispatch and receipt correlation for the installed own-account TUI door."""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID

import pytest

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
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1
from cadrumo.application.operations.registry import (
    OperationRegistry,
)
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui.runtime_own_accounts import RuntimeOwnAccountTuiDoorV1
from ._door_session_support import (
    PROFILE_ID,
    SESSION_ID,
    ScriptedController,
    SessionClient,
    install_scripted_controller,
    terminal_observation,
)
from .unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ES_IBAN = "ES9121000418450200051332"
_REFUSAL_CODE = "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
_REFUSAL_KEY = "errors.refused.refused_ledger_own_account_register_validation"


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
    return terminal_observation(
        registry,
        LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
        condition=condition,
        effect=effect,
        refusal_ref=_REFUSAL_CODE,
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


def _door(client: SessionClient) -> RuntimeOwnAccountTuiDoorV1:
    return RuntimeOwnAccountTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")


def _add_request() -> LedgerOwnAccountRequest:
    return LedgerOwnAccountRequest(
        profile_id=PROFILE_ID,
        action="add",
        label="main",
        holding=OwnAccountHolding.TITULAR,
        iban=_ES_IBAN,
    )


def test_own_account_door_submits_the_exact_request_and_reads_its_masked_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SessionClient()
    result = LedgerOwnAccountResult(
        profile_id=PROFILE_ID, action="add", own_account_id="acc-01", accounts=(_account(),), changed=True
    )
    controller = ScriptedController(observation=_observation(effect=OperationEffect.UPDATED), result=result)
    submissions = install_scripted_controller(monkeypatch, client, controller)
    door = _door(client)

    assert door.profile_id == PROFILE_ID
    assert asyncio.run(door(_add_request())) == result
    assert submissions[0]["definition_id"] == LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID
    assert submissions[0]["payload"] == _add_request()
    assert submissions[0]["expected_session_id"] == SESSION_ID
    assert controller.result_reads == [(LedgerOwnAccountResult, 1, False)]


def test_own_account_door_reads_its_session_binding_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = SessionClient()
    result = LedgerOwnAccountResult(
        profile_id=PROFILE_ID, action="add", own_account_id="acc-01", accounts=(_account(),), changed=True
    )
    install_scripted_controller(
        monkeypatch, client, ScriptedController(observation=_observation(effect=OperationEffect.UPDATED), result=result)
    )
    read_session = bridge.read_runtime_account_session
    on_loop: list[bool] = []

    def recording_read(
        received_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str
    ) -> object:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_loop.append(False)
        else:
            on_loop.append(True)
        return read_session(received_client, profile_id=profile_id, session_id=session_id, profile_label=profile_label)

    monkeypatch.setattr(bridge, "read_runtime_account_session", recording_read)
    door = _door(client)

    assert asyncio.run(door(_add_request())) == result
    # The constructor's check plus at least one during the submission.
    assert len(on_loop) >= 2
    assert not any(on_loop)


@pytest.mark.parametrize(
    ("result", "effect"),
    [
        # A change that the receipt reports as having no effect.
        (
            LedgerOwnAccountResult(
                profile_id=PROFILE_ID, action="add", own_account_id="acc-01", accounts=(_account(),), changed=True
            ),
            OperationEffect.NONE,
        ),
        # A result answering a different action.
        (
            LedgerOwnAccountResult(
                profile_id=PROFILE_ID, action="list", own_account_id="acc-01", accounts=(_account(),), changed=True
            ),
            OperationEffect.UPDATED,
        ),
        # An add that names no account.
        (
            LedgerOwnAccountResult(profile_id=PROFILE_ID, action="add", changed=True),
            OperationEffect.UPDATED,
        ),
    ],
)
def test_own_account_door_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch,
    result: LedgerOwnAccountResult,
    effect: OperationEffect,
) -> None:
    client = SessionClient()
    receipt = _observation(effect=effect)
    install_scripted_controller(monkeypatch, client, ScriptedController(observation=receipt, result=result))

    with raises_unsupported_result(effect, receipt.projection.definition_contract):
        asyncio.run(_door(client)(_add_request()))


def test_own_account_door_raises_the_recorded_refusal_of_a_refused_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SessionClient()
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key=_REFUSAL_KEY,
        context=(),
    )
    controller = ScriptedController(
        observation=_observation(condition=OperationTerminalCondition.REFUSED),
        result=None,
        detail=detail,
    )
    install_scripted_controller(monkeypatch, client, controller)
    request = LedgerOwnAccountRequest(profile_id=PROFILE_ID, action="remove", own_account_id="acc-01")

    with pytest.raises(RecordedRegisteredError) as raised:
        asyncio.run(_door(client)(request))

    assert raised.value.recorded_code == _REFUSAL_CODE
    assert controller.detail_reads == 1
    assert controller.result_reads == []


def test_own_account_door_keeps_the_bare_code_when_no_detail_was_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SessionClient()
    controller = ScriptedController(observation=_observation(condition=OperationTerminalCondition.REFUSED), result=None)
    install_scripted_controller(monkeypatch, client, controller)
    request = LedgerOwnAccountRequest(profile_id=PROFILE_ID, action="remove", own_account_id="acc-01")

    with pytest.raises(FrontendRefusedError) as raised:
        asyncio.run(_door(client)(request))

    assert raised.value.reason == _REFUSAL_CODE


def test_own_account_door_fails_closed_when_its_session_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SessionClient()
    submissions = install_scripted_controller(
        monkeypatch, client, ScriptedController(observation=_observation(), result=None)
    )
    door = _door(client)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door(LedgerOwnAccountRequest(profile_id=PROFILE_ID, action="list")))

    assert submissions == []
