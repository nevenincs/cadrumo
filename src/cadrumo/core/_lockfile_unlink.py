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

Only the sharing violation is tolerated. A denying ACL or a read-only volume
raises the same :class:`PermissionError` and never clears, so absorbing it
would turn a broken lockfile into an unexplained retry loop.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

_log = get_logger(__name__)

LOCKFILE_UNLINK_RETRY_SECONDS = 10.0
"""Default budget for retrying a blocked release; a reader's handle lives microseconds."""

_UNLINK_POLL_SECONDS = 0.02
_WINDOWS_SHARING_VIOLATION = 32
"""``ERROR_SHARING_VIOLATION``: the file is open in another process.

The tolerance is keyed on this code alone. A ``PermissionError`` carrying any
other code -- a denying ACL, a read-only volume, a directory standing where the
lockfile should be -- describes a condition no amount of waiting resolves, and
absorbing it would report a lockfile as merely contended when it is broken.
"""


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
        OSError: For any removal failure other than a sharing violation. Those
            do not clear on their own, so reporting them as contention would
            hide a broken lockfile behind a retry loop.
    """
    deadline = time.monotonic() + max(retry_seconds, 0.0)
    while True:
        try:
            path.unlink(missing_ok=True)
        except PermissionError as exc:
            if getattr(exc, "winerror", None) != _WINDOWS_SHARING_VIOLATION:
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
