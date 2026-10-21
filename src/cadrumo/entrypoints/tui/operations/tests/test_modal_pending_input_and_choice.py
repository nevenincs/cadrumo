"""A pending INPUT or CHOICE is rendered from its public facts, with no control that cannot answer it.

The public response surface applies or rejects a REVIEW and nothing else, for
every frontend. The modal therefore says what the operation is waiting for and
leaves the person the two controls that still act on it: cancel and detach.
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
from textual.pilot import Pilot
from textual.widgets import Button, Static

from .....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationReviewProjectionResultV1,
)
from .....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
    OperationUnsupportedInteractionV1,
)
from .....application.operations.frontend_requests import (
    OperationDetachSuccessV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
)
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationPublicContractSetV1
from .....core.i18n.render import tr
from .....core.operations import OperationEffect, OperationInteractionKind, OperationLifecycle
from ....operation_composition import build_production_operation_registry
from ..controller_port import OperationResponseControlPort
from ..interactions import (
    OperationModalUnsupportedInteractionV1,
    resolve_modal_interaction_state,
    unanswerable_interaction_text,
)
from ..modal import OperationModal, OperationModalDetachedOutcomeV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_INTERACTION_ID = "b" * 64
_NOW = datetime(2026, 9, 27, tzinfo=UTC)
_EXPIRY = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
_PRESENTATION = "modelo.edit.apply"

type _Kind = Literal[OperationInteractionKind.INPUT, OperationInteractionKind.CHOICE]


@lru_cache(maxsize=1)
def _contracts() -> OperationPublicContractSetV1:
    return build_production_operation_registry().public_contract_set


def _pending(kind: _Kind) -> OperationUnsupportedInteractionV1:
    return OperationUnsupportedInteractionV1(
        interaction_kind=kind,
        interaction_id=_INTERACTION_ID,
        revision=4,
        presentation_code=_PRESENTATION,
        unsupported_code="operation.interaction.unsupported",
        expires_at=_EXPIRY,
    )


def _observation() -> OperationObservationSuccessV1:
    """An operation whose registered contract declares INPUT, waiting on one."""
    contracts = _contracts()
    contract = next(row for row in contracts.definitions if OperationInteractionKind.INPUT in row.interaction_kinds)
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=contract.definition_id,
        subject_ref="work-unit-1",
        revision=4,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
        terminal_condition=None,
        effect=OperationEffect.NONE,
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
        pending_interaction=_pending(OperationInteractionKind.INPUT),
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


class _WaitingController:
    """Serve one waiting observation; every review door records that it was wrongly used."""

    def __init__(self) -> None:
        self.observation = _observation()
        self.review_reads = 0
        self.control_bindings = 0
        self.detached_at: int | None = None

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "session:pending-input"

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        return self.observation

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        self.review_reads += 1
        raise AssertionError("an INPUT interaction has no review projection to read")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        self.control_bindings += 1
        raise AssertionError("an INPUT interaction has no response control to bind")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("cancellation is not offered for this operation")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        self.detached_at = expected_revision
        return OperationDetachSuccessV1(operation_id=_OPERATION_ID, revision=expected_revision)


class _Host(App[None]):
    def __init__(self, controller: _WaitingController) -> None:
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


@pytest.mark.parametrize(
    ("kind", "kind_key"),
    [
        (OperationInteractionKind.INPUT, "tui.operations.interaction.kind.input"),
        (OperationInteractionKind.CHOICE, "tui.operations.interaction.kind.choice"),
    ],
)
def test_a_pending_input_or_choice_is_worded_from_its_public_facts(kind: _Kind, kind_key: str) -> None:
    text = unanswerable_interaction_text(_pending(kind))

    lines = text.splitlines()
    assert lines[0] == tr(kind_key)
    assert f"{tr('tui.operations.interaction.presentation')}: {_PRESENTATION}" in lines
    assert f"{tr('tui.operations.interaction.expires')}: {_EXPIRY.isoformat()}" in lines
    assert lines[-1] == tr("tui.operations.interaction.no_answer")
    assert _INTERACTION_ID not in text


def test_the_two_kinds_are_worded_differently() -> None:
    assert unanswerable_interaction_text(_pending(OperationInteractionKind.INPUT)) != unanswerable_interaction_text(
        _pending(OperationInteractionKind.CHOICE)
    )


def test_resolving_a_pending_input_reads_no_review_and_binds_no_response_control() -> None:
    async def run() -> None:
        controller = _WaitingController()
        state = await resolve_modal_interaction_state(controller, controller.observation.projection, BaseModel)
        assert isinstance(state, OperationModalUnsupportedInteractionV1)
        assert state.interaction.interaction_kind is OperationInteractionKind.INPUT
        assert controller.review_reads == 0
        assert controller.control_bindings == 0

    asyncio.run(run())


def test_the_modal_shows_a_pending_input_and_offers_only_the_controls_that_act_on_it() -> None:
    async def run() -> None:
        controller = _WaitingController()
        host = _Host(controller)
        async with host.run_test(size=(100, 40)) as pilot:
            await _until(pilot, lambda: isinstance(host.screen, OperationModal) and host.screen._view_model is not None)
            modal = host.screen
            assert isinstance(modal, OperationModal)
            shown = str(modal.query_one("#operation-modal-review", Static).content)
            assert tr("tui.operations.interaction.kind.input") in shown
            assert _PRESENTATION in shown
            assert tr("tui.operations.interaction.no_answer") in shown
            assert modal.query_one("#btn-operation-apply", Button).disabled
            assert modal.query_one("#btn-operation-reject", Button).disabled
            assert modal.query_one("#btn-operation-cancel", Button).disabled
            assert not modal.query_one("#btn-operation-detach", Button).disabled
            assert controller.review_reads == 0
            assert controller.control_bindings == 0
            await pilot.click("#btn-operation-detach")
            await _until(pilot, host.closed.is_set)
        assert controller.detached_at == 4
        assert host.outcome == OperationModalDetachedOutcomeV1(operation_id=_OPERATION_ID, revision=4)

    asyncio.run(run())
