"""Real in-memory MCP server+client session, for tests that want no mocks.

``mcp`` 2.0.0 removed ``mcp.shared.memory.create_connected_server_and_client_session``,
the pre-2.0 helper that started a real :class:`~mcp.server.Server` on the SDK's
in-process memory transport and handed back an already-initialized
:class:`~mcp.client.session.ClientSession`. The transport plumbing itself is
still shipped (``mcp.client._memory.InMemoryTransport`` wraps
``mcp.shared.memory.create_client_server_memory_streams`` plus the background
server task), but the 2.x SDK no longer bundles the client-session handshake
on top of it as a standalone function; the maintained public entry point for
that composition is now :class:`mcp.client.Client` in ``mode="legacy"``, which
performs the same handshake (``await session.initialize()`` — the context
manager does NOT call it implicitly) over the same in-memory transport.

:func:`connected_server_and_client_session` reproduces the removed helper's
exact contract on top of ``Client`` so every in-process MCP test in this
project shares one canonical composition instead of five independent
reimplementations.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from mcp.client import Client
from mcp.client.session import ClientSession, ElicitationFnT
from mcp.server import Server
from mcp.server.mcpserver import MCPServer

__all__ = ["connected_server_and_client_session"]


@asynccontextmanager
async def connected_server_and_client_session(
    server: Server[Any] | MCPServer,
    *,
    raise_exceptions: bool = False,
    elicitation_callback: ElicitationFnT | None = None,
) -> AsyncGenerator[ClientSession]:
    """Start ``server`` on the in-process memory transport; yield an initialized session.

    Drives the real handshake (``mode="legacy"``: ``initialize`` request/response,
    byte-identical to the pre-2.0 behaviour) over a real in-memory transport
    against the real ``server`` — no mocks. Response caching is disabled
    (``cache=None``): callers use the yielded ``ClientSession`` directly rather
    than ``Client``'s cached list/read wrappers, so a live cache would sit
    unused while still installing a message-handler eviction wrapper for no
    benefit.
    """
    async with Client(
        server,
        mode="legacy",
        raise_exceptions=raise_exceptions,
        elicitation_callback=elicitation_callback,
        cache=None,
    ) as client:
        yield client.session
