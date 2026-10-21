"""Retry, free space and the per-item writer lock shared by every setup provisioner.

A setup moves gigabytes over networks that reset, stall and throttle. A
transient fault -- a reset or refused connection, a temporary name-resolution
failure, a timeout, an HTTP ``5xx`` or ``429`` -- is retried with exponential
backoff and jitter: from 2 s, doubling to at most 60 s, for at most 6 attempts
inside 15 minutes. Everything else is final on the first attempt: a missing
approval, a full disk, a permission refusal, damaged content, the hardware, a
busy memory, any other ``4xx`` and a build without Google. Each retry is
reported to the person before the wait starts, and cancellation is honoured
during the wait.

Resuming rather than restarting belongs to each item's own mechanism -- the
model program keeps partial blobs, and an incomplete browser build is removed
before only that build downloads again -- so the runner here only decides
whether and when another attempt happens.
"""

from __future__ import annotations

import asyncio
import errno
import random
import shutil
import socket
import ssl
import time
from collections.abc import Awaitable, Callable, Generator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.errors.hierarchy import CadrumoError
from ..core.locks import exclusive_file_lock
from ..core.locks_errors import LockAcquisitionError
from .dependency_contracts import DependencySetupEvents, dependency_item_kind
from .provisioning_contracts import ProvisioningFactValue

__all__ = [
    "DEPENDENCY_RETRY_POLICY",
    "DependencyItemLockedError",
    "DependencyRetryPolicy",
    "DependencyTransferError",
    "classify_transfer_exception",
    "classify_transfer_status",
    "dependency_item_lock",
    "dependency_retry_delay",
    "measure_free_bytes",
    "run_with_retry",
]

_CANCEL_POLL_S: Final = 0.25


@dataclass(frozen=True, slots=True)
class DependencyRetryPolicy:
    """Backoff bounds for transient transfer failures."""

    initial_delay_s: float = 2.0
    max_delay_s: float = 60.0
    max_attempts: int = 6
    window_s: float = 15 * 60.0

    def delay_s(self, retry: int, *, jitter: float) -> float:
        """Return the wait before retry number ``retry`` (1 for the first), with ``jitter`` in ``[0, 1]``.

        The ceiling doubles from the initial delay up to the maximum, and the
        wait lands in its upper half, so retries never bunch together and never
        come sooner than half the backoff.
        """
        if retry < 1:
            raise ValueError("retries are numbered from 1")
        if not 0.0 <= jitter <= 1.0:
            raise ValueError("jitter is a fraction between 0 and 1")
        ceiling = min(self.max_delay_s, self.initial_delay_s * float(1 << (retry - 1)))
        return ceiling * (0.5 + 0.5 * jitter)


DEPENDENCY_RETRY_POLICY: Final = DependencyRetryPolicy()


def dependency_retry_delay(
    failed_attempt: int,
    elapsed_s: float,
    *,
    policy: DependencyRetryPolicy = DEPENDENCY_RETRY_POLICY,
    jitter: Callable[[], float] | None = None,
) -> float | None:
    """Return the wait before the attempt after ``failed_attempt``, or ``None`` when the budget is spent.

    ``failed_attempt`` counts from 1 and ``elapsed_s`` is the time since the
    first attempt began. The budget ends at the policy's last attempt, or
    when the next attempt would start after the time window closes. This is
    the schedule an item's own retry loop follows when it cannot use
    :func:`run_with_retry`.
    """
    if failed_attempt < 1:
        raise ValueError("attempts are numbered from 1")
    if failed_attempt >= policy.max_attempts:
        return None
    fraction = (random.SystemRandom().random if jitter is None else jitter)()
    delay = policy.delay_s(failed_attempt, jitter=fraction)
    if elapsed_s + delay > policy.window_s:
        return None
    return delay


class DependencyTransferError(CadrumoError):
    """One classified transfer failure: its category, whether a retry may help, and safe facts."""

    def __init__(
        self,
        category: DependencyFailureCategory,
        *,
        transient: bool,
        facts: Mapping[str, ProvisioningFactValue] | None = None,
    ) -> None:
        """Record the category, the retry decision and locale-neutral facts."""
        super().__init__(category.value)
        if transient and category in _NEVER_TRANSIENT:
            raise ValueError(f"{category.value} is never retried")
        self.category = category
        self.transient = transient
        self.facts: Mapping[str, ProvisioningFactValue] = {} if facts is None else dict(facts)


_NEVER_TRANSIENT: Final = frozenset(
    {
        DependencyFailureCategory.DISK_FULL,
        DependencyFailureCategory.NO_PERMISSION,
        DependencyFailureCategory.DAMAGED_DOWNLOAD,
        DependencyFailureCategory.NOT_ENOUGH_MEMORY,
        DependencyFailureCategory.MEMORY_BUSY,
        DependencyFailureCategory.NOT_IN_THIS_BUILD,
        DependencyFailureCategory.NEEDS_SIGN_IN,
        DependencyFailureCategory.CANCELLED,
        DependencyFailureCategory.SECURE_CONNECTION_FAILED,
        DependencyFailureCategory.BLOCKED_BY_NETWORK,
    }
)


def classify_transfer_status(status: int) -> DependencyTransferError | None:
    """Classify an HTTP status a transfer received, or ``None`` when it is a success."""
    if status < 400:
        return None
    facts: dict[str, ProvisioningFactValue] = {"http_status": status}
    if status == 429 or status >= 500:
        return DependencyTransferError(DependencyFailureCategory.HOST_UNREACHABLE, transient=True, facts=facts)
    if status in {403, 407}:
        return DependencyTransferError(DependencyFailureCategory.BLOCKED_BY_NETWORK, transient=False, facts=facts)
    return DependencyTransferError(DependencyFailureCategory.UNEXPECTED, transient=False, facts=facts)


_TRANSIENT_ERRNOS: Final = frozenset(
    {
        errno.ECONNRESET,
        errno.ECONNREFUSED,
        errno.ECONNABORTED,
        errno.ETIMEDOUT,
        errno.EPIPE,
        errno.ENETUNREACH,
        errno.EHOSTUNREACH,
        errno.ENETRESET,
    }
)
_DISK_FULL_ERRNOS: Final = frozenset({errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)})
_PERMISSION_ERRNOS: Final = frozenset({errno.EACCES, errno.EPERM, errno.EROFS})
# ERROR_DISK_FULL and ERROR_HANDLE_DISK_FULL, which Windows reports in ``winerror``.
_WINDOWS_DISK_FULL: Final = frozenset({39, 112})


def classify_transfer_exception(error: BaseException) -> DependencyTransferError:
    """Map an exception raised during a transfer onto its category and retry decision.

    Unrecognised errors are ``unexpected`` and never retried: retrying a
    failure nobody understands only hides it for fifteen minutes.
    """
    if isinstance(error, DependencyTransferError):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        classified = classify_transfer_status(error.response.status_code)
        if classified is not None:
            return classified
    if _secure_connection_failed(error):
        return DependencyTransferError(DependencyFailureCategory.SECURE_CONNECTION_FAILED, transient=False)
    if isinstance(error, httpx.TimeoutException | httpx.NetworkError | httpx.RemoteProtocolError):
        return DependencyTransferError(DependencyFailureCategory.HOST_UNREACHABLE, transient=True)
    if isinstance(error, socket.gaierror):
        transient = error.errno == socket.EAI_AGAIN
        return DependencyTransferError(DependencyFailureCategory.HOST_UNREACHABLE, transient=transient)
    if isinstance(error, TimeoutError | ConnectionError):
        return DependencyTransferError(DependencyFailureCategory.HOST_UNREACHABLE, transient=True)
    if isinstance(error, OSError):
        return _classify_os_error(error)
    return DependencyTransferError(DependencyFailureCategory.UNEXPECTED, transient=False)


def _secure_connection_failed(error: BaseException) -> bool:
    """Whether a TLS failure sits anywhere in ``error``'s cause or context chain.

    httpx wraps the transport's own error, which in turn wraps the
    ``ssl.SSLError``, so the direct cause alone does not show it.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if isinstance(current, ssl.SSLError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _classify_os_error(error: OSError) -> DependencyTransferError:
    if error.errno in _DISK_FULL_ERRNOS or getattr(error, "winerror", None) in _WINDOWS_DISK_FULL:
        return DependencyTransferError(DependencyFailureCategory.DISK_FULL, transient=False)
    if isinstance(error, PermissionError) or error.errno in _PERMISSION_ERRNOS:
        return DependencyTransferError(DependencyFailureCategory.NO_PERMISSION, transient=False)
    if error.errno in _TRANSIENT_ERRNOS:
        return DependencyTransferError(DependencyFailureCategory.HOST_UNREACHABLE, transient=True)
    return DependencyTransferError(DependencyFailureCategory.UNEXPECTED, transient=False)


@dataclass(frozen=True, slots=True)
class _RetryClock:
    sleep: Callable[[float], Awaitable[None]]
    monotonic: Callable[[], float]
    jitter: Callable[[], float]


async def run_with_retry[ResultT](
    attempt: Callable[[], Awaitable[ResultT]],
    *,
    events: DependencySetupEvents,
    policy: DependencyRetryPolicy = DEPENDENCY_RETRY_POLICY,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    jitter: Callable[[], float] | None = None,
) -> ResultT:
    """Run ``attempt`` until it succeeds, a failure is final, the budget ends or the person cancels.

    Every exception ``attempt`` raises is classified with
    :func:`classify_transfer_exception`. A transient failure is retried while
    attempts and the time window remain; a retry that would start after the
    window closes is not made. The final failure is raised as a
    :class:`DependencyTransferError`; cancellation raises one with category
    ``cancelled``.
    """
    clock = _RetryClock(
        sleep=sleep, monotonic=monotonic, jitter=random.SystemRandom().random if jitter is None else jitter
    )
    started = clock.monotonic()
    for number in range(1, policy.max_attempts + 1):
        if events.cancellation_requested:
            raise DependencyTransferError(DependencyFailureCategory.CANCELLED, transient=False)
        try:
            return await attempt()
        except asyncio.CancelledError:
            raise
        except Exception as error:  # every attempt failure is classified, never swallowed
            failure = classify_transfer_exception(error)
            if not failure.transient or number == policy.max_attempts:
                raise _final(failure, attempts=number) from error
            delay = policy.delay_s(number, jitter=clock.jitter())
            if clock.monotonic() - started + delay > policy.window_s:
                raise _final(failure, attempts=number) from error
            await events.retrying(attempt=number + 1, delay_s=delay)
            await _cancellable_wait(delay, events=events, clock=clock)
    raise AssertionError("retry loop always returns or raises")


def _final(failure: DependencyTransferError, *, attempts: int) -> DependencyTransferError:
    return DependencyTransferError(failure.category, transient=False, facts={**failure.facts, "attempts": attempts})


async def _cancellable_wait(delay_s: float, *, events: DependencySetupEvents, clock: _RetryClock) -> None:
    remaining = delay_s
    while remaining > 0:
        if events.cancellation_requested:
            raise DependencyTransferError(DependencyFailureCategory.CANCELLED, transient=False)
        step = min(_CANCEL_POLL_S, remaining)
        await clock.sleep(step)
        remaining -= step
    if events.cancellation_requested:
        raise DependencyTransferError(DependencyFailureCategory.CANCELLED, transient=False)


def measure_free_bytes(path: Path) -> int | None:
    """Return the free bytes on the volume holding ``path``, or ``None`` when it cannot be measured.

    ``path`` need not exist yet: the nearest existing ancestor is measured,
    which is the volume a new install will land on.
    """
    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            return None
        candidate = candidate.parent
    try:
        return shutil.disk_usage(candidate).free
    except OSError:
        return None


class DependencyItemLockedError(CadrumoError):
    """Another writer holds this item's setup lock, so this setup must not touch the item."""

    def __init__(self, item_id: str) -> None:
        """Name the item whose lock is held."""
        super().__init__(f"setup item {item_id!r} is being changed by another writer")
        self.item_id = item_id


@contextmanager
def dependency_item_lock(locks_root: Path, item_id: str) -> Generator[Path]:
    """Hold the exclusive setup lock of one item for the duration of a setup, without waiting.

    The lock is the operating system's lock on ``<locks_root>/<item>.setup.lock``,
    so it guards against a writer outside the runtime as well as a second
    runtime. It never waits: a held lock means someone else is changing the
    item right now, and the setup refuses rather than queueing behind them.
    """
    dependency_item_kind(item_id)
    locks_root.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        try:
            lock_path = stack.enter_context(exclusive_file_lock(locks_root / f"{item_id}.setup", timeout=0))
        except LockAcquisitionError as error:
            raise DependencyItemLockedError(item_id) from error
        yield lock_path
