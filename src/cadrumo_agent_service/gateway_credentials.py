"""Credentials bound to the gateway lifetime and startup cancellation."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Generator
from dataclasses import replace
from threading import Event
from typing import override

from cadrumo_client.contracts.deadline_budget import TimeoutDeadline

from .host.controller import (
    AgentCredentialSource,
    AgentGenerations,
    AgentHostError,
    AgentHostRefusal,
    ResolvedAgentCredentials,
)
from .host.store_lifecycle import InvocationCancellation


class GatewayCredentials(AgentCredentialSource):
    """Provide copies of gateway secrets while the service remains live."""

    def __init__(
        self,
        source: AgentCredentialSource,
        gateway_bearer: bytearray,
        host_token: bytearray,
        closing: Event,
        *,
        startup_cancellation: Callable[[], InvocationCancellation | None] | None = None,
        close_read: Callable[[], None] | None = None,
    ) -> None:
        """Bind the credential source and its cancellation boundary."""
        self._source = source
        self._gateway_bearer = gateway_bearer
        self._host_token = host_token
        self._closing = closing
        self._startup_cancellation = startup_cancellation
        self._close_read = close_read

    @contextlib.contextmanager
    def _read(self, deadline: TimeoutDeadline | None) -> Generator[None]:
        cancellation = self._startup_cancellation() if deadline is not None and self._startup_cancellation else None
        release = (
            cancellation.subscribe(self._close_read) if cancellation is not None and self._close_read else lambda: None
        )
        try:
            if cancellation is not None and cancellation.is_set():
                raise AgentHostError(AgentHostRefusal.CANCELLED)
            yield
        except BaseException as error:
            if cancellation is not None and cancellation.is_set():
                raise AgentHostError(AgentHostRefusal.CANCELLED) from error
            raise
        finally:
            release()

    @override
    def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
        if self._closing.is_set():
            raise AgentHostError(AgentHostRefusal.SIGNED_OUT)
        with self._read(deadline):
            return replace(
                self._source.resolve_for_agent(deadline=deadline),
                gateway_bearer=bytearray(self._gateway_bearer),
                host_token=bytearray(self._host_token),
            )

    @override
    def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations | None:
        if self._closing.is_set():
            return None
        with self._read(deadline):
            return self._source.current_generations(deadline=deadline)
