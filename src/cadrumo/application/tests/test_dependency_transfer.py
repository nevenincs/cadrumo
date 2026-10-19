"""Retry, free-space and item-lock behaviour of setup transfers, against real errors and a real local server."""

from __future__ import annotations

import asyncio
import errno
import socket
import threading
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

import httpx
import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..dependency_contracts import DependencySetupStep
from ..dependency_transfer import (
    DEPENDENCY_RETRY_POLICY,
    DependencyItemLockedError,
    DependencyRetryPolicy,
    DependencyTransferError,
    classify_transfer_exception,
    classify_transfer_status,
    dependency_item_lock,
    dependency_retry_delay,
    measure_free_bytes,
    require_free_space,
    run_with_retry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Events:
    def __init__(self, *, cancel_after_retries: int | None = None) -> None:
        self.retries: list[tuple[int, float]] = []
        self._cancel_after = cancel_after_retries

    async def step(self, step: DependencySetupStep) -> None:
        del step

    async def transferred(self, *, completed: int, total: int | None) -> None:
        del completed, total

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        self.retries.append((attempt, delay_s))

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel_after is not None and len(self.retries) >= self._cancel_after

    @asynccontextmanager
    async def irreversible(self) -> AsyncGenerator[None]:
        yield


class _Clock:
    """Virtual time: sleeping advances the clock instead of waiting."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept = 0.0

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.slept += seconds

    def monotonic(self) -> float:
        return self.now


@contextmanager
def _scripted_server(statuses: list[int]) -> Generator[tuple[str, list[int]]]:
    """A real HTTP server answering the scripted statuses in turn, then 200."""
    served: list[int] = []

    class Handler(BaseHTTPRequestHandler):
        @override
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:
            status = statuses.pop(0) if statuses else 200
            served.append(status)
            body = b"payload" if status == 200 else b""
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/", served
    finally:
        server.shutdown()
        server.server_close()


def test_backoff_doubles_from_two_seconds_to_a_minute_with_bounded_jitter() -> None:
    policy = DEPENDENCY_RETRY_POLICY
    assert [policy.delay_s(retry, jitter=1.0) for retry in range(1, 8)] == [2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]
    assert policy.delay_s(1, jitter=0.0) == 1.0
    assert policy.delay_s(6, jitter=0.0) == 30.0
    with pytest.raises(ValueError):
        policy.delay_s(0, jitter=0.5)
    with pytest.raises(ValueError):
        policy.delay_s(1, jitter=1.5)


def test_transient_server_errors_are_retried_until_the_download_succeeds() -> None:
    clock = _Clock()
    events = _Events()

    with _scripted_server([503, 429, 502]) as (url, served):

        async def fetch() -> bytes:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content

        body = asyncio.run(
            run_with_retry(fetch, events=events, sleep=clock.sleep, monotonic=clock.monotonic, jitter=lambda: 1.0)
        )
    assert body == b"payload"
    assert served == [503, 429, 502, 200]
    assert events.retries == [(2, 2.0), (3, 4.0), (4, 8.0)]
    assert clock.slept == 14.0


def test_a_permanent_status_is_final_on_the_first_attempt() -> None:
    clock = _Clock()
    events = _Events()
    with _scripted_server([404]) as (url, served):

        async def fetch() -> bytes:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content

        with pytest.raises(DependencyTransferError) as caught:
            asyncio.run(run_with_retry(fetch, events=events, sleep=clock.sleep, monotonic=clock.monotonic))
    assert served == [404]
    assert caught.value.category is DependencyFailureCategory.UNEXPECTED
    assert caught.value.transient is False
    assert caught.value.facts == {"http_status": 404, "attempts": 1}
    assert events.retries == []


def test_retries_stop_at_the_attempt_budget_and_report_a_final_failure() -> None:
    clock = _Clock()
    events = _Events()
    attempts = 0

    async def refused() -> None:
        nonlocal attempts
        attempts += 1
        raise ConnectionRefusedError(errno.ECONNREFUSED, "refused")

    with pytest.raises(DependencyTransferError) as caught:
        asyncio.run(
            run_with_retry(refused, events=events, sleep=clock.sleep, monotonic=clock.monotonic, jitter=lambda: 1.0)
        )
    assert attempts == DEPENDENCY_RETRY_POLICY.max_attempts
    assert caught.value.category is DependencyFailureCategory.HOST_UNREACHABLE
    assert caught.value.transient is False
    assert caught.value.facts["attempts"] == 6
    assert [attempt for attempt, _delay in events.retries] == [2, 3, 4, 5, 6]


def test_no_retry_starts_after_the_time_window_closes() -> None:
    clock = _Clock()
    events = _Events()
    policy = DependencyRetryPolicy(window_s=10.0)

    async def reset() -> None:
        raise ConnectionResetError(errno.ECONNRESET, "reset")

    with pytest.raises(DependencyTransferError) as caught:
        asyncio.run(
            run_with_retry(
                reset, events=events, policy=policy, sleep=clock.sleep, monotonic=clock.monotonic, jitter=lambda: 1.0
            )
        )
    assert events.retries == [(2, 2.0), (3, 4.0)]
    assert caught.value.facts["attempts"] == 3


def test_cancelling_during_the_wait_stops_without_another_attempt() -> None:
    clock = _Clock()
    events = _Events(cancel_after_retries=1)
    attempts = 0

    async def timeout() -> None:
        nonlocal attempts
        attempts += 1
        raise TimeoutError

    with pytest.raises(DependencyTransferError) as caught:
        asyncio.run(run_with_retry(timeout, events=events, sleep=clock.sleep, monotonic=clock.monotonic))
    assert caught.value.category is DependencyFailureCategory.CANCELLED
    assert attempts == 1


def test_real_errors_map_to_their_categories_and_retry_decisions() -> None:
    def classified(error: BaseException) -> tuple[DependencyFailureCategory, bool]:
        failure = classify_transfer_exception(error)
        return failure.category, failure.transient

    assert classified(OSError(errno.ENOSPC, "full")) == (DependencyFailureCategory.DISK_FULL, False)
    assert classified(PermissionError(errno.EACCES, "denied")) == (DependencyFailureCategory.NO_PERMISSION, False)
    assert classified(ConnectionResetError(errno.ECONNRESET, "reset")) == (
        DependencyFailureCategory.HOST_UNREACHABLE,
        True,
    )
    assert classified(socket.gaierror(socket.EAI_AGAIN, "again")) == (DependencyFailureCategory.HOST_UNREACHABLE, True)
    assert classified(socket.gaierror(socket.EAI_NONAME, "unknown")) == (
        DependencyFailureCategory.HOST_UNREACHABLE,
        False,
    )
    assert classified(httpx.ReadTimeout("slow")) == (DependencyFailureCategory.HOST_UNREACHABLE, True)
    assert classified(httpx.RemoteProtocolError("cut short")) == (DependencyFailureCategory.HOST_UNREACHABLE, True)
    assert classified(ValueError("odd")) == (DependencyFailureCategory.UNEXPECTED, False)
    assert classify_transfer_status(200) is None
    for status, category, transient in (
        (500, DependencyFailureCategory.HOST_UNREACHABLE, True),
        (429, DependencyFailureCategory.HOST_UNREACHABLE, True),
        (407, DependencyFailureCategory.BLOCKED_BY_NETWORK, False),
        (410, DependencyFailureCategory.UNEXPECTED, False),
    ):
        failure = classify_transfer_status(status)
        assert failure is not None
        assert (failure.category, failure.transient) == (category, transient)
    with pytest.raises(ValueError, match="never retried"):
        DependencyTransferError(DependencyFailureCategory.DISK_FULL, transient=True)


def test_free_space_is_measured_on_the_volume_a_new_install_lands_on(tmp_path: Path) -> None:
    future = tmp_path / "not-yet" / "created"
    free = measure_free_bytes(future)
    assert free is not None and free > 0
    assert require_free_space(future, download_bytes=0) > 0
    with pytest.raises(DependencyTransferError) as caught:
        require_free_space(future, download_bytes=free * 10)
    assert caught.value.category is DependencyFailureCategory.DISK_FULL
    assert caught.value.facts["free_space_measured"] is True
    assert int(caught.value.facts["required_bytes"]) > free


def test_the_item_lock_refuses_a_second_writer_without_waiting(tmp_path: Path) -> None:
    locks = tmp_path / "receipts"
    with dependency_item_lock(locks, "browser") as held:
        assert held.parent == locks
        with pytest.raises(DependencyItemLockedError), dependency_item_lock(locks, "browser"):
            pass
        with dependency_item_lock(locks, "local_ai"):
            pass
    with dependency_item_lock(locks, "browser"):
        pass
    with pytest.raises(ValueError), dependency_item_lock(locks, "chromium"):
        pass


def test_the_retry_schedule_port_follows_the_policy_and_ends_with_its_budget() -> None:
    assert [dependency_retry_delay(attempt, 0.0, jitter=lambda: 1.0) for attempt in range(1, 7)] == [
        2.0,
        4.0,
        8.0,
        16.0,
        32.0,
        None,
    ]
    assert dependency_retry_delay(2, 15 * 60.0 - 3.0, jitter=lambda: 1.0) is None
    assert dependency_retry_delay(2, 15 * 60.0 - 5.0, jitter=lambda: 1.0) == 4.0
    with pytest.raises(ValueError):
        dependency_retry_delay(0, 0.0)
