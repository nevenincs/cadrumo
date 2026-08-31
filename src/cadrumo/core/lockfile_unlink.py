"""Share-violation-tolerant lockfile removal shared by the crash-recoverable locks.

Every PID-stamped lockfile in this project is inspected by its waiters: a
process that finds the lock taken opens the file to read the holder's PID and
decide whether the holder is still alive. On Windows the CRT opens that read
without ``FILE_SHARE_DELETE``, so for as long as the reader's handle is open the
holder's ``unlink`` is refused with ``ERROR_SHARING_VIOLATION`` -- surfaced by
CPython as :class:`PermissionError` with ``winerror == 32``.

Left uncaught on a release path that is a **wedge**, not a delay: the lockfile
survives stamped with a PID that is still a live process, so no peer will ever
reclaim it as stale, and every later acquirer blocks to its own timeout. The
subsystem the lock guards is unusable until the holder exits.

The window is small but not theoretical. Under cross-process contention on this
project's own bucket lock, three of four contending processes stranded their
lockfile this way within a few seconds.

Two dispositions cover every call site, and which one applies is a property of
the caller, not of the error:

- **Releasing a lock this process holds** must retry to a deadline. Nobody else
  can clear it, so giving up strands the lock.
- **Reclaiming a lock judged stale**, or a best-effort cleanup, must not retry
  and must not raise. Losing that race costs one more poll, and the next
  attempt reclaims it.

Both are :func:`unlink_lockfile` with different retry budgets, so the two lock
subsystems and the locale catalogue guard cannot drift apart on the handling.

A blocked removal is never reported as a success. Windows cannot distinguish
contention from a denying ACL at the unlink boundary, so the retry budget is
what separates them: a transient block clears inside the window, and anything
that outlasts it comes back as ``False`` for the caller to refuse on.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ._windows_contention import is_windows_contention
from .logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

_log = get_logger(__name__)

LOCKFILE_UNLINK_RETRY_SECONDS = 10.0
"""Default budget for retrying a blocked release; a reader's handle lives microseconds."""

_UNLINK_POLL_SECONDS = 0.02


def unlink_lockfile(
    path: Path,
    *,
    retry_seconds: float = 0.0,
    reason: str,
) -> bool:
    """Remove ``path``, waiting out a peer's open read handle if asked to.

    Args:
        path: The lockfile to remove. An already-absent file is a success.
        retry_seconds: How long to keep retrying while the removal is refused
            with a sharing violation. ``0.0`` (the default) makes a single
            best-effort attempt suitable for a stale reclaim.
        reason: Short call-site tag carried into the debug log.

    Returns:
        ``True`` when the lockfile is gone -- removed here or already absent.
        ``False`` when a sharing violation outlasted ``retry_seconds``; the
        caller decides whether that is a refusal or one more poll.

    Raises:
        OSError: For any removal failure Windows does not report as contention,
            and for every ``PermissionError`` off Windows, where no
            sharing-violation class exists to confuse it with.
    """
    deadline = time.monotonic() + max(retry_seconds, 0.0)
    while True:
        try:
            path.unlink(missing_ok=True)
        except PermissionError as exc:
            if not is_windows_contention(exc):
                raise
            if time.monotonic() >= deadline:
                _log.debug(
                    "lockfile unlink blocked by an open handle reason=%s retry_seconds=%s",
                    reason,
                    retry_seconds,
                )
                return False
            time.sleep(_UNLINK_POLL_SECONDS)
            continue
        return True


__all__ = ["LOCKFILE_UNLINK_RETRY_SECONDS", "unlink_lockfile"]
