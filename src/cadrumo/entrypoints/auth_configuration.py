"""Shared frontend composition for the registered authentication operation."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..application.auth.configuration_submission import submit_auth_configuration
from .operation_composition import compose_operation_dependencies

if TYPE_CHECKING:
    from ..application.auth.configuration_result import AuthConfigurePublicResultV1
    from ..application.auth.operation_definitions import AuthConfigureOperationRequest
    from ..application.operations.composition import OperationComposedServices
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def run_auth_configuration(
    request: AuthConfigureOperationRequest,
    *,
    operation: PinnedAuthorityOperation,
    services: OperationComposedServices | None = None,
    event_loop: asyncio.AbstractEventLoop | None = None,
) -> AuthConfigurePublicResultV1:
    """Reuse the running TUI graph or scope the same graph to a CLI invocation.

    TUI calls this door on its profile worker thread. Its running event loop
    owns the service graph; it must never be moved to the worker's new loop.
    """
    if services is not None:
        if event_loop is None or not event_loop.is_running():
            raise ValueError("authentication configuration requires the composed graph's running loop")
        return asyncio.run_coroutine_threadsafe(
            submit_auth_configuration(request, services=services),
            event_loop,
        ).result()

    async def run() -> AuthConfigurePublicResultV1:
        composed = compose_operation_dependencies(authority_operation=operation)
        try:
            return await submit_auth_configuration(request, services=composed)
        finally:
            await composed.shutdown()

    return asyncio.run(run())
