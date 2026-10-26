"""A submitted TUI operation whose outcome is not known is reported as unknown, never as a refusal.

The doors submit through one exact-session helper. Once the runtime accepted
the submission, any failure may hide a saved change unless a terminal receipt
that committed nothing was observed, or the operation's definition permits no
effect that changes records. The operations are the registered own-account
write and the ledger review read, observed through their real definitions and
registrations; the session is checked by the real session reader against the
client's scripted status.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ActivityAssetAuthorityProvenance,
    ActivityAssetOperationPortsFactory,
)
from cadrumo.application.actividad_asset.activity_asset_projections import (
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
)
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetHistoryClaimResultSnapshot,
    ActivityAssetHistorySnapshot,
    ActivityAssetRevisionSnapshot,
    AmortizationClaimSnapshot,
)
from cadrumo.application.actividad_asset.registered_operations import (
    build_activity_asset_claim_definition,
    build_activity_asset_claim_registration,
    build_activity_asset_correct_definition,
    build_activity_asset_correct_registration,
    build_activity_asset_create_definition,
    build_activity_asset_create_registration,
)
from cadrumo.application.ledger.action_ports import LedgerActionPortsFactory
from cadrumo.application.ledger.own_account_operation import (
    LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    OwnAccountProjection,
    build_ledger_own_account_definition,
    build_ledger_own_account_registration,
)
from cadrumo.application.ledger.own_account_ports import OwnAccountRepositoryFactory
from cadrumo.application.ledger.review_operation import (
    LEDGER_REVIEW_OPERATION_DEFINITION_ID,
    LedgerReviewProjection,
    LedgerReviewRequest,
    build_ledger_review_definition,
    build_ledger_review_registration,
)
from cadrumo.application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
)
from cadrumo.application.operations.operation_definition import OperationDefinition
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code, resolve_error_message
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError, AccountSessionUnavailableError
from cadrumo.entrypoints.tui.ledger.models_actividad_asset import (
    ActivityAssetClaimRequestV1,
    ActivityAssetCorrectionRequestV1,
    ActivityAssetCreationRequestV1,
)
from cadrumo.entrypoints.tui.operations.outcome import (
    OperationOutcomeUnknownError,
    SessionExpiredOutcomeUnknownError,
    SessionUnavailableOutcomeUnknownError,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.operations.runtime_profile_session import RuntimeProfileSession
from ....frontend.tui.runtime_actividad_asset import RuntimeActivityAssetTuiActionsV1
from ....frontend.tui.runtime_ledger_review import RuntimeLedgerReviewTuiDoorV1
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
_LABEL = "Fixture profile"


@dataclass(frozen=True, slots=True)
class _Registered:
    """One operation as its real definition and registration declare it."""

    definition_id: str
    contract: OperationPublicDefinitionContractV1
    contract_set_digest: str
    result_type: type[BaseModel]
    allow_refusal_detail: bool = False
    """Whether the door reads a declared refusal's result, as the activity-asset doors do."""


def _registered(
    registry: OperationRegistry,
    definition_id: str,
    result_type: type[BaseModel],
    *,
    allow_refusal_detail: bool = False,
) -> _Registered:
    return _Registered(
        definition_id=definition_id,
        contract=registry.lookup_public_contract(definition_id),
        contract_set_digest=registry.public_contract_set.contract_set_digest,
        result_type=result_type,
        allow_refusal_detail=allow_refusal_detail,
    )


def _own_account() -> _Registered:
    """The own-account register: a write whose definition permits an updated effect."""
    factory = cast(OwnAccountRepositoryFactory, cast(object, lambda **_kwargs: None))
    definition = build_ledger_own_account_definition(factory)
    registry = OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_ledger_own_account_registration(definition),),
    )
    return _registered(registry, LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID, LedgerOwnAccountResult)


def _review() -> _Registered:
    """The ledger review queue: a read whose definition permits no effect that changes records."""
    actions = cast(LedgerActionPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_ledger_review_definition(actions)
    registry = OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_ledger_review_registration(definition),),
    )
    return _registered(registry, LEDGER_REVIEW_OPERATION_DEFINITION_ID, LedgerReviewProjection)


_OWN_ACCOUNT = _own_account()
_REVIEW = _review()


class _Client:
    """The retained runtime connection, answering status the way the runtime does."""

    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID
        self.subscriptions = 0
        self.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        self.transport_closed = False
        """Set by a failed exchange: the transport closes, and every later exchange is refused."""

    def subscribe_operation_changes(self, _receive: Callable[[], None]) -> Callable[[], None]:
        """Accept the operation cue and never fire it: the operation never advances."""
        self.subscriptions += 1
        return lambda: None

    def status(self) -> SimpleNamespace:
        if self.transport_closed:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        return SimpleNamespace(
            status=SimpleNamespace(
                connected=True,
                credential_authenticated=True,
                profile_bound=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=self.session_expires_at,
                denial=None,
            )
        )


class _Controller:
    """The submitted operation as the real controller reports it, with each exchange scripted."""

    operation_id = _OPERATION_ID
    client: _Client

    def __init__(
        self,
        registered: _Registered,
        *,
        observation: OperationObservationSuccessV1 | OperationObservationRefusalV1,
        result: BaseModel | None = None,
        detail: OperationErrorDetailV1 | None = None,
        result_refusal: Exception | None = None,
        observe_failure: RefusalError | None = None,
        start_failure: RefusalError | None = None,
        closes_transport: bool = False,
        on_observe: Callable[[], None] = lambda: None,
        on_detail: Callable[[], None] = lambda: None,
    ) -> None:
        self.registered = registered
        self.definition_contract = registered.contract
        self.observation = observation
        self.result = result
        self.detail = detail
        self.result_refusal = result_refusal
        self.observe_failure = observe_failure
        self.start_failure = start_failure
        self.closes_transport = closes_transport
        self.on_observe = on_observe
        self.on_detail = on_detail
        self.observations = 0
        self.result_reads = 0

    async def start(self) -> str:
        if self.start_failure is not None:
            raise self.start_failure
        return self.operation_id

    async def observe(
        self, after_cursor: int, *, page_limit: int
    ) -> OperationObservationSuccessV1 | OperationObservationRefusalV1:
        assert (after_cursor, page_limit) == (0, 1)
        self.observations += 1
        self.on_observe()
        if self.observe_failure is not None:
            # A failed exchange closes the transport before the refusal reaches the caller.
            self.client.transport_closed = self.closes_transport
            raise self.observe_failure
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
        assert (result_type, result_version, allow_refusal_detail) == (
            self.registered.result_type,
            1,
            self.registered.allow_refusal_detail,
        )
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
    registered: _Registered = _OWN_ACCOUNT,
    *,
    lifecycle: OperationLifecycle = OperationLifecycle.TERMINAL,
    condition: OperationTerminalCondition | None = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
) -> OperationObservationSuccessV1:
    """One observation of ``registered`` under its real public contract."""
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=registered.definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=registered.contract,
        contract_set_digest=registered.contract_set_digest,
        lifecycle=lifecycle,
        terminal_condition=condition,
        effect=effect,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=registered.contract.close_policy,
        cancellation=registered.contract.cancellation,
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


def _running(registered: _Registered = _OWN_ACCOUNT) -> OperationObservationSuccessV1:
    return _observation(registered, lifecycle=OperationLifecycle.RUNNING, condition=None)


def _install(monkeypatch: pytest.MonkeyPatch, client: _Client, controller: _Controller) -> list[dict[str, object]]:
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
    return RuntimeOwnAccountTuiDoorV1(cast(FrontendClient, client), profile_label=_LABEL)


def _review_door(client: _Client) -> RuntimeLedgerReviewTuiDoorV1:
    return RuntimeLedgerReviewTuiDoorV1(RuntimeProfileSession(cast(FrontendClient, client), profile_label=_LABEL))


def _add_request() -> LedgerOwnAccountRequest:
    return LedgerOwnAccountRequest(
        profile_id=_PROFILE_ID,
        action="add",
        label="main",
        holding=OwnAccountHolding.TITULAR,
        iban=_ES_IBAN,
    )


def _added(*, changed: bool = True) -> LedgerOwnAccountResult:
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
        profile_id=_PROFILE_ID, action="add", own_account_id="acc-01", accounts=(account,), changed=changed
    )


def _recorded_detail() -> OperationErrorDetailV1:
    return OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key=_REFUSAL_KEY,
        context=(),
    )


def _english(error: BaseException) -> str:
    with override_settings(cadrumo_output_language="en"):
        return resolve_error_message(error)


def test_a_write_still_running_at_the_deadline_is_unknown_not_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = _Client()
    controller = _Controller(_OWN_ACCOUNT, observation=_running())
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
    controller = _Controller(_OWN_ACCOUNT, observation=failed, detail=_recorded_detail())
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
    _install(monkeypatch, client, _Controller(_OWN_ACCOUNT, observation=failed))

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.effect is OperationEffect.PARTIAL
    assert isinstance(raised.value.reason, FrontendRefusedError)


def test_a_succeeded_write_whose_result_read_times_out_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    succeeded = _observation(effect=OperationEffect.UPDATED)
    controller = _Controller(
        _OWN_ACCOUNT, observation=succeeded, result_refusal=RefusalError(RefusalCode.DEADLINE_EXCEEDED)
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.effect is OperationEffect.UPDATED
    assert controller.result_reads == 1


def test_a_refused_observation_of_a_started_write_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runtime refused to say how the started write stands, so it may have saved the change."""
    client = _Client()
    refused = OperationObservationRefusalV1(
        code=OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE, requested_version=1, diagnostic_ref=None
    )
    controller = _Controller(_OWN_ACCOUNT, observation=refused)
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is None
    assert isinstance(raised.value.reason, FrontendRefusedError)
    assert raised.value.reason.reason == OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE.value
    assert controller.result_reads == 0


@pytest.mark.parametrize(
    "refusal",
    [FrontendRefusedError("result_unavailable"), RefusalError(RefusalCode.INVALID_FRAME)],
    ids=["refused", "invalid-frame"],
)
def test_a_result_read_that_fails_after_an_updated_receipt_is_unknown(
    monkeypatch: pytest.MonkeyPatch, refusal: Exception
) -> None:
    """The receipt said the change was saved; failing to read what it saved does not unsave it."""
    client = _Client()
    succeeded = _observation(effect=OperationEffect.UPDATED)
    controller = _Controller(_OWN_ACCOUNT, observation=succeeded, result_refusal=refusal)
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.effect is OperationEffect.UPDATED
    assert raised.value.reason is refusal
    assert raised.value.__cause__ is refusal
    assert controller.result_reads == 1


def test_a_result_that_disagrees_with_an_updated_receipt_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The door's correlation refuses the result, but the receipt already reported a saved change."""
    client = _Client()
    succeeded = _observation(effect=OperationEffect.UPDATED)
    # A result that claims nothing changed cannot correlate with a receipt that reports an update.
    controller = _Controller(_OWN_ACCOUNT, observation=succeeded, result=_added(changed=False))
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.effect is OperationEffect.UPDATED
    assert isinstance(raised.value.reason, RefusalError)
    assert raised.value.reason.reason is RefusalCode.INVALID_FRAME


def test_a_start_whose_acknowledgement_is_malformed_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runtime accepted the submission; an unreadable start acknowledgement does not say the write never ran."""
    client = _Client()
    controller = _Controller(
        _OWN_ACCOUNT, observation=_running(), start_failure=RefusalError(RefusalCode.INVALID_FRAME)
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is None
    assert controller.observations == 0


def test_a_dropped_connection_with_the_session_live_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(
        _OWN_ACCOUNT, observation=_running(), observe_failure=RefusalError(RefusalCode.CONNECTION_CLOSED)
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert not isinstance(raised.value, AccountSessionExpiredError)
    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is None
    assert _OPERATION_ID in _english(raised.value)


def test_a_dropped_connection_whose_session_expired_says_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """The session is gone, so the operator must sign in; the change may still be saved, so they are told."""
    client = _Client()

    def expire() -> None:
        client.session_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    controller = _Controller(
        _OWN_ACCOUNT,
        observation=_running(),
        observe_failure=RefusalError(RefusalCode.CONNECTION_CLOSED),
        on_observe=expire,
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(AccountSessionExpiredError) as raised:
        asyncio.run(_door(client)(_add_request()))

    error = raised.value
    assert isinstance(error, SessionExpiredOutcomeUnknownError)
    assert not isinstance(error, AccountSessionUnavailableError)
    assert error.outcome.operation_id == _OPERATION_ID
    assert error.outcome.effect is None
    assert get_registered_error_code(error).code == "FAIL_TUI_SESSION_EXPIRED_OUTCOME_UNKNOWN"
    message = _english(error)
    assert _OPERATION_ID in message
    assert message != _english(AccountSessionExpiredError())


def test_a_dropped_connection_that_closed_the_transport_is_unavailable_and_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed transport cannot report the session, so nothing says it expired: it is unavailable."""
    client = _Client()
    controller = _Controller(
        _OWN_ACCOUNT,
        observation=_running(),
        observe_failure=RefusalError(RefusalCode.CONNECTION_CLOSED),
        closes_transport=True,
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(AccountSessionUnavailableError) as raised:
        asyncio.run(_door(client)(_add_request()))

    error = raised.value
    assert isinstance(error, SessionUnavailableOutcomeUnknownError)
    assert error.outcome.operation_id == _OPERATION_ID
    assert get_registered_error_code(error).code == "FAIL_TUI_SESSION_UNAVAILABLE_OUTCOME_UNKNOWN"
    assert _OPERATION_ID in _english(error)


def test_a_lapsed_session_after_a_failed_receipt_with_an_effect_says_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    failed = _observation(condition=OperationTerminalCondition.FAILED, effect=OperationEffect.UNKNOWN)

    def lapse() -> None:
        client.session_id = _LAPSED_SESSION_ID

    _install(
        monkeypatch, client, _Controller(_OWN_ACCOUNT, observation=failed, detail=_recorded_detail(), on_detail=lapse)
    )
    door = _door(client)

    with pytest.raises(SessionExpiredOutcomeUnknownError) as raised:
        asyncio.run(door(_add_request()))

    assert raised.value.outcome.operation_id == _OPERATION_ID
    assert raised.value.outcome.effect is OperationEffect.UNKNOWN
    assert isinstance(raised.value.outcome.reason, RecordedRegisteredError)


def test_a_lapsed_session_after_a_receipt_that_committed_nothing_reports_the_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    refused = _observation(condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)

    def lapse() -> None:
        client.session_id = _LAPSED_SESSION_ID

    _install(
        monkeypatch, client, _Controller(_OWN_ACCOUNT, observation=refused, detail=_recorded_detail(), on_detail=lapse)
    )
    door = _door(client)

    with pytest.raises(AccountSessionExpiredError) as raised:
        asyncio.run(door(_add_request()))

    assert not isinstance(raised.value, SessionExpiredOutcomeUnknownError)
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
        "effect": OperationEffect.NONE.value,
        "refusal_code": _REFUSAL_CODE,
    }


def test_a_read_that_times_out_stays_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A read's definition permits no effect that changes records, so nothing may have been saved."""
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = _Client()
    controller = _Controller(_REVIEW, observation=_running(_REVIEW))
    _install(monkeypatch, client, controller)
    monkeypatch.setattr(bridge, "_OPERATION_TIMEOUT_SECONDS", 0.2)

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_review_door(client)(LedgerReviewRequest(profile_id=_PROFILE_ID)))

    assert raised.value.reason is RefusalCode.DEADLINE_EXCEEDED
    assert controller.observations >= 2


def test_a_read_that_settles_with_an_unknown_effect_stays_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every definition may settle unknown after owner loss; for a read that still changes no records."""
    client = _Client()
    failed = _observation(_REVIEW, condition=OperationTerminalCondition.FAILED, effect=OperationEffect.UNKNOWN)
    _install(monkeypatch, client, _Controller(_REVIEW, observation=failed))

    with pytest.raises(FrontendRefusedError):
        asyncio.run(_review_door(client)(LedgerReviewRequest(profile_id=_PROFILE_ID)))


def test_a_submission_whose_reply_is_lost_stays_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an accepted submission there is no operation to start, so nothing ran."""
    client = _Client()

    async def submit(
        _controller_type: type[OperationController], _client: FrontendClient, **_kwargs: object
    ) -> _Controller:
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert not isinstance(raised.value, OperationOutcomeUnknownError)
    assert raised.value.reason is RefusalCode.CONNECTION_CLOSED


def test_a_receipt_that_committed_nothing_stays_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    refused = _observation(condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(_OWN_ACCOUNT, observation=refused, detail=_recorded_detail()))

    with pytest.raises(RecordedRegisteredError) as recorded:
        asyncio.run(_door(client)(_add_request()))
    assert recorded.value.recorded_code == _REFUSAL_CODE

    failed = _observation(condition=OperationTerminalCondition.FAILED, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(_OWN_ACCOUNT, observation=failed))
    with pytest.raises(FrontendRefusedError):
        asyncio.run(_door(client)(_add_request()))


def test_a_refusal_whose_detail_read_times_out_stays_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A receipt that committed nothing is a refusal however its explanation is lost."""
    client = _Client()
    refused = _observation(condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)

    def deadline() -> None:
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)

    _install(
        monkeypatch,
        client,
        _Controller(_OWN_ACCOUNT, observation=refused, detail=_recorded_detail(), on_detail=deadline),
    )

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.reason is RefusalCode.DEADLINE_EXCEEDED


def test_a_result_the_receipt_does_not_support_stays_an_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    # A change the receipt reports as having no effect: nothing was committed, so the frame is simply invalid.
    succeeded = _observation(effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(_OWN_ACCOUNT, observation=succeeded, result=_added()))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client)(_add_request()))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


# -- Activity-asset writes -----------------------------------------------------------

_ASSET_ID = "outcome-asset"
_ASSET_AUTHORITY = ActivityAssetAuthorityProvenance(logical_generation="b" * 64, reader_incarnation="c" * 64)


def _asset_registered(
    definition_id: str,
    build_definition: Callable[[ActivityAssetOperationPortsFactory], OperationDefinition],
    build_registration: Callable[[OperationDefinition], OperationPublicDefinitionRegistrationV1],
    result_type: type[BaseModel],
) -> _Registered:
    """An activity-asset write as its real definition and registration declare it."""
    definition = build_definition(cast(ActivityAssetOperationPortsFactory, cast(object, lambda **_kwargs: None)))
    registry = OperationRegistry(definitions=(definition,), public_registrations=(build_registration(definition),))
    return _registered(registry, definition_id, result_type, allow_refusal_detail=True)


def _asset_revision(asset_id: str = _ASSET_ID) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="1" * 64,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="2" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000"),
            prior_allocation_provenance="outcome fixture allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-informacion-software",
        ),
    )


def _asset_forecast(revision: ActivityAssetRevision) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=2025,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="outcome-fixture-v1",
            source_reference="outcome fixture only",
        ),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=AssetScheduleHistory(),
        requested_free_amount=None,
    )


def _another_assets_history() -> ActivityAssetHistorySnapshot:
    """A persisted history that holds no revision of the asset the write named."""
    return ActivityAssetHistorySnapshot(
        revisions=(ActivityAssetRevisionSnapshot.from_domain(_asset_revision("other")),)
    )


def _asset_create(door: RuntimeActivityAssetTuiActionsV1) -> object:
    return door.create(ActivityAssetCreationRequestV1(revision=_asset_revision()))


def _asset_correct(door: RuntimeActivityAssetTuiActionsV1) -> object:
    return door.correct(ActivityAssetCorrectionRequestV1(revision=_asset_revision()))


def _asset_claim(door: RuntimeActivityAssetTuiActionsV1) -> object:
    return door.record_claim(
        ActivityAssetClaimRequestV1(forecast=_asset_forecast(_asset_revision()), creating_operation="asset.tui.claim")
    )


def _another_claim() -> ActivityAssetClaimProjection:
    """A saved claim for the same forecast but another creating operation, so not the claim requested."""
    revision = _asset_revision()
    claim = AmortizationClaim.from_schedule(
        _asset_forecast(revision), asset_kind=revision.asset_kind, creating_operation="asset.tui.other"
    )
    return ActivityAssetClaimProjection(
        profile_id=_PROFILE_ID,
        authority=_ASSET_AUTHORITY,
        outcome="succeeded",
        claim_result=ActivityAssetHistoryClaimResultSnapshot(
            history=ActivityAssetHistorySnapshot(revisions=(ActivityAssetRevisionSnapshot.from_domain(revision),)),
            claim=AmortizationClaimSnapshot.from_domain(claim),
            reused_existing_claim=False,
        ),
        claim_id=claim.claim_id,
    )


_ASSET_WRITES: dict[str, tuple[_Registered, Callable[[RuntimeActivityAssetTuiActionsV1], object], BaseModel]] = {
    "create": (
        _asset_registered(
            ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
            build_activity_asset_create_definition,
            build_activity_asset_create_registration,
            ActivityAssetCreateProjection,
        ),
        _asset_create,
        ActivityAssetCreateProjection(
            profile_id=_PROFILE_ID, authority=_ASSET_AUTHORITY, outcome="succeeded", history=_another_assets_history()
        ),
    ),
    "correct": (
        _asset_registered(
            ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
            build_activity_asset_correct_definition,
            build_activity_asset_correct_registration,
            ActivityAssetCorrectProjection,
        ),
        _asset_correct,
        ActivityAssetCorrectProjection(
            profile_id=_PROFILE_ID, authority=_ASSET_AUTHORITY, outcome="succeeded", history=_another_assets_history()
        ),
    ),
    "claim": (
        _asset_registered(
            ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
            build_activity_asset_claim_definition,
            build_activity_asset_claim_registration,
            ActivityAssetClaimProjection,
        ),
        _asset_claim,
        _another_claim(),
    ),
}


@pytest.mark.parametrize("write", sorted(_ASSET_WRITES))
def test_an_asset_write_whose_result_disagrees_with_an_updated_receipt_is_unknown(
    monkeypatch: pytest.MonkeyPatch, write: str
) -> None:
    """The receipt reported the asset change saved; a result that does not account for the request leaves it unknown."""
    registered, submit, result = _ASSET_WRITES[write]
    client = _Client()
    controller = _Controller(
        registered, observation=_observation(registered, effect=OperationEffect.UPDATED), result=result
    )
    _install(monkeypatch, client, controller)
    door = RuntimeActivityAssetTuiActionsV1(cast(FrontendClient, client), profile_label=_LABEL)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        submit(door)

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is OperationEffect.UPDATED
    assert isinstance(raised.value.reason, RefusalError)
    assert raised.value.reason.reason is RefusalCode.INVALID_FRAME
    assert controller.result_reads == 1
