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

A client of the 2026-07-28 revision performs no handshake: every request
carries its own protocol version, and ``server/discover`` replaces
``initialize``. :func:`connected_handshake_free_client` connects such a client
to the same real server over framed streams, the path the stdio entry point
serves, so the tests that use it say what that client is served.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Literal

import anyio
from mcp.client import Client
from mcp.client._transport import TransportStreams
from mcp.client.session import ClientSession, ElicitationFnT
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.mcpserver import MCPServer
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import LATEST_PROTOCOL_VERSION

__all__ = ["connected_handshake_free_client", "connected_server_and_client_session"]

_SERVER_EXIT_GRACE_SECONDS = 2.0


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


@asynccontextmanager
async def _served_over_streams(server: Server[Any]) -> AsyncGenerator[TransportStreams]:
    """Run ``server`` over one framed stream pair, with the options the stdio entry point runs it with."""
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        server_read, server_write = server_streams
        finished = anyio.Event()

        async def run() -> None:
            try:
                await server.run(
                    server_read,
                    server_write,
                    server.create_initialization_options(NotificationOptions(), experimental_capabilities={}),
                )
            finally:
                finished.set()

        async with anyio.create_task_group() as serving:
            serving.start_soon(run)
            try:
                yield client_streams
            finally:
                # End of input is how a stdio client leaves; the server then returns of its own accord.
                await client_streams[1].aclose()
                await server_write.aclose()
                with anyio.move_on_after(_SERVER_EXIT_GRACE_SECONDS):
                    await finished.wait()
                serving.cancel_scope.cancel()


@asynccontextmanager
async def connected_handshake_free_client(
    server: Server[Any], *, negotiation: Literal["discover", "pinned"] = "discover"
) -> AsyncGenerator[Client]:
    """Connect a client of the newest protocol revision to ``server``; it never sends ``initialize``.

    With ``discover`` the client asks ``server/discover`` what the server
    speaks and adopts the answer. With ``pinned`` it asks nothing first and
    sends its requests at the newest revision outright. Either way the
    server's first sight of the client is a request that carries its own
    version, over the same framing a stdio connection has.
    """
    async with Client(
        _served_over_streams(server),
        mode="auto" if negotiation == "discover" else LATEST_PROTOCOL_VERSION,
        cache=None,
    ) as client:
        yield client
