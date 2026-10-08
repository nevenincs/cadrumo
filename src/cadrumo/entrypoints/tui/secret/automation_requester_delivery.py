"""Native requester delivery, uncertainty capture and cleanup ownership."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from textual.widgets import Button, Static

from ....adapters.local_runtime.automation_requester import (
    AutomationRequesterCompletion,
    AutomationRequesterJourney,
    AutomationRequesterUncertainError,
)
from ....adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.deadline_budget import remaining_budget
from ....application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
)
from ....core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from ....core.i18n.render import tr
from . import automation_requester_contracts as _contracts
from .automation_requester_cleanup import RequesterCleanup

if TYPE_CHECKING:
    from .automation_requester import RuntimeAutomationRequesterScreen


@dataclass(slots=True)
class _RequestExecutionState:
    request_id: UUID | None = None
    submitted_attempted: bool = False


class RequesterDeliveryMixin:
    """Own the exact native client and retain every retryable cleanup resource."""

    def _retain_cleanup_owner(
        self: RuntimeAutomationRequesterScreen, identity: int, close: Callable[[], Awaitable[None]]
    ) -> None:
        if identity not in self._cleanup_owners:

            def released() -> None:
                self._cleanup_owners.pop(identity, None)

            self._cleanup_owners[identity] = RequesterCleanup(close, released=released)

    def _retain_cleanup_errors(self: RuntimeAutomationRequesterScreen, error: BaseException) -> None:
        """Adopt canonical failure attachments after the wire task returns to the UI."""
        pending = [error]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            identity = id(current)
            if identity in seen:
                continue
            seen.add(identity)
            if isinstance(current, AsyncResourceCleanupError):
                self._retain_cleanup_owner(identity, current.retry_cleanup)
            self._append_attached_cleanup_errors(current, pending)
            if isinstance(current, AutomationRequesterUncertainError) and current.__cause__ is not None:
                pending.append(current.__cause__)

    def _append_attached_cleanup_errors(self, current: BaseException, pending: list[BaseException]) -> None:
        for name in ("async_cleanup_error", "cleanup_error", "body_error"):
            attached = current.__dict__.get(name)
            if isinstance(attached, BaseException):
                pending.append(attached)

    def _reconcile(
        self: RuntimeAutomationRequesterScreen,
        enrollment: NativeEnrollmentClient,
        draft: _contracts.ProposalDraft,
    ) -> Callable[..., AutomationReceiptProjection]:
        fresh_opener = self._fresh_credential_client
        if fresh_opener is None or draft.credential_reference is None:
            raise ValueError("fresh protected credential reference required")

        def reconcile(submitted: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
            deadline = time.monotonic() + timeout
            reference = self._reconciliation_reference(enrollment, draft)
            remaining = remaining_budget(deadline)
            fresh = fresh_opener(self._profile_id, reference, remaining)
            return self._reconcile_fresh(fresh, submitted.request_id, deadline)

        return reconcile

    def _reconciliation_reference(
        self: RuntimeAutomationRequesterScreen,
        enrollment: NativeEnrollmentClient,
        draft: _contracts.ProposalDraft,
    ) -> UUID:
        if draft.kind is EnrollmentKind.ROTATE:
            reference = enrollment.delivered_credential_metadata().credential_reference
        else:
            reference = draft.credential_reference
        if reference is None:
            raise ValueError("missing protected credential reference")
        return reference

    @staticmethod
    def _reconcile_fresh(
        fresh: RuntimeFrontendClient, request_id: UUID, deadline: float
    ) -> AutomationReceiptProjection:
        try:
            remaining = remaining_budget(deadline)
            return fresh.reconcile_enrollment(request_id, timeout=remaining)
        finally:
            primary_error = sys.exception()

            async def close_fresh() -> None:
                await asyncio.to_thread(fresh.close)

            cleanup = RequesterCleanup(close_fresh, released=lambda: None)
            asyncio.run(
                close_async_resources(cleanup, task_name="tui-requester-reconcile-close", primary_error=primary_error)
            )

    async def _execute(self: RuntimeAutomationRequesterScreen, draft: _contracts.ProposalDraft) -> None:
        state = _RequestExecutionState()
        try:
            client = await self._open_request_client()
            await self._run_request(client, draft, state)
        except AutomationRequesterUncertainError as error:
            self._retain_cleanup_errors(error)
            self._outcome = _contracts.AutomationRequestOutcome(
                error.request_id,
                str(self._submitted.review_digest) if self._submitted is not None else None,
                None,
                None,
                True,
                error.reason,
            )
        except asyncio.CancelledError as error:
            self._retain_cleanup_errors(error)
            self._set_failed_outcome(state)
            raise
        except Exception as error:
            self._retain_cleanup_errors(error)
            self._set_failed_outcome(state)
        finally:
            self._busy = False
            self._render_outcome()

    async def _open_request_client(self: RuntimeAutomationRequesterScreen) -> RuntimeFrontendClient:
        client = self._client
        if client is not None:
            if not self._bound(client):
                raise ValueError("requester client binding changed")
            return client
        opener = self._open_client
        if opener is None:
            raise ValueError("requester opener absent")

        async def open_bound() -> RuntimeFrontendClient:
            return await opener(self._profile_id)

        opening = asyncio.create_task(open_bound(), name="tui-requester-open")
        interrupted = await self._settle_requester_open(opening)
        client = opening.result()
        self._owned_client = client
        if interrupted is not None:
            raise interrupted
        if not self._bound(client):
            raise ValueError("requester client binding changed")
        return client

    @staticmethod
    async def _settle_requester_open(
        opening: asyncio.Task[RuntimeFrontendClient],
    ) -> asyncio.CancelledError | None:
        interrupted: asyncio.CancelledError | None = None
        while not opening.done():
            try:
                await asyncio.shield(opening)
            except asyncio.CancelledError as caught:
                interrupted = caught
            except BaseException:
                break
        return interrupted

    async def _run_request(
        self: RuntimeAutomationRequesterScreen,
        client: RuntimeFrontendClient,
        draft: _contracts.ProposalDraft,
        state: _RequestExecutionState,
    ) -> None:
        enrollment = await await_cancellation_complete(
            asyncio.to_thread(
                client.prepare_enrollment if draft.kind is EnrollmentKind.ENROLL else client.prepare_grant_change,
                self._secrets_store,
            ),
            task_name="tui-requester-prepare",
        )
        state.request_id = enrollment.prepared.enrollment_request_id
        proposal = draft.proposal(enrollment.prepared.destination_id)
        reconcile = None if draft.kind is EnrollmentKind.ENROLL else self._reconcile(enrollment, draft)
        journey = AutomationRequesterJourney(enrollment, timeout=self._journey_timeout, reconcile=reconcile)
        state.submitted_attempted = True
        submitted = await await_cancellation_complete(
            asyncio.to_thread(journey.submit, proposal), task_name="tui-requester-submit"
        )
        self._submitted = submitted
        self._update_submitted_status()
        completed = await await_cancellation_complete(
            asyncio.to_thread(journey.wait_for_terminal), task_name="tui-requester-delivery"
        )
        self._outcome = self._completed_outcome(completed)

    def _update_submitted_status(self: RuntimeAutomationRequesterScreen) -> None:
        if not self._live or not self.is_mounted:
            return
        if self._reviewer_client is not None:
            self.query_one("#automation-request-review", Button).disabled = not self._reviewer_bound()
        submitted = self._submitted
        if submitted is None:
            return
        self.query_one("#automation-request-status", Static).update(
            f"{tr('tui.automation_request.requested')} · "
            f"{tr('tui.automation_request.request_id')}: {submitted.request_id} · "
            f"{tr('tui.automation_request.review_digest')}: {submitted.review_digest}"
        )

    def _set_failed_outcome(self: RuntimeAutomationRequesterScreen, state: _RequestExecutionState) -> None:
        self._outcome = _contracts.AutomationRequestOutcome(
            state.request_id if state.submitted_attempted else None,
            str(self._submitted.review_digest) if self._submitted is not None else None,
            None,
            None,
            state.submitted_attempted,
            None,
        )

    @staticmethod
    def _completed_outcome(completed: AutomationRequesterCompletion) -> _contracts.AutomationRequestOutcome:
        terminal = completed.terminal
        return _contracts.AutomationRequestOutcome(
            terminal.request_id,
            str(terminal.review_digest),
            terminal.stage,
            None if completed.credential is None else completed.credential.credential_reference,
            False,
            None,
        )

    def _reviewer_bound(self: RuntimeAutomationRequesterScreen) -> bool:
        reviewer = self._reviewer_client
        try:
            return (
                reviewer is not None
                and not self._reviewer_access_lost
                and reviewer.frontend is OperationFrontendProjection.TUI
                and reviewer.profile_id == self._profile_id
                and reviewer.session_id == self._reviewer_session_id
            )
        except Exception:
            return False
