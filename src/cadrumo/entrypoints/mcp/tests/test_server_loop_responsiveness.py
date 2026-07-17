"""Event-loop responsiveness while a subprocess-backed tool call is in flight.

The server is a thin protocol shell whose every verb ends in a blocking
``Popen.communicate``; both the direct per-verb path and the ``execute`` meta
path must run that work off the event loop so the session keeps serving
pings, tools-list requests, progress heartbeats, and concurrent calls for the
whole call duration (the timeout tiers reach minutes). The regression here is
the ``execute`` meta path: it dispatched the gated subprocess runner
synchronously inside the async ``call_tool`` handler, freezing the entire
session for the full call — the observed Claude client lags, drops, and
hangs on the default CORE surface, where most verbs are reached through
``execute``. The tests drive :func:`build_server` through the real SDK
in-process memory transport (client and server share one event loop, so a
blocked loop is directly observable) and a real CLI subprocess.

The observable invariant: a ``tools/list`` issued while the subprocess call is
in flight must complete well BEFORE the subprocess call does. On a blocked
loop the list is only served after the handler returns, so the two completions
land within milliseconds of each other; off-loop they are separated by the
remaining multi-second subprocess runtime. The assertion is the completion
GAP, not an absolute latency, so machine speed does not destabilise it.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from .._dispatch import tool_name_for_command
from .._server import build_server
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A real CLI subprocess (interpreter start + registry load) runs for multiple
#: seconds; the mid-call list round-trip is sub-millisecond on a free loop. One
#: second cleanly separates "served concurrently" from "served after the call".
_MIN_CONCURRENCY_GAP_SECONDS = 1.0


async def _list_mid_call_gap(tool_name: str, arguments: dict[str, object]) -> float:
    """Return seconds between the mid-call tools/list completing and the call completing."""
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        in_flight = asyncio.create_task(session.call_tool(tool_name, arguments))
        # Yield so the server task dequeues the call and reaches the subprocess
        # dispatch before the probe request is sent.
        await asyncio.sleep(0.2)
        listed = await session.list_tools()
        list_completed_at = time.monotonic()
        assert listed.tools
        result = await in_flight
        call_completed_at = time.monotonic()
        assert result.isError is False
        assert result.content
        return call_completed_at - list_completed_at


def test_execute_meta_tool_leaves_the_loop_serving_requests_mid_call() -> None:
    # The CORE-surface default dispatch path: most verbs reach the subprocess
    # through the execute meta-tool, so this path staying off-loop is what
    # keeps a default client session alive during real tax work.
    gap = asyncio.run(_list_mid_call_gap("execute", {"command_key": "contract", "arguments": {}}))
    assert gap > _MIN_CONCURRENCY_GAP_SECONDS, (
        "execute blocked the event loop: the mid-call tools/list was only "
        f"served once the subprocess call finished (gap {gap:.3f}s)"
    )


def test_direct_verb_tool_leaves_the_loop_serving_requests_mid_call() -> None:
    # Parity guard for the direct per-verb path (already off-loop via the
    # shared wrapper); a regression on either path re-freezes the session.
    gap = asyncio.run(_list_mid_call_gap(tool_name_for_command("contract"), {}))
    assert gap > _MIN_CONCURRENCY_GAP_SECONDS, (
        "the direct verb path blocked the event loop: the mid-call tools/list "
        f"was only served once the subprocess call finished (gap {gap:.3f}s)"
    )
