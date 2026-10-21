"""Peer-verified client handshake and application transport composition."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from ..contracts.contracts import (
    ByteChannel,
    ClientHello,
    RefusalCode,
    RefusalError,
    ServerHello,
    authority_generation_differs,
)
from .frame_io import DOCUMENT_FRAME_KIND, decode_document, document_frame, read_frame_payload
from .operation_transport import OperationTransport


class VerifiedConnection(OperationTransport):
    """A peer-verified, cohort-matched connection with a distinct secret channel.

    Construction completes the nonsecret handshake. Application session
    authority still requires the existing profile admission owner.
    """

    def __init__(self, channel: ByteChannel, *, expected: ClientHello, deadline: float) -> None:
        """Complete readiness on a native peer-verified channel or close it."""
        self._channel = channel
        # One response belongs to one request. Reentrant for login's secret
        # write and for failure paths that close while the exchange is held.
        self._exchange_lock = RLock()
        self._initialize_session_events()
        self._closed = True
        self._channel_closed = False
        self._connection_id: UUID | None = None
        self._lifecycle_notices = expected.lifecycle_notices == "v1"
        try:
            # This constructor owns failed-handshake cleanup. The public frame
            # helpers close failed exchanges, before an owner can be returned.
            channel.write_all(document_frame(expected), deadline=deadline)
            hello = decode_document(
                read_frame_payload(channel, kind=DOCUMENT_FRAME_KIND, deadline=deadline), ServerHello
            )
            if hello.product_version != expected.product_version or authority_generation_differs(
                hello.authority_generation, expected.authority_generation
            ):
                raise RefusalError(RefusalCode.VERSION_MISMATCH)
            if hello.storage_identity != expected.storage_identity:
                raise RefusalError(RefusalCode.ROOT_MISMATCH)
            self.hello = hello
            self._closed = False
        except BaseException as error:
            self._close_after_failure(error)
            raise
