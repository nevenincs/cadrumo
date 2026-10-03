"""Shared installed composition for authenticated frontend transport."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.core.paths import effective_storage_root
from cadrumo.domain.calculations.registry.authority import published_authority_generation


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


async def open_installed_runtime_client(
    *, profile_id: UUID, frontend: OperationFrontendProjection, timeout: float = 10
) -> RuntimeFrontendClient:
    """Connect to the exact running owner through the installed transport.

    This opens no profile and reads no credential. The caller must explicitly
    authenticate the returned connection and own it for its frontend lifetime.
    An absent or untrusted endpoint returns a typed refusal.
    """
    try:
        root = effective_storage_root().resolve(strict=True)
        product_version = version("cadrumo")
    except (OSError, PackageNotFoundError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root)
    )
    endpoint_cleanup = _InstalledClientCleanup(endpoint.close)
    try:
        launch = RuntimeLaunchDoor(
            endpoint,
            expected=RuntimeClientHello(
                product_version=product_version,
                storage_identity=endpoint.storage_identity,
                authority_generation=published_authority_generation(),
            ),
        )
        client = await RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=frontend, timeout=timeout)
    except BaseException as error:
        await _close_owned_resource(endpoint_cleanup, task_name="installed-runtime-endpoint-close", primary_error=error)
        raise
    try:
        await _close_owned_resource(endpoint_cleanup, task_name="installed-runtime-endpoint-close", primary_error=None)
    except AsyncResourceCleanupError as error:
        refusal = RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
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
