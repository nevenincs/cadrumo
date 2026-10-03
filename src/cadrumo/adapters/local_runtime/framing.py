"""Peer-verified runtime handshake and application transport composition."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from .runtime_frame_io import (
    DOCUMENT_FRAME_KIND,
    decode_document,
    document_frame,
    read_document,
    read_frame_payload,
    write_document,
)
from .runtime_operation_transport import RuntimeOperationTransport
from .runtime_transport_cleanup import close_runtime_transport_after_failure


class VerifiedRuntimeConnection(RuntimeOperationTransport):
    """A peer-verified, cohort-matched connection with a distinct secret channel.

    Construction completes the nonsecret handshake. Application session
    authority still requires the existing profile admission owner.
    """

    def __init__(self, channel: RuntimeByteChannel, *, expected: RuntimeClientHello, deadline: float) -> None:
        """Complete readiness on a native peer-verified channel or close it."""
        self._channel = channel
        # One response belongs to one request. Reentrant for login's secret
        # write and for failure paths that close while the exchange is held.
        self._exchange_lock = RLock()
        self._closed = True
        self._channel_closed = False
        self._connection_id: UUID | None = None
        try:
            # This constructor owns failed-handshake cleanup. The public frame
            # helpers close failed exchanges, before an owner can be returned.
            channel.write_all(document_frame(expected), deadline=deadline)
            hello = decode_document(
                read_frame_payload(channel, kind=DOCUMENT_FRAME_KIND, deadline=deadline), RuntimeServerHello
            )
            if hello.product_version != expected.product_version or _authority_generations_differ(
                hello.authority_generation, expected.authority_generation
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            if hello.storage_identity != expected.storage_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
            self.hello = hello
            self._closed = False
        except BaseException as error:
            self._close_after_failure(error)
            raise


def _authority_generations_differ(observed: str | None, expected: str | None) -> bool:
    """Whether both sides name a published authority generation and the names differ.

    A side that resolved no descriptor asserts no generation; the authority
    admission that would read one refuses that case on its own.
    """
    return observed is not None and expected is not None and observed != expected


def accept_runtime_handshake(
    channel: RuntimeByteChannel, *, identity: RuntimeServerHello, deadline: float
) -> RuntimeClientHello:
    """Complete current-cohort readiness before reading any application secret."""
    try:
        hello = read_document(channel, RuntimeClientHello, deadline=deadline)
        # Return only nonsecret native-owner identity even on a cohort/root
        # mismatch, so the client can issue the precise refusal before secrets.
        # No application admission follows unless both sides match below.
        write_document(channel, identity, deadline=deadline)
        if hello.product_version != identity.product_version or _authority_generations_differ(
            hello.authority_generation, identity.authority_generation
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        if hello.storage_identity != identity.storage_identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        return hello
    except BaseException as error:
        close_runtime_transport_after_failure(channel, error)
        raise
