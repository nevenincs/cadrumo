"""Server-side peer handshake admission over the shared native byte channel."""

from __future__ import annotations

from cadrumo_client.contracts.contracts import (
    ByteChannel,
    ClientHello,
    RefusalCode,
    RefusalError,
    ServerHello,
    authority_generation_differs,
)
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.transport_cleanup import close_transport_after_failure


def accept_connection_handshake(channel: ByteChannel, *, identity: ServerHello, deadline: float) -> ClientHello:
    """Complete current-cohort readiness before reading any application secret."""
    try:
        hello = read_document(channel, ClientHello, deadline=deadline)
        # Return only nonsecret native-owner identity even on a cohort/root
        # mismatch, so the client can issue the precise refusal before secrets.
        # No application admission follows unless both sides match below.
        write_document(channel, identity, deadline=deadline)
        if hello.product_version != identity.product_version or authority_generation_differs(
            hello.authority_generation, identity.authority_generation
        ):
            raise RefusalError(RefusalCode.VERSION_MISMATCH)
        if hello.storage_identity != identity.storage_identity:
            raise RefusalError(RefusalCode.ROOT_MISMATCH)
        return hello
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise
