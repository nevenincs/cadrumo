"""A profile worker waits for its next request on the channel, ending only for input, failure or cancellation."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_client.transport.windows_channel import WindowsChannel
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerRequest, ProfileWorkerSubmissionAbortRequest

from .. import worker_operation_requests as requests

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows transport"),
]


@contextmanager
def _pair(tmp_path: Path) -> Generator[tuple[WindowsChannel, WindowsChannel]]:
    """The worker's end and the runtime's end of one real named pipe."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir(parents=True)
    endpoint = WindowsEndpoint(storage_root=root)
    endpoint.listen()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            accepted = pool.submit(endpoint.accept, timeout=5)
            worker = endpoint.connect(timeout=5)
            runtime = accepted.result(timeout=5)
        try:
            yield worker, runtime
        finally:
            worker.close()
            runtime.close()
    finally:
        endpoint.close()


@pytest.fixture
def pair(tmp_path: Path) -> Generator[tuple[WindowsChannel, WindowsChannel]]:
    with _pair(tmp_path) as connected:
        yield connected


def _request() -> ProfileWorkerRequest:
    return ProfileWorkerRequest(
        root=ProfileWorkerSubmissionAbortRequest(
            request_id=uuid4(), upload_id=uuid4(), connection_id=uuid4(), session_id=uuid4()
        )
    )


def test_an_idle_receive_waits_until_the_worker_fails(pair: tuple[WindowsChannel, WindowsChannel]) -> None:
    worker, _runtime = pair

    async def scenario() -> None:
        failed = asyncio.Event()
        receiving = asyncio.create_task(requests.receive(worker, failed, input_executor))
        await asyncio.sleep(0.3)
        assert not receiving.done()
        failed.set()
        with pytest.raises(RefusalError) as caught:
            await asyncio.wait_for(receiving, 2)
        assert caught.value.reason is RefusalCode.UNAVAILABLE

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="profile-worker-input") as input_executor:
        asyncio.run(scenario())


def test_a_cancelled_receive_releases_the_channel_and_loses_no_request(
    pair: tuple[WindowsChannel, WindowsChannel],
) -> None:
    worker, runtime = pair

    async def scenario() -> None:
        failed = asyncio.Event()
        receiving = asyncio.create_task(requests.receive(worker, failed, input_executor))
        await asyncio.sleep(0.2)
        receiving.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(receiving, 2)
        request = _request()
        write_document(runtime, request, deadline=time.monotonic() + 5)
        assert await asyncio.wait_for(requests.receive(worker, failed, input_executor), 2) == request

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="profile-worker-input") as input_executor:
        asyncio.run(scenario())


def test_repeated_requests_reuse_owned_input_threads(
    pair: tuple[WindowsChannel, WindowsChannel], monkeypatch: pytest.MonkeyPatch
) -> None:
    worker, runtime = pair
    started: list[Thread] = []
    original_start = Thread.start

    def count_start(thread: Thread) -> None:
        if thread.name.startswith("profile-worker-input"):
            started.append(thread)
        original_start(thread)

    monkeypatch.setattr(Thread, "start", count_start)

    async def scenario() -> None:
        failed = asyncio.Event()
        for _ in range(24):
            request = _request()
            write_document(runtime, request, deadline=time.monotonic() + 5)
            assert await requests.receive(worker, failed, input_executor) == request

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="profile-worker-input") as input_executor:
        asyncio.run(scenario())
    assert len(started) <= 2, f"24 requests started {len(started)} native input threads"
    assert all(not thread.is_alive() for thread in started)


def test_control_and_operation_channels_wait_independently_on_the_shared_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = (Event(), Event())
    started: list[Thread] = []
    original_start = Thread.start

    def count_start(thread: Thread) -> None:
        if thread.name.startswith("profile-worker-input"):
            started.append(thread)
        original_start(thread)

    monkeypatch.setattr(Thread, "start", count_start)
    with _pair(tmp_path / "control") as control, _pair(tmp_path / "operation") as operation:
        channels = (control, operation)
        for index, (worker, _) in enumerate(channels):
            original_wait = worker.wait_readable

            def observe_wait(*wakes, wait=original_wait, signal=entered[index]):
                signal.set()
                return wait(*wakes)

            monkeypatch.setattr(worker, "wait_readable", observe_wait)

        async def scenario() -> None:
            failed = asyncio.Event()
            receiving = [
                asyncio.create_task(requests.receive(worker, failed, input_executor)) for worker, _ in channels
            ]
            try:
                assert all(await asyncio.gather(*(asyncio.to_thread(signal.wait, 2) for signal in entered)))
                first, second = _request(), _request()
                write_document(control[1], first, deadline=time.monotonic() + 5)
                assert await asyncio.wait_for(receiving[0], 2) == first
                assert not receiving[1].done()
                write_document(operation[1], second, deadline=time.monotonic() + 5)
                assert await asyncio.wait_for(receiving[1], 2) == second
            finally:
                for task in receiving:
                    task.cancel()
                await asyncio.gather(*receiving, return_exceptions=True)

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="profile-worker-input") as input_executor:
            asyncio.run(scenario())
    assert len(started) == 2
    assert all(not thread.is_alive() for thread in started)
