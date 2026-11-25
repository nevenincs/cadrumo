"""Non-touching account session observation over the exact runtime connection."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.application.overview.home import HomeAccountSession, HomeSessionPosture
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.operations import OperationEffect
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.tui.account import (
    AccountSessionExpiredError,
    AccountSessionReaderV1,
    AccountSessionUnavailableError,
)
from cadrumo.entrypoints.tui.operations.outcome import (
    OperationOutcomeUnknownError,
    SessionExpiredOutcomeUnknownError,
    SessionUnavailableOutcomeUnknownError,
)
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.profile_access import status_admits_session
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
    from cadrumo_client.transport.frontend_client import FrontendClient


def runtime_account_activity_reporter(client: FrontendClient) -> Callable[[], Awaitable[None]]:
    """Forward person input off the rendering loop; runtime owns renewal."""

    async def note_activity() -> None:
        await await_cancellation_complete(asyncio.to_thread(client.note_activity), task_name="tui-person-activity")

    return note_activity


def runtime_account_session_reader(
    client: FrontendClient, *, profile_id: UUID, profile_label: str
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
    client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str
) -> HomeAccountSession:
    """Observe an exact lease synchronously without extending its authority."""
    try:
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        status = client.status().status
    except (FrontendRefusedError, RefusalError) as error:
        raise AccountSessionUnavailableError() from error
    if not status.connected or status.denial in {
        AccessDenialCode.OS_SESSION_UNAVAILABLE,
        AccessDenialCode.BACKEND_UNAVAILABLE,
        AccessDenialCode.AUTHORITY_UNAVAILABLE,
        AccessDenialCode.STORAGE_UNAVAILABLE,
        AccessDenialCode.CUSTODY_UNAVAILABLE,
        # Suspended while a lost worker is replaced: unavailable for now, not expired.
        AccessDenialCode.CUSTODY_RECOVERING,
    }:
        raise AccountSessionUnavailableError()
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or not status_admits_session(
            status, profile_id=profile_id, session_id=session_id, at=now(), requires_automation_grant=False
        )
        or status.session_expires_at is None
    ):
        raise AccountSessionExpiredError()
    return HomeAccountSession(
        posture=HomeSessionPosture.ACTIVE,
        profile_label=profile_label,
        expires_at=status.session_expires_at,
    )


def session_lost_with_receipt(
    lost: AccountSessionExpiredError,
    operation_id: str,
    projection: OperationPublicProjectionV1 | None,
    *,
    unknown_outcome: OperationOutcomeUnknownError | None = None,
) -> AccountSessionExpiredError:
    """Keep a submitted operation's receipt visible when its retained session is lost.

    An expired session and a runtime that could not be observed stay distinct,
    as ``lost`` observed them, and the error keeps the operation ID with the
    last observed terminal facts. When ``unknown_outcome`` says the change may
    have been saved, the session error carries it, and its message says so
    with the operation ID.
    """
    unavailable = isinstance(lost, AccountSessionUnavailableError)
    if unknown_outcome is not None:
        if unavailable:
            return SessionUnavailableOutcomeUnknownError(unknown_outcome)
        return SessionExpiredOutcomeUnknownError(unknown_outcome)
    condition = projection.terminal_condition if projection is not None else None
    effect = projection.effect if projection is not None else OperationEffect.UNKNOWN
    refusal_code = projection.refusal_ref if projection is not None else None
    receipt: dict[str, object] = {
        "operation_id": operation_id,
        "terminal_condition": condition.value if condition is not None else "unknown",
        "effect": effect.value,
        "refusal_code": refusal_code,
    }
    if unavailable:
        return AccountSessionUnavailableError(context=receipt)
    return AccountSessionExpiredError(context=receipt)


__all__ = ["read_runtime_account_session", "runtime_account_session_reader", "session_lost_with_receipt"]
