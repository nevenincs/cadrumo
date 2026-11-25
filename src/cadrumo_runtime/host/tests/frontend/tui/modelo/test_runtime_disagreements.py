"""Runtime-backed disagreement answers keep the registered refusal and the profile, revision and session they were sent for.

The operation contracts are the real credit-resolution definitions' public
contracts. The controller stands at the transport boundary: it hands back the
terminal projection and the settled result a worker would release, so the cases
check what the host adapter submits and what it accepts back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.modelo.credit_resolution_contracts import (
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_REFUSAL_CODE,
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
    CreditResolutionAcceptRequest,
    CreditResolutionListProjection,
    CreditResolutionListRequest,
    CreditResolutionMutationProjection,
    CreditResolutionRefusalProjection,
    CreditResolutionRevokeRequest,
    CreditResolutionRowProjection,
    CreditResolutionSourceProjection,
)
from cadrumo.application.modelo.credit_resolution_operation import (
    build_credit_resolution_accept_definition,
    build_credit_resolution_list_definition,
    build_credit_resolution_list_registration,
    build_credit_resolution_mutation_registration,
    build_credit_resolution_revoke_definition,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
)
from cadrumo.domain.modelos.credit_resolution import CreditResolutionState
from cadrumo.domain.modelos.source_disagreement import SourceDisagreementRole
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from .....frontend.tui.modelo import runtime_disagreements
from .....frontend.tui.modelo.runtime_disagreements import RuntimeModeloDisagreements

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_REVISION = "c" * 64
_FINDING = "d4" * 8
_NOW = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)


@lru_cache(maxsize=1)
def _contracts():
    bundle = cast(Any, lambda *_args, **_kwargs: None)
    resolver = cast(Any, lambda _contract, _request: None)
    accept = build_credit_resolution_accept_definition(bundle)
    revoke = build_credit_resolution_revoke_definition(bundle)
    listing = build_credit_resolution_list_definition(bundle)
    return OperationRegistry(
        definitions=(accept, listing, revoke),
        public_registrations=(
            build_credit_resolution_mutation_registration(accept, access_resolver=resolver),
            build_credit_resolution_list_registration(listing, access_resolver=resolver),
            build_credit_resolution_mutation_registration(revoke, access_resolver=resolver),
        ),
    ).public_contract_set


def _terminal(
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
        subject_ref=_WORK_UNIT_ID,
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


def _row(state: CreditResolutionState = CreditResolutionState.ACTIVE) -> CreditResolutionRowProjection:
    return CreditResolutionRowProjection(
        finding_id=_FINDING,
        key="served-key",
        reached_casillas=("01",),
        sources=(
            CreditResolutionSourceProjection(
                role=SourceDisagreementRole.VALUE_SOURCE, source_family="served-family", value="10.00"
            ),
        ),
        accepted_role=SourceDisagreementRole.VALUE_SOURCE,
        reason="operator reason",
        state=state,
        resolved_at=_NOW,
        resolved_by_session="session-label",
        revoked_at=None if state is CreditResolutionState.ACTIVE else _NOW,
        revoked_by_session=None if state is CreditResolutionState.ACTIVE else "session-label",
        revision_id="stored-revision",
        applies=True,
        answer_words="served answer",
        answer_words_language=OutputLanguage.EN,
        state_words="served state",
        state_words_language=OutputLanguage.EN,
        current=True,
        current_words="served currency",
        current_words_language=OutputLanguage.EN,
        revocable=True,
    )


@dataclass
class _Client:
    profile_id: UUID = field(default_factory=uuid4)
    session_id: UUID = field(default_factory=uuid4)
    frontend: OperationFrontendProjection = OperationFrontendProjection.TUI


@dataclass
class _Controller:
    result: CreditResolutionMutationProjection
    operation_id: str = _OPERATION_ID
    started: bool = False
    read: list[tuple[type, int, bool]] = field(default_factory=list)

    async def start(self) -> None:
        self.started = True

    async def read_settled_result(
        self, _state: object, result_type: type, *, result_version: int, allow_refusal_detail: bool = False
    ) -> CreditResolutionMutationProjection:
        self.read.append((result_type, result_version, allow_refusal_detail))
        return self.result


@dataclass
class _Run:
    controller: _Controller
    submitted: list[dict[str, object]] = field(default_factory=list)
    observed: list[dict[str, object]] = field(default_factory=list)


def _bind(monkeypatch: pytest.MonkeyPatch, controller: _Controller, terminal: OperationPublicProjectionV1) -> _Run:
    run = _Run(controller)

    async def submit(_cls: object, _client: object, **kwargs: object) -> _Controller:
        run.submitted.append(kwargs)
        return controller

    async def await_terminal(_controller: object, **kwargs: object) -> OperationPublicProjectionV1:
        run.observed.append(kwargs)
        return terminal

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    monkeypatch.setattr(runtime_disagreements, "await_terminal_projection", await_terminal)
    return run


def _door(client: _Client) -> RuntimeModeloDisagreements:
    declaration = SimpleNamespace(work_unit_id=_WORK_UNIT_ID)
    return RuntimeModeloDisagreements(cast(FrontendClient, client), cast(Any, declaration))


def _accepted(client: _Client, *, profile_id: UUID | None = None) -> CreditResolutionMutationProjection:
    return CreditResolutionMutationProjection(
        outcome="accepted",
        profile_id=profile_id or client.profile_id,
        calculation_revision_id=_REVISION,
        resolution=_row(),
    )


def test_accepting_submits_the_exact_request_for_the_work_unit_and_session(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(_accepted(client))
    terminal = _terminal(
        MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    run = _bind(monkeypatch, controller, terminal)

    projection = _door(client).accept(_REVISION, _FINDING, "operator reason", OutputLanguage.EN)

    assert projection == controller.result
    (submitted,) = run.submitted
    assert submitted["definition_id"] == MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID
    assert submitted["subject_ref"] == _WORK_UNIT_ID
    assert submitted["expected_session_id"] == client.session_id
    assert submitted["payload"] == CreditResolutionAcceptRequest(
        profile_id=client.profile_id,
        calculation_revision_id=_REVISION,
        output_language=OutputLanguage.EN,
        finding_id=_FINDING,
        reason="operator reason",
    )
    assert controller.started
    assert controller.read == [(CreditResolutionMutationProjection, 1, True)]


def test_revoking_submits_the_revision_the_answer_is_stored_at(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(
        CreditResolutionMutationProjection(
            outcome="revoked",
            profile_id=client.profile_id,
            calculation_revision_id=_REVISION,
            resolution=_row(CreditResolutionState.REVOKED),
        )
    )
    terminal = _terminal(
        MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    run = _bind(monkeypatch, controller, terminal)

    projection = _door(client).revoke(_REVISION, _FINDING, "stored-revision", OutputLanguage.EN)

    assert projection.outcome == "revoked"
    assert run.submitted[0]["payload"] == CreditResolutionRevokeRequest(
        profile_id=client.profile_id,
        calculation_revision_id=_REVISION,
        output_language=OutputLanguage.EN,
        finding_id=_FINDING,
        expected_revision_id="stored-revision",
    )


def test_a_registered_refusal_is_read_as_its_typed_detail_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    refused = CreditResolutionMutationProjection(
        outcome="refused",
        profile_id=client.profile_id,
        calculation_revision_id=_REVISION,
        refusal=CreditResolutionRefusalProjection(
            code="REFUSED_CREDIT_RESOLUTION",
            reason="already_resolved",
            finding_id=_FINDING,
            refusal_words="Served refusal sentence.",
            refusal_words_language=OutputLanguage.EN,
        ),
    )
    controller = _Controller(refused)
    terminal = _terminal(
        MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.REFUSED,
        OperationEffect.NONE,
        refusal_ref=MODELO_CREDIT_RESOLUTION_REFUSAL_CODE,
    )
    _bind(monkeypatch, controller, terminal)

    projection = _door(client).accept(_REVISION, _FINDING, "operator reason", OutputLanguage.EN)

    assert projection.outcome == "refused"
    assert projection.refusal is not None
    assert projection.refusal.refusal_words == "Served refusal sentence."


def test_a_terminal_refusal_without_a_typed_detail_is_raised_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(_accepted(client))
    terminal = _terminal(
        MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.REFUSED,
        OperationEffect.NONE,
        refusal_ref="OPERATION_DENIED",
    )
    _bind(monkeypatch, controller, terminal)

    with pytest.raises(FrontendRefusedError) as raised:
        _door(client).accept(_REVISION, _FINDING, "operator reason", OutputLanguage.EN)

    assert raised.value.reason == "OPERATION_DENIED"
    assert controller.read == []


@pytest.mark.parametrize("fault", ["profile", "outcome", "revision"])
def test_a_result_for_another_profile_revision_or_outcome_is_an_invalid_frame(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    client = _Client()
    result = {
        "profile": _accepted(client, profile_id=uuid4()),
        "outcome": CreditResolutionMutationProjection(
            outcome="revoked",
            profile_id=client.profile_id,
            calculation_revision_id=_REVISION,
            resolution=_row(CreditResolutionState.REVOKED),
        ),
        "revision": CreditResolutionMutationProjection(
            outcome="accepted",
            profile_id=client.profile_id,
            calculation_revision_id="f" * 64,
            resolution=_row(),
        ),
    }[fault]
    terminal = _terminal(
        MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    _bind(monkeypatch, _Controller(result), terminal)

    with pytest.raises(RefusalError) as raised:
        _door(client).accept(_REVISION, _FINDING, "operator reason", OutputLanguage.EN)

    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_a_session_that_changed_since_the_workbench_opened_submits_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(_accepted(client))
    terminal = _terminal(
        MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    run = _bind(monkeypatch, controller, terminal)
    door = _door(client)
    client.session_id = uuid4()

    with pytest.raises(RefusalError) as raised:
        door.accept(_REVISION, _FINDING, "operator reason", OutputLanguage.EN)

    assert raised.value.reason is RefusalCode.CONNECTION_CLOSED
    assert run.submitted == []


def test_only_a_tui_session_may_hold_the_door() -> None:
    with pytest.raises(RefusalError):
        _door(_Client(frontend=OperationFrontendProjection.CLI))


def test_listing_reads_the_registered_read_for_the_work_unit_and_checks_what_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    asked: list[dict[str, object]] = []
    answers = {"revision": _REVISION}

    async def read(_client: object, **kwargs: object) -> CreditResolutionListProjection:
        asked.append(kwargs)
        return CreditResolutionListProjection(
            profile_id=client.profile_id, calculation_revision_id=answers["revision"], resolutions=(_row(),)
        )

    monkeypatch.setattr(runtime_disagreements, "read_operation", read)
    door = _door(client)

    projection = door.list_answers(_REVISION, OutputLanguage.EN)

    assert [row.finding_id for row in projection.resolutions] == [_FINDING]
    (call,) = asked
    assert call["definition_id"] == MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID
    assert call["subject_ref"] == _WORK_UNIT_ID
    assert call["session_id"] == client.session_id
    assert call["result_type"] is CreditResolutionListProjection
    assert call["payload"] == CreditResolutionListRequest(
        profile_id=client.profile_id, calculation_revision_id=_REVISION, output_language=OutputLanguage.EN
    )

    answers["revision"] = "f" * 64
    with pytest.raises(RefusalError) as raised:
        door.list_answers(_REVISION, OutputLanguage.EN)
    assert raised.value.reason is RefusalCode.INVALID_FRAME
