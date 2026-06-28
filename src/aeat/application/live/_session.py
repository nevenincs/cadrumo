"""Live AEAT session acquisition helpers.

This module uses :class:`AeatSession` and :class:`Settings` to acquire
authenticated sessions for live AEAT operations.
"""

from __future__ import annotations

from ...adapters.outbound.aeat.auth import AeatSession
from ...application.auth import ensure_authenticated_aeat_session
from ...core.access_gate import AeatAccessGate
from ...core.config import Settings, load_settings


async def active_verified_session(
    *,
    operation: str = "live-filed-read",
    target_url: str | None = None,
) -> tuple[AeatSession, Settings]:
    """Return an :class:`AeatSession` and :class:`Settings` after enforcing the live-read gate."""
    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    result = await ensure_authenticated_aeat_session(
        settings,
        operation=operation,
        target_url=target_url,
    )
    return result.session, settings


__all__ = ["active_verified_session"]
