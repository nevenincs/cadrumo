"""Removing an operation modal stops its observation before its widgets go.

Textual removes a screen by pruning its children first and only then
unmounting the screen, which is when it cancels the screen's workers. An
observation that completed inside that window used to resume the poll worker,
which then looked up a status row that had already been removed: ``NoMatches``
inside the worker, so ``WorkerFailed`` ended the whole application.

The app removes a modal without going through its own close controls when an
account action pops every screen above the base. A shutdown that closes the
screens while the app's message loop is still running, as the test harness
does when a test leaves an observing modal open, opens the same window. An
ordinary ``exit`` does not: Textual cancels every worker when the app's
message loop ends, before it closes any screen. The controller below holds its
observation open until the status row has been removed, which is exactly that
window, so the old code fails here every time rather than occasionally.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

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
from .....core.operations import OperationEffect, OperationLifecycle
from ....operation_composition import build_production_operation_registry
from ..controller_port import OperationResponseControlPort
from ..modal import OperationModal, OperationModalOutcomeV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OPERATION_ID = "b" * 64
_NOW = datetime(2026, 10, 23, tzinfo=UTC)
_DEADLINE_SECONDS = 10


@lru_cache(maxsize=1)
def _contracts() -> OperationPublicContractSetV1:
    return build_production_operation_registry().public_contract_set


def _running_observation() -> OperationObservationSuccessV1:
    contracts = _contracts()
    contract = next(row for row in contracts.definitions if row.definition_id == "user-profile.censo-review")
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=contract.definition_id,
        subject_ref="profile:active",
        revision=3,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.RUNNING,
        terminal_condition=None,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=True,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
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
        self.armed = False

    def arm(self) -> None:
        self.armed = True

    async def wait(self, timeout: float) -> None:
        del timeout
        await asyncio.Event().wait()

    def close(self) -> None:
        """Nothing to release."""


class _Controller:
    """Answers the first read at once and holds the second until the modal's status row is gone."""

    def __init__(self) -> None:
        self.modal: OperationModal | None = None
        self.waiter = _Waiter()
        self.observe_calls = 0
        self.held_read_cancelled = False

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "operator:removal"

    def operation_changes(self) -> _Waiter:
        return self.waiter

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        self.observe_calls += 1
        if self.observe_calls > 1:
            modal = self.modal
            assert modal is not None
            try:
                async with asyncio.timeout(_DEADLINE_SECONDS):
                    while modal.query("#operation-modal-status"):
                        await asyncio.sleep(0)
            except asyncio.CancelledError:
                self.held_read_cancelled = True
                raise
        return _running_observation()

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        raise AssertionError("no review is pending")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        raise AssertionError("no review is pending")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("removal must not cancel the operation")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError("removal must not detach from the operation")


class _Host(App[None]):
    def __init__(self, controller: _Controller) -> None:
        super().__init__()
        self.modal = OperationModal(controller)
        controller.modal = self.modal
        self.outcomes: list[OperationModalOutcomeV1 | None] = []

    def on_mount(self) -> None:
        self.push_screen(self.modal, self.outcomes.append)


async def _until(condition: Callable[[], bool], reason: str) -> None:
    try:
        async with asyncio.timeout(_DEADLINE_SECONDS):
            while not condition():
                await asyncio.sleep(0)
    except TimeoutError:
        raise AssertionError(reason) from None


@pytest.mark.asyncio
@pytest.mark.parametrize("removal", ["pop", "shutdown"])
async def test_removing_the_modal_mid_read_stops_observation_without_a_result(
    removal: Literal["pop", "shutdown"],
) -> None:
    controller = _Controller()
    host = _Host(controller)
    async with host.run_test(size=(100, 40)):
        await _until(lambda: controller.observe_calls == 2, "the modal never started its second read")
        if removal == "pop":
            await host.pop_screen()
            await _until(lambda: controller.held_read_cancelled, "the held read was never cancelled")
        # Otherwise leaving the block shuts the app down with the modal still observing.
    # Reaching here means ``run_test`` had no worker failure to re-raise.
    assert controller.held_read_cancelled
    # Removal is not a dismissal: no outcome, not even ``None``, reaches the caller.
    assert host.outcomes == []
