"""One exact authenticated runtime client owned by a parsed CLI invocation."""

from __future__ import annotations

from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

_CONTEXT_KEY = "cadrumo.cli.runtime_profile_client"


def bind_profile_client(ctx: typer.Context, client: RuntimeFrontendClient, *, profile_id: UUID) -> None:
    """Transfer one verified CLI client's lifetime to the parsed invocation."""
    if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.CLI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if _CONTEXT_KEY in ctx.meta:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    ctx.meta[_CONTEXT_KEY] = ctx.with_resource(client)


def bound_profile_client(ctx: typer.Context) -> RuntimeFrontendClient:
    """Return the authenticated connection and its immutable profile target."""
    client = ctx.meta.get(_CONTEXT_KEY)
    if not isinstance(client, RuntimeFrontendClient):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if client.frontend is not OperationFrontendProjection.CLI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return client


def require_profile_client(ctx: typer.Context, *, expected_profile_id: UUID) -> RuntimeFrontendClient:
    """Return only the connection bound to this command's exact target."""
    client = ctx.meta.get(_CONTEXT_KEY)
    if not isinstance(client, RuntimeFrontendClient):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if client.profile_id != expected_profile_id or client.frontend is not OperationFrontendProjection.CLI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return client
