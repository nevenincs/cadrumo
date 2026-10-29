"""Open and authenticate a profile worker's view connection."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import ByteChannel, ClientHello, RefusalCode, RefusalError
from cadrumo_client.contracts.view_stream import ViewWorkerBind
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document
from cadrumo_client.transport.framing import VerifiedConnection

from ..adapters.worker_native_identity import worker_view_namespace
from ..adapters.worker_transport import WorkerChannel, worker_endpoint

_LOGGER = get_logger("cadrumo_runtime.host.view_stream_relay")
_FRAME_SECONDS = 5.0


def _close_quietly(channel: ByteChannel) -> None:
    try:
        channel.close()
    except Exception as error:
        diagnostic_event(_LOGGER, "view_leg_close_failed", fields={"error_type": type(error).__name__}, level=30)


def open_worker_view_leg(
    *,
    storage_root: Path,
    identity: ProfileWorkerIdentity,
    verify: Callable[[WorkerChannel], None],
    product_version: str,
) -> tuple[ViewWorkerBind, WorkerChannel]:
    """Connect to the worker's view endpoint and admit only that worker's own native process.

    ``verify`` is the worker owner's native check of the channel's peer. An
    endpoint nobody listens on means the worker runs no view.
    """
    endpoint = worker_endpoint(storage_root=storage_root, worker_namespace=worker_view_namespace(identity.worker_id))
    try:
        channel = endpoint.connect(timeout=_FRAME_SECONDS)
    except RefusalError as error:
        if error.reason is RefusalCode.ENDPOINT_NOT_READY:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        raise
    try:
        verify(channel)
        deadline = time.monotonic() + _FRAME_SECONDS
        connection = VerifiedConnection(
            channel,
            expected=ClientHello(product_version=product_version, storage_identity=endpoint.storage_identity),
            deadline=deadline,
        )
        if connection.hello.boot_id != identity.runtime_boot_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="view_worker_boot")
        if read_document(channel, ProfileWorkerIdentity, deadline=deadline) != identity:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="view_worker_identity")
        bind = read_document(channel, ViewWorkerBind, deadline=deadline)
    except BaseException:
        _close_quietly(channel)
        raise
    return bind, channel
