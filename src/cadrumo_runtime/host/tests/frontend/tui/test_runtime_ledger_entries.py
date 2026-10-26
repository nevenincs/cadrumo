"""Exact-session dispatch and receipt correlation for the installed Records entry doors.

Every door is driven through its operation's real definition and public
registration, so each terminal receipt carries the contract the runtime would
publish. Each door must refuse a result for another profile, a receipt with an
effect its request cannot cause, a refusal receipt, and a lapsed session.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.export.tabular import ExportSerializationFormat
from cadrumo.application.ledger.action_ports import LedgerActionPortsFactory
from cadrumo.application.ledger.add_operation import build_ledger_add_definition, build_ledger_add_registration
from cadrumo.application.ledger.check_operation import (
    LEDGER_CHECK_OPERATION_DEFINITION_ID,
    LedgerCheckRequest,
    build_ledger_check_definition,
    build_ledger_check_registration,
)
from cadrumo.application.ledger.export_operation import (
    LEDGER_EXPORT_OPERATION_DEFINITION_ID,
    LedgerExportProjection,
    LedgerExportRequest,
    build_ledger_export_definition,
    build_ledger_export_registration,
)
from cadrumo.application.ledger.history_operation import (
    LEDGER_HISTORY_OPERATION_DEFINITION_ID,
    LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,
    LedgerHistoryRequest,
    build_ledger_history_definition,
    build_ledger_history_registration,
    build_ledger_history_typed_definition,
    build_ledger_history_typed_registration,
)
from cadrumo.application.ledger.ledger_add_contracts import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    LedgerAddRequest,
)
from cadrumo.application.ledger.lifecycle_contracts import (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationResult,
    LedgerLifecycleValidationProjection,
)
from cadrumo.application.ledger.lifecycle_mutation_operation import (
    LedgerLifecycleValidationRefusedError,
    build_ledger_archive_definition,
    build_ledger_archive_registration,
    build_ledger_exclude_definition,
    build_ledger_exclude_registration,
    build_ledger_restore_definition,
    build_ledger_restore_registration,
    build_ledger_stash_definition,
    build_ledger_stash_registration,
)
from cadrumo.application.ledger.list_operation import (
    LEDGER_LIST_OPERATION_DEFINITION_ID,
    LedgerListRequest,
    build_ledger_list_definition,
    build_ledger_list_registration,
)
from cadrumo.application.ledger.merge_operation import (
    LEDGER_MERGE_OPERATION_DEFINITION_ID,
    LedgerMergeRequest,
    build_ledger_merge_definition,
    build_ledger_merge_registration,
)
from cadrumo.application.ledger.own_account_ports import OwnAccountRepositoryFactory
from cadrumo.application.ledger.participation_read import TransactionParticipationIndexRepositoryFactory
from cadrumo.application.ledger.preflight_operation import (
    LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
    LedgerPreflightRequest,
    build_ledger_preflight_definition,
    build_ledger_preflight_registration,
)
from cadrumo.application.ledger.read_ports import LedgerReadPortsFactory
from cadrumo.application.ledger.remove_operation import (
    LEDGER_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRemoveRequest,
    build_ledger_remove_definition,
    build_ledger_remove_registration,
)
from cadrumo.application.ledger.reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetRequest,
    build_ledger_reset_definition,
    build_ledger_reset_registration,
)
from cadrumo.application.ledger.status_operation import (
    LEDGER_STATUS_OPERATION_DEFINITION_ID,
    LedgerStatusRequest,
    build_ledger_status_definition,
    build_ledger_status_registration,
)
from cadrumo.application.ledger.track_operation import (
    LEDGER_TRACK_OPERATION_DEFINITION_ID,
    LedgerTrackRequest,
    build_ledger_track_definition,
    build_ledger_track_registration,
)
from cadrumo.application.ledger.workspace import LedgerWorkspaceArea
from cadrumo.application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
from cadrumo.application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.operation_definition import OperationDefinition
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.prorrata_register.ports import ProrrataRegisterRepositoryFactory
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.entries_add import LedgerEntryAddScreen
from cadrumo.entrypoints.tui.ledger.entries_browse import LedgerEntriesBrowseScreen
from cadrumo.entrypoints.tui.ledger.entries_doors import LedgerEntriesDoorsV1
from cadrumo.entrypoints.tui.ledger.entries_export import LedgerEntriesExportScreen
from cadrumo.entrypoints.tui.ledger.entries_health import LedgerHealthScreen
from cadrumo.entrypoints.tui.ledger.entries_reset import LedgerResetScreen
from cadrumo.entrypoints.tui.ledger.models import (
    LedgerExclusionResultV1,
    LedgerExclusionSubmissionV1,
    LedgerExclusionSubmitterV1,
)
from cadrumo.entrypoints.tui.ledger.tests.entries_door_fixtures import (
    ENTRIES_PROFILE_ID,
    MemoryEntriesLedger,
    entries_controller,
    entry_id,
)
from cadrumo.entrypoints.tui.operations.outcome import OperationOutcomeUnknownError
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_ledger_entries import (
    RuntimeLedgerEntryTuiDoorV1,
    compose_entries_tools,
    compose_runtime_ledger_entries_doors,
    compose_runtime_ledger_exclusion_submitter,
)
from ....frontend.tui.runtime_ledger_tools import compose_runtime_ledger_tools
from .unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = ENTRIES_PROFILE_ID
_OTHER_PROFILE_ID = UUID("8ee00000-0000-4000-8000-0000000000ee")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 4, tzinfo=UTC)
_UNDECLARED_REFUSAL = "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
_UNDECLARED_REFUSAL_KEY = "errors.refused.refused_ledger_own_account_register_validation"
_LABEL = "Fixture profile"


def _never[T](**_kwargs: object) -> T:
    raise AssertionError("a contract builder must not open a repository")


_PORTS = cast(LedgerActionPortsFactory, _never)
_READS = cast(LedgerReadPortsFactory, _never)


def _definition(definition_id: str) -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
    """The operation's real definition and public registration, over factories it never calls."""
    builders: dict[str, Callable[[], OperationDefinition]] = {
        LEDGER_LIST_OPERATION_DEFINITION_ID: lambda: build_ledger_list_definition(_READS),
        LEDGER_ADD_OPERATION_DEFINITION_ID: lambda: build_ledger_add_definition(
            _PORTS, cast(ProrrataRegisterRepositoryFactory, _never), cast(OwnAccountRepositoryFactory, _never)
        ),
        LEDGER_REMOVE_OPERATION_DEFINITION_ID: lambda: build_ledger_remove_definition(_PORTS),
        LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: lambda: build_ledger_archive_definition(_PORTS),
        LEDGER_STASH_OPERATION_DEFINITION_ID: lambda: build_ledger_stash_definition(_PORTS),
        LEDGER_RESTORE_OPERATION_DEFINITION_ID: lambda: build_ledger_restore_definition(_PORTS),
        LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: lambda: build_ledger_exclude_definition(_PORTS),
        LEDGER_MERGE_OPERATION_DEFINITION_ID: lambda: build_ledger_merge_definition(_PORTS),
        LEDGER_HISTORY_OPERATION_DEFINITION_ID: lambda: build_ledger_history_definition(_READS),
        LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID: lambda: build_ledger_history_typed_definition(_READS),
        LEDGER_TRACK_OPERATION_DEFINITION_ID: lambda: build_ledger_track_definition(
            _PORTS, cast(TransactionParticipationIndexRepositoryFactory, _never)
        ),
        LEDGER_STATUS_OPERATION_DEFINITION_ID: lambda: build_ledger_status_definition(
            _PORTS, cast(VerificationRepositoryBundleFactory, _never)
        ),
        LEDGER_CHECK_OPERATION_DEFINITION_ID: lambda: build_ledger_check_definition(_PORTS),
        LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID: lambda: build_ledger_preflight_definition(_PORTS),
        LEDGER_RESET_OPERATION_DEFINITION_ID: lambda: build_ledger_reset_definition(_PORTS),
        LEDGER_EXPORT_OPERATION_DEFINITION_ID: lambda: build_ledger_export_definition(_PORTS),
    }
    registrations: dict[str, Callable[[OperationDefinition], OperationPublicDefinitionRegistrationV1]] = {
        LEDGER_LIST_OPERATION_DEFINITION_ID: build_ledger_list_registration,
        LEDGER_ADD_OPERATION_DEFINITION_ID: build_ledger_add_registration,
        LEDGER_REMOVE_OPERATION_DEFINITION_ID: build_ledger_remove_registration,
        LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: build_ledger_archive_registration,
        LEDGER_STASH_OPERATION_DEFINITION_ID: build_ledger_stash_registration,
        LEDGER_RESTORE_OPERATION_DEFINITION_ID: build_ledger_restore_registration,
        LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: build_ledger_exclude_registration,
        LEDGER_MERGE_OPERATION_DEFINITION_ID: build_ledger_merge_registration,
        LEDGER_HISTORY_OPERATION_DEFINITION_ID: build_ledger_history_registration,
        LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID: build_ledger_history_typed_registration,
        LEDGER_TRACK_OPERATION_DEFINITION_ID: build_ledger_track_registration,
        LEDGER_STATUS_OPERATION_DEFINITION_ID: build_ledger_status_registration,
        LEDGER_CHECK_OPERATION_DEFINITION_ID: build_ledger_check_registration,
        LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID: build_ledger_preflight_registration,
        LEDGER_RESET_OPERATION_DEFINITION_ID: build_ledger_reset_registration,
        LEDGER_EXPORT_OPERATION_DEFINITION_ID: build_ledger_export_registration,
    }
    definition = builders[definition_id]()
    return definition, registrations[definition_id](definition)


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID
        self.session_read_threads: list[int] = []
        """The thread of each blocking session read: at composition, then around each operation."""


class _Controller:
    operation_id = _OPERATION_ID
    client: _Client

    def __init__(
        self,
        *,
        observation: OperationObservationSuccessV1,
        result: BaseModel | None,
        detail: OperationErrorDetailV1 | None = None,
    ) -> None:
        self.observation = observation
        self.result = result
        self.detail = detail
        self.result_reads: list[tuple[type[BaseModel], bool]] = []

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
        assert result_version == 1
        self.result_reads.append((result_type, allow_refusal_detail))
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection.operation_id == self.operation_id
        return self.detail


def _observation(
    definition_id: str,
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
    refusal_ref: str | None = None,
) -> OperationObservationSuccessV1:
    definition, registration = _definition(definition_id)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    contract = registry.lookup_public_contract(definition_id)
    succeeded = condition is OperationTerminalCondition.SUCCEEDED
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=definition_id,
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
        result_ref="f" * 64 if succeeded else None,
        refusal_ref=(refusal_ref or _UNDECLARED_REFUSAL) if refused else None,
        failure_error_code=None if succeeded or refused else "ERROR_CADRUMO_CORE",
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

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == _LABEL
        client.session_read_threads.append(threading.get_ident())
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []

    async def submit(
        _controller_type: type[OperationController], received_client: FrontendClient, **kwargs: object
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        controller.client = client
        return controller

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions


def _doors(client: _Client) -> LedgerEntriesDoorsV1:
    return compose_runtime_ledger_entries_doors(cast(FrontendClient, client), profile_label=_LABEL)


_PERIOD = PublicPeriod(filing_year=2026, code="1T")


@dataclass(frozen=True)
class _Case:
    """One door, a request it may submit, the result its operation settles with, and that result's effect."""

    door: str
    definition_id: str
    request: BaseModel
    result: BaseModel
    effect: OperationEffect


def _cases() -> tuple[_Case, ...]:
    ledger = MemoryEntriesLedger.with_entries(4)
    listed = LedgerListRequest(profile_id=_PROFILE_ID, limit=2)
    added = LedgerAddRequest(
        profile_id=_PROFILE_ID, booked_date="2026-03-14", amount="10.00", direction="OUTGOING", description="Synthetic"
    )
    removed = LedgerRemoveRequest(profile_id=_PROFILE_ID, transaction_id=entry_id(0))
    moved = LedgerLifecycleMutationRequest(profile_id=_PROFILE_ID, transaction_id=entry_id(1))
    merged = LedgerMergeRequest(profile_id=_PROFILE_ID, child_ids=(entry_id(2), entry_id(3)))
    history = LedgerHistoryRequest(profile_id=_PROFILE_ID, transaction_prefix=entry_id(1))
    tracked = LedgerTrackRequest(profile_id=_PROFILE_ID, transaction_prefix=entry_id(1))
    status = LedgerStatusRequest(profile_id=_PROFILE_ID, period=_PERIOD)
    check = LedgerCheckRequest(profile_id=_PROFILE_ID, period=_PERIOD)
    preflight = LedgerPreflightRequest(profile_id=_PROFILE_ID, period=_PERIOD)
    reset = LedgerResetRequest(profile_id=_PROFILE_ID, reason="synthetic", dry_run=True)
    none, updated = OperationEffect.NONE, OperationEffect.UPDATED
    return (
        _Case("list_entries", LEDGER_LIST_OPERATION_DEFINITION_ID, listed, ledger.list_page(listed), none),
        _Case("history", LEDGER_HISTORY_OPERATION_DEFINITION_ID, history, ledger.history(history), none),
        _Case(
            "history_typed", LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID, history, ledger.history_typed(history), none
        ),
        _Case("track", LEDGER_TRACK_OPERATION_DEFINITION_ID, tracked, ledger.track(tracked), none),
        _Case("status", LEDGER_STATUS_OPERATION_DEFINITION_ID, status, ledger.status(status), none),
        _Case("check", LEDGER_CHECK_OPERATION_DEFINITION_ID, check, ledger.check(check), none),
        _Case("preflight", LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID, preflight, ledger.preflight(preflight), none),
        _Case("reset", LEDGER_RESET_OPERATION_DEFINITION_ID, reset, ledger.reset(reset), none),
        _Case(
            "archive", LEDGER_ARCHIVE_OPERATION_DEFINITION_ID, moved, ledger.lifecycle("ledger.archive", moved), updated
        ),
        _Case("stash", LEDGER_STASH_OPERATION_DEFINITION_ID, moved, ledger.lifecycle("ledger.stash", moved), updated),
        _Case(
            "restore", LEDGER_RESTORE_OPERATION_DEFINITION_ID, moved, ledger.lifecycle("ledger.restore", moved), updated
        ),
        _Case(
            "exclude", LEDGER_EXCLUDE_OPERATION_DEFINITION_ID, moved, ledger.lifecycle("ledger.exclude", moved), updated
        ),
        _Case("merge", LEDGER_MERGE_OPERATION_DEFINITION_ID, merged, ledger.merge(merged), updated),
        _Case("add", LEDGER_ADD_OPERATION_DEFINITION_ID, added, ledger.add(added), updated),
        _Case("remove", LEDGER_REMOVE_OPERATION_DEFINITION_ID, removed, ledger.remove(removed), updated),
    )


_CASES = _cases()
_IDS = [case.door for case in _CASES]
_OTHER_EFFECT = {OperationEffect.NONE: OperationEffect.UPDATED, OperationEffect.UPDATED: OperationEffect.NONE}


def _call(doors: LedgerEntriesDoorsV1, case: _Case) -> object:
    door = cast(Callable[[BaseModel], Coroutine[object, object, object]], getattr(doors, case.door))
    return asyncio.run(door(case.request))


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_submits_its_own_operation_and_reads_its_result(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    controller = _Controller(observation=_observation(case.definition_id, effect=case.effect), result=case.result)
    submissions = _install(monkeypatch, client, controller)
    doors = _doors(client)

    assert doors.profile_id == _PROFILE_ID
    assert _call(doors, case) == case.result
    assert submissions[0]["definition_id"] == case.definition_id
    assert submissions[0]["payload"] == case.request
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert [result_type for result_type, _ in controller.result_reads] == [type(case.result)]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_reads_its_session_off_the_event_loop_thread(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    """The session read is a blocking IPC exchange; a door awaited on the loop never runs it there."""
    client = _Client()
    controller = _Controller(observation=_observation(case.definition_id, effect=case.effect), result=case.result)
    _install(monkeypatch, client, controller)
    doors = _doors(client)
    assert client.session_read_threads, "composing the doors reads the session once, before any loop runs"
    client.session_read_threads.clear()

    _call(doors, case)

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads


def test_the_export_door_reads_its_session_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    request = _export_request(tmp_path)
    observation = _observation(LEDGER_EXPORT_OPERATION_DEFINITION_ID, effect=OperationEffect.UPDATED)
    _install(monkeypatch, client, _Controller(observation=observation, result=_export_projection(request)))
    doors = _doors(client)
    client.session_read_threads.clear()

    asyncio.run(doors.export(request))

    assert client.session_read_threads
    assert threading.get_ident() not in client.session_read_threads


def test_the_gate_catches_a_session_read_on_the_loop_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detector teeth: a binding check called directly on the loop thread is recorded there."""
    client = _Client()
    observation = _observation(LEDGER_LIST_OPERATION_DEFINITION_ID)
    _install(monkeypatch, client, _Controller(observation=observation, result=None))
    door = cast(RuntimeLedgerEntryTuiDoorV1[BaseModel, BaseModel], _doors(client).list_entries)
    client.session_read_threads.clear()

    async def read_on_the_loop() -> None:
        door._session.require_binding()

    asyncio.run(read_on_the_loop())

    assert client.session_read_threads == [threading.get_ident()]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_refuses_a_result_for_another_profile(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    foreign = case.result.model_copy(update={"profile_id": _OTHER_PROFILE_ID})
    observation = _observation(case.definition_id, effect=case.effect)
    _install(monkeypatch, client, _Controller(observation=observation, result=foreign))

    with raises_unsupported_result(observation.projection.effect, observation.projection.definition_contract):
        _call(_doors(client), case)


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_refuses_an_effect_its_request_cannot_cause(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    observation = _observation(case.definition_id, effect=_OTHER_EFFECT[case.effect])
    _install(monkeypatch, client, _Controller(observation=observation, result=case.result))

    with raises_unsupported_result(observation.projection.effect, observation.projection.definition_contract):
        _call(_doors(client), case)


def _registered_detail() -> OperationErrorDetailV1:
    return OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_UNDECLARED_REFUSAL,
        message_key=_UNDECLARED_REFUSAL_KEY,
        context=(),
    )


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_raises_the_recorded_refusal_of_a_refused_receipt(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    client = _Client()
    controller = _Controller(
        observation=_observation(case.definition_id, condition=OperationTerminalCondition.REFUSED),
        result=None,
        detail=_registered_detail(),
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(RecordedRegisteredError) as raised:
        _call(_doors(client), case)

    assert raised.value.recorded_code == _UNDECLARED_REFUSAL
    assert controller.result_reads == []


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_keeps_the_bare_code_when_no_detail_was_recorded(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    client = _Client()
    observation = _observation(case.definition_id, condition=OperationTerminalCondition.REFUSED)
    _install(monkeypatch, client, _Controller(observation=observation, result=None))

    with pytest.raises(FrontendRefusedError) as raised:
        _call(_doors(client), case)

    assert raised.value.reason == _UNDECLARED_REFUSAL


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_fails_closed_when_its_session_lapses(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    submissions = _install(monkeypatch, client, _Controller(observation=_observation(case.definition_id), result=None))
    doors = _doors(client)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        _call(doors, case)

    assert submissions == []


def _validation_refusal(operation_id: Literal["ledger.archive", "ledger.exclude"]) -> LedgerLifecycleOperationResult:
    return LedgerLifecycleOperationResult(
        outcome="validation_error",
        profile_id=_PROFILE_ID,
        operation_id=operation_id,
        validation=LedgerLifecycleValidationProjection(messages=("entry is cited by a filed declaration",)),
    )


def test_a_lifecycle_validation_refusal_is_read_as_the_operations_own_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    request = LedgerLifecycleMutationRequest(profile_id=_PROFILE_ID, transaction_id=entry_id(1))
    refused = _validation_refusal("ledger.archive")
    observation = _observation(
        LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    )
    controller = _Controller(observation=observation, result=refused)
    _install(monkeypatch, client, controller)

    assert asyncio.run(_doors(client).archive(request)) == refused
    assert controller.result_reads == [(LedgerLifecycleOperationResult, True)]


def test_an_add_validation_refusal_is_read_as_the_operations_own_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    request = LedgerAddRequest(
        profile_id=_PROFILE_ID, booked_date="2026-03-14", amount="13.13", direction="OUTGOING", description="Synthetic"
    )
    refused = MemoryEntriesLedger().add(request)
    observation = _observation(
        LEDGER_ADD_OPERATION_DEFINITION_ID,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    )
    _install(monkeypatch, client, _Controller(observation=observation, result=refused))

    assert asyncio.run(_doors(client).add(request)) == refused


def test_an_add_whose_entry_differs_from_the_request_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The receipt reported the entry added; a result for another entry leaves what was added unknown."""
    client = _Client()
    request = LedgerAddRequest(
        profile_id=_PROFILE_ID, booked_date="2026-03-14", amount="10.00", direction="OUTGOING", description="Synthetic"
    )
    other = MemoryEntriesLedger().add(request.model_copy(update={"amount": "11.00"}))
    observation = _observation(LEDGER_ADD_OPERATION_DEFINITION_ID, effect=OperationEffect.UPDATED)
    _install(monkeypatch, client, _Controller(observation=observation, result=other))

    with raises_unsupported_result(OperationEffect.UPDATED, observation.projection.definition_contract):
        asyncio.run(_doors(client).add(request))


def _export_request(tmp_path: Path) -> LedgerExportRequest:
    return LedgerExportRequest(
        profile_id=_PROFILE_ID, output_path=str(tmp_path / "ledger.csv"), export_format=ExportSerializationFormat.CSV
    )


def _export_projection(request: LedgerExportRequest) -> LedgerExportProjection:
    return MemoryEntriesLedger().export(request)


def test_the_export_door_returns_the_written_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _Client()
    request = _export_request(tmp_path)
    projection = _export_projection(request)
    observation = _observation(LEDGER_EXPORT_OPERATION_DEFINITION_ID, effect=OperationEffect.UPDATED)
    submissions = _install(monkeypatch, client, _Controller(observation=observation, result=projection))

    written = asyncio.run(_doors(client).export(request))

    assert written == projection
    assert submissions[0]["definition_id"] == LEDGER_EXPORT_OPERATION_DEFINITION_ID
    assert submissions[0]["payload"] == request
    assert submissions[0]["expected_session_id"] == _SESSION_ID


@pytest.mark.parametrize("effect", [OperationEffect.PARTIAL, OperationEffect.UNKNOWN])
def test_a_failed_export_that_may_have_written_reports_its_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, effect: OperationEffect
) -> None:
    client = _Client()
    observation = _observation(
        LEDGER_EXPORT_OPERATION_DEFINITION_ID, condition=OperationTerminalCondition.FAILED, effect=effect
    )
    controller = _Controller(observation=observation, result=None, detail=_registered_detail())
    _install(monkeypatch, client, controller)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(_doors(client).export(_export_request(tmp_path)))

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is effect
    assert isinstance(raised.value.reason, RecordedRegisteredError)
    assert controller.result_reads == []


def test_a_failed_export_that_wrote_nothing_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _Client()
    observation = _observation(
        LEDGER_EXPORT_OPERATION_DEFINITION_ID, condition=OperationTerminalCondition.FAILED, effect=OperationEffect.NONE
    )
    _install(monkeypatch, client, _Controller(observation=observation, result=None))

    with pytest.raises(FrontendRefusedError):
        asyncio.run(_doors(client).export(_export_request(tmp_path)))


@pytest.mark.parametrize(
    "change",
    [
        {"profile_id": _OTHER_PROFILE_ID},
        {"output_path": "/elsewhere/ledger.csv"},
        {"export_format": ExportSerializationFormat.XLSX},
    ],
)
def test_the_export_door_reports_a_report_for_another_request_as_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, change: dict[str, object]
) -> None:
    client = _Client()
    request = _export_request(tmp_path)
    foreign = _export_projection(request).model_copy(update=change)
    observation = _observation(LEDGER_EXPORT_OPERATION_DEFINITION_ID, effect=OperationEffect.UPDATED)
    _install(monkeypatch, client, _Controller(observation=observation, result=foreign))

    # The export reported a published file, so a report for another request leaves that file unknown.
    with raises_unsupported_result(OperationEffect.UPDATED, observation.projection.definition_contract):
        asyncio.run(_doors(client).export(request))


def test_the_export_door_refuses_a_wrong_effect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _Client()
    request = _export_request(tmp_path)
    observation = _observation(LEDGER_EXPORT_OPERATION_DEFINITION_ID, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(observation=observation, result=_export_projection(request)))

    with pytest.raises(RefusalError):
        asyncio.run(_doors(client).export(request))


def test_the_export_door_refuses_a_refusal_receipt_and_a_lapsed_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    refused = _observation(LEDGER_EXPORT_OPERATION_DEFINITION_ID, condition=OperationTerminalCondition.REFUSED)
    submissions = _install(monkeypatch, client, _Controller(observation=refused, result=None))
    doors = _doors(client)

    with pytest.raises(FrontendRefusedError):
        asyncio.run(doors.export(_export_request(tmp_path)))

    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(doors.export(_export_request(tmp_path)))
    assert len(submissions) == 1


def _exclusion(transaction_id: str) -> LedgerExclusionSubmissionV1:
    return LedgerExclusionSubmissionV1(
        action=ActionReference(action_id=lookup_action("operator.ledger.classify").action_id),
        transaction_id=transaction_id,
    )


def _excluded(transaction_id: str) -> LedgerLifecycleOperationResult:
    request = LedgerLifecycleMutationRequest(profile_id=_PROFILE_ID, transaction_id=transaction_id)
    return MemoryEntriesLedger.with_entries(4).lifecycle("ledger.exclude", request)


def _submitter(client: _Client) -> LedgerExclusionSubmitterV1:
    return compose_runtime_ledger_exclusion_submitter(cast(FrontendClient, client), profile_label=_LABEL)


def test_the_exclusion_submitter_excludes_exactly_the_submitted_entry_off_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    observation = _observation(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID, effect=OperationEffect.UPDATED)
    controller = _Controller(observation=observation, result=_excluded(entry_id(1)))
    submissions = _install(monkeypatch, client, controller)
    submitter = _submitter(client)
    client.session_read_threads.clear()

    result = asyncio.run(submitter(_exclusion(entry_id(1))))

    assert result == LedgerExclusionResultV1(transaction_id=entry_id(1))
    assert submissions[0]["definition_id"] == LEDGER_EXCLUDE_OPERATION_DEFINITION_ID
    assert cast(LedgerLifecycleMutationRequest, submissions[0]["payload"]).transaction_id == entry_id(1)
    assert client.session_read_threads
    assert threading.get_ident() not in client.session_read_threads


def test_the_exclusion_submitter_reports_a_settled_entry_it_did_not_submit_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The receipt reported an exclusion; one of another entry leaves the submitted entry's state unknown."""
    client = _Client()
    observation = _observation(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID, effect=OperationEffect.UPDATED)
    settled = _excluded(entry_id(1))
    assert settled.result is not None
    moved = settled.result.transaction.model_copy(update={"transaction_id": entry_id(1)[:-1] + "f"})
    other = settled.model_copy(update={"result": settled.result.model_copy(update={"transaction": moved})})
    _install(monkeypatch, client, _Controller(observation=observation, result=other))

    with raises_unsupported_result(OperationEffect.UPDATED, observation.projection.definition_contract):
        asyncio.run(_submitter(client)(_exclusion(entry_id(1))))


def test_the_exclusion_submitter_refuses_another_action(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    observation = _observation(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID)
    submissions = _install(monkeypatch, client, _Controller(observation=observation, result=None))
    other = LedgerExclusionSubmissionV1(
        action=ActionReference(action_id=lookup_action("operator.ledger.review").action_id),
        transaction_id=entry_id(1),
    )

    with pytest.raises(RefusalError):
        asyncio.run(_submitter(client)(other))
    assert submissions == []


def test_the_exclusion_submitter_surfaces_the_operations_validation_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    observation = _observation(
        LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    )
    _install(monkeypatch, client, _Controller(observation=observation, result=_validation_refusal("ledger.exclude")))

    with pytest.raises(LedgerLifecycleValidationRefusedError):
        asyncio.run(_submitter(client)(_exclusion(entry_id(1))))


def test_the_exclusion_submitter_refuses_a_wrong_effect_and_a_refusal_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    wrong_effect = _observation(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(observation=wrong_effect, result=_excluded(entry_id(1))))
    with pytest.raises(RefusalError):
        asyncio.run(_submitter(client)(_exclusion(entry_id(1))))

    refused = _observation(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID, condition=OperationTerminalCondition.REFUSED)
    _install(monkeypatch, client, _Controller(observation=refused, result=None, detail=_registered_detail()))
    with pytest.raises(RecordedRegisteredError):
        asyncio.run(_submitter(client)(_exclusion(entry_id(1))))


def test_the_exclusion_submitter_fails_closed_when_its_session_lapses(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    observation = _observation(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID)
    submissions = _install(monkeypatch, client, _Controller(observation=observation, result=None))
    submitter = _submitter(client)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(submitter(_exclusion(entry_id(1))))
    assert submissions == []


def test_the_entries_composer_offers_its_five_tools_through_the_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    observation = _observation(LEDGER_LIST_OPERATION_DEFINITION_ID)
    _install(monkeypatch, client, _Controller(observation=observation, result=None))

    tools = compose_runtime_ledger_tools(
        cast(FrontendClient, client), profile_label=_LABEL, composers=(compose_entries_tools,)
    )

    assert [(tool.key, tool.area) for tool in tools] == [
        ("ledger.tool.entries.browse", LedgerWorkspaceArea.ENTRIES),
        ("ledger.tool.entries.add", LedgerWorkspaceArea.ENTRIES),
        ("ledger.tool.entries.export", LedgerWorkspaceArea.ENTRIES),
        ("ledger.tool.entries.health", LedgerWorkspaceArea.OVERVIEW),
        ("ledger.tool.entries.reset", LedgerWorkspaceArea.OVERVIEW),
    ]
    assert [type(tool.build(entries_controller())) for tool in tools] == [
        LedgerEntriesBrowseScreen,
        LedgerEntryAddScreen,
        LedgerEntriesExportScreen,
        LedgerHealthScreen,
        LedgerResetScreen,
    ]
