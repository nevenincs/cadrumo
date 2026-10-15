"""Runtime-hosted TUI process execution and lifetime for product assertions."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_MODULE = "cadrumo_runtime.host.frontend.tui"
_ALTERNATE_SCREEN = b"?1049h"
_SETTLE_SECONDS = 5.0
_REPO_ROOT = Path(__file__).parents[6]


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
        "-I",
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
        remaining, _ = await process.communicate()
        received.extend(remaining or b"")
        return None, bytes(received)
    returncode = await process.wait()
    return returncode, bytes(received)


def _run_module(*, timeout: float, root: Path) -> tuple[int | None, bytes]:
    """Execute the module as a real process and return its status and output."""
    return asyncio.run(_run_module_async(timeout=timeout, root=root))


def run_tui_module(root: Path) -> tuple[int | None, bytes]:
    """Run a real host module once, allowing 45 seconds to reach the terminal."""
    return _run_module(timeout=45.0, root=root)
