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
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from datetime import timedelta
from typing import ClassVar, Literal, override

from pydantic import BaseModel
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ItemGrid, Vertical, VerticalScroll
from textual.messages import Prune
from textual.screen import ModalScreen
from textual.widgets import Button, Static
from textual.worker import Worker, WorkerCancelled, WorkerFailed

from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.components_operations import COMPONENTS_SETUP_OPERATION_ID, ProvisionReviewProjection
from ....application.dependency_contracts import DependencySetupStep, DependencyStatusRow
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import dependency_name_key
from ....application.operations.error_detail import OperationErrorDetailV1
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.frontend_requests import (
    OperationCancellationRefusalCode,
    OperationCancellationSuccessV1,
    OperationDetachRefusalCode,
    OperationDetachSuccessV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalCode,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
)
from ....application.operations.interactions import (
    OperationResponseIntent,
    OperationResponseIntentValue,
)
from ....application.operations.models import OperationId, OperationRevision
from ....core.i18n.render import tr
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import OperationLifecycle
from ....core.operator_notice_messages import operation_notice_message
from ....core.time.clock import now
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import tokenised
from ..setup.focus import SetupItemRequested
from ..setup.offer import current_setup_row, offers_setup, setup_held_text, setup_offer_label
from ..setup.review import setup_review_text
from .controller_port import (
    OperationChangeSourcePort,
    OperationChangeWaiterPort,
    OperationControllerPort,
    OperationErrorDetailPort,
    OperationReviewClaimPort,
)
from .interactions import (
    OperationModalInteractionStateV1,
    OperationModalReviewInteractionV1,
    OperationModalUnsupportedInteractionV1,
    resolve_modal_interaction_state,
    unanswerable_interaction_text,
)
from .logs import OperationModalLogRowV1, OperationModalLogViewV1, build_initial_log_view, fold_event_page
from .projection import OperationModalViewModelV1, build_operation_modal_view_model
from .refusal_explanation import operation_error_explanation, public_refusal_explanation, recorded_setup_item

# A refused observation is not watched, so no cue follows it: retry with backoff.
_REFUSED_RETRY_FIRST = timedelta(milliseconds=200)
_REFUSED_RETRY_MAX = timedelta(seconds=5)


class _NoOperationCues:
    """The waiter for a controller whose runtime sends no operation cue.

    It never wakes, so the modal holds what it last observed until the person
    acts or closes it. Nothing re-reads on a timer: the runtime's cue is the
    only signal that an operation advanced.
    """

    armed = True

    def arm(self) -> None:
        """Nothing to subscribe to."""

    async def wait(self, timeout: float) -> None:
        """Wait until the observer is cancelled; no cue will ever arrive."""
        del timeout
        await asyncio.Event().wait()

    def close(self) -> None:
        """Nothing to release."""


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
    """Generic modal presenting one supervised operation until it settles.

    A settled operation closes the modal at once, unless its recorded verdict
    asks for one setup item and that item's current row can be read: then the
    modal stays and says why. When the row's action sets the item up, it offers
    to open the setup page on that item; opening it only asks the root to
    navigate, and the setup page asks before setting anything up. When the row
    reads blocked, it shows the row's own sentence and offers nothing.
    """

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

    def __init__(
        self,
        controller: OperationControllerPort,
        *,
        review_text: Callable[[BaseModel], str] | None = None,
        response_only: bool = False,
    ) -> None:
        """Bind the modal to exactly one already-submitted operation.

        ``review_text`` words a REVIEW projection for a person, for a caller
        that knows its operation's projection type; without it the modal shows
        the projection's own document.
        """
        super().__init__()
        self._controller = controller
        self._response_only = response_only
        self._review_text = review_text
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
        # A settled refusal that needs a setup item, held open so the person can go and set it up.
        self._held_outcome: OperationModalSettledOutcomeV1 | None = None
        self._setup_detail: OperationErrorDetailV1 | None = None
        self._setup_row: DependencyStatusRow | None = None

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
                yield Static("", id="operation-modal-progress")
                yield Static("", id="operation-modal-deadlines")
                yield Static("", id="operation-modal-diagnostic")
                yield Static("", id="operation-modal-action-refusal")
                yield Static("", id="operation-modal-receipt")
                yield Static("", id="operation-modal-setup")
                yield Static("", id="operation-modal-review")
                yield Static("", id="operation-modal-log")
            with ItemGrid(id="operation-modal-actions", min_column_width=_ACTION_MIN_COLUMN_WIDTH):
                setup = Button("", id="btn-operation-setup", classes="-primary")
                setup.display = False
                yield setup
                claim = localized(
                    Button(tr("operation.modal.action.claim"), id="btn-operation-claim"), "operation.modal.action.claim"
                )
                claim.display = False
                yield claim
                yield localized(
                    Button(tr("operation.modal.action.reject"), id="btn-operation-reject", disabled=True),
                    "operation.modal.action.reject",
                )
                yield localized(
                    Button(
                        tr("operation.modal.action.apply"), id="btn-operation-apply", classes="-primary", disabled=True
                    ),
                    "operation.modal.action.apply",
                )
                yield localized(
                    Button(tr("operation.modal.action.cancel"), id="btn-operation-cancel"),
                    "operation.modal.action.cancel",
                )
                yield localized(
                    Button(tr("operation.modal.action.detach"), id="btn-operation-detach"),
                    "operation.modal.action.detach",
                )
                yield localized(
                    Button(tr("operation.modal.action.close"), id="btn-operation-close"), "operation.modal.action.close"
                )

    def on_mount(self) -> None:
        """Start observing, on each runtime cue, as an exclusive worker."""
        if self._response_only:
            self.query_one("#btn-operation-cancel", Button).display = False
            self.query_one("#btn-operation-detach", Button).display = False
        self._poll_worker = self.run_worker(self._poll_loop(), name="operation-modal-poll", exclusive=True)

    async def refresh_language(self) -> None:
        """Reword the held observation without restarting or answering the operation."""
        refresh_localized_widgets(self)
        self._refresh_view_state()
        self._render_action_refusal()

    async def _poll_loop(self) -> None:
        try:
            await self._observe_until_stopped()
        except (FrontendRefusedError, RefusalError) as error:
            self._runtime_access_lost(error)

    async def _observe_until_stopped(self) -> None:
        controller = self._controller
        changes: OperationChangeWaiterPort = (
            controller.operation_changes() if isinstance(controller, OperationChangeSourcePort) else _NoOperationCues()
        )
        try:
            await self._observe_with(changes)
        finally:
            changes.close()

    async def _observe_with(self, changes: OperationChangeWaiterPort) -> None:
        cursor = self._log_view.next_cursor
        refused_retry = _REFUSED_RETRY_FIRST
        while self._observing():
            if changes.armed:
                changes.arm()
            observed = await self._controller.observe(cursor)
            if not self._observing():
                return
            if not isinstance(observed, OperationObservationSuccessV1):
                self._clear_private_view(
                    tr("operation.modal.claim.unavailable") if self._response_only else observed.code.value
                )
                cursor = 0
                await asyncio.sleep(refused_retry.total_seconds())
                refused_retry = min(refused_retry * 2, _REFUSED_RETRY_MAX)
                continue
            refused_retry = _REFUSED_RETRY_FIRST
            self._log_view = fold_event_page(self._log_view, observed.event_page)
            restart_cursor = self._log_view.restart_cursor
            if self._log_view.resynchronized and restart_cursor is not None:
                cursor = restart_cursor
            else:
                cursor = self._log_view.next_cursor
            if self._view_model is None:
                self._clear_action_refusal()
            if self._response_only and observed.projection.definition_id != COMPONENTS_SETUP_OPERATION_ID:
                self._observation_stopped = True
                self._clear_private_view(tr("operation.modal.claim.unavailable"))
                return
            self._view_model = build_operation_modal_view_model(observed.projection)
            self._interaction = await resolve_modal_interaction_state(
                self._controller,
                observed.projection,
                ProvisionReviewProjection
                if observed.projection.definition_id == COMPONENTS_SETUP_OPERATION_ID
                else BaseModel,
                current=self._interaction,
            )
            if not self._observing():
                self._clear_private_view(self._action_refusal or "")
                return
            self._refresh_view_state()
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                detail = await self._settled_error_detail(observed.projection)
                outcome = OperationModalSettledOutcomeV1(
                    view_model=self._view_model, error_explanation=operation_error_explanation(detail)
                )
                setup_item = recorded_setup_item(detail)
                row = None if setup_item is None else await current_setup_row(self.app, setup_item)
                if not self._observing():
                    return
                if row is None:
                    self.dismiss(outcome)
                else:
                    self._hold_for_setup(outcome, detail, row)
                return
            if not changes.armed:
                # Subscribed only now; observe once more so nothing between the two reads is missed.
                changes.arm()
            else:
                await changes.wait(float("inf"))

    def _observing(self) -> bool:
        """Read the current state, which another action may change across an await."""
        return not self._observation_stopped

    async def _settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        """Read the stopped executor's recorded detail when the bound controller can supply it."""
        controller = self._controller
        if not isinstance(controller, OperationErrorDetailPort):
            return None
        return await controller.settled_error_detail(projection)

    def _hold_for_setup(
        self, outcome: OperationModalSettledOutcomeV1, detail: OperationErrorDetailV1 | None, row: DependencyStatusRow
    ) -> None:
        """Keep the settled modal open on the needed item: its setup offer, or why it cannot be set up."""
        self._observation_stopped = True
        self._held_outcome = outcome
        self._setup_detail = detail
        self._setup_row = row
        self._render_setup_offer()
        target = "#btn-operation-setup" if offers_setup(row) else "#btn-operation-close"
        self.query_one(target, Button).focus()

    def _render_setup_offer(self) -> None:
        """Say why the operation stopped, then the item's offer or its row's sentence, in the current language."""
        row = self._setup_row
        button = self.query_one("#btn-operation-setup", Button)
        reason = self.query_one("#operation-modal-setup", Static)
        if row is None:
            button.display = False
            reason.update("")
            return
        explanation = operation_error_explanation(self._setup_detail)
        view_model = self._view_model
        shown = None if view_model is None else public_refusal_explanation(view_model.receipt_ref)
        lines = [] if explanation is None or explanation == shown else [explanation]
        if offers_setup(row):
            button.label = setup_offer_label(row)
            button.display = True
        else:
            button.display = False
            lines.append(setup_held_text(row))
        reason.update("\n".join(lines))

    def _runtime_access_lost(self, error: FrontendRefusedError | RefusalError) -> None:
        self._observation_stopped = True
        code = error.reason if isinstance(error, FrontendRefusedError) else error.reason.value
        setup_review = self._response_only or (
            self._view_model is not None and self._view_model.projection.definition_id == COMPONENTS_SETUP_OPERATION_ID
        )
        self._clear_private_view(code)
        if setup_review:
            match code:
                case "review_already_claimed":
                    self._action_refusal = tr("operation.modal.claim.already_claimed")
                case "review_claim_stale":
                    self._action_refusal = tr("operation.modal.claim.stale")
                case "response_authority_required":
                    self._action_refusal = tr("operation.modal.claim.authority_lost")
                case _:
                    self._action_refusal = tr("operation.modal.claim.unavailable")
            self._render_action_refusal()

    def _clear_private_view(self, code: str) -> None:
        """Discard private presentation when it can no longer be authorized."""
        self._view_model = None
        self._interaction = None
        self._log_view = build_initial_log_view(self._controller.operation_id)
        self._action_refusal = code
        for suffix in ("phase", "progress", "deadlines", "diagnostic", "receipt", "review", "log"):
            self.query_one(f"#operation-modal-{suffix}", Static).update("")
        self.query_one("#operation-modal-status", Static).update(tr("operation.modal.status.access_unavailable"))
        self._render_action_refusal()
        for action in ("cancel", "detach", "claim", "apply", "reject"):
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

    @on(Prune)
    def _stop_observing_on_removal(self) -> None:
        """Cancel the poll worker as soon as removal begins, before any row is removed.

        A screen can be removed without its own close controls: the app pops
        every screen above the base for an account action, and a shutdown
        closes the screens. Textual removes this screen's rows first and
        cancels its workers only afterwards, at unmount, so a read completing
        between the two resumed the worker against rows that no longer existed
        and its failure ended the app. The ``Prune`` request is handled by this
        screen before it removes any row, and a cancelled worker runs no more
        of its own code. Nothing is reported: removal is not a dismissal and
        says nothing about the operation's outcome.
        """
        self._observation_stopped = True
        worker = self._poll_worker
        self._poll_worker = None
        if worker is not None:
            worker.cancel()

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
            projection = interaction.projection
            if isinstance(projection, ProvisionReviewProjection):
                review.update(setup_review_text(projection.plan))
            else:
                review.update(
                    projection.model_dump_json() if self._review_text is None else self._review_text(projection)
                )
        elif isinstance(interaction, OperationModalUnsupportedInteractionV1):
            review.update(unanswerable_interaction_text(interaction.interaction))
        else:
            review.update("")
        log_widget = self.query_one("#operation-modal-log", Static)
        log_widget.update("\n".join(_log_row_text(row) for row in self._log_view.rows))
        self.query_one("#btn-operation-cancel", Button).display = not self._response_only
        self.query_one("#btn-operation-detach", Button).display = not self._response_only
        self.query_one("#btn-operation-cancel", Button).disabled = (
            self._response_only or not view_model.cancel_control_enabled
        )
        self.query_one("#btn-operation-detach", Button).disabled = (
            self._response_only or not view_model.detach_control_enabled
        )
        apply_enabled = isinstance(interaction, OperationModalReviewInteractionV1) and interaction.apply_enabled
        reject_enabled = isinstance(interaction, OperationModalReviewInteractionV1) and interaction.reject_enabled
        claim = self.query_one("#btn-operation-claim", Button)
        claim.display = (
            isinstance(interaction, OperationModalReviewInteractionV1)
            and interaction.reviewed_document_digest is not None
        )
        claim.disabled = (
            not isinstance(interaction, OperationModalReviewInteractionV1) or interaction.control is not None
        )
        self.query_one("#btn-operation-apply", Button).disabled = not apply_enabled
        self.query_one("#btn-operation-reject", Button).disabled = not reject_enabled
        self.query_one("#btn-operation-close", Button).disabled = view_model.spinner_visible and not self._response_only
        self._render_setup_offer()

    def _refresh_detail_rows(self, view_model: OperationModalViewModelV1) -> None:
        """Draw the phase, deadline, diagnostic and receipt facts.

        Each row is written from the derived view model alone, and each is
        blanked when its fact is absent rather than left holding the last
        value it had: a stale deadline or a receipt belonging to a previous
        revision is worse than no row at all.
        """
        phase = view_model.phase_code
        self.query_one("#operation-modal-phase", Static).update(
            f"{tr('operation.modal.detail.phase')}: {_phase_text(phase)}" if phase is not None else ""
        )
        progress = view_model.projection.progress
        self.query_one("#operation-modal-progress", Static).update(
            ""
            if progress is None
            else _progress_text(progress.completed, progress.total, progress.unit_code, progress.subject_code)
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
        elif event.button.id == "btn-operation-claim":
            await self._claim_review()
        elif event.button.id == "btn-operation-apply":
            await self._respond(intent=OperationResponseIntent.APPLY)
        elif event.button.id == "btn-operation-reject":
            await self._respond(intent=OperationResponseIntent.REJECT)
        elif event.button.id == "btn-operation-close":
            await self.action_request_close()
        elif event.button.id == "btn-operation-setup":
            await self._open_setup()

    async def _open_setup(self) -> None:
        """Close with the settled outcome, then ask the root to open the setup page on the needed item."""
        outcome, row = self._held_outcome, self._setup_row
        if outcome is None or row is None or not offers_setup(row):
            return
        await self._stop_poll_worker()
        self.dismiss(outcome)
        self.app.post_message(SetupItemRequested(row.item_id))

    async def action_request_close(self) -> None:
        """Close the modal, detaching first if the operation is still live."""
        if self._response_only:
            await self._stop_poll_worker()
            self.dismiss(None)
            return
        if self._held_outcome is not None:
            await self._stop_poll_worker()
            self.dismiss(self._held_outcome)
            return
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
        if self._response_only or view_model is None or not view_model.cancel_control_enabled:
            return
        try:
            result = await self._controller.cancel(expected_revision=view_model.projection.revision)
        except (FrontendRefusedError, RefusalError) as error:
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
        if self._response_only or view_model is None:
            return
        try:
            result = await self._controller.detach(expected_revision=view_model.projection.revision)
        except (FrontendRefusedError, RefusalError) as error:
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

    async def _claim_review(self) -> None:
        """Claim the displayed document before inspecting any response authority."""
        interaction = self._interaction
        controller = self._controller
        if (
            not isinstance(interaction, OperationModalReviewInteractionV1)
            or interaction.control is not None
            or interaction.reviewed_document_digest is None
            or not isinstance(controller, OperationReviewClaimPort)
        ):
            return
        self.query_one("#btn-operation-claim", Button).disabled = True
        try:
            claimed = await controller.claim_review(
                interaction.interaction.review_reference,
                interaction.reviewed_document_digest,
            )
            if not self._observing():
                return
            reference = claimed.reference
            pending = interaction.interaction.model_copy(
                update={"revision": reference.revision, "review_reference": reference}
            )
            control = await self._controller.response_control(
                interaction_id=reference.interaction_id, revision=reference.revision
            )
            availability = await control.inspect()
            if not self._observing():
                return
            permitted = (
                availability.permitted_intents
                if isinstance(availability, OperationResponseControlSuccessV1)
                else frozenset()
            )
            # Retain only the binding acknowledged by the runtime, never an observed one.
            self._interaction = replace(
                interaction,
                interaction=pending,
                control=control,
                apply_enabled="apply" in permitted,
                reject_enabled="reject" in permitted,
            )
            self._clear_action_refusal()
            self._refresh_view_state()
        except (FrontendRefusedError, RefusalError) as error:
            self._runtime_access_lost(error)

    async def _respond(self, *, intent: OperationResponseIntentValue) -> None:
        try:
            await self._send_response(intent=intent)
        except (FrontendRefusedError, RefusalError) as error:
            self._runtime_access_lost(error)

    async def _send_response(self, *, intent: OperationResponseIntentValue) -> None:
        interaction = self._interaction
        if not isinstance(interaction, OperationModalReviewInteractionV1):
            return
        pending = interaction.interaction
        control = interaction.control
        if control is None:
            return
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
    if row.completed is not None and row.total is not None:
        return _progress_text(row.completed, row.total, row.unit_code, row.subject_code)
    if row.phase_code is not None:
        return _phase_text(row.phase_code)
    if row.notice_code is not None:
        prompt = operation_notice_message(row.notice_code, row.display_code)
        if prompt is not None:
            return prompt
    code = row.notice_code or row.code
    return f"{tr(code)}: {row.display_code}" if row.display_code is not None else tr(code)


__all__ = [
    "OperationModal",
    "OperationModalDetachedOutcomeV1",
    "OperationModalOutcomeV1",
    "OperationModalSettledOutcomeV1",
]


def _progress_text(completed: int, total: int, unit_code: str | None, subject_code: str | None) -> str:
    """Word the runtime's measured progress with its subject and unit."""
    declaration = next((item for item in dependency_item_declarations() if item.item_id == subject_code), None)
    name = (
        tr(subject_code)
        if declaration is None and subject_code is not None
        else ("" if declaration is None else tr(dependency_name_key(declaration)))
    )
    if unit_code == "bytes" and declaration is not None:
        return tr(
            "tui.setup.progress_bytes",
            name=name,
            done=f"{completed:,} B",
            total=f"{total:,} B",
            percent=completed * 100 // total,
        )
    subject = "" if not name else f"{name}: "
    unit = "" if unit_code is None else f" {tr(unit_code)}"
    return f"{subject}{completed:,} / {total:,}{unit} ({completed * 100 // total}%)"


def _phase_text(code: str) -> str:
    """Word setup phase coordinates using the component and step declarations."""
    if code == COMPONENTS_SETUP_OPERATION_ID:
        return tr("tui.setup.working")
    if code in {"config.provision.status", "config.provision.verify"}:
        return tr("tui.setup.checking")
    parts = code.split(".")
    if len(parts) == 4 and parts[:2] == ["dependencies", "setup"]:
        declaration = next((item for item in dependency_item_declarations() if item.item_id == parts[2]), None)
        steps = {
            DependencySetupStep.PLAN.value: "tui.setup.step.plan",
            DependencySetupStep.PREFLIGHT.value: "tui.setup.step.preflight",
            DependencySetupStep.DOWNLOAD.value: "tui.setup.step.download",
            DependencySetupStep.INSTALL.value: "tui.setup.step.install",
            DependencySetupStep.VERIFY.value: "tui.setup.step.verify",
            DependencySetupStep.CLEANUP.value: "tui.setup.step.cleanup",
        }
        step = steps.get(parts[3])
        if declaration is not None and step is not None:
            return tr("tui.setup.progress", name=tr(dependency_name_key(declaration)), step=tr(step))
    return tr(code)
