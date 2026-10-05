"""Non-touching account session observation over the exact runtime connection."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ...application.overview.home import HomeAccountSession, HomeSessionPosture
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.runtime.profile_access import status_admits_session
from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from .account import AccountSessionExpiredError, AccountSessionReaderV1

if TYPE_CHECKING:
    from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
    from ...application.operations.frontend_projection import OperationPublicProjectionV1
    from .operations.runtime_controller import RuntimeOperationController


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


def session_expired_with_receipt(
    controller: RuntimeOperationController | None,
    projection: OperationPublicProjectionV1 | None,
) -> AccountSessionExpiredError:
    """Keep a submitted operation's receipt visible when its retained session expires.

    Before submission there is no receipt. After it, the operation ID is kept
    with the last observed terminal facts, and an unobserved effect is unknown.
    """
    if controller is None:
        return AccountSessionExpiredError()
    condition = projection.terminal_condition if projection is not None else None
    effect = projection.effect if projection is not None else OperationEffect.UNKNOWN
    refusal_code = projection.refusal_ref if projection is not None else None
    return AccountSessionExpiredError(
        context={
            "operation_id": str(controller.operation_id),
            "terminal_condition": condition.value if condition is not None else "unknown",
            "effect": effect.value,
            "refusal_code": refusal_code,
        }
    )


__all__ = ["read_runtime_account_session", "runtime_account_session_reader", "session_expired_with_receipt"]
