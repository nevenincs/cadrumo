"""One exact authenticated runtime client owned by a parsed CLI invocation."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Generator
from concurrent.futures import Future
from contextlib import contextmanager, suppress
from contextvars import copy_context
from threading import Thread
from typing import Never
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from ...core.click_context import json_output_requested
from ...core.errors.hierarchy import CadrumoError
from ...core.i18n.render import tr

_CONTEXT_KEY = "cadrumo.cli.runtime_profile_client"
_NOTICE_KEY = "cadrumo.cli.runtime_notice_clients"


class _NoticeSubscriptions:
    def __init__(self) -> None:
        self.clients: set[RuntimeFrontendClient] = set()


def _has_retained_cleanup(error: BaseException) -> bool:
    return any(
        isinstance(error.__dict__.get(field), AsyncResourceCleanupError) and bool(error.__dict__[field].resources)
        for field in ("async_cleanup_error", "cleanup_error")
    )


def _raise_release_setup_failure(
    owner: RuntimeTransportCleanup, failure: BaseException, primary: BaseException | None
) -> Never:
    """Retain the actual transport when the synchronous bridge cannot start."""
    cleanup = AsyncResourceCleanupError(
        (owner,), (failure,), retry_task_name="cli-profile-transport-close", close_attempts=1
    )
    if primary is None:
        raise cleanup from None
    seen: set[int] = set()
    retained_fields: list[str] = []
    for field in ("async_cleanup_error", "cleanup_error"):
        previous = primary.__dict__.get(field)
        if isinstance(previous, AsyncResourceCleanupError):
            retained_fields.append(field)
            if id(previous) not in seen:
                seen.add(id(previous))
                cleanup = previous.merged_with(cleanup)
    field = "cleanup_error" if isinstance(primary, asyncio.CancelledError) else "async_cleanup_error"
    for retained_field in (*retained_fields, field):
        primary.__dict__[retained_field] = cleanup
    raise primary from None


def _release_profile_client(client: RuntimeFrontendClient, primary: BaseException | None) -> None:
    """Preserve a rendered typed primary if its actual native owner stays unsettled."""
    # The command boundary renders a typed error, then raises Exit from
    # that exact error. An unresolved owner cannot be reduced to an int.
    rendered = (
        primary.__cause__ if isinstance(primary, typer.Exit) and isinstance(primary.__cause__, CadrumoError) else None
    )
    release_primary = rendered if rendered is not None else primary
    owner = client.cleanup_owner(primary_error=release_primary)

    def release() -> None:
        asyncio.run(
            close_async_resources(owner, task_name="cli-profile-transport-close", primary_error=release_primary)
        )

    try:
        if not owner.released:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                release()
            else:
                # A synchronous Click scope can be entered by an SDK caller on an
                # active loop. The transport release has no callback to that loop.
                _release_profile_transport_thread(release, owner, release_primary)
    finally:
        _discard_released_profile_cleanup(owner, release_primary)
    if rendered is not None and _has_retained_cleanup(rendered):
        raise rendered from None


@contextmanager
def _owned_profile_client(client: RuntimeFrontendClient) -> Generator[RuntimeFrontendClient]:
    """Release the invocation's exact transport without replacing its primary."""
    try:
        yield client
    except BaseException as error:
        _release_profile_client(client, error)
        raise
    else:
        _release_profile_client(client, None)


def bind_profile_client(ctx: typer.Context, client: RuntimeFrontendClient, *, profile_id: UUID) -> None:
    """Transfer one verified CLI client's lifetime to the parsed invocation."""
    if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.CLI:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if _CONTEXT_KEY in ctx.meta:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    ctx.meta[_CONTEXT_KEY] = ctx.with_resource(_owned_profile_client(client))
    subscribe_profile_notices(ctx, client)


def subscribe_profile_notices(ctx: typer.Context, client: RuntimeFrontendClient) -> None:
    """Attach human-only presentation before authentication, once per invocation client."""
    if not json_output_requested() and sys.stdin.isatty() and sys.stderr.isatty():
        subscriptions = ctx.meta.setdefault(_NOTICE_KEY, _NoticeSubscriptions())
        if not isinstance(subscriptions, _NoticeSubscriptions):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if client in subscriptions.clients:
            return
        message = tr("common.manager.update_pending")

        def notice(_event: object) -> None:
            with suppress(OSError):
                typer.echo(message, err=True)

        ctx.call_on_close(client.subscribe_lifecycle_notices(notice))
        subscriptions.clients.add(client)


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
    client = bound_profile_client(ctx)
    if client.profile_id != expected_profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return client


def _release_profile_transport_thread(
    release: Callable[[], None], owner: RuntimeTransportCleanup, release_primary: BaseException | None
) -> None:
    """Bridge synchronous release through a joined thread while retaining failed native custody."""
    try:
        context = copy_context()
        result: Future[None] = Future()

        def threaded_release() -> None:
            try:
                context.run(release)
            except BaseException as error:
                result.set_exception(error)
            else:
                result.set_result(None)

        thread = Thread(target=threaded_release, name="cli-profile-transport-close")
        thread.start()
    except BaseException as error:
        _raise_release_setup_failure(owner, error, release_primary)
    try:
        result.result()
    finally:
        thread.join()


def _discard_released_profile_cleanup(owner: RuntimeTransportCleanup, release_primary: BaseException | None) -> None:
    """Drop retained resource references only after their native owner reports release."""
    if owner.released and release_primary is not None:
        for field in ("async_cleanup_error", "cleanup_error"):
            cleanup = release_primary.__dict__.get(field)
            if isinstance(cleanup, AsyncResourceCleanupError):
                cleanup.discard_released_resources(owner)
