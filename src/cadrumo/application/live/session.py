"""Live AEAT session acquisition helpers.

This module is the shared read-only entry gate for application-live services.
It loads :class:`Settings`, enforces
:meth:`cadrumo.core.access_gate.AeatAccessGate.require_live_read`, and only then
returns an authenticated :class:`AeatSession`. It never calls
``require_live_write`` and never performs AEAT-side mutations.

See Also:
    :class:`~cadrumo.core.access_gate.AeatAccessGate`
        Core gate that authorizes pytest live reads and refuses all live writes.
    :func:`~cadrumo.application.auth.ensure_authenticated_aeat_session`
        Auth service called only after the read gate passes.
    :mod:`cadrumo.application.live`
        Public read-only live facade that routes remote acquisition helpers
        through this session boundary.
"""

from __future__ import annotations

from ...application.auth.protocols import AeatSessionPort
from ...application.auth.sessions import ensure_authenticated_aeat_session
from ...core.access_gate import AeatAccessGate
from ...core.config import Settings, load_settings


async def active_verified_session(
    *,
    operation: str = "live-filed-read",
    target_url: str | None = None,
) -> tuple[AeatSessionPort, Settings]:
    """Return an authenticated session and :class:`Settings` after the live-read gate.

    The ``operation`` and optional ``target_url`` are forwarded to the
    authentication service for diagnostics and provider routing after
    :class:`AeatAccessGate` has authorized a read-only live operation.
    """
    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    result = await ensure_authenticated_aeat_session(
        settings,
        operation=operation,
        target_url=target_url,
    )
    session: AeatSessionPort = result.session
    return session, settings


__all__ = ["active_verified_session"]
