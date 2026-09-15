"""Supervised subprocess runtime for the MCP call path.

Every MCP tool call shells the deterministic ``aeat`` CLI. An un-timed-out
``subprocess.run`` risks a Playwright-backed live pull that stalls - a network
hang, a changed AEAT DOM selector - hanging the MCP call forever, and many
clients time out a ``tools/call`` well under a minute, misreading a legitimate
slow pull as failure. There is also no way to terminate a hung child without an
explicit timeout.

This runtime wraps the call in a per-tier timeout: generous for the
AEAT-sede / live family, tighter for local mutations,
tight for local reads. On timeout it terminates the WHOLE process tree - a
Playwright pull spawns a browser child, so killing only the ``aeat`` process
would strand the browser - and returns a typed timed-out result the caller
renders as an instructive, localized refusal. The tier is derived from the
command's own annotations, so it tracks the classification the gates already use.
Migration to the (deprecated-in-v1, redesigned-in-RC) MCP Tasks mechanism is
deferred until the v2 SDK is stable.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ._settings import load_mcp_settings

if TYPE_CHECKING:
    from anyio import CapacityLimiter

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: Process-wide bound on MCP calls dispatched off the event loop at once, built
#: lazily on first use from the settings-derived capacity so the anyio default
#: (40 threads) never governs. Both transports share it: it caps concurrent
#: supervised subprocess spawns (robustness research F3 - an unbounded burst
#: thrashes CPU/RAM) and concurrent warm in-process worker threads. Cached as a
#: singleton because a ``CapacityLimiter`` must live for the whole server session,
#: not be rebuilt per call.
_SERVING_LIMITER: CapacityLimiter | None = None


def serving_capacity_limiter() -> CapacityLimiter:
    """Return the shared, settings-sized limiter bounding off-loop MCP dispatch.

    Sizes the limiter from ``cadrumo_mcp_serving_concurrency`` on first use and
    reuses it thereafter. Passed to ``anyio.to_thread.run_sync`` so the explicit
    cap replaces the anyio default thread-pool bound for every tool call - the
    robustness research F3 remedy.
    """
    global _SERVING_LIMITER
    if _SERVING_LIMITER is None:
        from anyio import CapacityLimiter

        _SERVING_LIMITER = CapacityLimiter(load_mcp_settings().cadrumo_mcp_serving_concurrency)
    return _SERVING_LIMITER


class CallTier(StrEnum):
    """The timeout tier a command runs under.

    ``LIVE`` is the AEAT-sede / open-world family (a portal pull that may take
    minutes); ``MUTATE`` is a local state change; ``READ`` is a local read.
    """

    READ = "read"
    MUTATE = "mutate"
    LIVE = "live"


#: The per-tier wall-clock ceiling, in seconds. Generous for the live/sede family
#: (a Playwright portal pull legitimately runs for minutes), tighter for local
#: work so a stuck local call fails fast. Local mutations still need enough
#: headroom for cold installed-client startup and registry loading.
_TIER_TIMEOUTS: dict[CallTier, float] = {
    CallTier.READ: 45.0,
    CallTier.MUTATE: 180.0,
    CallTier.LIVE: 420.0,
}


def tier_for(*, read_only: bool, open_world: bool) -> CallTier:
    """Choose the timeout tier from a command's annotations.

    Open-world (AEAT-sede) verbs get the live tier regardless of read/write - a
    portal read can be as slow as a portal write; a local read gets the read
    tier; everything else gets the mutate tier.
    """
    if open_world:
        return CallTier.LIVE
    if read_only:
        return CallTier.READ
    return CallTier.MUTATE


def timeout_seconds(tier: CallTier) -> float:
    """Return the wall-clock ceiling in seconds for ``tier``."""
    return _TIER_TIMEOUTS[tier]


class SupervisedResult(BaseModel):
    """The outcome of a supervised subprocess run.

    ``executable`` is the exact first argv element passed to
    :class:`subprocess.Popen`, giving payload-free telemetry an observation of
    the child origin rather than a separate resolver query. ``timed_out`` is
    true when the process exceeded its tier ceiling and its process tree was
    terminated; ``stdout``/``stderr``/``returncode`` carry the completed process
    output otherwise (and best-effort partial output on timeout).
    """

    model_config = _STRICT_FROZEN

    executable: str
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool


async def _terminate_tree(process: asyncio.subprocess.Process) -> None:
    """Terminate ``process`` and every child it spawned.

    A live pull spawns a browser child, so killing only the top process would
    strand it. On Windows ``taskkill /T`` walks the tree; on POSIX the child was
    started in its own session so the whole process group is signalled.

    Every path must kill something. An unresolvable ``taskkill`` (a trimmed
    ``PATH``, a hardened image) previously returned having terminated nothing at
    all, so a hung call left its whole tree running and the timeout refusal was a
    lie. Falling back to ``process.kill()`` still cannot reach a grandchild
    browser, but killing the direct child is strictly better than killing
    nothing, and it keeps the supervised contract honest.
    """
    if process.returncode is not None:
        return
    if sys.platform == "win32":
        taskkill = shutil.which("taskkill")
        if taskkill is None:
            _kill_process(process)
            return
        killer = await asyncio.create_subprocess_exec(
            taskkill,
            "/F",
            "/T",
            "/PID",
            str(process.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.communicate()
        if process.returncode is None:
            _kill_process(process)
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        _kill_process(process)


def _kill_process(process: asyncio.subprocess.Process) -> None:
    """Kill a process whose tree-level termination path was unavailable."""
    with contextlib.suppress(ProcessLookupError):
        process.kill()


def _decode_output(payload: bytes | None, *, encoding: str, errors: str) -> str:
    """Decode captured child output, treating an absent stream as empty."""
    return (payload or b"").decode(encoding, errors)


async def _create_process(
    argv: Sequence[str],
    *,
    stdin_payload: str | None,
    creationflags: int = 0,
    start_new_session: bool = False,
    env: Mapping[str, str] | None = None,
) -> asyncio.subprocess.Process:
    """Start a no-shell child with isolated streams and an optional stdin payload."""
    if not argv:
        raise ValueError("a subprocess argv must contain an executable")
    return await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE if stdin_payload is not None else asyncio.subprocess.DEVNULL,
        env=None if env is None else dict(env),
        creationflags=creationflags,
        start_new_session=start_new_session,
    )


async def _communicate(
    process: asyncio.subprocess.Process,
    *,
    stdin_payload: str | None,
    encoding: str,
    errors: str,
    timeout_s: float | None,
) -> tuple[str, str]:
    """Collect child streams with an optional wall-clock bound."""
    payload = None if stdin_payload is None else stdin_payload.encode(encoding, errors)
    communicate = process.communicate(payload)
    if timeout_s is None:
        stdout, stderr = await communicate
    else:
        stdout, stderr = await asyncio.wait_for(communicate, timeout=timeout_s)
    return _decode_output(stdout, encoding=encoding, errors=errors), _decode_output(
        stderr,
        encoding=encoding,
        errors=errors,
    )


async def _run_supervised_async(
    argv: Sequence[str],
    *,
    timeout_s: float,
    encoding: str,
    errors: str,
    stdin_payload: str | None,
) -> SupervisedResult:
    """Run one child asynchronously so Ruff's shell heuristic is inapplicable."""
    creationflags = 0
    start_new_session = False
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        start_new_session = True
    process = await _create_process(
        argv,
        stdin_payload=stdin_payload,
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    try:
        stdout, stderr = await _communicate(
            process,
            stdin_payload=stdin_payload,
            encoding=encoding,
            errors=errors,
            timeout_s=timeout_s,
        )
    except TimeoutError:
        await _terminate_tree(process)
        try:
            stdout, stderr = await _communicate(
                process,
                stdin_payload=None,
                encoding=encoding,
                errors=errors,
                timeout_s=5.0,
            )
        except TimeoutError:
            stdout, stderr = "", ""
        return SupervisedResult(
            executable=str(argv[0]),
            stdout=stdout,
            stderr=stderr,
            returncode=-1,
            timed_out=True,
        )
    return SupervisedResult(
        executable=str(argv[0]),
        stdout=stdout,
        stderr=stderr,
        returncode=process.returncode if process.returncode is not None else -1,
        timed_out=False,
    )


async def _run_captured_async(
    argv: Sequence[str],
    *,
    timeout_s: float | None,
    encoding: str,
    errors: str,
    stdin_payload: str | None,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    """Run one no-shell child and expose the stdlib completed-process shape."""
    process = await _create_process(
        argv,
        stdin_payload=stdin_payload,
        env=env,
    )
    stdout = stderr = ""
    try:
        stdout, stderr = await _communicate(
            process,
            stdin_payload=stdin_payload,
            encoding=encoding,
            errors=errors,
            timeout_s=timeout_s,
        )
    except TimeoutError as error:
        await _terminate_tree(process)
        with contextlib.suppress(TimeoutError):
            await _communicate(
                process,
                stdin_payload=None,
                encoding=encoding,
                errors=errors,
                timeout_s=5.0,
            )
        raise subprocess.TimeoutExpired(
            list(argv),
            timeout_s or 0.0,
            output=stdout,
            stderr=stderr,
        ) from error
    return subprocess.CompletedProcess(
        list(argv),
        process.returncode if process.returncode is not None else -1,
        stdout,
        stderr,
    )


def run_captured(
    argv: Sequence[str],
    *,
    timeout_s: float | None = None,
    encoding: str = "utf-8",
    errors: str = "replace",
    stdin_payload: str | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a bounded no-shell child and return decoded stdout and stderr."""
    return asyncio.run(
        _run_captured_async(
            argv,
            timeout_s=timeout_s,
            encoding=encoding,
            errors=errors,
            stdin_payload=stdin_payload,
            env=env,
        ),
    )


def run_supervised(
    argv: Sequence[str],
    *,
    timeout_s: float,
    encoding: str,
    errors: str = "replace",
    stdin_payload: str | None = None,
) -> SupervisedResult:
    """Run ``argv`` with a wall-clock ceiling and process-tree termination.

    The child is started in its own process group / session so its whole tree can
    be signalled, ``stdin`` is isolated to ``DEVNULL`` (an agent console never
    answers an interactive prompt), and on timeout the tree is terminated and
    ``timed_out`` is set. Best-effort partial output is captured after a kill.

    Returns:
        The :class:`SupervisedResult`.
    """
    return asyncio.run(
        _run_supervised_async(
            argv,
            timeout_s=timeout_s,
            encoding=encoding,
            errors=errors,
            stdin_payload=stdin_payload,
        ),
    )
