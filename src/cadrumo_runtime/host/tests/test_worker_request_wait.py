"""A profile worker waits for its next request on the channel, ending only for input, failure or cancellation."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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


@pytest.fixture
def pair(tmp_path: Path) -> Generator[tuple[WindowsChannel, WindowsChannel]]:
    """The worker's end and the runtime's end of one real named pipe."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
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
        receiving = asyncio.create_task(requests.receive(worker, failed))
        await asyncio.sleep(0.3)
        assert not receiving.done()
        failed.set()
        with pytest.raises(RefusalError) as caught:
            await asyncio.wait_for(receiving, 2)
        assert caught.value.reason is RefusalCode.UNAVAILABLE

    asyncio.run(scenario())


def test_a_cancelled_receive_releases_the_channel_and_loses_no_request(
    pair: tuple[WindowsChannel, WindowsChannel],
) -> None:
    worker, runtime = pair

    async def scenario() -> None:
        failed = asyncio.Event()
        receiving = asyncio.create_task(requests.receive(worker, failed))
        await asyncio.sleep(0.2)
        receiving.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(receiving, 2)
        request = _request()
        write_document(runtime, request, deadline=time.monotonic() + 5)
        assert await asyncio.wait_for(requests.receive(worker, failed), 2) == request

    asyncio.run(scenario())
