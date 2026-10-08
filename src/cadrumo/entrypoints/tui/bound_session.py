"""The admitted TUI session a screen is pinned to, and whether it is still the one it opened with."""

from __future__ import annotations

import asyncio
from datetime import datetime

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.registry import OperationFrontendProjection
from ...application.user_profile.access_contracts import ProfileAccessStatus
from ...core.async_cleanup import await_cancellation_complete
from ...core.time.clock import now


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

    def __init__(self, client: RuntimeFrontendClient, *, known_expires_at: datetime | None = None) -> None:
        """Pin the client's profile and session as they stand at admission."""
        self._client = client
        self._profile_id = client.profile_id
        self._session_id = client.session_id
        self.known_expires_at = known_expires_at
        """The last session expiry the runtime reported, or ``None`` before it has reported one."""

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
        return valid
