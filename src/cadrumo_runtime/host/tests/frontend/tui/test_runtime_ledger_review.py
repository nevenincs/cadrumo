"""Exact-session dispatch and receipt correlation for the installed Records review reads.

Both doors are proved against their operation's real definition and public
registration: each submits the exact request under the pinned session, reads
its session off the event-loop thread, and refuses a result for another
profile, a receipt reporting an effect, a refusal receipt, and a lapsed session.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.action_ports import LedgerActionPortsFactory
from cadrumo.application.ledger.evidence_followup_contracts import (
    AttachmentStoreFactory,
    EvidenceConsentEntriesFactory,
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceFollowupOperationPorts,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
)
from cadrumo.application.ledger.evidence_followup_registration import (
    build_ledger_evidence_followup_definitions,
    build_ledger_evidence_followup_registrations,
)
from cadrumo.application.ledger.extraction_draft_repository import ExtractionDraftRepositoryFactory
from cadrumo.application.ledger.review_operation import (
    LedgerReviewProjection,
    LedgerReviewRequest,
    LedgerReviewRowProjection,
    build_ledger_review_definition,
    build_ledger_review_registration,
)
from cadrumo.application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.review.filter import LedgerReviewStatus
from cadrumo.core.config import Settings
from cadrumo.core.confirmation_gate import ConfirmationBlockReason
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.identity.transaction_ids import TransactionId
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_ledger_review import (
    RuntimeLedgerEvidenceReviewListTuiDoorV1,
    RuntimeLedgerReviewDoorsV1,
    RuntimeLedgerReviewTuiDoorV1,
    compose_runtime_ledger_review_doors,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE_ID = UUID("6cc00000-0000-4000-8000-0000000000cc")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 4, tzinfo=UTC)
_TRANSACTION_ID = cast("TransactionId", "a" * 64)
_RECORDED_CODE = "REFUSED_LEDGER_EVIDENCE_INPUT"
_RECORDED_KEY = "errors.refused.refused_ledger_evidence_input"


def _registry() -> OperationRegistry:
    """Both review reads, declared through their own builders."""
    actions = cast(LedgerActionPortsFactory, cast(object, lambda **_kwargs: None))
    followup_ports = LedgerEvidenceFollowupOperationPorts(
        settings=cast(Settings, object()),
        attachment_store_factory=cast(AttachmentStoreFactory, cast(object, lambda _bucket: None)),
        extraction_draft_repository_factory=cast(
            ExtractionDraftRepositoryFactory, cast(object, lambda **_kwargs: None)
        ),
        consent_entries_factory=cast(EvidenceConsentEntriesFactory, cast(object, lambda **_kwargs: ())),
    )
    review = build_ledger_review_definition(actions)
    followup = build_ledger_evidence_followup_definitions(followup_ports)
    definitions = (review, *followup)
    registrations = (
        build_ledger_review_registration(review),
        *build_ledger_evidence_followup_registrations(followup),
    )
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )


_REGISTRY = _registry()


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
    ) -> BaseModel:
        assert projection.operation_id == self.operation_id
        self.result_reads.append((result_type, result_version, allow_refusal_detail))
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection.operation_id == self.operation_id
        self.detail_reads += 1
        return self.detail


def _observation(
    definition_id: str,
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
    refusal_ref: str | None = None,
) -> OperationObservationSuccessV1:
    contract = _REGISTRY.lookup_public_contract(definition_id)
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=_REGISTRY.public_contract_set.contract_set_digest,
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
        refusal_ref=refusal_ref if refused else None,
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
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        controller.client = client
        return controller

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions


def _review(profile_id: UUID, *, prefix: str | None = None) -> LedgerReviewProjection:
    return LedgerReviewProjection(
        profile_id=profile_id,
        transaction_prefix=prefix,
        rows=(
            LedgerReviewRowProjection(
                id=_TRANSACTION_ID,
                date="2026-03-14",
                amount="1250.00",
                description="Material de oficina",
                status=LedgerReviewStatus.PENDING,
            ),
        ),
        filters=(),
    )


def _drafts(profile_id: UUID) -> LedgerEvidenceReviewListProjection:
    return LedgerEvidenceReviewListProjection(
        profile_id=profile_id,
        rows=(
            EvidenceReviewQueueRowProjection(
                evidence_reference="0000000000000001",
                extractor="local-reader",
                drafted_at=_NOW,
                blocking_count=1,
                reasons=(ConfirmationBlockReason.CLOSURE_DISCREPANCY,),
                advisory_count=0,
            ),
        ),
    )


@dataclass(frozen=True)
class _Case:
    """One door: the field that holds it, its request, and a result its receipt supports."""

    door: str
    door_type: type
    definition_id: str
    request: BaseModel
    result: Callable[[UUID], BaseModel]
    result_type: type[BaseModel]


_CASES = (
    _Case(
        "review",
        RuntimeLedgerReviewTuiDoorV1,
        "ledger.review",
        LedgerReviewRequest(profile_id=_PROFILE_ID),
        _review,
        LedgerReviewProjection,
    ),
    _Case(
        "evidence_review",
        RuntimeLedgerEvidenceReviewListTuiDoorV1,
        "ledger.evidence.review.list",
        LedgerEvidenceReviewListRequest(profile_id=_PROFILE_ID),
        _drafts,
        LedgerEvidenceReviewListProjection,
    ),
)
_IDS = [case.door for case in _CASES]


def _doors(client: _Client) -> RuntimeLedgerReviewDoorsV1:
    return compose_runtime_ledger_review_doors(cast(FrontendClient, client), profile_label="Fixture profile")


class _ReadDoor(Protocol):
    @property
    def profile_id(self) -> UUID: ...

    async def __call__(self, request: BaseModel, /) -> BaseModel: ...


def _door(client: _Client, case: _Case) -> _ReadDoor:
    door = getattr(_doors(client), case.door)
    assert isinstance(door, case.door_type)
    return cast(_ReadDoor, door)


def test_every_door_has_a_case_and_names_its_registered_operation() -> None:
    assert {case.door for case in _CASES} == set(RuntimeLedgerReviewDoorsV1.__dataclass_fields__)
    for case in _CASES:
        assert _REGISTRY.lookup_public_contract(case.definition_id).definition_id == case.definition_id


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_submits_the_exact_request_and_reads_its_registered_result(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    client = _Client()
    result = case.result(_PROFILE_ID)
    controller = _Controller(observation=_observation(case.definition_id), result=result)
    submissions = _install(monkeypatch, client, controller)
    door = _door(client, case)

    assert door.profile_id == _PROFILE_ID
    assert asyncio.run(door(case.request)) == result
    assert len(submissions) == 1
    assert submissions[0]["definition_id"] == case.definition_id
    assert submissions[0]["payload"] == case.request
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert controller.result_reads == [(case.result_type, 1, False)]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_refuses_a_result_for_another_profile(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    observation = _observation(case.definition_id)
    _install(monkeypatch, client, _Controller(observation=observation, result=case.result(_OTHER_PROFILE_ID)))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
@pytest.mark.parametrize("effect", [OperationEffect.UPDATED, OperationEffect.PARTIAL])
def test_each_door_refuses_a_receipt_reporting_an_effect(
    monkeypatch: pytest.MonkeyPatch, case: _Case, effect: OperationEffect
) -> None:
    """A read that reports writing something is not the read the screen asked for."""
    client = _Client()
    observation = _observation(case.definition_id, effect=effect)
    _install(monkeypatch, client, _Controller(observation=observation, result=case.result(_PROFILE_ID)))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_raises_the_recorded_error_of_a_refusal_receipt(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_RECORDED_CODE,
        message_key=_RECORDED_KEY,
        context=(),
    )
    observation = _observation(
        case.definition_id, condition=OperationTerminalCondition.REFUSED, refusal_ref=_RECORDED_CODE
    )
    controller = _Controller(observation=observation, result=None, detail=detail)
    _install(monkeypatch, client, controller)

    with pytest.raises(RecordedRegisteredError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.recorded_code == _RECORDED_CODE
    assert controller.detail_reads == 1
    assert controller.result_reads == []


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_fails_closed_when_its_session_lapses(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    submissions = _install(monkeypatch, client, _Controller(observation=_observation(case.definition_id), result=None))
    door = _door(client, case)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door(case.request))

    assert submissions == []


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_reads_its_session_off_the_event_loop_thread(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    """The session read is a blocking IPC exchange; a door awaited on the loop never runs it there."""
    client = _Client()
    controller = _Controller(observation=_observation(case.definition_id), result=case.result(_PROFILE_ID))
    _install(monkeypatch, client, controller)
    door = _door(client, case)
    client.session_read_threads.clear()

    asyncio.run(door(case.request))

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads


def test_a_review_detail_answering_another_selection_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The detail read names one entry by prefix; a list answer to it is not that entry."""
    client = _Client()
    request = LedgerReviewRequest(profile_id=_PROFILE_ID, transaction_prefix="aaaa")
    _install(monkeypatch, client, _Controller(observation=_observation("ledger.review"), result=_review(_PROFILE_ID)))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_doors(client).review(request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_composing_the_doors_observes_the_session_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = _Client()
    reads: list[UUID] = []

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == "Fixture profile"
        reads.append(session_id)
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    doors = _doors(client)

    assert reads == [_SESSION_ID]
    assert doors.review.profile_id == doors.evidence_review.profile_id == _PROFILE_ID
