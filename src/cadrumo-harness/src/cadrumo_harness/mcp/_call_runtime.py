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

import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Sequence
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


def _terminate_tree(process: subprocess.Popen[str]) -> None:
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
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        taskkill = shutil.which("taskkill")
        if taskkill is None:
            process.kill()
            return
        subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv is fixed
            [taskkill, "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def run_supervised(
    argv: Sequence[str],
    *,
    timeout_s: float,
    encoding: str,
    errors: str = "replace",
) -> SupervisedResult:
    """Run ``argv`` with a wall-clock ceiling and process-tree termination.

    The child is started in its own process group / session so its whole tree can
    be signalled, ``stdin`` is isolated to ``DEVNULL`` (an agent console never
    answers an interactive prompt), and on timeout the tree is terminated and
    ``timed_out`` is set. Best-effort partial output is captured after a kill.

    Returns:
        The :class:`SupervisedResult`.
    """
    creationflags = 0
    start_new_session = False
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        start_new_session = True

    process = subprocess.Popen(  # noqa: S603  # nosem
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding=encoding,
        errors=errors,
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _terminate_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return SupervisedResult(
            executable=str(argv[0]),
            stdout=stdout or "",
            stderr=stderr or "",
            returncode=-1,
            timed_out=True,
        )
    return SupervisedResult(
        executable=str(argv[0]),
        stdout=stdout or "",
        stderr=stderr or "",
        returncode=process.returncode,
        timed_out=False,
    )
