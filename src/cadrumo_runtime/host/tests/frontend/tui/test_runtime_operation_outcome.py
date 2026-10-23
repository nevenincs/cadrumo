"""A submitted TUI operation whose outcome is not known is reported as unknown, never as a refusal.

The doors submit through one exact-session helper. Once the operation is
submitted, a wait that ends before its settlement is observed, or a receipt
that did not succeed yet reports an effect, may hide a saved change; only a
receipt that committed nothing is a refusal. The operation is the registered
own-account write, observed through its real definition and registration.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

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
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.operations.outcome import OperationOutcomeUnknownError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_own_accounts import RuntimeOwnAccountTuiDoorV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_LAPSED_SESSION_ID = UUID("7cc00000-0000-4000-8000-0000000000cc")
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
        self.subscriptions = 0

    def subscribe_operation_changes(self, _receive: Callable[[], None]) -> Callable[[], None]:
        """Accept the operation cue and never fire it: the operation never advances."""
        self.subscriptions += 1
        return lambda: None


class _Controller:
    """The submitted operation as the real controller reports it, with each exchange scripted."""

    operation_id = _OPERATION_ID
    client: _Client

    def __init__(
        self,
        *,
        observation: OperationObservationSuccessV1,
        result: BaseModel | None = None,
        detail: OperationErrorDetailV1 | None = None,
        result_refusal: RefusalError | None = None,
        on_detail: Callable[[], None] = lambda: None,
    ) -> None:
        self.observation = observation
        self.result = result
        self.detail = detail
        self.result_refusal = result_refusal
        self.on_detail = on_detail
        self.observations = 0
        self.result_reads = 0

    async def start(self) -> str:
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert (after_cursor, page_limit) == (0, 1)
        self.observations += 1
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
        assert (result_type, result_version, allow_refusal_detail) == (LedgerOwnAccountResult, 1, False)
        self.result_reads += 1
        if self.result_refusal is not None:
            raise self.result_refusal
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection.operation_id == self.operation_id
        self.on_detail()
        return self.detail


def _observation(
    *,
    lifecycle: OperationLifecycle = OperationLifecycle.TERMINAL,
    condition: OperationTerminalCondition | None = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
) -> OperationObservationSuccessV1:
    """One observation of the own-account operation through its real definition and registration."""
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
        lifecycle=lifecycle,
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
        result_ref="f" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
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


def _install(monkeypatch: pytest.MonkeyPatch, client: _Client, controller: _Controller) -> list[dict[str, object]]:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def read_session(
        _client: FrontendClient,
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
        _controller_type: type[OperationController],
        received_client: FrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        controller.client = client
        return controller

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions


def _door(client: _Client) -> RuntimeOwnAccountTuiDoorV1:
    return RuntimeOwnAccountTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")


def _add_request() -> LedgerOwnAccountRequest:
    return LedgerOwnAccountRequest(
        profile_id=_PROFILE_ID,
        action="add",
        label="main",
        holding=OwnAccountHolding.TITULAR,
        iban=_ES_IBAN,
    )


def _added() -> LedgerOwnAccountResult:
    account = OwnAccountProjection(
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
    return LedgerOwnAccountResult(
        profile_id=_PROFILE_ID, action="add", own_account_id="acc-01", accounts=(account,), changed=True
    )


def _recorded_detail() -> OperationErrorDetailV1:
    return OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key=_REFUSAL_KEY,
        context=(),
    )


def test_a_write_still_running_at_the_deadline_is_unknown_not_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = _Client()
    running = _observation(lifecycle=OperationLifecycle.RUNNING, condition=None)
    controller = _Controller(observation=running)
    submissions = _install(monkeypatch, client, controller)
    # The real observation loop runs against a short deadline, so the budget itself expires.
    monkeypatch.setattr(bridge, "_OPERATION_TIMEOUT_SECONDS", 0.2)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is None
    assert isinstance(raised.value.__cause__, RefusalError)
    assert raised.value.__cause__.reason is RefusalCode.DEADLINE_EXCEEDED
    assert len(submissions) == 1
    assert controller.observations >= 2
    assert client.subscriptions == 1
    assert controller.result_reads == 0
    assert raised.value.context is not None
    assert raised.value.context["operation_id"] == _OPERATION_ID
    assert _OPERATION_ID in resolve_error_message(raised.value)


@pytest.mark.parametrize("effect", [OperationEffect.UNKNOWN, OperationEffect.PARTIAL, OperationEffect.UPDATED])
def test_a_failed_receipt_with_an_effect_is_unknown_and_keeps_the_recorded_reason(
    monkeypatch: pytest.MonkeyPatch, effect: OperationEffect
) -> None:
    client = _Client()
    failed = _observation(condition=OperationTerminalCondition.FAILED, effect=effect)
    controller = _Controller(observation=failed, detail=_recorded_detail())
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is effect
    reason = raised.value.reason
    assert isinstance(reason, RecordedRegisteredError)
    assert reason.recorded_code == _REFUSAL_CODE
    assert controller.result_reads == 0


def test_a_failed_receipt_with_an_effect_and_no_recorded_reason_is_still_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    failed = _observation(condition=OperationTerminalCondition.FAILED, effect=OperationEffect.PARTIAL)
    _install(monkeypatch, client, _Controller(observation=failed))

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.effect is OperationEffect.PARTIAL
    assert raised.value.reason is None


def test_a_succeeded_write_whose_result_read_times_out_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    succeeded = _observation(effect=OperationEffect.UPDATED)
    controller = _Controller(observation=succeeded, result_refusal=RefusalError(RefusalCode.DEADLINE_EXCEEDED))
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.effect is OperationEffect.UPDATED
    assert controller.result_reads == 1


def test_a_receipt_that_committed_nothing_stays_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    refused = _observation(condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(observation=refused, detail=_recorded_detail()))

    with pytest.raises(RecordedRegisteredError) as recorded:
        asyncio.run(_door(client)(_add_request()))
    assert recorded.value.recorded_code == _REFUSAL_CODE

    failed = _observation(condition=OperationTerminalCondition.FAILED, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(observation=failed))
    with pytest.raises(FrontendRefusedError):
        asyncio.run(_door(client)(_add_request()))


def test_a_refusal_whose_detail_read_times_out_stays_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A receipt that committed nothing is a refusal however its explanation is lost."""
    client = _Client()
    refused = _observation(condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)

    def deadline() -> None:
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)

    _install(monkeypatch, client, _Controller(observation=refused, detail=_recorded_detail(), on_detail=deadline))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.reason is RefusalCode.DEADLINE_EXCEEDED


def test_a_result_the_receipt_does_not_support_stays_an_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    # A change the receipt reports as having no effect.
    succeeded = _observation(effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(observation=succeeded, result=_added()))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_a_lapsed_session_reports_the_receipt_rather_than_an_unknown_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    failed = _observation(condition=OperationTerminalCondition.FAILED, effect=OperationEffect.UNKNOWN)

    def lapse() -> None:
        client.session_id = _LAPSED_SESSION_ID

    _install(monkeypatch, client, _Controller(observation=failed, detail=_recorded_detail(), on_detail=lapse))
    door = _door(client)

    with pytest.raises(AccountSessionExpiredError) as raised:
        asyncio.run(door(_add_request()))

    assert not isinstance(raised.value, OperationOutcomeUnknownError)
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.FAILED.value,
        "effect": OperationEffect.UNKNOWN.value,
        "refusal_code": None,
    }
