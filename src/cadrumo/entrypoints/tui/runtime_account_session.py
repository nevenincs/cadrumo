"""Non-touching account session observation over the exact runtime connection."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.overview.home import HomeAccountSession, HomeSessionPosture
from ...application.runtime.contracts import RuntimeRefusalError
from ...core.async_cleanup import await_cancellation_complete
from ...core.time.clock import now
from .account import AccountSessionExpiredError, AccountSessionReaderV1

if TYPE_CHECKING:
    from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient


def runtime_account_session_reader(
    client: RuntimeFrontendClient, *, profile_id: UUID, profile_label: str
) -> AccountSessionReaderV1:
    """Pin one admitted lease; status checks neither refresh nor transfer it."""
    if client.profile_id != profile_id:
        raise ValueError("account reader requires the client's exact profile")
    session_id = client.session_id

    async def account_session() -> HomeAccountSession:
        return await await_cancellation_complete(
            asyncio.to_thread(
                read_runtime_account_session,
                client,
                profile_id=profile_id,
                session_id=session_id,
                profile_label=profile_label,
            ),
            task_name="tui-runtime-session-status",
        )

    return account_session


def read_runtime_account_session(
    client: RuntimeFrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str
) -> HomeAccountSession:
    """Observe an exact lease synchronously without extending its authority."""
    try:
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        status = client.status().status
    except (RuntimeFrontendRefusedError, RuntimeRefusalError):
        raise AccountSessionExpiredError() from None
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or not status.connected
        or not status.credential_authenticated
        or not status.profile_bound
        or status.profile_id != profile_id
        or status.session_id != session_id
        or status.session_expires_at is None
        or status.session_expires_at <= now()
        or status.denial is not None
    ):
        raise AccountSessionExpiredError()
    return HomeAccountSession(
        posture=HomeSessionPosture.ACTIVE,
        profile_label=profile_label,
        expires_at=status.session_expires_at,
    )


__all__ = ["read_runtime_account_session", "runtime_account_session_reader"]
