"""The TUI work-create handoff keeps one exact runtime session and receipt."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.modelo.declarations_calendar import DeclarationsCalendarEntryRefV1
from cadrumo.application.modelo.declarations_workspace import (
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
)
from cadrumo.application.modelo.metadata_projection import ModeloWorkMetadataSnapshot
from cadrumo.application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
    build_modelo_work_create_definition,
    build_modelo_work_create_registration,
)
from cadrumo.application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.overview.calendar_models import OverviewPeriodState
from cadrumo.application.overview.next_actions import declare_next_action
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.workbench_generation import WorkbenchGenerationProjectionResultV1, WorkbenchGenerationV1
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from cadrumo.entrypoints.tui.declarations.models import ModeloWorkCreateHandoffV1, ModeloWorkCreateResultV1
from cadrumo.entrypoints.tui.declarations.tests.calendar_fixtures import calendar_row
from cadrumo.entrypoints.tui.modelo import runtime_work_create
from cadrumo.entrypoints.tui.modelo.lifecycle import ModeloLifecycleActionUnavailableError
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 9, 28, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_ADVISORIES = ("modelo.work.advisory.identity",)


class _Client:
    def __init__(self, *, profile_id: UUID = _PROFILE, session_id: UUID = _SESSION) -> None:
        self.profile_id = profile_id
        self.session_id = session_id
        self.frontend = OperationFrontendProjection.TUI
        self.result_requests: list[OperationResultProjectionRequestV1] = []
        self.result_document: dict[str, object] | None = None

    def read_result_document(
        self, request: OperationResultProjectionRequestV1, *, deadline: float
    ) -> dict[str, object]:
        del deadline
        self.result_requests.append(request)
        assert self.result_document is not None
        return self.result_document


@lru_cache(maxsize=1)
def _contract_set():
    """Build the actual closed request/result contract without composing ports."""
    factory = cast(ActiveWorkLifecyclePortsFactory, cast(object, lambda: None))
    definition = build_modelo_work_create_definition(factory)
    registration = build_modelo_work_create_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)).public_contract_set


def _unit(profile_id: UUID = _PROFILE, period: Period = _PERIOD) -> ModeloWorkMetadataSnapshot:
    instant = datetime(2026, 3, 10, 12, tzinfo=UTC)
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id),
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            revision_id="2026-y-siguientes",
        ),
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=period.filing_year,
        period=period,
        revision_id="2026-y-siguientes",
        name="First-quarter return",
        created_at=instant,
        updated_at=instant,
        state=WorkUnitState.BORRADOR,
    )
    return ModeloWorkMetadataSnapshot.from_work_unit(unit)


def _success_result(
    *, reused: bool, profile_id: UUID = _PROFILE, period: Period = _PERIOD
) -> ModeloWorkCreateProjection:
    return ModeloWorkCreateProjection(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        outcome=ModeloWorkCreateSuccess(
            unit=_unit(profile_id, period),
            reused=reused,
            name_applied=None,
            applicability_guard_bypassed=False,
            advisory_keys=_ADVISORIES,
        ),
    )


def _refusal_result(*, profile_id: UUID = _PROFILE, period: Period = _PERIOD) -> ModeloWorkCreateProjection:
    return ModeloWorkCreateProjection(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        outcome=ModeloWorkCreateRefusal(modelo="303", reason="taxpayer category excludes this form"),
    )


def _observation(
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.UPDATED,
    refusal_code: str | None = None,
    operation_id: str = _OPERATION_ID,
    subject_ref: str | None = None,
) -> OperationObservationSuccessV1:
    contracts = _contract_set()
    contract = contracts.definitions[0]
    state = OperationPublicProjectionV1(
        operation_id=operation_id,
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref or profile_operation_subject(str(_PROFILE)),
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
        result_ref="f" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=refusal_code,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=operation_id,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


class _Controller:
    operation_id = _OPERATION_ID

    def __init__(
        self,
        observation: OperationObservationSuccessV1,
        result: ModeloWorkCreateProjection,
        *,
        after_result: Callable[[], None] | None = None,
    ) -> None:
        self.observation = observation
        self.result = result
        self.after_result = after_result
        self.started = False
        self.result_reads: list[tuple[type[object], int, bool]] = []

    async def start(self) -> str:
        self.started = True
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert after_cursor == 0
        assert page_limit == 1
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[object],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> ModeloWorkCreateProjection:
        assert projection.operation_id == self.operation_id
        self.result_reads.append((result_type, result_version, allow_refusal_detail))
        if self.after_result is not None:
            self.after_result()
        return self.result


def _bind_submit(
    monkeypatch: pytest.MonkeyPatch,
    client: _Client,
    controller: _Controller,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def submit(actual_client: RuntimeFrontendClient, **kwargs: object) -> _Controller:
        assert actual_client is client
        calls.append(kwargs)
        return controller

    monkeypatch.setattr(RuntimeOperationController, "submit", submit)
    return calls


@pytest.mark.parametrize("reused", (False, True), ids=("created", "reused"))
def test_runtime_create_submits_exact_profile_period_and_refreshes_after_success(
    monkeypatch: pytest.MonkeyPatch, reused: bool
) -> None:
    client = _Client()
    result = _success_result(reused=reused)
    controller = _Controller(_observation(effect=OperationEffect.NONE if reused else OperationEffect.UPDATED), result)
    submissions = _bind_submit(monkeypatch, client, controller)
    refreshes: list[str] = []
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=lambda: refreshes.append("refreshed")
    )

    returned = handoff(" 303 ", 2026, _PERIOD)

    assert returned.reused is reused
    assert returned.advisory_keys == _ADVISORIES
    assert refreshes == ["refreshed"]
    assert controller.started
    assert controller.result_reads == [(ModeloWorkCreateProjection, 1, True)]
    assert len(submissions) == 1
    submission = submissions[0]
    assert submission["definition_id"] == MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
    assert submission["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert submission["payload"] == ModeloWorkCreateRequest(
        profile_id=_PROFILE,
        modelo="303",
        period=PublicPeriod.from_period(_PERIOD),
        actor="operator:tui-modelo",
    )
    assert submission["expected_session_id"] == _SESSION
    assert isinstance(submission["deadline"], float)


def test_runtime_create_returns_the_declaration_the_refreshed_generation_admits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    result = _success_result(reused=False)
    controller = _Controller(_observation(effect=OperationEffect.UPDATED), result)
    _bind_submit(monkeypatch, client, controller)
    created = result.outcome
    assert not isinstance(created, ModeloWorkCreateRefusal)
    admitted = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=created.unit.work_unit_id,
        modelo="303",
        filing_year=_PERIOD.filing_year,
        period=_PERIOD,
        state=WorkUnitState.BORRADOR,
        has_current_calculation=False,
        has_current_filing=False,
    )
    other = admitted.model_copy(update={"work_unit_id": "f" * 64})
    # Only the declarations projection of the refreshed generation is read here.
    refreshed = WorkbenchGenerationV1.model_construct(
        declarations=WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1].model_construct(
            projection=DeclarationsWorkspaceProjectionV1.model_construct(declarations=(other, admitted))
        )
    )
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=lambda: refreshed
    )

    returned = handoff("303", 2026, _PERIOD)

    assert returned.declaration == admitted
    assert returned.advisory_keys == _ADVISORIES


def test_runtime_create_registered_applicability_refusal_preserves_terminal_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    observation = _observation(
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        refusal_code=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    )
    controller = _Controller(observation, _refusal_result())
    submissions = _bind_submit(monkeypatch, client, controller)
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=lambda: pytest.fail("refusal cannot refresh")
    )

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        handoff("303", 2026, _PERIOD)

    assert len(submissions) == 1
    assert controller.result_reads == [(ModeloWorkCreateProjection, 1, True)]
    assert raised.value.context == {
        "modelo": "303",
        "reason": "taxpayer category excludes this form",
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
        "effect": OperationEffect.NONE.value,
        "refusal_code": MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    }


def test_runtime_create_rejects_ceded_model_before_runtime_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(_observation(), _success_result(reused=False))
    submissions = _bind_submit(monkeypatch, client, controller)
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=lambda: pytest.fail("ceded model cannot refresh")
    )

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        handoff("600", 2026, _PERIOD)

    assert raised.value.translated_message == "cli.app.modelo.work.create_stub_modelo_600_refused"
    assert submissions == []


@pytest.mark.parametrize("mismatch", ("operation", "subject"))
def test_runtime_create_rejects_observation_not_correlated_to_request(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    client = _Client()
    observation = _observation(
        operation_id="b" * 64 if mismatch == "operation" else _OPERATION_ID,
        subject_ref="profile:foreign" if mismatch == "subject" else None,
    )
    controller = _Controller(observation, _success_result(reused=False))
    _bind_submit(monkeypatch, client, controller)
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=lambda: pytest.fail("mismatch cannot refresh")
    )

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        handoff("303", 2026, _PERIOD)

    assert controller.started
    assert controller.result_reads == []
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": "unknown",
        "effect": OperationEffect.UNKNOWN.value,
        "refusal_code": None,
    }


def test_runtime_create_rejects_session_replacement_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(_observation(), _success_result(reused=False))
    submissions = _bind_submit(monkeypatch, client, controller)
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client),
        refresh_after_success=lambda: pytest.fail("replaced session cannot refresh"),
    )
    client.session_id = uuid4()

    with pytest.raises(RuntimeRefusalError) as raised:
        handoff("303", 2026, _PERIOD)

    assert raised.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert submissions == []


def test_runtime_create_rejects_session_change_after_terminal_result_read(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(
        _observation(),
        _success_result(reused=False),
        after_result=lambda: setattr(client, "session_id", uuid4()),
    )
    _bind_submit(monkeypatch, client, controller)
    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=lambda: pytest.fail("changed session cannot refresh")
    )

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        handoff("303", 2026, _PERIOD)

    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
        "effect": OperationEffect.UPDATED.value,
        "refusal_code": None,
    }


def test_runtime_create_refresh_failure_keeps_the_known_success_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(_observation(), _success_result(reused=False))
    _bind_submit(monkeypatch, client, controller)

    def fail_refresh() -> None:
        raise ModeloLifecycleActionUnavailableError(
            translated_message="tui.declarations.refusal.handoff",
            context={"operation_id": "different-operation"},
        )

    handoff = runtime_work_create.compose_runtime_work_create_handoff(
        cast(RuntimeFrontendClient, client), refresh_after_success=fail_refresh
    )

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        handoff("303", 2026, _PERIOD)

    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
        "effect": OperationEffect.UPDATED.value,
        "refusal_code": None,
    }


def test_calendar_create_handoff_submits_the_entry_natural_address() -> None:
    calls: list[tuple[str, int, Period]] = []

    def create(modelo: str, filing_year: int, period: Period, /) -> ModeloWorkCreateResultV1:
        calls.append((modelo, filing_year, period))
        return ModeloWorkCreateResultV1(reused=False)

    recover = runtime_work_create.compose_runtime_calendar_create_handoff(cast(ModeloWorkCreateHandoffV1, create))
    entry: DeclarationsCalendarEntryRefV1 = calendar_row(
        "303",
        "1T",
        date(2026, 4, 20),
        ObligationStatus.UPCOMING,
        OverviewPeriodState.DUE,
    )
    action = declare_next_action("operator.modelo.work.create", modelo="303", year=2026, period=str(_PERIOD))

    recover(action, entry)

    assert calls == [("303", 2026, _PERIOD)]


def test_runtime_controller_requires_explicit_refusal_detail_optin() -> None:
    result = _refusal_result()
    observation = _observation(
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        refusal_code=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    )
    contract = observation.projection.definition_contract
    result_schema = contract.result_schema
    assert result_schema is not None
    success_document = OperationResultProjectionSuccessV1[ModeloWorkCreateProjection](
        result_schema=result_schema,
        definition_contract_digest=contract.definition_contract_digest,
        projection=result,
    )
    client = _Client()
    client.result_document = success_document.model_dump(mode="json")
    controller = RuntimeOperationController(
        client=cast(RuntimeFrontendClient, client),
        operation_id=_OPERATION_ID,
        session_id=_SESSION,
        deadline=time.monotonic() + 30,
    )

    with pytest.raises(RuntimeRefusalError) as raised:
        asyncio.run(
            controller.read_settled_result(observation.projection, ModeloWorkCreateProjection, result_version=1)
        )

    assert raised.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert client.result_requests == []
    allowed = asyncio.run(
        controller.read_settled_result(
            observation.projection,
            ModeloWorkCreateProjection,
            result_version=1,
            allow_refusal_detail=True,
        )
    )

    assert allowed == result
    assert len(client.result_requests) == 1
    request = client.result_requests[0]
    assert request.operation_id == _OPERATION_ID
    assert request.terminal_revision == observation.projection.revision
    assert request.definition_contract_digest == contract.definition_contract_digest
    assert request.result_schema == result_schema
