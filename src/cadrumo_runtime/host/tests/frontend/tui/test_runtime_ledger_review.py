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
from cadrumo.application.operations.registry import (
    OperationRegistry,
)
from cadrumo.application.review.filter import LedgerReviewStatus
from cadrumo.core.config import Settings
from cadrumo.core.confirmation_gate import ConfirmationBlockReason
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.identity.transaction_ids import TransactionId
from cadrumo.core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from ....frontend.tui.runtime_ledger_review import (
    RuntimeLedgerEvidenceReviewListTuiDoorV1,
    RuntimeLedgerReviewDoorsV1,
    RuntimeLedgerReviewTuiDoorV1,
    compose_runtime_ledger_review_doors,
)
from ._door_session_support import (
    NOW,
    OTHER_PROFILE_ID,
    PROFILE_ID,
    RECORDED_CODE,
    RECORDED_KEY,
    SESSION_ID,
    ScriptedController,
    SessionClient,
    install_scripted_controller,
    terminal_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TRANSACTION_ID = cast("TransactionId", "a" * 64)


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
                drafted_at=NOW,
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
        LedgerReviewRequest(profile_id=PROFILE_ID),
        _review,
        LedgerReviewProjection,
    ),
    _Case(
        "evidence_review",
        RuntimeLedgerEvidenceReviewListTuiDoorV1,
        "ledger.evidence.review.list",
        LedgerEvidenceReviewListRequest(profile_id=PROFILE_ID),
        _drafts,
        LedgerEvidenceReviewListProjection,
    ),
)
_IDS = [case.door for case in _CASES]


def _doors(client: SessionClient) -> RuntimeLedgerReviewDoorsV1:
    return compose_runtime_ledger_review_doors(cast(FrontendClient, client), profile_label="Fixture profile")


class _ReadDoor(Protocol):
    @property
    def profile_id(self) -> UUID: ...

    async def __call__(self, request: BaseModel, /) -> BaseModel: ...


def _door(client: SessionClient, case: _Case) -> _ReadDoor:
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
    client = SessionClient()
    result = case.result(PROFILE_ID)
    controller = ScriptedController(observation=terminal_observation(_REGISTRY, case.definition_id), result=result)
    submissions = install_scripted_controller(monkeypatch, client, controller)
    door = _door(client, case)

    assert door.profile_id == PROFILE_ID
    assert asyncio.run(door(case.request)) == result
    assert len(submissions) == 1
    assert submissions[0]["definition_id"] == case.definition_id
    assert submissions[0]["payload"] == case.request
    assert submissions[0]["expected_session_id"] == SESSION_ID
    assert controller.result_reads == [(case.result_type, 1, False)]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_refuses_a_result_for_another_profile(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = SessionClient()
    observation = terminal_observation(_REGISTRY, case.definition_id)
    install_scripted_controller(
        monkeypatch, client, ScriptedController(observation=observation, result=case.result(OTHER_PROFILE_ID))
    )

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
@pytest.mark.parametrize("effect", [OperationEffect.UPDATED, OperationEffect.PARTIAL])
def test_each_door_refuses_a_receipt_reporting_an_effect(
    monkeypatch: pytest.MonkeyPatch, case: _Case, effect: OperationEffect
) -> None:
    """A read that reports writing something is not the read the screen asked for."""
    client = SessionClient()
    observation = terminal_observation(_REGISTRY, case.definition_id, effect=effect)
    install_scripted_controller(
        monkeypatch, client, ScriptedController(observation=observation, result=case.result(PROFILE_ID))
    )

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_raises_the_recorded_error_of_a_refusal_receipt(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = SessionClient()
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=RECORDED_CODE,
        message_key=RECORDED_KEY,
        context=(),
    )
    observation = terminal_observation(
        _REGISTRY, case.definition_id, condition=OperationTerminalCondition.REFUSED, refusal_ref=RECORDED_CODE
    )
    controller = ScriptedController(observation=observation, result=None, detail=detail)
    install_scripted_controller(monkeypatch, client, controller)

    with pytest.raises(RecordedRegisteredError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.recorded_code == RECORDED_CODE
    assert controller.detail_reads == 1
    assert controller.result_reads == []


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_fails_closed_when_its_session_lapses(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = SessionClient()
    submissions = install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(observation=terminal_observation(_REGISTRY, case.definition_id), result=None),
    )
    door = _door(client, case)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door(case.request))

    assert submissions == []


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_reads_its_session_off_the_event_loop_thread(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    """The session read is a blocking IPC exchange; a door awaited on the loop never runs it there."""
    client = SessionClient()
    controller = ScriptedController(
        observation=terminal_observation(_REGISTRY, case.definition_id), result=case.result(PROFILE_ID)
    )
    install_scripted_controller(monkeypatch, client, controller)
    door = _door(client, case)
    client.session_read_threads.clear()

    asyncio.run(door(case.request))

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads


def test_a_review_detail_answering_another_selection_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The detail read names one entry by prefix; a list answer to it is not that entry."""
    client = SessionClient()
    request = LedgerReviewRequest(profile_id=PROFILE_ID, transaction_prefix="aaaa")
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(observation=terminal_observation(_REGISTRY, "ledger.review"), result=_review(PROFILE_ID)),
    )

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_doors(client).review(request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_composing_the_doors_observes_the_session_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = SessionClient()
    reads: list[UUID] = []

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == "Fixture profile"
        reads.append(session_id)
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    doors = _doors(client)

    assert reads == [SESSION_ID]
    assert doors.review.profile_id == doors.evidence_review.profile_id == PROFILE_ID
