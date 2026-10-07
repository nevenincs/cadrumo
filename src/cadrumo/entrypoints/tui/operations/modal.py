"""The generic detachable operation modal, built solely from public DTOs.

This modal drives exactly one submitted operation through
:class:`~cadrumo.entrypoints.tui.operations.controller_port.OperationControllerPort`
and renders exactly the public projection,
event-page, REVIEW, response-control, cancellation, detach and typed
Workspace-refresh DTOs those public services return. It never imports a
persisted snapshot, a journal record, or a supervisor-private type, and it
never reclassifies lifecycle truth beyond what
:func:`build_operation_modal_view_model` already derived.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from typing import ClassVar, Literal, override

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ItemGrid, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static
from textual.worker import Worker, WorkerCancelled, WorkerFailed

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.frontend_requests import (
    OperationCancellationRefusalCode,
    OperationCancellationSuccessV1,
    OperationDetachRefusalCode,
    OperationDetachSuccessV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalCode,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from ....application.operations.interactions import (
    OperationResponseIntent,
    OperationResponseIntentValue,
)
from ....application.operations.models import OperationId, OperationRevision
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.i18n.render import tr
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import OperationLifecycle
from ....core.time.clock import now
from ...operation_notice_messages import operation_notice_message
from ..components.theme import tokenised
from .controller_port import OperationControllerPort, OperationErrorDetailPort
from .interactions import (
    OperationModalInteractionStateV1,
    OperationModalReviewInteractionV1,
    resolve_modal_interaction_state,
)
from .logs import OperationModalLogRowV1, OperationModalLogViewV1, build_initial_log_view, fold_event_page
from .projection import OperationModalViewModelV1, build_operation_modal_view_model
from .refusal_explanation import operation_error_explanation, public_refusal_explanation

_POLL_INTERVAL = timedelta(milliseconds=200)


class OperationModalSettledOutcomeV1(BaseModel):
    """The modal closed because its bound operation reached settlement."""

    model_config = STRICT_FROZEN_CONFIG
    disposition: Literal["settled"] = "settled"
    view_model: OperationModalViewModelV1
    #: The stopped executor's own localized message, when it recorded one.
    error_explanation: str | None = None


class OperationModalDetachedOutcomeV1(BaseModel):
    """The modal closed because the operator detached from a live operation."""

    model_config = STRICT_FROZEN_CONFIG
    disposition: Literal["detached"] = "detached"
    operation_id: OperationId
    revision: OperationRevision


type OperationModalOutcomeV1 = OperationModalSettledOutcomeV1 | OperationModalDetachedOutcomeV1


_ACTION_MIN_COLUMN_WIDTH = 16
"""Narrowest column the modal action row will lay a button into.

Equal to Textual's own ``Button`` minimum width, so a column never asks a
button to render below the size it will claim anyway. That minimum is what
makes the single row impossible rather than merely tight: five buttons hold
at least eighty columns between them in EVERY catalogue, before gutters,
against a modal body sixty-four columns wide on the eighty-column floor.
Label length is therefore not the binding constraint and no language is a
special case. Wrapping at this width keeps every action inside the body, and
the grid collapses back to a single row wherever the body is wide enough.
"""


class OperationModal(ModalScreen[OperationModalOutcomeV1 | None]):
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
        height: $cadrumo-modal-height;
    }
    #operation-modal-content { height: 1fr; }
    #operation-modal-status { text-style: bold; margin: $cadrumo-space-0; }
    #operation-modal-review { color: $text; margin: $cadrumo-space-0; }
    #operation-modal-log { color: $text-muted; height: auto; max-height: $cadrumo-log-max-height; overflow-y: auto; }
    #operation-modal-actions {
        height: auto;
        grid-gutter: $cadrumo-space-0 $cadrumo-control-gap;
        margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0;
    }
    #operation-modal-actions Button { width: 1fr; margin: $cadrumo-space-0; }
    """)
    BINDINGS: ClassVar = [Binding("escape", "request_close", "", show=False)]

    def __init__(self, controller: OperationControllerPort) -> None:
        """Bind the modal to exactly one already-submitted operation."""
        super().__init__()
        self._controller = controller
        self._view_model: OperationModalViewModelV1 | None = None
        # The last operator action this modal refused, held on the screen rather
        # than written straight to the widget because the poll worker re-renders
        # on every observation and would erase it within the tick. It is cleared
        # by the next action that succeeds.
        self._action_refusal: str | None = None
        self._log_view: OperationModalLogViewV1 = build_initial_log_view(controller.operation_id)
        # The modal renders whatever REVIEW projection an operation publishes,
        # so its interaction state is parameterised by the projection base.
        self._interaction: OperationModalInteractionStateV1[BaseModel] | None = None
        # NOT `_closing`: that name is Textual's own on ``MessagePump``, and
        # setting it here made the framework's `_close_messages` return early
        # without posting its stop sentinel, so the screen could never be
        # removed and app shutdown waited on it forever.
        self._observation_stopped = False
        self._poll_worker: Worker[None] | None = None

    @override
    def compose(self) -> ComposeResult:
        # The body keeps one fixed size and the rows scroll inside it, so the
        # actions never move: a sized-to-content body re-centred on every poll
        # that filled a row, and an operator clicking a control as it became
        # enabled was aiming at where it had just been.
        with Vertical(id="operation-modal-body"):
            with VerticalScroll(id="operation-modal-content"):
                yield Static("", id="operation-modal-status")
                yield Static("", id="operation-modal-phase")
                yield Static("", id="operation-modal-deadlines")
                yield Static("", id="operation-modal-diagnostic")
                yield Static("", id="operation-modal-action-refusal")
                yield Static("", id="operation-modal-receipt")
                yield Static("", id="operation-modal-review")
                yield Static("", id="operation-modal-log")
            with ItemGrid(id="operation-modal-actions", min_column_width=_ACTION_MIN_COLUMN_WIDTH):
                yield Button(tr("operation.modal.action.reject"), id="btn-operation-reject", disabled=True)
                yield Button(
                    tr("operation.modal.action.apply"), id="btn-operation-apply", classes="-primary", disabled=True
                )
                yield Button(tr("operation.modal.action.cancel"), id="btn-operation-cancel")
                yield Button(tr("operation.modal.action.detach"), id="btn-operation-detach")
                yield Button(tr("operation.modal.action.close"), id="btn-operation-close")

    def on_mount(self) -> None:
        """Start the bounded observation poll loop as an exclusive worker."""
        self._poll_worker = self.run_worker(self._poll_loop(), name="operation-modal-poll", exclusive=True)

    async def _poll_loop(self) -> None:
        try:
            await self._observe_until_stopped()
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            self._runtime_access_lost(error)

    async def _observe_until_stopped(self) -> None:
        cursor = self._log_view.next_cursor
        while self._observing():
            observed = await self._controller.observe(cursor)
            if not self._observing():
                return
            if not isinstance(observed, OperationObservationSuccessV1):
                self._clear_private_view(observed.code.value)
                cursor = 0
                await asyncio.sleep(_POLL_INTERVAL.total_seconds())
                continue
            self._log_view = fold_event_page(self._log_view, observed.event_page)
            restart_cursor = self._log_view.restart_cursor
            if self._log_view.resynchronized and restart_cursor is not None:
                cursor = restart_cursor
            else:
                cursor = self._log_view.next_cursor
            if self._view_model is None:
                self._clear_action_refusal()
            self._view_model = build_operation_modal_view_model(observed.projection)
            self._interaction = await resolve_modal_interaction_state(
                self._controller, observed.projection, BaseModel, current=self._interaction
            )
            if not self._observing():
                self._clear_private_view(self._action_refusal or "")
                return
            self._refresh_view_state()
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                explanation = await self._settled_error_explanation(observed.projection)
                self.dismiss(OperationModalSettledOutcomeV1(view_model=self._view_model, error_explanation=explanation))
                return
            await asyncio.sleep(_POLL_INTERVAL.total_seconds())

    def _observing(self) -> bool:
        """Read the current state, which another action may change across an await."""
        return not self._observation_stopped

    async def _settled_error_explanation(self, projection: OperationPublicProjectionV1) -> str | None:
        """Read the stopped executor's own message when the bound controller can supply its detail."""
        controller = self._controller
        if not isinstance(controller, OperationErrorDetailPort):
            return None
        return operation_error_explanation(await controller.settled_error_detail(projection))

    def _runtime_access_lost(self, error: RuntimeFrontendRefusedError | RuntimeRefusalError) -> None:
        self._observation_stopped = True
        code = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
        self._clear_private_view(code)

    def _clear_private_view(self, code: str) -> None:
        """Discard private presentation when it can no longer be authorized."""
        self._view_model = None
        self._interaction = None
        self._log_view = build_initial_log_view(self._controller.operation_id)
        self._action_refusal = code
        for suffix in ("phase", "deadlines", "diagnostic", "receipt", "review", "log"):
            self.query_one(f"#operation-modal-{suffix}", Static).update("")
        self.query_one("#operation-modal-status", Static).update(tr("operation.modal.status.access_unavailable"))
        self._render_action_refusal()
        for action in ("cancel", "detach", "apply", "reject"):
            self.query_one(f"#btn-operation-{action}", Button).disabled = True
        self.query_one("#btn-operation-close", Button).disabled = False

    async def _stop_poll_worker(self) -> None:
        """End the poll worker and wait for it, so teardown never races a live poll."""
        self._observation_stopped = True
        worker = self._poll_worker
        if worker is None:
            return
        self._poll_worker = None
        worker.cancel()
        with suppress(WorkerCancelled, WorkerFailed):
            await worker.wait()

    def _refresh_view_state(self) -> None:
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
        self._refresh_detail_rows(view_model)
        review = self.query_one("#operation-modal-review", Static)
        interaction = self._interaction
        if isinstance(interaction, OperationModalReviewInteractionV1):
            review.update(interaction.projection.model_dump_json())
        else:
            review.update("")
        log_widget = self.query_one("#operation-modal-log", Static)
        log_widget.update("\n".join(_log_row_text(row) for row in self._log_view.rows))
        self.query_one("#btn-operation-cancel", Button).disabled = not view_model.cancel_control_enabled
        self.query_one("#btn-operation-detach", Button).disabled = not view_model.detach_control_enabled
        apply_enabled = isinstance(interaction, OperationModalReviewInteractionV1) and interaction.apply_enabled
        reject_enabled = isinstance(interaction, OperationModalReviewInteractionV1) and interaction.reject_enabled
        self.query_one("#btn-operation-apply", Button).disabled = not apply_enabled
        self.query_one("#btn-operation-reject", Button).disabled = not reject_enabled
        self.query_one("#btn-operation-close", Button).disabled = view_model.spinner_visible

    def _refresh_detail_rows(self, view_model: OperationModalViewModelV1) -> None:
        """Draw the phase, deadline, diagnostic and receipt facts.

        Each row is written from the derived view model alone, and each is
        blanked when its fact is absent rather than left holding the last
        value it had: a stale deadline or a receipt belonging to a previous
        revision is worse than no row at all.
        """
        phase = view_model.phase_code
        self.query_one("#operation-modal-phase", Static).update(
            f"{tr('operation.modal.detail.phase')}: {tr(phase)}" if phase is not None else ""
        )
        # Every locale key below is spelled as a literal argument to `tr`.
        # The catalogue tooling reads those literals to know a key is live,
        # so a key assembled from a variable is invisible to it and drifts
        # out of the catalogues on the next scaffold.
        deadlines: list[str] = []
        if view_model.execution_deadline_at is not None:
            deadlines.append(
                f"{tr('operation.modal.detail.execution_deadline')}: {view_model.execution_deadline_at.isoformat()}"
            )
        if view_model.cleanup_deadline_at is not None:
            deadlines.append(
                f"{tr('operation.modal.detail.cleanup_deadline')}: {view_model.cleanup_deadline_at.isoformat()}"
            )
        self.query_one("#operation-modal-deadlines", Static).update("  ".join(deadlines))
        diagnostic = view_model.diagnostic_ref
        self.query_one("#operation-modal-diagnostic", Static).update(
            f"{tr('operation.modal.detail.diagnostic')}: {diagnostic}" if diagnostic is not None else ""
        )
        # Repainted with every observation so the poll worker cannot wipe a
        # refusal the operator has not acted on yet.
        self._render_action_refusal()
        receipt = self.query_one("#operation-modal-receipt", Static)
        if view_model.receipt_kind == "result":
            receipt.update(f"{tr('operation.modal.detail.receipt_result')}: {view_model.receipt_ref}")
        elif view_model.receipt_kind == "refusal":
            refusal = f"{tr('operation.modal.detail.receipt_refusal')}: {view_model.receipt_ref}"
            explanation = public_refusal_explanation(view_model.receipt_ref)
            receipt.update(refusal if explanation is None else f"{refusal}\n{explanation}")
        else:
            receipt.update("")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch one operator action through the bound controller only."""
        if event.button.id == "btn-operation-cancel":
            await self._request_cancel()
        elif event.button.id == "btn-operation-detach":
            await self._request_detach()
        elif event.button.id == "btn-operation-apply":
            await self._respond(intent=OperationResponseIntent.APPLY)
        elif event.button.id == "btn-operation-reject":
            await self._respond(intent=OperationResponseIntent.REJECT)
        elif event.button.id == "btn-operation-close":
            await self.action_request_close()

    async def action_request_close(self) -> None:
        """Close the modal, detaching first if the operation is still live."""
        view_model = self._view_model
        if view_model is None:
            # No observation has ever succeeded, so there is no revision to
            # detach against and no outcome to report. Leaving is still the
            # operator's right: Escape is bound here and the Close button keeps
            # its compose-time enabled state until a render disables it, so
            # returning early made BOTH inert and the modal impossible to
            # leave whenever observation refused from the first poll onward.
            # ``None`` is the screen's own declared result type and the
            # sign-out caller already reads it as "backed out", not as failure.
            await self._stop_poll_worker()
            self.dismiss(None)
            return
        if view_model.detach_control_enabled:
            await self._request_detach()
        elif not view_model.spinner_visible:
            # Reap before dismissing for the same reason the detach path does:
            # dismissing alone pops the screen while the worker may still be
            # parked in its sleep or inside the observation read.
            await self._stop_poll_worker()
            self.dismiss(OperationModalSettledOutcomeV1(view_model=view_model))

    async def _request_cancel(self) -> None:
        view_model = self._view_model
        if view_model is None or not view_model.cancel_control_enabled:
            return
        try:
            result = await self._controller.cancel(expected_revision=view_model.projection.revision)
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            self._runtime_access_lost(error)
            return
        if isinstance(result, OperationCancellationSuccessV1):
            self._clear_action_refusal()
            return
        # A refused cancel used to fall off the end of this method. The button
        # stayed enabled and nothing changed on screen, so the only feedback the
        # operator got was that pressing Cancel did nothing -- which reads as an
        # unresponsive control rather than a decision, and the natural response
        # is to press it again.
        self._show_action_refusal(result.code)

    async def _request_detach(self) -> None:
        view_model = self._view_model
        if view_model is None:
            return
        try:
            result = await self._controller.detach(expected_revision=view_model.projection.revision)
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            self._runtime_access_lost(error)
            return
        if isinstance(result, OperationDetachSuccessV1):
            # Flagging alone let the screen pop while the worker was still parked
            # in its sleep or inside the observation read, so teardown raced a live
            # poller. Stop it and wait for it to actually end before dismissing.
            await self._stop_poll_worker()
            self.dismiss(
                OperationModalDetachedOutcomeV1(operation_id=self._controller.operation_id, revision=result.revision)
            )
        else:
            self._show_action_refusal(result.code)

    async def _respond(self, *, intent: OperationResponseIntentValue) -> None:
        try:
            await self._send_response(intent=intent)
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            self._runtime_access_lost(error)

    async def _send_response(self, *, intent: OperationResponseIntentValue) -> None:
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
            # Same silent discard as the cancel path, and worse here: apply and
            # reject are how the operator answers a question the operation is
            # blocked on, so a discarded refusal leaves them pressing a button
            # against a modal that will not move.
            self._show_action_refusal(outcome.code)
            return
        self._clear_action_refusal()

    def _show_action_refusal(
        self,
        code: OperationCancellationRefusalCode | OperationResponseControlRefusalCode | OperationDetachRefusalCode,
    ) -> None:
        """Say why the operator's action was refused, in their own language.

        The copy key is derived from the refusal code's own value rather than
        read out of a hand-written table, so a code added to either enum cannot
        be silently unnamed here -- it is the enum that decides which keys must
        exist, and a completeness gate holds the catalogues to it.
        """
        self._action_refusal = tr(f"operation.modal.refusal.{code.value}")
        self._render_action_refusal()

    def _clear_action_refusal(self) -> None:
        """Drop a stale refusal once an action succeeds."""
        self._action_refusal = None
        self._render_action_refusal()

    def _render_action_refusal(self) -> None:
        """Paint the retained refusal, if the modal is still composed."""
        refusal = self._action_refusal
        self.query_one("#operation-modal-action-refusal", Static).update(
            "" if refusal is None else f"{tr('operation.modal.detail.action_refused')}: {refusal}"
        )


def _log_row_text(row: OperationModalLogRowV1) -> str:
    """Render one log row, as the operator's own prompt when its notice asks them to act."""
    if row.notice_code is not None:
        prompt = operation_notice_message(row.notice_code, row.display_code)
        if prompt is not None:
            return prompt
    return f"{tr(row.code)}: {row.display_code}" if row.display_code is not None else tr(row.code)


__all__ = [
    "OperationModal",
    "OperationModalDetachedOutcomeV1",
    "OperationModalOutcomeV1",
    "OperationModalSettledOutcomeV1",
]
