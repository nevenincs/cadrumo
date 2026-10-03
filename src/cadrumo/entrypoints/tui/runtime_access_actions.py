"""Action dispatch and failure policy for runtime access controls."""

from __future__ import annotations

import asyncio
from typing import Final, Literal, Protocol, TypeVar
from uuid import UUID

from textual.widget import Widget
from textual.widgets import Input, Static

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_projections import PublicAccessSession
from ...application.user_profile.automation_lifecycle import AutomationDenialKind
from ...core.async_cleanup import await_cancellation_complete
from ...core.i18n.render import tr
from .runtime_access_projection import denial_acknowledgement

type _Action = Literal[
    "refresh", "deny_key", "deny_grant", "deny_all", "lock_current", "lock_selected", "lock_profile", "resume"
]

_BUTTON_ACTIONS: Final[dict[str, _Action]] = {
    "runtime-access-refresh": "refresh",
    "runtime-access-deny-key": "deny_key",
    "runtime-access-deny-grant": "deny_grant",
    "runtime-access-deny-all": "deny_all",
    "runtime-access-lock-current": "lock_current",
    "runtime-access-lock-selected": "lock_selected",
    "runtime-access-lock-profile": "lock_profile",
    "runtime-access-resume": "resume",
}


def _grant_selection(raw: str) -> frozenset[UUID]:
    """Parse explicit selected grant identities; blank means human-only resume."""
    if not raw.strip():
        return frozenset[UUID]()
    parts = tuple(part.strip() for part in raw.split(","))
    if not all(parts):
        raise ValueError("empty selected grant")
    selected = tuple(UUID(part) for part in parts)
    if len(set(selected)) != len(selected):
        raise ValueError("repeated selected grant")
    return frozenset(selected)


_WidgetT = TypeVar("_WidgetT", bound=Widget)


class _RuntimeAccessActionHost(Protocol):
    _busy: bool
    _client: RuntimeFrontendClient
    _profile_id: UUID
    _session_id: UUID
    _resume_dispatched: bool

    def query_one(self, selector: str, _expect_type: type[_WidgetT], /) -> _WidgetT: ...

    def _active(self) -> bool: ...

    def _controls(self) -> None: ...

    def _status(self, key: str, *, code: str | None = None) -> None: ...

    def _show_sessions(self, sessions: tuple[PublicAccessSession, ...]) -> None: ...

    def _lose_access(self) -> None: ...

    def _resume_fenced(self) -> bool: ...

    async def _recover_owned(self, password: bytearray, grants: frozenset[UUID]) -> None: ...

    async def _retain_self_lock_after_human_refusal(self) -> bool: ...

    def _resume_failed(self, *, code: str, uncertain: bool) -> None: ...

    async def _dispatch_action(self, action: _Action) -> tuple[bool, str | None]: ...

    def _show_action_completion(self, acknowledgement: str | None) -> None: ...

    async def _handle_refusal(
        self, action: _Action, error: RuntimeFrontendRefusedError | RuntimeRefusalError
    ) -> None: ...

    def _handle_uncertain_failure(self, action: _Action) -> None: ...

    def _handle_unexpected_failure(self, action: _Action) -> None: ...

    def _finish_action(self, action: _Action) -> None: ...

    async def _perform_denial(self, action: _Action) -> tuple[bool, str | None]: ...

    async def _perform_current_lock(self) -> tuple[bool, str | None]: ...

    async def _perform_selected_lock(self) -> tuple[bool, str | None]: ...

    async def _perform_profile_lock(self) -> tuple[bool, str | None]: ...

    async def _perform_resume(self) -> tuple[bool, str | None]: ...


class _RuntimeAccessActionsMixin:
    async def _perform(self: _RuntimeAccessActionHost, action: _Action) -> None:
        if self._busy or not self._active():
            return
        if action == "resume":
            if self._resume_fenced():
                return
            self._resume_dispatched = False
        self._busy = True
        self._controls()
        self._status("tui.runtime_access.busy")
        try:
            completed, acknowledgement = await self._dispatch_action(action)
            if completed:
                self._show_action_completion(acknowledgement)
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            await self._handle_refusal(action, error)
        except asyncio.CancelledError:
            self._handle_uncertain_failure(action)
            raise
        except Exception:
            self._handle_unexpected_failure(action)
        finally:
            self._finish_action(action)

    async def _dispatch_action(self: _RuntimeAccessActionHost, action: _Action) -> tuple[bool, str | None]:
        if action == "refresh":
            sessions = await await_cancellation_complete(
                asyncio.to_thread(self._client.sessions), task_name="tui-access-session-inventory"
            )
            self._show_sessions(sessions)
            return True, None
        if action in {"deny_key", "deny_grant", "deny_all"}:
            return await self._perform_denial(action)
        if action == "lock_current":
            return await self._perform_current_lock()
        if action == "lock_selected":
            return await self._perform_selected_lock()
        if action == "lock_profile":
            return await self._perform_profile_lock()
        return await self._perform_resume()

    async def _perform_denial(self: _RuntimeAccessActionHost, action: _Action) -> tuple[bool, str | None]:
        target: UUID | None = None
        if action != "deny_all":
            try:
                target = UUID(self.query_one("#runtime-access-target", Input).value.strip())
            except ValueError:
                self._status("tui.runtime_access.invalid_target")
                return False, None
        kind = {
            "deny_key": AutomationDenialKind.KEY,
            "deny_grant": AutomationDenialKind.GRANT,
            "deny_all": AutomationDenialKind.ALL,
        }[action]
        denied = await await_cancellation_complete(
            asyncio.to_thread(self._client.deny_automation, kind, target_id=target), task_name="tui-access-denial"
        )
        if denied.profile_id != self._profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if self._active():
            self.query_one("#runtime-access-target", Input).value = ""
        return True, denial_acknowledgement(denied)

    async def _perform_current_lock(self: _RuntimeAccessActionHost) -> tuple[bool, str | None]:
        locked = await await_cancellation_complete(
            asyncio.to_thread(self._client.lock), task_name="tui-current-session-lock"
        )
        if self._session_id not in locked.session_ids:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        acknowledgement = tr("tui.runtime_access.sessions_locked", session_ids=", ".join(map(str, locked.session_ids)))
        self._lose_access()
        return True, acknowledgement

    async def _perform_selected_lock(self: _RuntimeAccessActionHost) -> tuple[bool, str | None]:
        try:
            target_session_id = UUID(self.query_one("#runtime-access-target", Input).value.strip())
        except ValueError:
            self._status("tui.runtime_access.invalid_target")
            return False, None
        locked = await await_cancellation_complete(
            asyncio.to_thread(self._client.revoke_session, target_session_id), task_name="tui-selected-session-lock"
        )
        acknowledgement = tr("tui.runtime_access.sessions_locked", session_ids=", ".join(map(str, locked.session_ids)))
        if self._active():
            self.query_one("#runtime-access-target", Input).value = ""
        if self._session_id in locked.session_ids:
            self._lose_access()
        else:
            sessions = await await_cancellation_complete(
                asyncio.to_thread(self._client.sessions), task_name="tui-access-session-inventory"
            )
            self._show_sessions(sessions)
        return True, acknowledgement

    async def _perform_profile_lock(self: _RuntimeAccessActionHost) -> tuple[bool, str | None]:
        denied = await await_cancellation_complete(
            asyncio.to_thread(self._client.deny_automation, AutomationDenialKind.PROFILE_LOCK),
            task_name="tui-profile-lock",
        )
        if denied.profile_id != self._profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        acknowledgement = denial_acknowledgement(denied)
        self._lose_access()
        return True, acknowledgement

    async def _perform_resume(self: _RuntimeAccessActionHost) -> tuple[bool, str | None]:
        password_input = self.query_one("#runtime-access-password", Input)
        password = bytearray(password_input.value.encode("utf-8"))
        password_input.value = ""
        try:
            grants = _grant_selection(self.query_one("#runtime-access-grants", Input).value)
        except ValueError:
            password[:] = bytes(len(password))
            self._status("tui.runtime_access.invalid_grants")
            return False, None
        await await_cancellation_complete(self._recover_owned(password, grants), task_name="tui-profile-recovery")
        if self._active():
            self.query_one("#runtime-access-grants", Input).value = ""
        return True, None

    def _show_action_completion(self: _RuntimeAccessActionHost, acknowledgement: str | None) -> None:
        self._status("tui.runtime_access.completed")
        if acknowledgement is not None and self._active():
            self.query_one("#runtime-access-status", Static).update(acknowledgement)

    async def _handle_refusal(
        self: _RuntimeAccessActionHost, action: _Action, error: RuntimeFrontendRefusedError | RuntimeRefusalError
    ) -> None:
        code = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
        human_refusal = (
            action not in {"lock_current", "resume"}
            and isinstance(error, RuntimeFrontendRefusedError)
            and error.reason == AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value
        )
        if human_refusal and await self._retain_self_lock_after_human_refusal():
            self._status("tui.runtime_access.refused", code=code)
        elif action == "resume":
            self._resume_failed(
                code=code,
                uncertain=isinstance(error, RuntimeRefusalError)
                or error.reason in {item.value for item in RuntimeRefusalCode},
            )
        else:
            self._lose_access()
            self._status("tui.runtime_access.access_lost", code=code)

    def _handle_uncertain_failure(self: _RuntimeAccessActionHost, action: _Action) -> None:
        if action == "resume":
            self._resume_failed(code=RuntimeRefusalCode.UNAVAILABLE.value, uncertain=True)

    def _handle_unexpected_failure(self: _RuntimeAccessActionHost, action: _Action) -> None:
        if action == "resume":
            self._resume_failed(code=RuntimeRefusalCode.UNAVAILABLE.value, uncertain=True)
        else:
            self._lose_access()
            self._status("tui.runtime_access.access_lost")

    def _finish_action(self: _RuntimeAccessActionHost, action: _Action) -> None:
        self._busy = False
        if not self._active():
            return
        if action == "resume":
            self.query_one("#runtime-access-password", Input).value = ""
            self.query_one("#runtime-access-grants", Input).value = ""
        self._controls()
