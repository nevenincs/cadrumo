"""Use an existing native sign-in for the bootstrap repair report when available."""

from __future__ import annotations

import asyncio

import typer

from cadrumo_client.commands.profile_binding import bind_profile_client
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.sign_in import SignInPresence
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation_client import open_installed_installation_client
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_client.transport.transport_cleanup import TransportCleanup, close_transport_after_failure

from ...application.operations.registry import OperationFrontendProjection
from ...core.async_cleanup import AsyncResourceCleanupError, close_async_resources


async def _current_client() -> FrontendClient | None:
    discovery = await open_installed_installation_client()
    owner = TransportCleanup(discovery)
    try:
        active = await asyncio.to_thread(discovery.active_profile)
    except BaseException as error:
        await close_async_resources(owner, task_name="repair-profile-discovery-close", primary_error=error)
        raise
    await close_async_resources(owner, task_name="repair-profile-discovery-close", primary_error=None)
    if active.presence is not SignInPresence.PRESENT or active.signed_in_profile_id is None:
        return None
    client = await open_installed_client(
        profile_id=active.signed_in_profile_id, frontend=OperationFrontendProjection.CLI
    )
    try:
        # Presence supplies a target only. The runtime must still verify this
        # native connection and its proof; repair never asks for credentials.
        await asyncio.to_thread(client.resume_receipt)
    except BaseException as error:
        await close_async_resources(
            client.cleanup_owner(primary_error=error), task_name="repair-profile-admission-close", primary_error=error
        )
        raise
    return client


def bind_optional_current_profile(ctx: typer.Context) -> None:
    """Bind only a proven current sign-in, preserving unavailable bootstrap repair."""
    try:
        client = asyncio.run(_current_client())
    except (RefusalError, FrontendRefusedError, ProfileReceiptRefusedError) as error:
        for field in ("async_cleanup_error", "cleanup_error"):
            cleanup = error.__dict__.get(field)
            if isinstance(cleanup, AsyncResourceCleanupError) and cleanup.resources:
                raise
        return
    if client is None:
        return
    try:
        bind_profile_client(ctx, client, profile_id=client.profile_id)
    except BaseException as error:
        close_transport_after_failure(client, error)
        raise
