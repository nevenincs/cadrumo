"""The operation modal prompts the operator for a Cl@ve approval as soon as its notice arrives."""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Static

from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicNoticeEventV1,
)
from .....application.operations.persistence.replay import OperationReplayStatus
from .....core.i18n.render import tr
from ..modal import OperationModal
from .test_runtime_access_loss import _NOW, _OPERATION_ID, _Controller, _Host, _until

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _notice(
    revision: int, sequence: int, notice_code: str, display_code: str | None = None
) -> OperationPublicNoticeEventV1:
    return OperationPublicNoticeEventV1(
        revision=revision,
        sequence=sequence,
        timestamp=_NOW,
        code=notice_code,
        notice_code=notice_code,
        display_code=display_code,
    )


def _with_notices(observation: OperationObservationSuccessV1) -> OperationObservationSuccessV1:
    projection = observation.projection.model_copy(update={"anchor_cursor": 4})
    revision = projection.revision
    events = (
        _notice(revision, 1, "auth.clave-movil.approval-pending", "YLL"),
        _notice(revision, 2, "auth.clave-movil.qr-scan-pending"),
        _notice(revision, 3, "operation.started"),
        _notice(revision, 4, "operation.started", "RH4"),
    )
    return OperationObservationSuccessV1(
        projection=projection,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=4,
            requested_cursor=0,
            status=OperationReplayStatus.PAGE,
            events=events,
            next_cursor=4,
            restart_cursor=None,
        ),
    )


def test_clave_notices_render_the_localized_prompt_and_unknown_codes_render_as_before() -> None:
    async def run() -> None:
        controller = _Controller(failing_action="observe")
        controller.observation = _with_notices(controller.observation)
        host = _Host(controller)
        async with host.run_test(size=(100, 40)) as pilot:
            await _until(pilot, lambda: isinstance(host.screen, OperationModal) and host.screen._view_model is not None)
            modal = host.screen
            assert isinstance(modal, OperationModal)
            lines = str(modal.query_one("#operation-modal-log", Static).content).split("\n")
            approval = tr("operation.notice.clave_movil_approval_pending_with_code", code="YLL")
            assert "YLL" in approval
            assert lines == [
                approval,
                tr("operation.notice.clave_movil_qr_scan_pending"),
                tr("operation.started"),
                f"{tr('operation.started')}: RH4",
            ]
            controller.release_second_observe.set()

    asyncio.run(run())
