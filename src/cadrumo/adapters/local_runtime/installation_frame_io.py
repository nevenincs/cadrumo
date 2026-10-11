"""Complete installation replies over bounded document frames.

A storage inventory, a log tail or a reset journal can outgrow one frame. The
reply then travels as a correlated transfer header and ordered chunks, and the
reader releases it only when every chunk arrived and the digest matches.
"""

from __future__ import annotations

import base64
import json

from ...application.runtime.access_management import RuntimeSessionInventoryTransfer
from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.installation_requests import (
    INSTALLATION_REPLY_MAX_BYTES,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
    RuntimeInstallationReplyTransfer,
)
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatusTransfer, RuntimeReply
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from .runtime_frame_io import MAXIMUM_FRAME_BYTES, read_document, write_document
from .runtime_transport_cleanup import close_runtime_transport_after_failure

type InstallationSettledReply = (
    RuntimeInstallationCompleted | RuntimeInstallationRefused | RuntimeInstallationFailed | RuntimeAccessRefusal
)
"""Every reply that ends one installation act."""


def installation_reply_payload(reply: InstallationSettledReply) -> bytes:
    """Encode one settled reply, refusing one no transfer could carry.

    Raises:
        ValueError: The reply is larger than the transfer bound. Nothing has
            been written, so the caller can still answer with a smaller reply.
    """
    payload = canonical_json_bytes(reply.model_dump(mode="json"))
    if len(payload) > INSTALLATION_REPLY_MAX_BYTES:
        raise ValueError("installation reply exceeds its transfer bound")
    return payload


def write_installation_reply(
    channel: RuntimeByteChannel, reply: InstallationSettledReply, payload: bytes, *, deadline: float
) -> None:
    """Write ``reply`` whole: in one frame when it fits, as a correlated transfer otherwise.

    ``payload`` is the encoding :func:`installation_reply_payload` returned for
    this same reply.
    """
    if len(payload) <= MAXIMUM_FRAME_BYTES:
        write_document(channel, reply, deadline=deadline)
        return
    write_document(
        channel,
        RuntimeInstallationReplyTransfer(
            request_id=reply.request_id,
            runtime_boot_id=reply.runtime_boot_id,
            connection_id=reply.connection_id,
            byte_count=len(payload),
            payload_digest=sha256_hex(payload),
        ),
        deadline=deadline,
    )
    for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
        write_document(
            channel,
            SubmissionPayloadChunk(
                offset=offset,
                encoded=base64.b64encode(payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES]).decode("ascii"),
            ),
            deadline=deadline,
        )


def read_installation_reply(
    channel: RuntimeByteChannel, header: RuntimeInstallationReplyTransfer, *, deadline: float
) -> RuntimeReply:
    """Release only a complete, strictly decoded reply that matches its transfer identity.

    The caller still decides whether the released reply is the one its request expects.
    """
    buffer = SubmissionPayloadBuffer(
        SubmissionPayloadDescriptor(byte_count=header.byte_count, payload_digest=header.payload_digest)
    )
    try:
        for _ in range(0, header.byte_count, SUBMISSION_PAYLOAD_CHUNK_BYTES):
            buffer.append(read_document(channel, SubmissionPayloadChunk, deadline=deadline))
        document = json.loads(
            buffer.finish(), object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        reply = RuntimeReply.model_validate_json(canonical_json_bytes(document))
        carried = reply.root
        if isinstance(
            carried, RuntimeInstallationReplyTransfer | RuntimeProfileStatusTransfer | RuntimeSessionInventoryTransfer
        ):
            raise ValueError("a reply transfer cannot carry another transfer")
        if (carried.request_id, carried.runtime_boot_id, carried.connection_id) != (
            header.request_id,
            header.runtime_boot_id,
            header.connection_id,
        ):
            raise ValueError("installation reply transfer identity mismatch")
        return reply
    except (ValueError, TypeError, RecursionError) as failure:
        error = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        for name in ("_runtime_transport_cleanup", "async_cleanup_error"):
            if name in failure.__dict__:
                error.__dict__[name] = failure.__dict__[name]
        close_runtime_transport_after_failure(channel, error)
        raise error from None
    except BaseException as error:
        close_runtime_transport_after_failure(channel, error)
        raise
    finally:
        buffer.close()
