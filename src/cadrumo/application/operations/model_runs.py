"""The port through which a running operation's model work reaches the agent service.

The supervisor binds one port to each executing operation, for the duration of
its executor, from the execution authority the runtime composed. Model work
deep inside an executor finds it through :func:`current_model_run_port`. Code
running outside an operation finds none, and its off-host model work refuses.
Nothing here holds or sees a credential: a run is a request, and the service
that owns provider settings resolves the lane and runs it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol, runtime_checkable

from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRoleSelection,
)

from ...core.model_roles import ModelRole
from .models import OperationIdentity


class ModelRunPort(Protocol):
    """Model work for one running operation, answered by the agent service."""

    async def lookup(self, role: ModelRole) -> ModelRunLane | ModelRunRefusal:
        """Return the lane and model the service would use for ``role``; nothing secret."""
        ...

    async def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        """Return every role's selection state as the service reports it; nothing secret."""
        ...

    async def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        """Run one tool-less request and return its final reply text, or a closed refusal."""
        ...


@runtime_checkable
class OperationModelRuns(Protocol):
    """The execution authority's door to model runs, keyed by the operation that asks."""

    async def model_run_lookup(self, identity: OperationIdentity, role: str) -> ModelRunLane | ModelRunRefusal:
        """Resolve the lane for ``role`` on behalf of the running operation ``identity``."""
        ...

    async def model_run_selections(
        self, identity: OperationIdentity
    ) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        """Read every role's selection state on behalf of the running operation ``identity``."""
        ...

    async def model_run(
        self, identity: OperationIdentity, header: ModelRunHeader, body: ModelRunBody
    ) -> ModelRunOutput | ModelRunRefusal:
        """Run one request on behalf of the running operation ``identity``."""
        ...


_CURRENT: ContextVar[ModelRunPort | None] = ContextVar("cadrumo_model_run_port", default=None)


def current_model_run_port() -> ModelRunPort | None:
    """Return the port bound to the operation this code runs for, or ``None`` outside one."""
    return _CURRENT.get()


@contextmanager
def bound_model_runs(port: ModelRunPort | None) -> Generator[None]:
    """Bind ``port`` for the current context until the block exits."""
    token = _CURRENT.set(port)
    try:
        yield
    finally:
        _CURRENT.reset(token)


class _OperationBoundModelRuns:
    """One operation's port, answered on the loop that runs the operation's supervisor.

    Model work may run on another event loop in a worker thread; its calls are
    handed to the operation's own loop, where the execution authority lives.
    """

    def __init__(self, owner: OperationModelRuns, identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> None:
        self._owner, self._identity, self._loop = owner, identity, loop

    async def lookup(self, role: ModelRole) -> ModelRunLane | ModelRunRefusal:
        return await self._on_owner_loop(self._owner.model_run_lookup(self._identity, role.value))

    async def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        return await self._on_owner_loop(self._owner.model_run_selections(self._identity))

    async def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        return await self._on_owner_loop(self._owner.model_run(self._identity, header, body))

    async def _on_owner_loop[T](self, call: Coroutine[None, None, T]) -> T:
        # Always a task of its own: the authority holds one permit per task, and
        # the caller's task may already hold another.
        if asyncio.get_running_loop() is self._loop:
            return await asyncio.create_task(call)
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(call, self._loop))


def operation_model_run_port(owner: object, identity: OperationIdentity) -> ModelRunPort | None:
    """Return the port for one running operation, or ``None`` when the authority runs no models."""
    if not isinstance(owner, OperationModelRuns):
        return None
    return _OperationBoundModelRuns(owner, identity, asyncio.get_running_loop())


async def run_with_model_runs[T](port: ModelRunPort | None, work: Awaitable[T]) -> T:
    """Await ``work`` with ``port`` bound for everything it runs."""
    with bound_model_runs(port):
        return await work


__all__ = [
    "ModelRunPort",
    "OperationModelRuns",
    "bound_model_runs",
    "current_model_run_port",
    "operation_model_run_port",
    "run_with_model_runs",
]
