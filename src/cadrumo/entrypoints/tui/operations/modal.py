"""The generic detachable operation modal, built solely from public DTOs.

This modal drives exactly one submitted operation through
:class:`OperationController` and renders exactly the public projection,
event-page, REVIEW, response-control, cancellation, detach and typed
Workspace-refresh DTOs those public services return. It never imports a
persisted snapshot, a journal record, or a supervisor-private type, and it
never reclassifies lifecycle truth beyond what
:func:`build_operation_modal_view_model` already derived.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import ClassVar, Literal, override

from pydantic import BaseModel, ConfigDict
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ....application.operations.frontend_contracts import (
    OperationCancellationSuccessV1,
    OperationDetachSuccessV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from ....application.operations.models import OperationId, OperationRevision
from ....core.i18n import tr
from ....core.operations import OperationLifecycle
from ....core.time import now
from ..components.theme import tokenised
from .controller import OperationController
from .interactions import (
    OperationModalInteractionStateV1,
    OperationModalReviewInteractionV1,
    resolve_modal_interaction_state,
)
from .logs import OperationModalLogViewV1, build_initial_log_view, fold_event_page
from .projection import OperationModalViewModelV1, build_operation_modal_view_model

_POLL_INTERVAL = timedelta(milliseconds=200)
_MODAL_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")


class OperationModalSettledOutcomeV1(BaseModel):
    """The modal closed because its bound operation reached settlement."""

    model_config = _MODAL_CONFIG
    disposition: Literal["settled"] = "settled"
    view_model: OperationModalViewModelV1


class OperationModalDetachedOutcomeV1(BaseModel):
    """The modal closed because the operator detached from a live operation."""

    model_config = _MODAL_CONFIG
    disposition: Literal["detached"] = "detached"
    operation_id: OperationId
    revision: OperationRevision


type OperationModalOutcomeV1 = OperationModalSettledOutcomeV1 | OperationModalDetachedOutcomeV1


class OperationModal(ModalScreen[OperationModalOutcomeV1]):
    """Generic modal presenting one supervised operation until it settles."""

    DEFAULT_CSS = tokenised("""
    OperationModal {
        align: center middle;
    }
    #operation-modal-body {
        border: $cadrumo-radius-overlay $accent;
        background: $surface;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        width: $cadrumo-modal-width;
        height: auto;
        max-height: $cadrumo-modal-height;
    }
    #operation-modal-status { text-style: bold; margin: $cadrumo-space-0; }
    #operation-modal-review { color: $text; margin: $cadrumo-space-0; }
    #operation-modal-log { color: $text-muted; height: auto; max-height: $cadrumo-log-max-height; overflow-y: auto; }
    #operation-modal-actions {
        height: auto;
        align-horizontal: right;
        margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0;
    }
    #operation-modal-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
    """)
    BINDINGS: ClassVar = [Binding("escape", "request_close", "", show=False)]

    def __init__(self, controller: OperationController) -> None:
        """Bind the modal to exactly one already-submitted operation."""
        super().__init__()
        self._controller = controller
        self._view_model: OperationModalViewModelV1 | None = None
        self._log_view: OperationModalLogViewV1 = build_initial_log_view(controller.operation_id)
        self._interaction: OperationModalInteractionStateV1 | None = None
        self._closing = False

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="operation-modal-body"):
            yield Static("", id="operation-modal-status")
            yield Static("", id="operation-modal-review")
            yield Static("", id="operation-modal-log")
            with Horizontal(id="operation-modal-actions"):
                yield Button(tr("operation.modal.action.reject"), id="btn-operation-reject")
                yield Button(tr("operation.modal.action.apply"), id="btn-operation-apply", classes="-primary")
                yield Button(tr("operation.modal.action.cancel"), id="btn-operation-cancel")
                yield Button(tr("operation.modal.action.detach"), id="btn-operation-detach")
                yield Button(tr("operation.modal.action.close"), id="btn-operation-close")

    def on_mount(self) -> None:
        """Start the bounded observation poll loop as an exclusive worker."""
        self.run_worker(self._poll_loop(), name="operation-modal-poll", exclusive=True)

    async def _poll_loop(self) -> None:
        cursor = self._log_view.next_cursor
        while not self._closing:
            observed = await self._controller.observe(cursor)
            if not isinstance(observed, OperationObservationSuccessV1):
                await asyncio.sleep(_POLL_INTERVAL.total_seconds())
                continue
            self._log_view = fold_event_page(self._log_view, observed.event_page)
            cursor = self._log_view.restart_cursor if self._log_view.resynchronized else self._log_view.next_cursor
            self._view_model = build_operation_modal_view_model(observed.projection)
            self._interaction = await resolve_modal_interaction_state(self._controller, observed.projection)
            self._render()
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                self.dismiss(OperationModalSettledOutcomeV1(view_model=self._view_model))
                return
            await asyncio.sleep(_POLL_INTERVAL.total_seconds())

    def _render(self) -> None:
        view_model = self._view_model
        if view_model is None:
            return
        status = self.query_one("#operation-modal-status", Static)
        if view_model.terminal_copy_key is not None:
            status.update(tr(view_model.terminal_copy_key))
        elif view_model.spinner_visible:
            status.update(tr("operation.modal.status.running"))
        else:
            status.update("")
        review = self.query_one("#operation-modal-review", Static)
        interaction = self._interaction
        if isinstance(interaction, OperationModalReviewInteractionV1):
            review.update(interaction.projection.model_dump_json())
        else:
            review.update("")
        log_widget = self.query_one("#operation-modal-log", Static)
        log_widget.update("\n".join(tr(row.code) for row in self._log_view.rows))
        self.query_one("#btn-operation-cancel", Button).disabled = not view_model.cancel_control_enabled
        self.query_one("#btn-operation-detach", Button).disabled = not view_model.detach_control_enabled
        apply_enabled = isinstance(interaction, OperationModalReviewInteractionV1) and interaction.apply_enabled
        reject_enabled = isinstance(interaction, OperationModalReviewInteractionV1) and interaction.reject_enabled
        self.query_one("#btn-operation-apply", Button).disabled = not apply_enabled
        self.query_one("#btn-operation-reject", Button).disabled = not reject_enabled
        self.query_one("#btn-operation-close", Button).disabled = view_model.spinner_visible

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch one operator action through the bound controller only."""
        if event.button.id == "btn-operation-cancel":
            await self._request_cancel()
        elif event.button.id == "btn-operation-detach":
            await self._request_detach()
        elif event.button.id == "btn-operation-apply":
            await self._respond(intent="apply")
        elif event.button.id == "btn-operation-reject":
            await self._respond(intent="reject")
        elif event.button.id == "btn-operation-close":
            self.action_request_close()

    async def action_request_close(self) -> None:
        """Close the modal, detaching first if the operation is still live."""
        view_model = self._view_model
        if view_model is not None and view_model.detach_control_enabled:
            await self._request_detach()
        elif view_model is not None and not view_model.spinner_visible:
            self.dismiss(OperationModalSettledOutcomeV1(view_model=view_model))

    async def _request_cancel(self) -> None:
        view_model = self._view_model
        if view_model is None or not view_model.cancel_control_enabled:
            return
        result = await self._controller.cancel(expected_revision=view_model.projection.revision)
        if isinstance(result, OperationCancellationSuccessV1):
            return

    async def _request_detach(self) -> None:
        view_model = self._view_model
        if view_model is None:
            return
        result = await self._controller.detach(expected_revision=view_model.projection.revision)
        if isinstance(result, OperationDetachSuccessV1):
            self._closing = True
            self.dismiss(
                OperationModalDetachedOutcomeV1(operation_id=self._controller.operation_id, revision=result.revision)
            )

    async def _respond(self, *, intent: Literal["apply", "reject"]) -> None:
        interaction = self._interaction
        if not isinstance(interaction, OperationModalReviewInteractionV1):
            return
        pending = interaction.interaction
        control = interaction.control
        if intent == "apply":
            outcome = await control.apply(
                OperationResponseApplyRequestV1(
                    operation_id=self._controller.operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=self._controller.actor_ref,
                    responded_at=now(),
                )
            )
        else:
            outcome = await control.reject(
                OperationResponseRejectRequestV1(
                    operation_id=self._controller.operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=self._controller.actor_ref,
                    responded_at=now(),
                )
            )
        if not isinstance(outcome, OperationResponseMutationSuccessV1):
            return


__all__ = [
    "OperationModal",
    "OperationModalDetachedOutcomeV1",
    "OperationModalOutcomeV1",
    "OperationModalSettledOutcomeV1",
]
