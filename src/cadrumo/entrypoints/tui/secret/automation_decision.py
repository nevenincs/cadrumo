"""Human confirmation of one exact automation review through the runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Literal, cast, override
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Input, Static
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ....adapters.local_runtime.automation_decision import (
    AutomationDecisionCompletion,
    AutomationDecisionRunError,
    run_automation_decision,
)
from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.operations.models import OperationId
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.automation_enrollment import AutomationReviewProjection
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..components.theme import tokenised

type AutomationDecision = Literal["approve", "decline"]


@dataclass(frozen=True, slots=True)
class AutomationDecisionUiOutcome:
    """Safe settlement facts; no password, credential or exception is retained."""

    operation_id: OperationId | None
    terminal_condition: OperationTerminalCondition | None
    effect: OperationEffect | None
    reason: str | None
    completed: bool
    access_lost: bool


class RuntimeAutomationDecisionScreen(ModalScreen[AutomationDecisionUiOutcome | None]):
    """Keep a reviewed decision and its borrowed client alive through settlement."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = tokenised("""
    RuntimeAutomationDecisionScreen { align: center middle; }
    #automation-decision-body {
        width: $cadrumo-modal-width;
        height: $cadrumo-modal-height;
        border: $cadrumo-radius-overlay $accent;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        background: $surface;
    }
    #automation-decision-consent { height: 1fr; }
    """)

    def __init__(
        self,
        client: RuntimeFrontendClient,
        review: AutomationReviewProjection,
        *,
        decision: AutomationDecision,
        consent_text: str,
        session_expires_at: datetime | None,
        on_access_lost: Callable[[], None],
    ) -> None:
        """Pin the exact displayed review and original human session."""
        super().__init__()
        if decision not in {"approve", "decline"}:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
        if review.receipt.profile_id != client.profile_id:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        self._client = client
        self._review: AutomationReviewProjection | None = review
        self._decision: AutomationDecision = decision
        self._consent_text = consent_text
        self._on_access_lost = on_access_lost
        self._profile_id: UUID = client.profile_id
        self._session_id: UUID = client.session_id
        self._known_session_expires_at = session_expires_at
        self._lifetime_timer: Timer | None = None
        self._worker: Worker[None] | None = None
        self._decision_task: asyncio.Task[AutomationDecisionCompletion] | None = None
        self._busy = False
        self._live = True
        self._access_lost = False
        self._outcome: AutomationDecisionUiOutcome | None = None
        self._pending_proof: bytearray | None = None

    @property
    def access_lost(self) -> bool:
        """Report loss without transferring the borrowed client."""
        return self._access_lost

    @property
    def settled_outcome(self) -> AutomationDecisionUiOutcome | None:
        """Retain canonical operation facts after a cancelled presentation worker."""
        return self._outcome

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="automation-decision-body"):
            yield Static(tr("tui.automation_decision.title"))
            yield Static(tr("tui.automation_decision.consent"))
            with VerticalScroll(id="automation-decision-consent"):
                yield Static(self._consent_text, id="automation-decision-review", markup=False)
            if self._decision == "approve":
                yield Static(tr("tui.automation_decision.password"))
                yield Input(password=True, id="automation-decision-password")
            yield Static("", id="automation-decision-status", markup=False)
            yield Button(
                tr(
                    "tui.automation_decision.confirm_approve"
                    if self._decision == "approve"
                    else "tui.automation_decision.confirm_decline"
                ),
                id="automation-decision-confirm",
            )
            yield Button(tr("tui.automation_decision.cancel"), id="automation-decision-cancel")

    def on_mount(self) -> None:
        """Observe known expiry without another private inventory read."""
        self._lifetime_timer = self.set_interval(0.5, self._check_lifetime)
        self._check_lifetime()

    async def on_unmount(self) -> None:
        """Drain a submitted decision before releasing the borrowed client."""
        self._live = False
        if self._lifetime_timer is not None:
            self._lifetime_timer.stop()
            self._lifetime_timer = None
        self._consent_text = ""
        self._review = None
        if self._decision == "approve":
            for field in self.query("#automation-decision-password"):
                cast("Input", field).value = ""
        for review in self.query("#automation-decision-review"):
            cast("Static", review).update("")
        worker = self._worker
        if worker is not None:
            worker.cancel()
        task = self._decision_task
        if task is not None:
            with suppress(asyncio.CancelledError, Exception):
                await await_cancellation_complete(task, task_name="tui-automation-decision-settlement")
            if task.done():
                self._outcome = self._task_outcome(task)
        if worker is not None:
            with suppress(WorkerCancelled, WorkerError, WorkerFailed, asyncio.CancelledError):
                await await_cancellation_complete(worker.wait(), task_name="tui-automation-decision-drain")
        self._decision_task = None
        if self._pending_proof is not None:
            self._pending_proof[:] = bytes(len(self._pending_proof))
            self._pending_proof = None

    def _bound_identity(self) -> bool:
        try:
            return (
                self._client.frontend is OperationFrontendProjection.TUI
                and self._client.profile_id == self._profile_id
                and self._client.session_id == self._session_id
            )
        except Exception:
            return False

    def _check_lifetime(self) -> None:
        if not self._live or self._access_lost:
            return
        expires_at = self._known_session_expires_at
        if not self._bound_identity() or (expires_at is not None and expires_at <= datetime.now(UTC)):
            self._lose_access()

    async def _bound_status(self) -> bool:
        if not self._bound_identity():
            return False
        try:
            reply = await await_cancellation_complete(
                asyncio.to_thread(self._client.status), task_name="tui-automation-decision-status"
            )
        except Exception:
            return False
        status = reply.status
        valid = (
            self._bound_identity()
            and status.connected
            and status.credential_authenticated
            and status.profile_bound
            and status.profile_id == self._profile_id
            and status.session_id == self._session_id
            and status.session_expires_at is not None
            and status.session_expires_at > datetime.now(UTC)
            and status.denial is None
        )
        if valid:
            self._known_session_expires_at = status.session_expires_at
        return valid

    def _lose_access(self) -> None:
        if self._access_lost:
            return
        self._access_lost = True
        self._consent_text = ""
        self._review = None
        self._on_access_lost()
        if self._decision == "approve":
            for field in self.query("#automation-decision-password"):
                cast("Input", field).value = ""
        for review in self.query("#automation-decision-review"):
            cast("Static", review).update("")
        if self._live and self.is_mounted:
            for status in self.query("#automation-decision-status"):
                cast("Static", status).update(tr("tui.automation_decision.access_lost"))
            for confirm in self.query("#automation-decision-confirm"):
                cast("Button", confirm).disabled = True

    def _status(self, outcome: AutomationDecisionUiOutcome) -> None:
        if not self._live or not self.is_mounted or self._access_lost:
            return
        parts = [
            tr("tui.automation_decision.completed" if outcome.completed else "tui.automation_decision.unavailable")
        ]
        if outcome.operation_id is not None:
            parts.append(f"{tr('tui.automation_decision.operation_id')}: {outcome.operation_id}")
        if outcome.terminal_condition is not None:
            parts.append(f"{tr('tui.automation_decision.terminal_condition')}: {outcome.terminal_condition.value}")
        if outcome.effect is not None:
            parts.append(f"{tr('tui.automation_decision.effect')}: {outcome.effect.value}")
        elif outcome.operation_id is not None:
            parts.append(f"{tr('tui.automation_decision.effect')}: {tr('tui.automation_decision.unknown_effect')}")
        self.query_one("#automation-decision-status", Static).update(" · ".join(parts))

    @staticmethod
    def _task_outcome(task: asyncio.Task[AutomationDecisionCompletion]) -> AutomationDecisionUiOutcome:
        try:
            completion = task.result()
        except AutomationDecisionRunError as error:
            return AutomationDecisionUiOutcome(
                error.operation_id, error.terminal_condition, error.effect, error.reason, False, False
            )
        except BaseException:
            return AutomationDecisionUiOutcome(None, None, None, None, False, False)
        return AutomationDecisionUiOutcome(
            completion.operation_id, OperationTerminalCondition.SUCCEEDED, completion.effect, None, True, False
        )

    async def _perform(self, review: AutomationReviewProjection, proof: bytearray | None) -> None:
        self._outcome = AutomationDecisionUiOutcome(None, None, None, None, False, False)
        try:
            if not await self._bound_status():
                self._lose_access()
                return
            if self._access_lost or not self._live or not self._bound_identity():
                self._lose_access()
                return
            task = asyncio.create_task(
                asyncio.to_thread(
                    run_automation_decision, self._client, review, decision=self._decision, password=proof
                ),
                name="tui-automation-decision",
            )
            self._decision_task = task
            await await_cancellation_complete(task, task_name="tui-automation-decision")
        except Exception:
            self._outcome = AutomationDecisionUiOutcome(None, None, None, None, False, False)
        finally:
            task = self._decision_task
            if task is not None and task.done():
                self._outcome = self._task_outcome(task)
            if proof is not None:
                proof[:] = bytes(len(proof))
                self._pending_proof = None
            if self._live and not await self._bound_status():
                self._lose_access()
            self._busy = False
            self._status(self._outcome)
            if self._live and self.is_mounted and not self._access_lost:
                self.query_one("#automation-decision-cancel", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """A confirmation consumes one fresh proof and one immutable review."""
        if event.button.id == "automation-decision-cancel":
            self.action_close()
            return
        if event.button.id != "automation-decision-confirm" or self._busy or self._access_lost:
            return
        if self._outcome is not None or not self._bound_identity():
            if not self._bound_identity():
                self._lose_access()
            return
        review = self._review
        if review is None:
            self._lose_access()
            return
        proof: bytearray | None = None
        if self._decision == "approve":
            field = self.query_one("#automation-decision-password", Input)
            proof = bytearray(field.value, "utf-8")
            field.value = ""
            self._pending_proof = proof
        self._busy = True
        self.query_one("#automation-decision-confirm", Button).disabled = True
        self.query_one("#automation-decision-cancel", Button).disabled = True
        self.query_one("#automation-decision-status", Static).update(tr("tui.automation_decision.busy"))
        self._worker = self.run_worker(
            self._perform(review, proof), group="automation-decision", exclusive=True, exit_on_error=False
        )

    def action_close(self) -> None:
        """Dismiss after owned work settles; the client stays with its parent."""
        if not self._busy:
            outcome = self._outcome
            if outcome is None and self._access_lost:
                outcome = AutomationDecisionUiOutcome(None, None, None, None, False, True)
            elif outcome is not None and self._access_lost:
                outcome = AutomationDecisionUiOutcome(
                    outcome.operation_id,
                    outcome.terminal_condition,
                    outcome.effect,
                    outcome.reason,
                    outcome.completed,
                    True,
                )
            self.dismiss(outcome)


__all__ = ["AutomationDecisionUiOutcome", "RuntimeAutomationDecisionScreen"]
