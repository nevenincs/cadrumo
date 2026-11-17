"""Profile identity and runtime-client binding for one CLI invocation."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .common import active_bucket_id_or_refuse


def active_profile_id() -> UUID:
    """Return the immutable profile selected for this invocation."""
    return UUID(active_bucket_id_or_refuse())


def active_profile_client(ctx: typer.Context) -> FrontendClient:
    """Bind the invocation client to the selected profile."""
    return require_profile_client(ctx, expected_profile_id=active_profile_id())


def exact_profile_client(ctx: typer.Context, profile_id: UUID) -> FrontendClient:
    """Refuse a different requested profile before binding the invocation client."""
    expected_profile_id = active_profile_id()
    if profile_id != expected_profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return require_profile_client(ctx, expected_profile_id=expected_profile_id)
