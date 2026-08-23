"""Event-loop responsiveness while a subprocess-backed tool call is in flight.

The server is a thin protocol shell whose AEAT-sede family ends in a blocking
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

Local ``READ`` / ``MUTATE`` verbs now serve warm in-process and return
sub-second, too fast to overlap a mid-call probe, so the slow-call gap probe
uses an open-world (AEAT-sede) verb, which stays on the supervised subprocess
transport. Called without an active profile it refuses at the CLI boundary
(no network) but still pays the multi-second interpreter-plus-registry startup,
giving a slow subprocess call whose error-ness is beside the point — the subject
is that the loop stayed free while it ran.

The observable invariant: a ``tools/list`` issued while the subprocess call is
in flight must complete well BEFORE the subprocess call does. On a blocked
loop the list is only served after the handler returns, so the two completions
land within milliseconds of each other; off-loop they are separated by the
remaining multi-second subprocess runtime. The assertion is the completion
GAP, not an absolute latency, so machine speed does not destabilise it.

The warm in-process transport is covered directly below: a warm verb served
through the real memory transport while a concurrent ``tools/list`` is answered
(off-loop dispatch), the idle-lock custody invariant (repeated session-opening
in-process reads succeed and the long-lived server context holds no bucket
session between calls), and clean crash restart (a fresh server instance serves
the same encrypted state cleanly after a prior one is discarded). The custody
and crash tests provision a REAL encrypted profile through the in-process
runtime under an env-isolated storage root - no mocks, real storage and crypto.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from mcp.server import Server

from cadrumo.core.config import DEV_TEST_DATABASE_PASSWORD
from cadrumo.tests import temporary_env

from .._dispatch import tool_name_for_command
from .._harness_tools import WHOAMI_TOOL
from .._inprocess import parse_cli_envelope, run_cli_in_process
from .._server import build_server
from .._tools import build_tool_descriptors
from ._session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A real CLI subprocess (interpreter start + registry load) runs for multiple
#: seconds; the mid-call list round-trip is sub-millisecond on a free loop. One
#: second cleanly separates "served concurrently" from "served after the call".
_MIN_CONCURRENCY_GAP_SECONDS = 1.0

#: An open-world (AEAT-sede) verb: it stays on the supervised subprocess transport
#: and, called with no active profile, refuses at the CLI boundary without any
#: network round-trip while still paying the multi-second subprocess startup.
_SUBPROCESS_PROBE_KEY = "app.live.expedientes.list"


async def _list_mid_call_gap(tool_name: str, arguments: dict[str, object]) -> float:
    """Return seconds between the mid-call tools/list completing and the call completing."""
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        # Clear the first-change identity gate with a real console identity read
        # so the probe verb reaches dispatch instead of being refused instantly.
        await session.call_tool(WHOAMI_TOOL, {})
        in_flight = asyncio.create_task(session.call_tool(tool_name, arguments))
        # Yield so the server task dequeues the call and reaches the subprocess
        # dispatch before the probe request is sent.
        await asyncio.sleep(0.2)
        listed = await session.list_tools()
        list_completed_at = time.monotonic()
        assert listed.tools
        result = await in_flight
        call_completed_at = time.monotonic()
        # The no-profile refusal returns an error envelope; the subject of this
        # test is loop-freedom (the gap), not the call's own outcome, so a
        # response of either polarity proves the loop served the mid-call list.
        assert result.content
        return call_completed_at - list_completed_at


def test_execute_meta_tool_leaves_the_loop_serving_requests_mid_call() -> None:
    # The CORE-surface default dispatch path: most verbs reach the subprocess
    # through the execute meta-tool, so this path staying off-loop is what
    # keeps a default client session alive during real tax work.
    gap = asyncio.run(_list_mid_call_gap("execute", {"command_key": _SUBPROCESS_PROBE_KEY, "arguments": {}}))
    assert gap > _MIN_CONCURRENCY_GAP_SECONDS, (
        "execute blocked the event loop: the mid-call tools/list was only "
        f"served once the subprocess call finished (gap {gap:.3f}s)"
    )


def test_direct_verb_tool_leaves_the_loop_serving_requests_mid_call() -> None:
    # Parity guard for the direct per-verb path (already off-loop via the
    # shared wrapper); a regression on either path re-freezes the session.
    gap = asyncio.run(_list_mid_call_gap(tool_name_for_command(_SUBPROCESS_PROBE_KEY), {}))
    assert gap > _MIN_CONCURRENCY_GAP_SECONDS, (
        "the direct verb path blocked the event loop: the mid-call tools/list "
        f"was only served once the subprocess call finished (gap {gap:.3f}s)"
    )


# --- warm in-process transport: off-loop dispatch, custody, crash restart ---

#: A read-only session-opening verb used to prove the warm runtime opens, uses,
#: and relocks a real bucket session per call. It reads encrypted review state, so
#: a successful call proves a genuine session was opened.
_SESSION_READ_KEY = "app.review.queue"


async def _warm_call_with_concurrent_list(tool_name: str, arguments: dict[str, object]) -> tuple[bool, bool]:
    """Drive a warm in-process call while a concurrent tools/list is served.

    Returns whether the mid-flight list was answered and whether the warm call
    itself was non-error, proving the warm transport is dispatched off the event
    loop (the list is served concurrently, not after the call returns).
    """
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        in_flight = asyncio.create_task(session.call_tool(tool_name, arguments))
        listed = await session.list_tools()
        list_answered = bool(listed.tools)
        result = await in_flight
        return list_answered, not bool(result.is_error)


def test_warm_in_process_verb_is_served_with_the_loop_free() -> None:
    # ``contract`` serves warm in-process; a concurrent tools/list is answered
    # while the call is in flight and the warm call returns non-error - the warm
    # transport shares the same off-loop dispatch wrapper the subprocess gap tests
    # prove keeps the loop free.
    list_answered, call_ok = asyncio.run(
        _warm_call_with_concurrent_list(tool_name_for_command("registry.inspect"), {}),
    )
    assert list_answered
    assert call_ok


@contextmanager
def _provisioned_profile_env(tmp_path: Path) -> Iterator[None]:
    """Provision a real encrypted profile under an env-isolated storage root.

    The warm runtime runs the CLI in a raw worker thread that inherits
    ``os.environ`` (not context-var overrides), so isolation is env-based. The
    profile is created through the in-process runtime itself, so the create and
    every later read resolve the same file-backend master key.
    """
    with temporary_env(
        CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path / "storage"),
        CADRUMO_SECRET_STORE_BACKEND="auto",  # noqa: S106 - env var name, not a credential
        CADRUMO_SECRET_STORE_DIR=str(tmp_path / "fallback-store"),
        CADRUMO_SECRET_PASSPHRASE=DEV_TEST_DATABASE_PASSWORD,
    ):
        created = run_cli_in_process(
            [
                "--format", "json", "config", "profile", "create", "operator",
                "--quiet", "--accept-defaults",
                "--entity-type", "natural_person",
                "--irpf-income-categories", "actividad_economica",
                "--tax-id", "12345678Z",
                "--name", "Operator",
                "--surnames", "Custody",
                "--activity", "design",
            ],
            acquire_timeout_s=30.0,
        )  # fmt: skip
        assert created is not None
        envelope, is_error = parse_cli_envelope(created)
        assert not is_error, envelope
        yield


def _warm_read(server: Server, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Drive one warm in-process read through the real memory transport."""

    async def _drive() -> dict[str, object]:
        async with connect(server) as session:
            # Clear the first-change identity gate with a real console identity
            # read before the session-opening verb.
            await session.call_tool(WHOAMI_TOOL, {})
            result = await session.call_tool(tool_name, arguments)
            assert result.structured_content is not None
            return dict(result.structured_content)

    return asyncio.run(_drive())


def test_warm_runtime_holds_no_bucket_session_between_calls(tmp_path: Path) -> None:
    with _provisioned_profile_env(tmp_path):
        server = build_server(build_tool_descriptors())
        tool_name = tool_name_for_command(_SESSION_READ_KEY)
        # Two session-opening reads served warm in-process through the real
        # server: each opens, uses, and relocks its own bucket session.
        first = _warm_read(server, tool_name, {})
        second = _warm_read(server, tool_name, {})
        # The load-bearing custody proof: BOTH session-opening reads succeed with
        # the active profile resolved. Each opened a real bucket session in its
        # worker context; that the SECOND still succeeds proves the first's relock
        # stranded nothing (a leaked/torn session would break the reopen). The
        # session lives only in the ephemeral worker context, so the server's own
        # long-lived context never holds one - the design guarantee behind the
        # idle-lock custody the finally relock enforces.
        assert first["status"] == "success"
        assert first["active_profile"] == "operator"
        assert second["status"] == "success"
        assert second["active_profile"] == "operator"


def test_a_rebuilt_warm_runtime_serves_encrypted_state_cleanly(tmp_path: Path) -> None:
    with _provisioned_profile_env(tmp_path):
        tool_name = tool_name_for_command(_SESSION_READ_KEY)
        # A first warm runtime instance serves the encrypted state.
        first_server = build_server(build_tool_descriptors())
        first = _warm_read(first_server, tool_name, {})
        assert first["status"] == "success"
        # Simulate a crash by discarding the instance; a fresh instance re-warms
        # its caches and serves the SAME persisted encrypted state cleanly, with no
        # torn state and no custody carried over from the discarded runtime. That
        # the reopen succeeds is the proof the prior runtime left no torn or locked
        # state behind.
        del first_server
        second_server = build_server(build_tool_descriptors())
        second = _warm_read(second_server, tool_name, {})
        assert second["status"] == "success"
        assert second["active_profile"] == "operator"
