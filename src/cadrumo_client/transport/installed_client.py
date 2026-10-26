"""Shared installed composition for authenticated frontend transport."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.core.paths import effective_storage_root
from cadrumo.domain.calculations.registry.authority_location import published_authority_generation

from ..contracts.access_vocabulary import AccessScope
from ..contracts.contracts import ClientHello, RefusalCode, RefusalError
from ..contracts.deadline_budget import (
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    bounded_deadline_after,
    remaining_budget,
)
from .frontend_client import FrontendClient
from .posix_endpoint import PosixEndpoint
from .product_version import installed_product_version
from .startup import LaunchDoor
from .windows import WindowsEndpoint


class _InstalledClientCleanup:
    """Retain native endpoint or untransferred client release until successful."""

    def __init__(self, close: Callable[[], None]) -> None:
        self._close = close
        self._released = False

    async def close(self) -> None:
        """Settle blocking release off the frontend loop, including later retries."""
        if not self._released:
            await asyncio.to_thread(self._close)
            self._released = True


async def _close_owned_resource(
    resource: _InstalledClientCleanup, *, task_name: str, primary_error: BaseException | None
) -> None:
    """Preserve earlier retry owners when cancellation arrives during release."""
    try:
        await close_async_resources(resource, task_name=task_name, primary_error=primary_error)
    except asyncio.CancelledError as cancellation:
        failures = _retained_cleanup_failures(primary_error, cancellation)
        if failures:
            retained = failures[0]
            for failure in failures[1:]:
                retained = retained.merged_with(failure)
            cancellation.__dict__["async_cleanup_error"] = retained
            if isinstance(cancellation.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
                cancellation.__dict__["cleanup_error"] = retained
        raise


async def open_installed_client(
    *,
    profile_id: UUID,
    frontend: OperationFrontendProjection,
    timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    scope: AccessScope | None = None,
    presents_pages: bool = False,
) -> FrontendClient:
    """Connect to the exact running owner through the installed transport.

    This opens no profile and reads no credential. The caller must explicitly
    authenticate the returned connection and own it for its frontend lifetime.
    An absent or untrusted endpoint returns a typed refusal. An optional scope
    narrows a later API-key login on this connection. A caller that shows
    pages declares ``presents_pages`` so a page the person chooses elsewhere
    is delivered to this connection.
    """
    deadline = bounded_deadline_after(timeout, subject="installed client")
    try:
        root, product_version, authority_generation = await asyncio.wait_for(
            asyncio.to_thread(_connection_metadata), timeout=remaining_budget(deadline)
        )
    except TimeoutError:
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED) from None
    remaining_budget(deadline)
    endpoint = (
        WindowsEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixEndpoint(storage_root=root, create_namespace=False)
    )
    endpoint_cleanup = _InstalledClientCleanup(endpoint.close)
    try:
        launch = LaunchDoor(
            endpoint,
            expected=ClientHello(
                lifecycle_notices="v1",
                presentation="v1" if presents_pages else None,
                product_version=product_version,
                storage_identity=endpoint.storage_identity,
                authority_generation=authority_generation,
            ),
        )
        client = await FrontendClient.open(
            launch, profile_id=profile_id, frontend=frontend, timeout=remaining_budget(deadline), scope=scope
        )
    except BaseException as error:
        await _close_owned_resource(endpoint_cleanup, task_name="installed-runtime-endpoint-close", primary_error=error)
        raise
    try:
        await _close_owned_resource(endpoint_cleanup, task_name="installed-runtime-endpoint-close", primary_error=None)
    except AsyncResourceCleanupError as error:
        refusal = RefusalError(RefusalCode.UNAVAILABLE)
        refusal.__dict__["async_cleanup_error"] = error
        await _close_owned_resource(
            _InstalledClientCleanup(client.close), task_name="installed-runtime-client-close", primary_error=refusal
        )
        raise refusal from error
    except BaseException as error:
        await _close_owned_resource(
            _InstalledClientCleanup(client.close), task_name="installed-runtime-client-close", primary_error=error
        )
        raise
    return client


def _connection_metadata() -> tuple[Path, str, str | None]:
    """Read immutable connection inputs off the loop before acquiring native resources."""
    try:
        return (
            effective_storage_root().resolve(strict=True),
            installed_product_version(),
            published_authority_generation(),
        )
    except (OSError, PackageNotFoundError):
        # An OS metadata timeout is unavailability, not expiry of the caller's budget.
        raise RefusalError(RefusalCode.UNAVAILABLE) from None


def _retained_cleanup_failures(
    primary_error: BaseException | None,
    cancellation: asyncio.CancelledError,
) -> list[AsyncResourceCleanupError]:
    """Retain each original cleanup owner once when release itself is cancelled."""
    failures: list[AsyncResourceCleanupError] = []
    for error in (primary_error, cancellation):
        if error is None:
            continue
        for name in ("async_cleanup_error", "cleanup_error"):
            failure = error.__dict__.get(name)
            if isinstance(failure, AsyncResourceCleanupError) and all(failure is not prior for prior in failures):
                failures.append(failure)
    return failures
