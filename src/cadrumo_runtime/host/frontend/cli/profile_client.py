"""The runtime owns opening native CLI profile clients."""

from __future__ import annotations

import asyncio
from uuid import UUID

import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.commands.profile_binding import subscribe_profile_notices
from cadrumo_client.transport.frontend_client import FrontendClient


def open_cli_profile_client(profile_id: UUID, ctx: typer.Context | None = None) -> FrontendClient:
    """Open an exact CLI client and optionally attach its notice lifetime to a command."""
    from cadrumo_client.transport.installed_client import open_installed_client

    client = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        if ctx is not None:
            subscribe_profile_notices(ctx, client)
    except BaseException as primary:
        try:
            client.close()
        except Exception:
            primary.add_note("Profile client cleanup did not complete.")
        raise
    return client
