"""An operation modal re-reads its operation on the runtime's cue, never on a timer, when the cue exists."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import lru_cache

import pytest
from pydantic import BaseModel
from textual.app import App

from .....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationReviewProjectionResultV1,
)
from .....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
)
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationPublicContractSetV1
from .....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ....operation_composition import build_production_operation_registry
from ...tests.settling import settle_until
from ..controller_port import OperationChangeSourcePort, OperationResponseControlPort
from ..modal import OperationModal, OperationModalSettledOutcomeV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 17, tzinfo=UTC)


@lru_cache(maxsize=1)
def _contracts() -> OperationPublicContractSetV1:
    return build_production_operation_registry().public_contract_set


def _observation(*, terminal: bool) -> OperationObservationSuccessV1:
    contracts = _contracts()
    contract = next(row for row in contracts.definitions if row.definition_id == "user-profile.censo-review")
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=contract.definition_id,
        subject_ref="profile:active",
        revision=5 if terminal else 4,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.RUNNING,
        terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
        effect=OperationEffect.UPDATED if terminal else OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=not terminal,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref="sha256:" + "e" * 64 if terminal else None,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=0,
        requested_cursor=0,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=page)


class _Waiter:
    def __init__(self) -> None:
        self.changed = asyncio.Event()
        self.armed = False
        self.closed = False

    def arm(self) -> None:
        self.armed = True
        self.changed.clear()

    async def wait(self, timeout: float) -> None:
        await self.changed.wait()

    def close(self) -> None:
        self.closed = True


class _Controller:
    """A runtime binding whose observations are scripted; with ``cue``, each read is a committed change."""

    def __init__(self, *observations: OperationObservationSuccessV1, cue: bool) -> None:
        self.observations = list(observations)
        self.waiter = _Waiter()
        self.cue = cue
        self.observe_calls = 0

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "operator:cues"

    def operation_changes(self) -> _Waiter:
        return self.waiter

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        self.observe_calls += 1
        if self.cue and self.waiter.armed:
            self.waiter.changed.set()
        return self.observations.pop(0)

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        raise AssertionError("no review is pending")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        raise AssertionError("no review is pending")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("not cancelled")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError("not detached")


class _Host(App[None]):
    def __init__(self, controller: _Controller | _Uncued) -> None:
        super().__init__()
        self.controller = controller
        self.outcome: object = None

    async def _present(self) -> None:
        self.outcome = await self.push_screen_wait(OperationModal(self.controller))
        self.exit()

    def on_mount(self) -> None:
        self.run_worker(self._present())


def test_the_controller_offers_the_cue_port() -> None:
    assert isinstance(_Controller(cue=True), OperationChangeSourcePort)


@pytest.mark.asyncio
async def test_each_cue_reads_the_operation_again_until_it_settles() -> None:
    running = _observation(terminal=False)
    controller = _Controller(running, running, _observation(terminal=True), cue=True)
    host = _Host(controller)
    async with host.run_test(size=(100, 40)) as pilot:
        await settle_until(
            pilot,
            lambda: isinstance(host.outcome, OperationModalSettledOutcomeV1),
            "the modal to settle on the terminal read",
            workers=False,
        )
    # The first read subscribes; the second, armed, is cued; the third is terminal.
    assert controller.observe_calls == 3
    assert controller.waiter.closed


@pytest.mark.asyncio
async def test_without_a_cue_a_running_operation_is_not_read_again() -> None:
    running = _observation(terminal=False)
    controller = _Controller(running, running, running, cue=False)
    host = _Host(controller)
    async with host.run_test(size=(100, 40)) as pilot:
        await settle_until(
            pilot, lambda: controller.observe_calls >= 2, "the first reads of the operation", workers=False
        )
        await pilot.pause(1.0)
        assert controller.observe_calls == 2


class _Uncued:
    """A runtime binding that offers no change cue at all."""

    def __init__(self, *observations: OperationObservationSuccessV1) -> None:
        self._scripted = _Controller(*observations, cue=False)

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return self._scripted.actor_ref

    @property
    def observe_calls(self) -> int:
        return self._scripted.observe_calls

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        return await self._scripted.observe(after_cursor, page_limit=page_limit)

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        raise AssertionError("no review is pending")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        raise AssertionError("no review is pending")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("not cancelled")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError("not detached")


@pytest.mark.asyncio
async def test_a_controller_without_cues_is_read_once_and_never_on_a_timer() -> None:
    running = _observation(terminal=False)
    controller = _Uncued(running, running, running)
    assert not isinstance(controller, OperationChangeSourcePort)
    host = _Host(controller)
    async with host.run_test(size=(100, 40)) as pilot:
        await settle_until(
            pilot, lambda: controller.observe_calls >= 1, "the first reads of the operation", workers=False
        )
        # Long enough for several of the former 200 ms polls.
        await pilot.pause(1.0)
        assert controller.observe_calls == 1
