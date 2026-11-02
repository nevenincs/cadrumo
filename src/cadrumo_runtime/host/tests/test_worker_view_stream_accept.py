"""The worker's view listener keeps accepting after a peer is refused at accept, as the other listeners do."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo_client.contracts.contracts import (
    ACCEPT_REFUSALS_THAT_KEEP_LISTENING,
    ChannelWake,
    RefusalCode,
    RefusalError,
)
from cadrumo_client.contracts.view_stream import ViewClosedReason, ViewWorkerBind

from ...adapters.worker_native_identity import worker_view_namespace
from ...adapters.worker_transport import WorkerChannel, worker_endpoint
from ..view_stream_state import close_view_leg_quietly
from ..view_stream_worker_link import open_worker_view_leg
from ..worker_view_stream import WorkerViewStream
from .test_view_stream_relay import _operation_id, _same_process_worker
from .view_stream_host_support import synthetic_worker_identity

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VERSION = "test"
_WAIT_SECONDS = 20.0


def _wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + _WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.02)


@pytest.mark.parametrize("refusal", sorted(ACCEPT_REFUSALS_THAT_KEEP_LISTENING, key=lambda code: code.value))
def test_a_refusal_that_keeps_listeners_listening_leaves_the_view_listener_serving_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refusal: RefusalCode
) -> None:
    identity = synthetic_worker_identity()
    bind = ViewWorkerBind(operation_id=_operation_id(), session_id=uuid4())
    endpoint = worker_endpoint(storage_root=tmp_path, worker_namespace=worker_view_namespace(identity.worker_id))
    real_accept = endpoint.accept
    refused: list[bool] = []

    def accept_after_one_refusal(*, timeout: float | None = 5.0, wakes: tuple[ChannelWake, ...] = ()) -> WorkerChannel:
        if not refused:
            refused.append(True)
            raise RefusalError(refusal)
        return real_accept(timeout=timeout, wakes=wakes)

    monkeypatch.setattr(endpoint, "accept", accept_after_one_refusal)
    stream = WorkerViewStream(
        endpoint=endpoint,
        identity=identity,
        parent_pid=os.getpid(),
        product_version=_VERSION,
        bind=bind,
    )
    legs: list[WorkerChannel] = []
    try:
        _wait_until(lambda: bool(refused))
        bound, channel = open_worker_view_leg(
            storage_root=tmp_path, identity=identity, verify=_same_process_worker, product_version=_VERSION
        )
        legs.append(channel)
        assert bound == bind
        _wait_until(lambda: stream.connected)
    finally:
        for leg in legs:
            close_view_leg_quietly(leg)
        stream.close(ViewClosedReason.CANCELLED)
