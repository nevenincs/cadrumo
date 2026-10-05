"""Profile-resume workflow owned by the runtime login screen."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, cast
from uuid import UUID

from textual.widgets import Input, Select

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete
from ....core.i18n.render import tr
from ..components.status import PinnedStatusBar
from .runtime_login_session import ResumeAttemptState, open_to_completion

if TYPE_CHECKING:
    from .runtime_login import RuntimeLoginScreen


class RuntimeLoginRecoveryMixin:
    """Own profile recovery, its refusal boundary, and recovery input capture."""

    def _resume_unknown(self: RuntimeLoginScreen, profile_id: UUID, code: str) -> None:
        """Fence replay of a dispatched recovery whose effect was not confirmed."""
        self._uncertain_resumes.add(profile_id)
        if self._active():
            self.query_one("#runtime-login-status", PinnedStatusBar).show_warning(
                f"{tr('tui.runtime_access.resume')}: {tr('tui.runtime_access.unknown')} ({code})"
            )

    async def _open_recovery_client(
        self: RuntimeLoginScreen, profile_id: UUID
    ) -> tuple[RuntimeFrontendClient, asyncio.CancelledError | None]:
        async def open_recovery(selected: UUID) -> RuntimeFrontendClient:
            try:
                return await self._open_client(selected)
            except BaseException as error:
                self._retain_reference_cleanup(error)
                raise

        return await open_to_completion(open_recovery, profile_id)

    async def _perform_recovery(
        self: RuntimeLoginScreen,
        profile_id: UUID,
        proof: bytearray,
        grants: frozenset[UUID],
        state: ResumeAttemptState,
    ) -> None:
        state.client, interrupted_open = await self._open_recovery_client(profile_id)
        if interrupted_open is not None:
            raise interrupted_open
        client = state.client
        if not self._active():
            return
        if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        state.dispatched = True
        receipt = await await_cancellation_complete(
            asyncio.to_thread(client.recover_profile, proof, grants=grants),
            task_name="tui-runtime-profile-resume",
        )
        if receipt.profile_id != profile_id or receipt.reactivated_grants != grants:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        state.completed = True
        if self._active():
            self.query_one("#runtime-login-status", PinnedStatusBar).show_success(tr("tui.runtime_access.completed"))

    def _show_resume_failure(
        self: RuntimeLoginScreen, profile_id: UUID, error: BaseException, *, dispatched: bool
    ) -> bool:
        if isinstance(error, RuntimeFrontendRefusedError):
            if dispatched and error.reason in {code.value for code in RuntimeRefusalCode}:
                self._resume_unknown(profile_id, error.reason)
            else:
                self._status_refused(error.reason)
            return False
        if isinstance(error, RuntimeRefusalError):
            if dispatched:
                self._resume_unknown(profile_id, error.reason.value)
            else:
                self._status_refused(error.reason.value)
            return False
        if isinstance(error, asyncio.CancelledError):
            if dispatched:
                self._resume_unknown(profile_id, RuntimeRefusalCode.UNAVAILABLE.value)
            return True
        if dispatched:
            self._resume_unknown(profile_id, RuntimeRefusalCode.UNAVAILABLE.value)
        else:
            self._status_refused(RuntimeRefusalCode.UNAVAILABLE.value)
        return False

    def _show_recovery_cleanup_failure(self: RuntimeLoginScreen, *, completed: bool) -> None:
        if not self._active():
            return
        status = self.query_one("#runtime-login-status", PinnedStatusBar)
        if completed:
            status.show_warning(f"{tr('tui.runtime_access.completed')} ({RuntimeRefusalCode.UNAVAILABLE.value})")
        else:
            self._status_refused(RuntimeRefusalCode.UNAVAILABLE.value)

    async def _resume_attempt(
        self: RuntimeLoginScreen, profile_id: UUID, proof: bytearray, grants: frozenset[UUID]
    ) -> None:
        """Own fresh recovery and release; recovery never produces a login handoff."""
        state = ResumeAttemptState()
        try:
            try:
                await self._perform_recovery(profile_id, proof, grants, state)
            except (RuntimeFrontendRefusedError, RuntimeRefusalError, asyncio.CancelledError, Exception) as error:
                state.primary_error = error
                if self._show_resume_failure(profile_id, error, dispatched=state.dispatched):
                    raise
            finally:
                proof[:] = bytes(len(proof))
                if self._pending_proof is proof:
                    self._pending_proof = None
                if state.client is not None:
                    await self._close_untransferred(
                        state.client,
                        primary_error=state.primary_error if state.primary_error is not None else sys.exception(),
                    )
        except AsyncResourceCleanupError:
            # The pool already retains the failed candidate; never re-run recovery.
            self._show_recovery_cleanup_failure(completed=state.completed)
        finally:
            self._busy = False
            if self._active():
                self.query_one("#runtime-login-resume-password", Input).value = ""
                self.query_one("#runtime-login-resume-grants", Input).value = ""
                self._controls()

    def _resume_profile_id(self: RuntimeLoginScreen) -> UUID | None:
        selected = cast("Select[str]", self.query_one("#runtime-login-profile", Select)).value
        if not isinstance(selected, str) or selected not in self._profile_ids:
            self._status_refused()
            return None
        profile_id = self._profile_ids[selected]
        if profile_id in self._uncertain_resumes:
            self.query_one("#runtime-login-resume-password", Input).value = ""
            self.query_one("#runtime-login-resume-grants", Input).value = ""
            self._resume_unknown(profile_id, RuntimeRefusalCode.UNAVAILABLE.value)
            return None
        return profile_id

    def _resume_inputs(self: RuntimeLoginScreen) -> tuple[bytearray, tuple[UUID, ...]] | None:
        password = self.query_one("#runtime-login-resume-password", Input)
        grants_field = self.query_one("#runtime-login-resume-grants", Input)
        proof = bytearray(password.value.encode("utf-8"))
        password.value = ""
        raw = grants_field.value.strip()
        grants_field.value = ""
        try:
            parts = () if not raw else tuple(item.strip() for item in raw.split(","))
            selected_grants = tuple(UUID(item) for item in parts)
            if len(set(selected_grants)) != len(selected_grants):
                raise ValueError("repeated selected grant")
        except ValueError:
            proof[:] = bytes(len(proof))
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(tr("tui.runtime_access.invalid_grants"))
            return None
        if not proof:
            self.query_one("#runtime-login-status", PinnedStatusBar).show_error(
                tr("tui.runtime_login.credential_required")
            )
            return None
        return proof, selected_grants

    def _start_resume(
        self: RuntimeLoginScreen, profile_id: UUID, proof: bytearray, selected_grants: tuple[UUID, ...]
    ) -> None:
        self._busy = True
        self._pending_proof = proof
        self._controls()
        self.query_one("#runtime-login-status", PinnedStatusBar).show_progress(tr("tui.runtime_access.busy"))
        self._worker = self.run_worker(
            self._resume_attempt(profile_id, proof, frozenset(selected_grants)),
            name="tui-runtime-profile-resume",
            group="tui-runtime-login",
            exclusive=True,
            exit_on_error=False,
        )
