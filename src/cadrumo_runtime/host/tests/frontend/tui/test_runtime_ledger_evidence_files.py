"""Exact-session dispatch and receipt correlation for the twelve installed evidence and attachment doors.

Each door is proved against its operation's real definition and public
registration: it submits the exact request under the pinned session, and it
refuses a result for another profile, a receipt reporting the wrong effect, a
refusal receipt, and a lapsed session.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.action_ports import LedgerActionPortsFactory
from cadrumo.application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationId,
    LedgerAttachmentOperationResult,
    LedgerAttachmentProjection,
    LedgerAttachRequest,
    LedgerDetachRequest,
    build_ledger_attach_definition,
    build_ledger_attach_registration,
    build_ledger_detach_definition,
    build_ledger_detach_registration,
)
from cadrumo.application.ledger.attachment_review import AttachmentReviewItem
from cadrumo.application.ledger.batch_ingest import BatchRunResult
from cadrumo.application.ledger.evidence import MediaKind
from cadrumo.application.ledger.evidence_followup_contracts import (
    AttachmentStoreFactory,
    ConsentWithdrawalSurveyProjection,
    EvidenceConsentEntriesFactory,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceFollowupOperationPorts,
    LedgerEvidenceReviewSummaryProjection,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from cadrumo.application.ledger.evidence_followup_registration import (
    build_ledger_evidence_followup_definitions,
    build_ledger_evidence_followup_registrations,
    build_ledger_evidence_review_summary_definition,
    build_ledger_evidence_review_summary_registration,
)
from cadrumo.application.ledger.evidence_ingestion_contracts import (
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidenceBatchSnapshot,
)
from cadrumo.application.ledger.evidence_ingestion_operation import (
    build_ledger_evidence_ingestion_definitions,
    build_ledger_evidence_ingestion_registrations,
)
from cadrumo.application.ledger.evidence_ingestion_operation_ports import LedgerEvidenceIngestionPortsFactory
from cadrumo.application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdatePatch,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
    build_ledger_evidence_remove_definition,
    build_ledger_evidence_remove_registration,
    build_ledger_evidence_update_definition,
    build_ledger_evidence_update_registration,
)
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePortsFactory
from cadrumo.application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
    LedgerEvidenceAutomationRecordProjection,
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceRecordProjection,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRefusal,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
    build_ledger_evidence_query_definition,
    build_ledger_evidence_query_registration,
    build_ledger_evidence_view_definition,
    build_ledger_evidence_view_registration,
)
from cadrumo.application.ledger.extraction_draft_repository import ExtractionDraftRepositoryFactory
from cadrumo.application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from cadrumo.application.ledger.transaction_projection import LedgerTransactionProjection
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
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.attachments.models import AttachmentSource
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.evidence_files_doors import LedgerEvidenceFilesDoorsV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_ledger_evidence_files import (
    RuntimeEvidenceFilesTuiDoorV1,
    compose_evidence_files_tools,
    compose_runtime_evidence_files_doors,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE_ID = UUID("6cc00000-0000-4000-8000-0000000000cc")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 4, tzinfo=UTC)
_EVIDENCE_ID = "0000000000000001"
_DIGEST = "d" * 64
_TRANSACTION_ID = "a" * 64
_EVENT_ID = "e" * 64
_RECORDED_CODE = "REFUSED_LEDGER_EVIDENCE_INPUT"
_RECORDED_KEY = "errors.refused.refused_ledger_evidence_input"


def _registry() -> OperationRegistry:
    """Every evidence and attachment operation, declared through its own builders."""
    actions = cast(LedgerActionPortsFactory, cast(object, lambda **_kwargs: None))
    evidence = cast(LedgerEvidencePortsFactory, cast(object, lambda **_kwargs: None))
    ingestion = cast(LedgerEvidenceIngestionPortsFactory, cast(object, lambda **_kwargs: None))
    followup_ports = LedgerEvidenceFollowupOperationPorts(
        settings=cast(Settings, object()),
        attachment_store_factory=cast(AttachmentStoreFactory, cast(object, lambda _bucket: None)),
        extraction_draft_repository_factory=cast(
            ExtractionDraftRepositoryFactory, cast(object, lambda **_kwargs: None)
        ),
        consent_entries_factory=cast(EvidenceConsentEntriesFactory, cast(object, lambda **_kwargs: ())),
    )
    attach = build_ledger_attach_definition(actions)
    detach = build_ledger_detach_definition(actions)
    view = build_ledger_evidence_view_definition(evidence)
    query = build_ledger_evidence_query_definition(evidence)
    update = build_ledger_evidence_update_definition(evidence)
    remove = build_ledger_evidence_remove_definition(evidence)
    batch = build_ledger_evidence_ingestion_definitions(ingestion)
    followup = build_ledger_evidence_followup_definitions(followup_ports)
    summary = build_ledger_evidence_review_summary_definition(followup_ports)
    definitions = (attach, detach, view, query, update, remove, *batch, *followup, summary)
    registrations = (
        build_ledger_attach_registration(attach),
        build_ledger_detach_registration(detach),
        build_ledger_evidence_view_registration(view),
        build_ledger_evidence_query_registration(query),
        build_ledger_evidence_update_registration(update),
        build_ledger_evidence_remove_registration(remove),
        *build_ledger_evidence_ingestion_registrations(batch),
        *build_ledger_evidence_followup_registrations(followup),
        build_ledger_evidence_review_summary_registration(summary),
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


# Synthetic results, each built from the operation's own public model.


def _record(profile_id: UUID = _PROFILE_ID, **changes: object) -> LedgerEvidenceRecordProjection:
    record = LedgerEvidenceRecordProjection(
        evidence_id=_EVIDENCE_ID,
        bucket_id=str(profile_id),
        source_path="factura-0001.pdf",
        source_sha256=_DIGEST,
        attachment_id=_DIGEST,
        media_kind=MediaKind.PDF,
        supplier="Suministros Delta SL",
        invoice_number="F-2026-0001",
        invoice_date="2026-03-14",
        taxable_base="100",
        iva_rate="21",
        iva_amount="21",
        created_at=_NOW,
        updated_at=_NOW,
    )
    return record.model_copy(update=changes)


def _attachment() -> AttachmentReviewItem:
    return AttachmentReviewItem(
        attachment_id=_DIGEST,
        sha256=_DIGEST,
        mime_type="application/pdf",
        bytes_size=2048,
        source=AttachmentSource.LOCAL_FILE,
        provider_locator="not-exposed",
        captured_at=_NOW.isoformat(),
        linked_invoice_ids=(),
        pending_review=True,
    )


def _review(profile_id: UUID = _PROFILE_ID) -> LedgerEvidenceReviewViewProjection:
    return LedgerEvidenceReviewViewProjection(
        profile_id=profile_id,
        evidence_reference=_EVIDENCE_ID,
        extractor="local-reader",
        drafted_at=_NOW,
        draft=InvoiceDraftProjectionV1(supplier_name="Suministros Delta SL"),
    )


def _batch(profile_id: UUID = _PROFILE_ID) -> LedgerEvidenceBatchProjection:
    return LedgerEvidenceBatchProjection(
        profile_id=profile_id,
        write_count=0,
        effect=OperationEffect.NONE,
        direction=InvoiceKind.RECEIVED,
        run=LedgerEvidenceBatchSnapshot.from_run(BatchRunResult()),
    )


def _transaction(attachment_ids: tuple[str, ...]) -> LedgerTransactionProjection:
    return LedgerTransactionProjection(
        transaction_id=_TRANSACTION_ID,
        date="2026-03-14",
        booked_date="2026-03-14",
        value_date=None,
        amount="1250.00",
        currency="EUR",
        direction="outgoing",
        counterparty="Suministros Delta SL",
        description="Material de oficina",
        business_classification="business",
        business_pct=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id=None,
        invoice_id=None,
        attachment_ids=attachment_ids,
        notes="",
        lifecycle_state="active",
        classified_by="manual",
        classified_at=None,
        classification_reason="",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at=_NOW.isoformat(),
        modified_at=_NOW.isoformat(),
    )


def _attachment_result(
    operation_id: LedgerAttachmentOperationId, profile_id: UUID = _PROFILE_ID
) -> LedgerAttachmentOperationResult:
    return LedgerAttachmentOperationResult(
        outcome="updated",
        profile_id=profile_id,
        operation_id=operation_id,
        result=LedgerAttachmentProjection(
            profile_id=profile_id,
            operation_id=operation_id,
            transaction=_transaction((_DIGEST,) if operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID else ()),
            review_status=LedgerReviewStatus.PENDING,
            bucket_event_ids=(_EVENT_ID,),
        ),
    )


@dataclass(frozen=True)
class _Case:
    """One door: a request, a result its receipt supports, and that receipt's effect."""

    door: str
    definition_id: str
    request: BaseModel
    result: Callable[[UUID], BaseModel]
    effect: OperationEffect
    result_type: type[BaseModel]
    result_version: int = 1
    allow_refusal_detail: bool = False

    @property
    def wrong_effect(self) -> OperationEffect:
        return OperationEffect.NONE if self.effect is OperationEffect.UPDATED else OperationEffect.UPDATED


_UPDATE_REQUEST = LedgerEvidenceUpdateRequest(
    profile_id=_PROFILE_ID,
    evidence_id=_EVIDENCE_ID,
    patch=LedgerEvidenceUpdatePatch(supplier="Suministros Gamma SL"),
    patch_fields=("supplier",),
)

_CASES = (
    _Case(
        "query",
        "ledger.evidence.query",
        LedgerEvidenceQueryRequest(profile_id=_PROFILE_ID),
        lambda profile: LedgerEvidenceQueryProjection(
            profile_id=profile,
            count=1,
            rows=(LedgerEvidenceAutomationRecordProjection.from_person_projection(_record(profile)),),
        ),
        OperationEffect.NONE,
        LedgerEvidenceQueryProjection,
    ),
    _Case(
        "view",
        "ledger.evidence.view",
        LedgerEvidenceViewRequest(profile_id=_PROFILE_ID, evidence_id=_EVIDENCE_ID),
        lambda profile: LedgerEvidenceViewProjection(
            profile_id=profile, outcome=LedgerEvidenceViewSuccess(record=_record(profile))
        ),
        OperationEffect.NONE,
        LedgerEvidenceViewProjection,
        result_version=2,
        allow_refusal_detail=True,
    ),
    _Case(
        "update",
        "ledger.evidence.update",
        _UPDATE_REQUEST,
        lambda profile: LedgerEvidenceUpdateProjection(
            profile_id=profile, record=_record(profile, supplier="Suministros Gamma SL"), bucket_event_ids=(_EVENT_ID,)
        ),
        OperationEffect.UPDATED,
        LedgerEvidenceUpdateProjection,
    ),
    _Case(
        "remove",
        "ledger.evidence.remove",
        LedgerEvidenceRemoveRequest(profile_id=_PROFILE_ID, evidence_id=_EVIDENCE_ID),
        lambda profile: LedgerEvidenceRemoveProjection(
            profile_id=profile, record=_record(profile), bucket_event_ids=(_EVENT_ID,)
        ),
        OperationEffect.UPDATED,
        LedgerEvidenceRemoveProjection,
    ),
    _Case(
        "batch",
        "ledger.evidence.batch",
        LedgerEvidenceBatchRequest(
            profile_id=_PROFILE_ID,
            sources=("facturas",),
            source_directory=str(Path.cwd()),
            direction=InvoiceKind.RECEIVED,
        ),
        _batch,
        OperationEffect.NONE,
        LedgerEvidenceBatchProjection,
    ),
    _Case(
        "attachment_queue",
        "ledger.evidence.attachment_queue",
        LedgerEvidenceAttachmentQueueRequest(profile_id=_PROFILE_ID),
        lambda profile: LedgerEvidenceAttachmentQueueProjection(profile_id=profile, count=1, rows=(_attachment(),)),
        OperationEffect.NONE,
        LedgerEvidenceAttachmentQueueProjection,
    ),
    _Case(
        "attachment_view",
        "ledger.evidence.attachment_view",
        LedgerEvidenceAttachmentViewRequest(profile_id=_PROFILE_ID, attachment_id=_DIGEST),
        lambda profile: LedgerEvidenceAttachmentViewProjection(profile_id=profile, item=_attachment()),
        OperationEffect.NONE,
        LedgerEvidenceAttachmentViewProjection,
    ),
    _Case(
        "consent_list",
        "ledger.evidence.consent.list",
        LedgerEvidenceConsentListRequest(profile_id=_PROFILE_ID),
        lambda profile: LedgerEvidenceConsentListProjection(
            profile_id=profile, survey=ConsentWithdrawalSurveyProjection()
        ),
        OperationEffect.NONE,
        LedgerEvidenceConsentListProjection,
    ),
    _Case(
        "review_view",
        "ledger.evidence.review.view",
        LedgerEvidenceReviewViewRequest(profile_id=_PROFILE_ID, evidence_reference=_EVIDENCE_ID),
        _review,
        OperationEffect.NONE,
        LedgerEvidenceReviewViewProjection,
        result_version=2,
    ),
    _Case(
        "review_summary",
        "ledger.evidence.review.summary",
        LedgerEvidenceReviewViewRequest(profile_id=_PROFILE_ID, evidence_reference=_EVIDENCE_ID),
        lambda profile: LedgerEvidenceReviewSummaryProjection.from_review_view(_review(profile)),
        OperationEffect.NONE,
        LedgerEvidenceReviewSummaryProjection,
    ),
    _Case(
        "attach",
        LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        LedgerAttachRequest(profile_id=_PROFILE_ID, transaction_id=_TRANSACTION_ID, attachment_ids=(_DIGEST,)),
        lambda profile: _attachment_result(LEDGER_ATTACH_OPERATION_DEFINITION_ID, profile),
        OperationEffect.UPDATED,
        LedgerAttachmentOperationResult,
        allow_refusal_detail=True,
    ),
    _Case(
        "detach",
        LEDGER_DETACH_OPERATION_DEFINITION_ID,
        LedgerDetachRequest(profile_id=_PROFILE_ID, transaction_id=_TRANSACTION_ID, attachment_ids=(_DIGEST,)),
        lambda profile: _attachment_result(LEDGER_DETACH_OPERATION_DEFINITION_ID, profile),
        OperationEffect.UPDATED,
        LedgerAttachmentOperationResult,
        allow_refusal_detail=True,
    ),
)
_IDS = [case.door for case in _CASES]


def _doors(client: _Client) -> LedgerEvidenceFilesDoorsV1:
    return compose_runtime_evidence_files_doors(cast(FrontendClient, client), profile_label="Fixture profile")


def _door(client: _Client, case: _Case) -> RuntimeEvidenceFilesTuiDoorV1[BaseModel, BaseModel]:
    door = getattr(_doors(client), case.door)
    assert isinstance(door, RuntimeEvidenceFilesTuiDoorV1)
    return cast("RuntimeEvidenceFilesTuiDoorV1[BaseModel, BaseModel]", door)


def test_every_door_has_a_case_and_names_its_registered_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    _install(monkeypatch, client, _Controller(observation=_observation("ledger.evidence.query"), result=None))
    doors = _doors(client)
    assert {case.door for case in _CASES} == set(LedgerEvidenceFilesDoorsV1.__dataclass_fields__)
    for case in _CASES:
        door = getattr(doors, case.door)
        assert isinstance(door, RuntimeEvidenceFilesTuiDoorV1)
        assert door.definition_id == case.definition_id
        assert _REGISTRY.lookup_public_contract(case.definition_id).definition_id == case.definition_id


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_submits_the_exact_request_and_reads_its_registered_result(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    client = _Client()
    result = case.result(_PROFILE_ID)
    controller = _Controller(observation=_observation(case.definition_id, effect=case.effect), result=result)
    submissions = _install(monkeypatch, client, controller)
    door = _door(client, case)

    assert door.profile_id == _PROFILE_ID
    assert asyncio.run(door(case.request)) == result
    assert submissions[0]["definition_id"] == case.definition_id
    assert submissions[0]["payload"] == case.request
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert controller.result_reads == [(case.result_type, case.result_version, case.allow_refusal_detail)]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_refuses_a_result_for_another_profile(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    observation = _observation(case.definition_id, effect=case.effect)
    _install(monkeypatch, client, _Controller(observation=observation, result=case.result(_OTHER_PROFILE_ID)))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_each_door_refuses_a_receipt_reporting_the_wrong_effect(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    observation = _observation(case.definition_id, effect=case.wrong_effect)
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
    controller = _Controller(
        observation=_observation(case.definition_id, effect=case.effect), result=case.result(_PROFILE_ID)
    )
    _install(monkeypatch, client, controller)
    door = _door(client, case)
    client.session_read_threads.clear()

    asyncio.run(door(case.request))

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads


def test_a_success_result_under_a_declared_refusal_receipt_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    case = _CASES[1]
    client = _Client()
    observation = _observation(
        case.definition_id,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
    )
    _install(monkeypatch, client, _Controller(observation=observation, result=case.result(_PROFILE_ID)))

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client, case)(case.request))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_the_view_s_declared_missing_record_is_read_as_its_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    request = LedgerEvidenceViewRequest(profile_id=_PROFILE_ID, evidence_id=_EVIDENCE_ID)
    missing = LedgerEvidenceViewProjection(profile_id=_PROFILE_ID, outcome=LedgerEvidenceViewRefusal())
    observation = _observation(
        "ledger.evidence.view",
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
    )
    _install(monkeypatch, client, _Controller(observation=observation, result=missing))

    assert asyncio.run(_doors(client).view(request)) == missing


@pytest.mark.parametrize("operation_id", [LEDGER_ATTACH_OPERATION_DEFINITION_ID, LEDGER_DETACH_OPERATION_DEFINITION_ID])
def test_an_attachment_validation_refusal_is_read_as_its_messages(
    monkeypatch: pytest.MonkeyPatch, operation_id: LedgerAttachmentOperationId
) -> None:
    client = _Client()
    refused = LedgerAttachmentOperationResult(
        outcome="validation_error",
        profile_id=_PROFILE_ID,
        operation_id=operation_id,
        validation_messages=("attachment not found",),
    )
    observation = _observation(
        operation_id,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
    )
    _install(monkeypatch, client, _Controller(observation=observation, result=refused))
    doors = _doors(client)
    if operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID:
        answered = asyncio.run(
            doors.attach(
                LedgerAttachRequest(profile_id=_PROFILE_ID, transaction_id=_TRANSACTION_ID, attachment_ids=(_DIGEST,))
            )
        )
    else:
        answered = asyncio.run(
            doors.detach(
                LedgerDetachRequest(profile_id=_PROFILE_ID, transaction_id=_TRANSACTION_ID, attachment_ids=(_DIGEST,))
            )
        )

    assert answered == refused


def test_an_update_that_did_not_apply_the_requested_value_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    stale = LedgerEvidenceUpdateProjection(profile_id=_PROFILE_ID, record=_record(), bucket_event_ids=(_EVENT_ID,))
    observation = _observation("ledger.evidence.update", effect=OperationEffect.UPDATED)
    _install(monkeypatch, client, _Controller(observation=observation, result=stale))

    with pytest.raises(RefusalError):
        asyncio.run(_doors(client).update(_UPDATE_REQUEST))


def test_a_view_answering_another_record_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    other = LedgerEvidenceViewProjection(
        profile_id=_PROFILE_ID, outcome=LedgerEvidenceViewSuccess(record=_record(evidence_id="0000000000000002"))
    )
    _install(monkeypatch, client, _Controller(observation=_observation("ledger.evidence.view"), result=other))

    with pytest.raises(RefusalError):
        asyncio.run(_doors(client).view(LedgerEvidenceViewRequest(profile_id=_PROFILE_ID, evidence_id=_EVIDENCE_ID)))


def test_composing_the_doors_observes_the_session_once_and_names_six_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    client = _Client()
    reads: list[UUID] = []

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == "Fixture profile"
        reads.append(session_id)
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    tools = compose_evidence_files_tools(cast(FrontendClient, client), "Fixture profile")

    assert reads == [_SESSION_ID]
    assert [tool.key for tool in tools] == [
        "ledger.tool.evidence_files.records",
        "ledger.tool.evidence_files.batch",
        "ledger.tool.evidence_files.queue",
        "ledger.tool.evidence_files.review",
        "ledger.tool.evidence_files.consent",
        "ledger.tool.evidence_files.attachments",
    ]
