"""Real proofs that ``python -m cadrumo.entrypoints.tui`` starts a session.

The module is EXECUTED as its own process here, never imported. An entry
point that imports cleanly and fails to start is the defect these exist to
catch, and an import-based assertion cannot see it: the delegation could
name a symbol that resolves and still raise, hang, or reach the CLI on the
way up.

Assertions are against the terminal control sequence a started Textual
session emits and against process behaviour, never against rendered prose.
The prose is locale data read from the same catalogue the app reads, so
asserting it would prove only that one file was consulted twice.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODULE = "cadrumo.entrypoints.tui"
_ALTERNATE_SCREEN = b"?1049h"
"""The control sequence a Textual session emits when it takes the terminal."""

_STARTUP_GRACE_SECONDS = 45.0
"""The longest a cold start may take to reach the terminal."""

_SETTLE_SECONDS = 5.0
"""How long a started session must then stay up.

A delegation that raises on the way up does so while the app is being built
and mounted, which is inside this window; waiting out the whole start-up grace
after the terminal was already taken only spent it.
"""

_REPO_ROOT = Path(__file__).parents[5]


def _isolated_environment(root: Path) -> dict[str, str]:
    """An environment whose only profile store is an empty one of its own.

    The module otherwise reads whatever storage the host happens to hold, and
    what it does next depends on that: an empty store opens registration, a
    populated one opens login or resumes a session, and a store another
    process is writing reports itself as changing and exits. A start-up proof
    that depends on the machine it runs on proves nothing reliably, so the
    process sees a fresh empty store and a fresh secret store every time.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root / "storage")
    environment["CADRUMO_SECRET_STORE_DIR"] = str(root / "secret-store")
    return environment


async def _run_module_async(*, timeout: float, root: Path) -> tuple[int | None, bytes]:
    """Execute the module through the audited async process boundary."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        _MODULE,
        cwd=_REPO_ROOT,
        env=_isolated_environment(root),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stream = process.stdout
    if stream is None:
        raise RuntimeError("the TUI module process has no output pipe")
    received = bytearray()

    # Read into a buffer this frame owns. Cancelling ``communicate()`` on a
    # timeout discards whatever it had already read, which made a session that
    # DID take the terminal look as if it had printed nothing.
    async def drain_until_started() -> bool:
        while chunk := await stream.read(4096):
            received.extend(chunk)
            if _ALTERNATE_SCREEN in received:
                return True
        return False

    async def drain() -> None:
        while chunk := await stream.read(4096):
            received.extend(chunk)

    try:
        started = await asyncio.wait_for(drain_until_started(), timeout=timeout)
        if started:
            await asyncio.wait_for(drain(), timeout=_SETTLE_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()
        return None, bytes(received)
    returncode = await process.wait()
    return returncode, bytes(received)


def _run_module(*, timeout: float, root: Path) -> tuple[int | None, bytes]:
    """Execute the module as a real process and return its status and output."""
    return asyncio.run(_run_module_async(timeout=timeout, root=root))


@pytest.fixture(scope="module")
def module_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[int | None, bytes]:
    """One real execution of the module, read by every proof below."""
    return _run_module(timeout=_STARTUP_GRACE_SECONDS, root=tmp_path_factory.mktemp("tui-module"))


def test_module_execution_starts_a_session_rather_than_raising(module_run: tuple[int | None, bytes]) -> None:
    """The module runs a real full-screen session instead of failing on invocation."""
    status, output = module_run

    assert status is None, (
        f"the session ended by itself with status {status}; a started TUI holds the terminal:\n"
        f"{output.decode('utf-8', errors='replace')[:2000]}"
    )
    assert _ALTERNATE_SCREEN in output, (
        "no session took the terminal:\n" + output.decode("utf-8", errors="replace")[:2000]
    )


def test_module_execution_reports_no_traceback(module_run: tuple[int | None, bytes]) -> None:
    """A delegation that resolves but raises on the way up leaves a traceback."""
    _, output = module_run
    rendered = output.decode("utf-8", errors="replace")

    assert "Traceback (most recent call last)" not in rendered, rendered[:2000]
