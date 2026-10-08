"""A rendered private operation view is discarded when its authority disappears."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import cast

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, Static

from .....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from .....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationResponseMutationResultV1,
    OperationReviewProjectionResultV1,
)
from .....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionSuccessV1,
)
from .....application.operations.interactions import OperationResponseIntent, OperationResponseIntentValue
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationPublicContractSetV1
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....core.operations import OperationEffect, OperationLifecycle
from ....operation_composition import build_production_operation_registry
from ..controller_port import OperationResponseControlPort
from ..interactions import OperationModalReviewInteractionV1, resolve_modal_interaction_state
from ..modal import OperationModal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_INTERACTION_ID = "b" * 64
_NOW = datetime(2026, 9, 27, tzinfo=UTC)


class _SafeReview(BaseModel):
    code: str


@lru_cache(maxsize=1)
def _contracts() -> OperationPublicContractSetV1:
    return build_production_operation_registry().public_contract_set


def _observation() -> OperationObservationSuccessV1:
    contracts = _contracts()
    contract = next(row for row in contracts.definitions if row.definition_id == "user-profile.censo-review")
    assert contract.review_projection_schema is not None
    assert contract.interaction_response_schema is not None
    reference = OperationReviewProjectionReferenceV1(
        operation_id=_OPERATION_ID,
        interaction_id=_INTERACTION_ID,
        revision=4,
        review_projection_schema=contract.review_projection_schema,
        definition_contract_digest=contract.definition_contract_digest,
        expires_at=None,
    )
    pending = OperationReviewAvailableInteractionV1(
        operation_id=_OPERATION_ID,
        interaction_id=_INTERACTION_ID,
        revision=4,
        presentation_code="operation.review.ready",
        response_schema=contract.interaction_response_schema,
        expires_at=None,
        review_reference=reference,
    )
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=contract.definition_id,
        subject_ref="profile:active",
        revision=4,
        anchor_cursor=1,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
        terminal_condition=None,
        effect=OperationEffect.NONE,
        phase_code="operation.review.ready",
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
        pending_interaction=pending,
        result_ref=None,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=1,
        requested_cursor=0,
        status=OperationReplayStatus.PAGE,
        events=(
            OperationPublicPhaseEventV1(
                revision=4,
                sequence=1,
                timestamp=_NOW,
                code="operation.review.ready",
                phase_code="operation.review.ready",
            ),
        ),
        next_cursor=1,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=page)


class _Control:
    def __init__(self) -> None:
        self.inspect_count = 0
        self.permitted: frozenset[OperationResponseIntentValue] = frozenset(
            {OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}
        )

    async def inspect(self) -> OperationResponseControlSuccessV1:
        self.inspect_count += 1
        return OperationResponseControlSuccessV1(
            operation_id=_OPERATION_ID,
            interaction_id=_INTERACTION_ID,
            revision=4,
            available=bool(self.permitted),
            permitted_intents=self.permitted,
        )

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationResultV1:
        raise RuntimeFrontendRefusedError("profile_session_expired")

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationResultV1:
        raise RuntimeFrontendRefusedError("profile_session_expired")


class _Controller:
    def __init__(self, *, failing_action: str) -> None:
        self.failing_action = failing_action
        self.observation = _observation()
        self.control = _Control()
        self.second_observe_started = asyncio.Event()
        self.release_second_observe = asyncio.Event()
        self.observe_calls = 0
        self.control_bindings = 0

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "operator:access-loss"

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        self.observe_calls += 1
        if self.observe_calls == 1:
            return self.observation
        self.second_observe_started.set()
        await self.release_second_observe.wait()
        if self.failing_action == "transport":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if self.failing_action == "observe":
            raise RuntimeFrontendRefusedError("profile_session_expired")
        projection = self.observation.projection
        return OperationObservationSuccessV1(
            projection=projection,
            event_page=OperationPublicEventPageV1(
                operation_id=_OPERATION_ID,
                anchor_cursor=1,
                requested_cursor=1,
                status=OperationReplayStatus.CAUGHT_UP,
                events=(),
                next_cursor=1,
                restart_cursor=None,
            ),
        )

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        contract = self.observation.projection.definition_contract
        assert contract.review_projection_schema is not None
        result = OperationReviewProjectionSuccessV1[_SafeReview](
            projection_schema=contract.review_projection_schema,
            definition_contract_digest=contract.definition_contract_digest,
            projection=_SafeReview(code="review.private"),
        )
        return cast(OperationReviewProjectionResultV1[ReviewT], result)

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        self.control_bindings += 1
        return self.control

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise RuntimeFrontendRefusedError("profile_session_expired")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise RuntimeFrontendRefusedError("profile_session_expired")


class _Host(App[None]):
    def __init__(self, controller: _Controller) -> None:
        super().__init__()
        self.controller = controller
        self.closed = asyncio.Event()
        self.outcome: object = object()

    async def _present(self) -> None:
        self.outcome = await self.push_screen_wait(OperationModal(self.controller))
        self.closed.set()
        self.exit()

    def on_mount(self) -> None:
        self.run_worker(self._present())


async def _until(pilot: Pilot[None], predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(10):
        while not predicate():
            await pilot.pause(0.02)


@pytest.mark.parametrize("failing_action", ["observe", "transport", "cancel", "detach", "apply", "reject"])
def test_runtime_loss_erases_rendered_private_state_and_leaves_only_close(failing_action: str) -> None:
    async def run() -> None:
        controller = _Controller(failing_action=failing_action)
        host = _Host(controller)
        async with host.run_test(size=(100, 40)) as pilot:
            await _until(pilot, lambda: isinstance(host.screen, OperationModal) and host.screen._view_model is not None)
            modal = host.screen
            assert isinstance(modal, OperationModal)
            assert "review.private" in str(modal.query_one("#operation-modal-review", Static).content)
            assert modal.query_one("#operation-modal-log", Static).content
            await controller.second_observe_started.wait()
            if failing_action in {"observe", "transport"}:
                controller.release_second_observe.set()
            else:
                await pilot.click(f"#btn-operation-{failing_action}")
            await _until(pilot, lambda: modal._view_model is None)
            controller.release_second_observe.set()
            await pilot.pause(0.05)
            assert modal._interaction is None
            assert modal._log_view.rows == ()
            for suffix in ("phase", "deadlines", "diagnostic", "receipt", "review", "log"):
                assert not modal.query_one(f"#operation-modal-{suffix}", Static).content
            for action in ("cancel", "detach", "apply", "reject"):
                assert modal.query_one(f"#btn-operation-{action}", Button).disabled
            assert not modal.query_one("#btn-operation-close", Button).disabled
            await pilot.click("#btn-operation-close")
            await _until(pilot, host.closed.is_set)
            assert host.outcome is None

    asyncio.run(run())


def test_cached_review_controls_reinspect_permission_without_rebinding() -> None:
    async def run() -> None:
        controller = _Controller(failing_action="observe")
        projection = controller.observation.projection
        first = await resolve_modal_interaction_state(controller, projection, BaseModel)
        assert isinstance(first, OperationModalReviewInteractionV1)
        assert first.apply_enabled and first.reject_enabled
        controller.control.permitted = frozenset()
        second = await resolve_modal_interaction_state(controller, projection, BaseModel, current=first)
        assert isinstance(second, OperationModalReviewInteractionV1)
        assert not second.apply_enabled and not second.reject_enabled
        assert second.control is first.control
        assert controller.control_bindings == 1
        assert controller.control.inspect_count == 2

    asyncio.run(run())
