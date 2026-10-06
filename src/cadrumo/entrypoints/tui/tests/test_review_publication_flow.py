"""The review flow reaches the existing operation modal and never replays lost admission."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import cast, override
from uuid import UUID

import pytest
from textual.app import App
from textual.pilot import Pilot

from ....application.export.google_operation import GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT
from ....application.export.publication_receipt import PublicationReceipt, PublicationState, ReadableExportAuthorization
from ....application.export.review_snapshot import ReviewSnapshot
from ....application.operations.frontend_projection import OperationNoPendingInteractionV1, OperationPublicProjectionV1
from ....application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from ....application.operations.persistence.replay import OperationReplayStatus
from ....application.operations.registry import OperationPublicContractSetV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...operation_composition import build_production_operation_registry
from ...tests.review_publication_fixture import (
    frontend_authorization,
    frontend_created_publication,
    frontend_publication,
    frontend_published_publication,
    frontend_review_label,
    frontend_review_snapshot,
)
from ..operations.controller_port import OperationControllerPort
from ..operations.modal import OperationModal
from ..review_publication import ReviewPublicationOfferScreen, ReviewPublicationResultScreen
from ..review_publication_flow import ReviewPublicationFlow

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 10, 5, tzinfo=UTC)
_OPERATION_ID = "1" * 64


@lru_cache(maxsize=1)
def _contracts() -> OperationPublicContractSetV1:
    return build_production_operation_registry().public_contract_set


def _observation(*, terminal: bool) -> OperationObservationSuccessV1:
    contracts = _contracts()
    contract = next(item for item in contracts.definitions if item.definition_id == "export.google-sheets")
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=contract.definition_id,
        subject_ref="profile:00000000-0000-0000-0000-000000000001",
        revision=4,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.RUNNING,
        terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
        effect=OperationEffect.UPDATED if terminal else OperationEffect.NONE,
        phase_code=GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
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
        result_ref="f" * 64 if terminal else None,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=projection,
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


class _Controller:
    operation_id = _OPERATION_ID
    actor_ref = "operator:review-ui-test"

    def __init__(self, *, lose_admission: bool = False) -> None:
        self.lose_admission = lose_admission
        self.release = asyncio.Event()
        self.observe_count = 0
        self.start_count = 0
        self.running_observation = _observation(terminal=False)
        self.terminal_observation = _observation(terminal=True)
        self.start_acknowledgement = self.operation_id

    async def start(self) -> str:
        self.start_count += 1
        if self.lose_admission:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        return self.start_acknowledgement

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        self.observe_count += 1
        if self.observe_count == 1:
            return self.running_observation
        await self.release.wait()
        return self.terminal_observation


class _Door:
    def __init__(self, *, lose_admission: bool = False, unavailable_offer: bool = False) -> None:
        self.snapshot = frontend_review_snapshot()
        self.authorization = frontend_authorization(frontend_publication(self.snapshot))
        self.receipt: PublicationReceipt | None = frontend_published_publication(self.snapshot)
        self.controller = _Controller(lose_admission=lose_admission)
        self.unavailable_offer = unavailable_offer
        self.offers = 0
        self.submissions = 0
        self.result_reads = 0

    async def load_offer(self) -> tuple[ReviewSnapshot, ReadableExportAuthorization]:
        self.offers += 1
        if self.unavailable_offer:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        return self.snapshot, self.authorization

    async def submit(
        self, snapshot: ReviewSnapshot, authorization: ReadableExportAuthorization
    ) -> OperationControllerPort:
        assert snapshot is self.snapshot and authorization is self.authorization
        self.submissions += 1
        return cast(OperationControllerPort, self.controller)

    async def read_receipt(self, projection: OperationPublicProjectionV1) -> PublicationReceipt | None:
        assert projection.operation_id == _OPERATION_ID
        self.result_reads += 1
        return self.receipt


async def _until(pilot: Pilot[None], predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(10):
        while not predicate():
            await pilot.pause(0.02)
    # A pushed screen becomes app.screen before its first layout. Settle that
    # layout before a caller clicks a control whose region may still be empty.
    await pilot.pause()


@pytest.mark.asyncio
async def test_disclosure_reaches_real_operation_progress_then_the_receipt_link() -> None:
    app: App[None] = App()
    door = _Door()
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        assert door.offers == 1 and door.submissions == 0
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: isinstance(app.screen, OperationModal))
        assert door.submissions == door.controller.start_count == 1
        door.controller.release.set()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationResultScreen))
        assert door.result_reads == 1
        assert not notices


@pytest.mark.asyncio
async def test_cancelling_disclosure_never_submits() -> None:
    app: App[None] = App()
    door = _Door()
    flow = ReviewPublicationFlow(app, door, notice=lambda _: None, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.press("escape")
        await pilot.pause()
        assert door.submissions == door.controller.start_count == door.result_reads == 0


@pytest.mark.asyncio
async def test_lost_submission_acknowledgement_is_visible_and_cannot_be_replayed() -> None:
    app: App[None] = App()
    door = _Door(lose_admission=True)
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: bool(notices))
        flow.open()
        await pilot.pause()
        assert notices[-1] == "google_review.notice.submission_unresolved"
        assert door.submissions == door.controller.start_count == 1
        assert door.result_reads == 0


@pytest.mark.asyncio
async def test_unavailable_prerequisites_refuse_before_an_offer_or_submission() -> None:
    app: App[None] = App()
    door = _Door(unavailable_offer=True)
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: bool(notices))
        assert notices == ["runtime_connection_closed"]
        assert not isinstance(app.screen, ReviewPublicationOfferScreen)
        assert door.submissions == 0


@pytest.mark.asyncio
async def test_a_receipt_for_another_publication_is_refused_without_replay() -> None:
    app: App[None] = App()
    door = _Door()
    door.receipt = PublicationReceipt.model_validate(
        {**frontend_publication(door.snapshot).model_dump(), "publication_id": UUID(int=9)}
    )
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: isinstance(app.screen, OperationModal))
        door.controller.release.set()
        await _until(pilot, lambda: bool(notices))
        assert notices[-1] == "google_review.notice.receipt_unavailable"
        assert not isinstance(app.screen, ReviewPublicationResultScreen)
        flow.open()
        await pilot.pause()
        assert notices[-1] == "google_review.notice.submission_unresolved"
        assert door.submissions == 1


@pytest.mark.asyncio
async def test_missing_custody_receipt_after_updated_effect_prevents_another_submission() -> None:
    app: App[None] = App()
    door = _Door()
    door.receipt = None
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: isinstance(app.screen, OperationModal))
        door.controller.release.set()
        await _until(pilot, lambda: bool(notices))
        assert notices[-1] == "google_review.notice.receipt_unavailable"
        assert not isinstance(app.screen, ReviewPublicationResultScreen)
        flow.open()
        await pilot.pause()
        assert notices[-1] == "google_review.notice.submission_unresolved"
        assert door.submissions == door.controller.start_count == door.result_reads == 1


@pytest.mark.parametrize(
    "state",
    [PublicationState.PREPARED, PublicationState.REMOTE_CREATED, PublicationState.POPULATED, PublicationState.VERIFIED],
)
@pytest.mark.asyncio
async def test_unfinished_retained_checkpoint_with_updated_effect_prevents_reopening(state: PublicationState) -> None:
    app: App[None] = App()
    door = _Door()
    receipt = frontend_publication(door.snapshot)
    if state is not PublicationState.PREPARED:
        receipt = frontend_created_publication(door.snapshot)
    if state in {PublicationState.POPULATED, PublicationState.VERIFIED}:
        receipt = receipt.advance(PublicationState.POPULATED)
    if state is PublicationState.VERIFIED:
        receipt = receipt.advance(PublicationState.VERIFIED)
    door.receipt = receipt
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: isinstance(app.screen, OperationModal))
        door.controller.release.set()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationResultScreen))
        flow.open()
        await pilot.pause()
        assert notices[-1] == "google_review.notice.submission_unresolved"
        assert door.submissions == door.controller.start_count == door.result_reads == 1


@pytest.mark.parametrize(
    ("condition", "effect"),
    [
        (OperationTerminalCondition.FAILED, OperationEffect.UPDATED),
        (OperationTerminalCondition.SUCCEEDED, OperationEffect.UNKNOWN),
    ],
)
@pytest.mark.asyncio
async def test_persisted_publication_cannot_override_the_current_supervised_outcome(
    condition: OperationTerminalCondition, effect: OperationEffect
) -> None:
    app: App[None] = App()
    door = _Door()
    observation = door.controller.terminal_observation
    projection = OperationPublicProjectionV1.model_validate(
        {**observation.projection.model_dump(), "terminal_condition": condition, "effect": effect}
    )
    door.controller.terminal_observation = OperationObservationSuccessV1(
        projection=projection, event_page=observation.event_page
    )
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: isinstance(app.screen, OperationModal))
        door.controller.release.set()
        await _until(pilot, lambda: bool(notices))
        assert notices[-1] == "google_review.notice.receipt_unavailable"
        assert not isinstance(app.screen, ReviewPublicationResultScreen)
        flow.open()
        await pilot.pause()
        assert door.submissions == 1
        assert notices[-1] == "google_review.notice.submission_unresolved"


@pytest.mark.asyncio
async def test_start_acknowledgement_for_another_operation_remains_unresolved() -> None:
    app: App[None] = App()
    door = _Door()
    door.controller.start_acknowledgement = "9" * 64
    notices: list[str] = []
    flow = ReviewPublicationFlow(app, door, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        flow.open()
        await _until(pilot, lambda: isinstance(app.screen, ReviewPublicationOfferScreen))
        await pilot.click("#review-publication-publish")
        await _until(pilot, lambda: bool(notices))
        assert notices[-1] == "google_review.notice.submission_unresolved"
        assert not isinstance(app.screen, OperationModal)
        flow.open()
        await pilot.pause()
        assert door.submissions == door.controller.start_count == 1
        assert door.result_reads == 0


class _PendingOfferDoor(_Door):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @override
    async def load_offer(self) -> tuple[ReviewSnapshot, ReadableExportAuthorization]:
        self.started.set()
        await self.release.wait()
        return await super().load_offer()


@pytest.mark.asyncio
async def test_distinct_review_flows_do_not_cancel_each_others_offer_workers() -> None:
    app: App[None] = App()
    first = _PendingOfferDoor()
    second = _PendingOfferDoor()
    notices: list[str] = []
    first_flow = ReviewPublicationFlow(app, first, notice=notices.append, label=frontend_review_label)
    second_flow = ReviewPublicationFlow(app, second, notice=notices.append, label=frontend_review_label)
    async with app.run_test(size=(120, 45)) as pilot:
        first_flow.open()
        await _until(pilot, first.started.is_set)
        second_flow.open()
        await _until(pilot, second.started.is_set)
        first.release.set()
        second.release.set()
        await _until(pilot, lambda: first.offers == second.offers == 1)
        assert not notices
        assert first.submissions == second.submissions == 0
