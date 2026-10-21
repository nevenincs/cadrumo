"""Complete installation replies over bounded document frames.

A storage inventory, a log tail or a reset journal can outgrow one frame. The
reply then travels as a correlated transfer header and ordered chunks, and the
reader releases it only when every chunk arrived and the digest matches.
"""

from __future__ import annotations

import base64
import json

from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex

from ..contracts.access_management import SessionInventoryTransfer
from ..contracts.contracts import ByteChannel, RefusalCode, RefusalError
from ..contracts.installation_requests import (
    INSTALLATION_REPLY_MAX_BYTES,
    InstallationCompleted,
    InstallationFailed,
    InstallationRefused,
    InstallationReplyTransfer,
)
from ..contracts.profile_access import AccessRefusal, ProfileStatusTransfer, Reply
from ..contracts.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from .frame_io import MAXIMUM_FRAME_BYTES, read_document, write_document
from .transport_cleanup import close_transport_after_failure

type InstallationSettledReply = InstallationCompleted | InstallationRefused | InstallationFailed | AccessRefusal
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
    channel: ByteChannel, reply: InstallationSettledReply, payload: bytes, *, deadline: float
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
        InstallationReplyTransfer(
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


def read_installation_reply(channel: ByteChannel, header: InstallationReplyTransfer, *, deadline: float) -> Reply:
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
        reply = Reply.model_validate_json(canonical_json_bytes(document))
        carried = reply.root
        if isinstance(carried, InstallationReplyTransfer | ProfileStatusTransfer | SessionInventoryTransfer):
            raise ValueError("a reply transfer cannot carry another transfer")
        if (carried.request_id, carried.runtime_boot_id, carried.connection_id) != (
            header.request_id,
            header.runtime_boot_id,
            header.connection_id,
        ):
            raise ValueError("installation reply transfer identity mismatch")
        return reply
    except (ValueError, TypeError, RecursionError) as failure:
        error = RefusalError(RefusalCode.INVALID_FRAME)
        for name in ("_transport_cleanup", "async_cleanup_error"):
            if name in failure.__dict__:
                error.__dict__[name] = failure.__dict__[name]
        close_transport_after_failure(channel, error)
        raise error from None
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise
    finally:
        buffer.close()
