"""Exact-profile runtime login with an owned, cancellation-complete connection."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from typing import ClassVar, cast
from uuid import UUID

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Input, Select
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ....application.user_profile.login_interaction import ProfileLoginChoice
from ....core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from ....core.i18n.render import tr
from ..components.app_access import TypedAppAccess
from ..components.status import PinnedStatusBar
from ..components.theme import BASE_CSS, tokenised
from .automation_requester import RuntimeAutomationRequesterScreen
from .credentials import CREDENTIAL_PANEL_CSS
from .runtime_login_attempt import RuntimeLoginAttemptMixin
from .runtime_login_contracts import (
    RuntimeClientOpener,
    RuntimeCredentialClientOpener,
    RuntimeLoginAcceptor,
    RuntimeLoginHandoff,
    RuntimeLoginMethod,
)
from .runtime_login_form import RuntimeLoginFormMixin
from .runtime_login_recovery import RuntimeLoginRecoveryMixin
from .runtime_login_session import LoginCleanup

type RuntimeRequesterFactory = Callable[[UUID], RuntimeAutomationRequesterScreen]


class RuntimeLoginScreen(
    RuntimeLoginFormMixin,
    RuntimeLoginAttemptMixin,
    RuntimeLoginRecoveryMixin,
    TypedAppAccess,
    Screen[RuntimeLoginHandoff | None],
):
    """Prompt for one exact profile and proof without opening local custody."""

    BINDINGS: ClassVar = [Binding("escape", "abandon", "", show=False)]
    SCOPED_CSS = False
    DEFAULT_CSS = tokenised(
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + """
    #runtime-login-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
    """
    )

    def __init__(
        self,
        *,
        choices: Sequence[ProfileLoginChoice],
        open_client: RuntimeClientOpener,
        open_credential_client: RuntimeCredentialClientOpener | None = None,
        requester_factory: RuntimeRequesterFactory | None = None,
        accept_handoff: RuntimeLoginAcceptor,
        preselected: str | None = None,
    ) -> None:
        """Bind a nonsecret profile inventory and an exact-client opener."""
        super().__init__()
        if not choices:
            raise ValueError("runtime login requires a profile choice")
        parsed: dict[str, UUID] = {}
        for choice in choices:
            identity = UUID(choice.profile_id)
            if str(identity) != choice.profile_id or choice.profile_id in parsed:
                raise ValueError("runtime login requires distinct canonical profile identities")
            parsed[choice.profile_id] = identity
        self._choices = tuple(choices)
        self._profile_ids = parsed
        self._preselected = preselected if preselected in parsed else self._choices[0].profile_id
        self._open_client = open_client
        self._open_credential_client = open_credential_client
        self._requester_factory = requester_factory
        self._accept_handoff = accept_handoff
        self._busy = False
        self._live = True
        self._transferred = False
        self._worker: Worker[None] | None = None
        self._pending_proof: bytearray | None = None
        self._input_fields: tuple[Input, ...] = ()
        self._cleanup_owners: dict[int, LoginCleanup] = {}
        self._uncertain_resumes: set[UUID] = set()

    def _active(self) -> bool:
        """Check liveness afresh after each asynchronous native boundary."""
        return self._live and self.is_mounted

    async def on_unmount(self) -> None:
        """Drain native work and close an untransferred client before exit."""
        self._live = False
        for input_field in self._input_fields:
            input_field.value = ""
        self._input_fields = ()
        worker = self._worker
        try:
            if not self._transferred and worker is not None:
                worker.cancel()
                with suppress(WorkerCancelled, WorkerError, WorkerFailed):
                    await await_cancellation_complete(worker.wait(), task_name="tui-runtime-login-drain")
        finally:
            try:
                await close_async_resources(
                    *tuple(self._cleanup_owners.values()), task_name="tui-runtime-login-release"
                )
            finally:
                if self._pending_proof is not None:
                    self._pending_proof[:] = bytes(len(self._pending_proof))
                    self._pending_proof = None

    def _retain_reference_cleanup(self, error: BaseException) -> None:
        """Adopt cleanup ownership before a failed opener becomes a UI refusal."""
        for name in ("async_cleanup_error", "cleanup_error"):
            failure = error.__dict__.get(name)
            if isinstance(failure, AsyncResourceCleanupError):
                identity = id(failure)
                self._retain_cleanup_owner(identity, failure.retry_cleanup)

    def _retain_cleanup_owner(self, identity: int, close: Callable[[], Awaitable[None]]) -> LoginCleanup:
        owner = self._cleanup_owners.get(identity)
        if owner is None:

            def released() -> None:
                self._cleanup_owners.pop(identity, None)

            owner = LoginCleanup(close, released=released)
            self._cleanup_owners[identity] = owner
        return owner

    def on_select_changed(self, event: Select.Changed) -> None:
        """Switch proof labels without reinterpreting a previously entered value."""
        if self._busy:
            return
        if event.select.id == "runtime-login-profile":
            self.query_one("#runtime-login-resume-password", Input).value = ""
            self.query_one("#runtime-login-resume-grants", Input).value = ""
            self._controls()
            return
        if event.select.id != "runtime-login-method":
            return
        method = event.value
        if not isinstance(method, RuntimeLoginMethod):
            return
        self._show_method(method)

    def action_resume(self) -> None:
        """Freeze exact profile, explicit selected grants and one fresh masked proof."""
        if self._busy:
            return
        profile_id = self._resume_profile_id()
        if profile_id is None:
            return
        inputs = self._resume_inputs()
        if inputs is None:
            return
        proof, selected_grants = inputs
        self._start_resume(profile_id, proof, selected_grants)

    def _status_refused(self, code: str | None = None) -> None:
        if self._active():
            message = tr("tui.runtime_login.refused")
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                message if code is None else f"{message} ({code})"
            )
            if (
                cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
                is RuntimeLoginMethod.RECEIPT
            ):
                self.query_one("#runtime-login-method", Select).focus()
            elif (
                cast("Select[RuntimeLoginMethod]", self.query_one("#runtime-login-method", Select)).value
                is RuntimeLoginMethod.API_REFERENCE
            ):
                self.query_one("#runtime-login-reference", Input).focus()
            else:
                self.query_one("#runtime-login-credential", Input).focus()

    def action_submit(self) -> None:
        """Freeze exact profile and method before copying one masked proof."""
        if self._busy:
            return
        selection = self._selected_login()
        if selection is None:
            return
        selected, method = selection
        credential = self.query_one("#runtime-login-credential", Input)
        reference_field = self.query_one("#runtime-login-reference", Input)
        reference_raw = reference_field.value.strip()
        reference_field.value = ""
        valid_reference, reference = self._reference_input(method, credential, reference_raw)
        if not valid_reference:
            return
        proof = self._proof_input(method, credential)
        if method in {RuntimeLoginMethod.PASSWORD, RuntimeLoginMethod.API_KEY} and not proof:
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                tr("tui.runtime_login.credential_required")
            )
            return
        self._start_login_attempt(selected, method, proof, reference)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch only explicit submit or abandon controls."""
        if event.button.id == "runtime-login-submit":
            self.action_submit()
        elif event.button.id == "runtime-login-resume":
            self.action_resume()
        elif event.button.id == "runtime-login-cancel":
            self.action_abandon()
        elif event.button.id == "runtime-login-request-access" and not self._busy:
            self._request_access()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the masked field submits the chosen proof family."""
        if event.input.id in {"runtime-login-credential", "runtime-login-reference"}:
            self.action_submit()

    def action_abandon(self) -> None:
        """Dismiss only when no owned native exchange is pending."""
        if not self._busy:
            for input_field in self._input_fields:
                input_field.value = ""
            self.dismiss(None)


__all__ = [
    "RuntimeLoginScreen",
    "RuntimeRequesterFactory",
]
