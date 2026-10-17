"""The admitted TUI session a screen is pinned to, and whether it is still the one it opened with."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from textual.message_pump import MessagePump
from textual.timer import Timer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessStatus
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.time.clock import now
from cadrumo_client.transport.frontend_client import FrontendClient

#: Past the known expiry, so a timer that wakes a little early still finds it passed.
_EXPIRY_MARGIN_SECONDS = 0.05


def _status_confirms_session(status: ProfileAccessStatus, profile_id: object, session_id: object) -> bool:
    return (
        status.connected
        and status.credential_authenticated
        and status.profile_bound
        and status.profile_id == profile_id
        and status.session_id == session_id
        and status.session_expires_at is not None
        and status.session_expires_at > now()
        and status.denial is None
    )


class BoundSession:
    """One admitted TUI connection and the profile session it was admitted for."""

    def __init__(self, client: FrontendClient, *, known_expires_at: datetime | None = None) -> None:
        """Pin the client's profile and session as they stand at admission."""
        self._client = client
        self._profile_id = client.profile_id
        self._session_id = client.session_id
        self.known_expires_at = known_expires_at
        """The last session expiry the runtime reported, or ``None`` before it has reported one."""
        self._watcher: tuple[MessagePump, Callable[[], None]] | None = None
        self._expiry_timer: Timer | None = None

    def watch(self, owner: MessagePump, check: Callable[[], None]) -> Callable[[], None]:
        """Call ``check`` on ``owner`` each time the session may have ended, until the returned stop.

        The client pushes retirement and the loss of its connection, and the
        known expiry is one timer at its deadline, re-armed whenever the runtime
        reports another, so nothing is checked on an interval.
        """
        self._watcher = (owner, check)

        def retired() -> None:
            # This runs on the client's reader thread; ``call_later`` posts to ``owner``'s loop.
            owner.call_later(check)

        unsubscribe = self._client.subscribe_session_retirement(retired)
        self._arm_expiry()

        def stop() -> None:
            unsubscribe()
            self._watcher = None
            if self._expiry_timer is not None:
                self._expiry_timer.stop()
                self._expiry_timer = None

        return stop

    def _arm_expiry(self) -> None:
        if self._expiry_timer is not None:
            self._expiry_timer.stop()
            self._expiry_timer = None
        expires_at = self.known_expires_at
        if self._watcher is None or expires_at is None:
            return
        owner, _check = self._watcher
        delay = max(0.0, (expires_at - now()).total_seconds()) + _EXPIRY_MARGIN_SECONDS
        self._expiry_timer = owner.set_timer(delay, self._expiry_due)

    def _expiry_due(self) -> None:
        watcher = self._watcher
        if watcher is None:
            return
        watcher[1]()
        expires_at = self.known_expires_at
        if self._watcher is not None and expires_at is not None and expires_at > now():
            # Woken before the deadline, or the runtime reported a later one.
            self._arm_expiry()

    def identity_holds(self) -> bool:
        """Whether the client is still the TUI connection for the profile session pinned at admission."""
        try:
            return (
                self._client.frontend is OperationFrontendProjection.TUI
                and self._client.profile_id == self._profile_id
                and self._client.session_id == self._session_id
            )
        except Exception:
            return False

    def lifetime_ended(self) -> bool:
        """Whether the pinned identity is gone or the last reported expiry has passed, without asking the runtime."""
        expires_at = self.known_expires_at
        return not self.identity_holds() or (expires_at is not None and expires_at <= now())

    async def confirm_with_runtime(self, *, task_name: str) -> bool:
        """Ask the runtime whether the pinned session is still authenticated, bound and unexpired.

        A confirmed answer records the runtime's reported expiry; any refusal or failure reads as not confirmed.
        """
        if not self.identity_holds():
            return False
        try:
            reply = await await_cancellation_complete(asyncio.to_thread(self._client.status), task_name=task_name)
        except Exception:
            return False
        status = reply.status
        valid = self.identity_holds() and _status_confirms_session(status, self._profile_id, self._session_id)
        if valid:
            self.known_expires_at = status.session_expires_at
            self._arm_expiry()
        return valid
