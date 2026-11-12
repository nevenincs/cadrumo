"""Runtime-backed IVA balance reads and recordings keep the registered refusal, the profile and the session.

The operation contracts are the real wallet definitions' public contracts. The
controller stands at the transport boundary: it hands back the terminal
projection, the recorded refusal detail and the settled result a worker would
release, so the cases check what the host adapter submits and what it accepts
back. A refusal is the application's own recorded detail; a failure after a
recording was sent is raised unchanged so the screen keeps its outcome unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.modelo.iva_wallet_balance_operation import (
    MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletBalanceProjection,
    ModeloIvaWalletBalanceRequest,
    build_modelo_iva_wallet_balance_definition,
    build_modelo_iva_wallet_balance_registration,
)
from cadrumo.application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
    ModeloIvaWalletCorrectionRequest,
    build_modelo_iva_wallet_correction_definition,
    build_modelo_iva_wallet_correction_registration,
)
from cadrumo.application.modelo.iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideProjection,
    ModeloIvaWalletOverrideRequest,
    build_modelo_iva_wallet_override_definition,
    build_modelo_iva_wallet_override_registration,
)
from cadrumo.application.modelo.iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedProjection,
    ModeloIvaWalletSeedRequest,
    build_modelo_iva_wallet_seed_definition,
    build_modelo_iva_wallet_seed_registration,
)
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.entrypoints.tui.modelo.wallet import (
    IvaWalletActionKind,
    IvaWalletEntryV1,
    IvaWalletNotSentError,
    IvaWalletRefusedError,
)
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from .....frontend.tui.modelo import runtime_wallet
from .....frontend.tui.modelo.runtime_wallet import RuntimeModeloIvaWallet

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)
_YEAR = newest_authored_edition("303")
_PERIOD = PublicPeriod(filing_year=_YEAR, code="1T")
_NIF = "00000000T"


@lru_cache(maxsize=1)
def _contracts():
    factory = cast(Any, lambda **_kwargs: None)
    definitions = (
        build_modelo_iva_wallet_balance_definition(factory),
        build_modelo_iva_wallet_correction_definition(factory),
        build_modelo_iva_wallet_override_definition(factory),
        build_modelo_iva_wallet_seed_definition(factory),
    )
    builders = (
        build_modelo_iva_wallet_balance_registration,
        build_modelo_iva_wallet_correction_registration,
        build_modelo_iva_wallet_override_registration,
        build_modelo_iva_wallet_seed_registration,
    )
    return OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(build(definition) for build, definition in zip(builders, definitions, strict=True)),
    ).public_contract_set


def _terminal(
    client: _Client,
    definition_id: str,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    *,
    refusal_ref: str | None = None,
) -> OperationPublicProjectionV1:
    contracts = _contracts()
    contract = next(item for item in contracts.definitions if item.definition_id == definition_id)
    return OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
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
        result_ref="e" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=refusal_ref,
        failure_error_code=None,
        diagnostic_ref=None,
    )


@dataclass
class _Client:
    profile_id: UUID = field(default_factory=uuid4)
    session_id: UUID = field(default_factory=uuid4)
    frontend: OperationFrontendProjection = OperationFrontendProjection.TUI


@dataclass
class _Controller:
    result: object = None
    detail: OperationErrorDetailV1 | None = None
    operation_id: str = _OPERATION_ID
    started: bool = False
    read: list[tuple[type, int]] = field(default_factory=list)

    async def start(self) -> None:
        self.started = True

    async def settled_error_detail(self, _state: object) -> OperationErrorDetailV1 | None:
        return self.detail

    async def read_settled_result(self, _state: object, result_type: type, *, result_version: int) -> object:
        self.read.append((result_type, result_version))
        return self.result


@dataclass
class _Run:
    submitted: list[dict[str, object]] = field(default_factory=list)
    observed: list[dict[str, object]] = field(default_factory=list)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    controller: _Controller,
    terminal: OperationPublicProjectionV1 | Exception,
    *,
    submit_error: Exception | None = None,
) -> _Run:
    run = _Run()

    async def submit(_cls: object, _client: object, **kwargs: object) -> _Controller:
        run.submitted.append(kwargs)
        if submit_error is not None:
            raise submit_error
        return controller

    async def await_terminal(_controller: object, **kwargs: object) -> OperationPublicProjectionV1:
        run.observed.append(kwargs)
        if isinstance(terminal, Exception):
            raise terminal
        return terminal

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    monkeypatch.setattr(runtime_wallet, "await_terminal_projection", await_terminal)
    return run


def _door(client: _Client) -> RuntimeModeloIvaWallet:
    return RuntimeModeloIvaWallet(cast(FrontendClient, client))


def _balance(client: _Client, *, year: int = _YEAR) -> ModeloIvaWalletBalanceProjection:
    return ModeloIvaWalletBalanceProjection(
        profile_id=client.profile_id,
        as_of_year=year,
        total_balance="30.00",
        active_balance="20.00",
        expired_balance="10.00",
        lot_count=1,
        next_expiry_year=_YEAR + 3,
        unallocated_applied_amount="0",
    )


def _seed(client: _Client, *, profile_id: UUID | None = None) -> ModeloIvaWalletSeedProjection:
    return ModeloIvaWalletSeedProjection(
        profile_id=profile_id or client.profile_id,
        period=_PERIOD,
        taxpayer_nif=_NIF,
        amount="45.00",
        provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
    )


def test_reading_submits_the_year_for_the_profile_subject_and_returns_the_released_balance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    controller = _Controller(_balance(client))
    terminal = _terminal(
        client,
        MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.NONE,
    )
    run = _bind(monkeypatch, controller, terminal)

    balance = _door(client).read_balance(_YEAR)

    assert balance == controller.result
    (submitted,) = run.submitted
    assert submitted["definition_id"] == MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID
    assert submitted["subject_ref"] == profile_operation_subject(str(client.profile_id))
    assert submitted["expected_session_id"] == client.session_id
    assert submitted["payload"] == ModeloIvaWalletBalanceRequest(profile_id=client.profile_id, as_of_year=_YEAR)
    assert controller.started
    assert controller.read == [(ModeloIvaWalletBalanceProjection, 1)]


def test_a_balance_for_another_year_or_profile_is_an_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    terminal = _terminal(
        client,
        MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.NONE,
    )
    _bind(monkeypatch, _Controller(_balance(client, year=_YEAR + 1)), terminal)
    with pytest.raises(RefusalError) as other_year:
        _door(client).read_balance(_YEAR)
    _bind(monkeypatch, _Controller(_balance(_Client())), terminal)
    with pytest.raises(RefusalError) as other_profile:
        _door(client).read_balance(_YEAR)

    assert other_year.value.reason is RefusalCode.INVALID_FRAME
    assert other_profile.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.parametrize(
    ("kind", "definition_id", "request_type", "result_type"),
    [
        (
            IvaWalletActionKind.SEED,
            MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
            ModeloIvaWalletSeedRequest,
            ModeloIvaWalletSeedProjection,
        ),
        (
            IvaWalletActionKind.CORRECT,
            MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
            ModeloIvaWalletCorrectionRequest,
            ModeloIvaWalletCorrectionProjection,
        ),
        (
            IvaWalletActionKind.OVERRIDE,
            MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
            ModeloIvaWalletOverrideRequest,
            ModeloIvaWalletOverrideProjection,
        ),
    ],
)
def test_each_recording_submits_its_own_request_with_exactly_the_fields_it_takes(
    monkeypatch: pytest.MonkeyPatch,
    kind: IvaWalletActionKind,
    definition_id: str,
    request_type: type,
    result_type: type,
) -> None:
    client = _Client()
    projections = {
        IvaWalletActionKind.SEED: _seed(client),
        IvaWalletActionKind.CORRECT: ModeloIvaWalletCorrectionProjection(
            profile_id=client.profile_id,
            period=_PERIOD,
            taxpayer_nif=_NIF,
            previous_amount="40.00",
            amount="45.00",
            provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION,
            reason="a reason",
        ),
        IvaWalletActionKind.OVERRIDE: ModeloIvaWalletOverrideProjection(
            profile_id=client.profile_id,
            period=_PERIOD,
            taxpayer_nif=_NIF,
            amount="45.00",
            reason="a reason",
            evidence_locator="a locator",
            selected_authority="taxpayer_override",
            divergence="override",
        ),
    }
    controller = _Controller(projections[kind])
    terminal = _terminal(client, definition_id, OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED)
    run = _bind(monkeypatch, controller, terminal)

    receipt = _door(client).record(
        IvaWalletEntryV1(
            kind=kind,
            filing_year=_YEAR,
            period_code="1T",
            amount="45.00",
            reason="a reason" if kind is not IvaWalletActionKind.SEED else "",
            evidence_locator="a locator" if kind is IvaWalletActionKind.OVERRIDE else "",
        )
    )

    assert receipt == projections[kind]
    (submitted,) = run.submitted
    assert submitted["definition_id"] == definition_id
    payload = submitted["payload"]
    assert isinstance(payload, request_type)
    assert isinstance(payload, BaseModel)
    assert (
        payload.model_dump(mode="json", exclude={"profile_id", "period"})
        == {
            IvaWalletActionKind.SEED: {"amount": "45.00"},
            IvaWalletActionKind.CORRECT: {"amount": "45.00", "reason": "a reason"},
            IvaWalletActionKind.OVERRIDE: {"amount": "45.00", "reason": "a reason", "evidence_locator": "a locator"},
        }[kind]
    )
    assert controller.read == [(result_type, 1)]


def test_a_request_the_applications_own_model_rejects_is_never_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    run = _bind(monkeypatch, _Controller(), RuntimeError("must not be observed"))

    for entry in (
        IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="1T", amount="1,5"),
        IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="not a period", amount="1"),
        IvaWalletEntryV1(kind=IvaWalletActionKind.CORRECT, filing_year=_YEAR, period_code="1T", amount="1"),
    ):
        with pytest.raises(IvaWalletNotSentError):
            _door(client).record(entry)

    assert run.submitted == []


def test_a_refused_recording_raises_the_recorded_detail_as_served_words(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    detail = build_operation_error_detail(ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH))
    assert detail is not None and detail.refusal_words is not None
    terminal = _terminal(
        client,
        MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.REFUSED,
        OperationEffect.NONE,
        refusal_ref="REFUSED_PROFILE_ACCESS",
    )
    controller = _Controller(detail=detail)
    _bind(monkeypatch, controller, terminal)

    with pytest.raises(IvaWalletRefusedError) as raised:
        _door(client).record(
            IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="1T", amount="1")
        )

    refusal = raised.value.refusal
    assert refusal is not None and refusal.refusal_words is not None
    assert refusal.refusal_words.words == detail.refusal_words
    assert controller.read == []


def test_a_request_refused_before_it_was_recorded_is_a_refusal_not_an_unknown_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    _bind(
        monkeypatch, _Controller(), RuntimeError("never reached"), submit_error=FrontendRefusedError("OPERATION_DENIED")
    )

    with pytest.raises(IvaWalletRefusedError):
        _door(client).record(
            IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="1T", amount="1")
        )


@pytest.mark.parametrize(
    "terminal_state",
    [
        (OperationTerminalCondition.REFUSED, OperationEffect.UNKNOWN),
        (OperationTerminalCondition.FAILED, OperationEffect.UNKNOWN),
        (OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
    ],
)
def test_an_ambiguous_terminal_is_not_settled_as_a_refusal(
    monkeypatch: pytest.MonkeyPatch, terminal_state: tuple[OperationTerminalCondition, OperationEffect]
) -> None:
    client = _Client()
    condition, effect = terminal_state
    terminal = _terminal(
        client,
        MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        condition,
        effect,
        refusal_ref="OPERATION_DENIED" if condition is OperationTerminalCondition.REFUSED else None,
    )
    _bind(monkeypatch, _Controller(_seed(client)), terminal)

    with pytest.raises((FrontendRefusedError, RefusalError)) as raised:
        _door(client).record(
            IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="1T", amount="1")
        )

    assert not isinstance(raised.value, IvaWalletRefusedError)


def test_a_transport_failure_while_waiting_is_raised_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    lost = RefusalError(RefusalCode.CONNECTION_CLOSED)
    _bind(monkeypatch, _Controller(), lost)

    with pytest.raises(RefusalError) as raised:
        _door(client).record(
            IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="1T", amount="1")
        )

    assert raised.value is lost


def test_a_receipt_for_another_profile_is_an_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    terminal = _terminal(
        client,
        MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    _bind(monkeypatch, _Controller(_seed(client, profile_id=uuid4())), terminal)

    with pytest.raises(RefusalError) as raised:
        _door(client).record(
            IvaWalletEntryV1(kind=IvaWalletActionKind.SEED, filing_year=_YEAR, period_code="1T", amount="45.00")
        )

    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_the_door_is_refused_to_a_frontend_that_is_not_the_tui_and_a_replaced_session() -> None:
    client = _Client(frontend=OperationFrontendProjection.CLI)
    with pytest.raises(RefusalError):
        _door(client)

    tui = _Client()
    door = _door(tui)
    tui.session_id = uuid4()
    with pytest.raises(RefusalError) as raised:
        door.read_balance(_YEAR)
    assert raised.value.reason is RefusalCode.CONNECTION_CLOSED
