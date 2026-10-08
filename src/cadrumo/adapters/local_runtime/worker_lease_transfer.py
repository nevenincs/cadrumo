"""Bounded full-scope lease transfer over the verified worker control pipe."""

from __future__ import annotations

import base64
import json

from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_worker import (
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerLeaseRequest,
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerRequest,
)
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from .runtime_frame_io import read_document, write_document


def write_worker_lease(channel: RuntimeByteChannel, request: ProfileWorkerRequest, *, deadline: float) -> None:
    """Send exactly one lease command before any separately framed secret."""
    if not isinstance(request.root, ProfileWorkerLeaseRequest | ProfileWorkerHumanBindingRequest):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    try:
        header = ProfileWorkerLeaseTransferRequest(
            request_id=request.root.request_id, byte_count=len(payload), payload_digest=sha256_hex(payload)
        )
        write_document(channel, ProfileWorkerRequest(header), deadline=deadline)
        for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
            write_document(
                channel,
                SubmissionPayloadChunk(
                    offset=offset,
                    encoded=base64.b64encode(payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES]).decode("ascii"),
                ),
                deadline=deadline,
            )
    except (ValueError, TypeError):
        channel.close()
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    except BaseException:
        channel.close()
        raise


def read_worker_lease(
    channel: RuntimeByteChannel, header: ProfileWorkerLeaseTransferRequest, *, deadline: float
) -> ProfileWorkerRequest:
    """Verify complete bytes and command identity before any custody mutation."""
    buffer = SubmissionPayloadBuffer(
        SubmissionPayloadDescriptor(byte_count=header.byte_count, payload_digest=header.payload_digest)
    )
    try:
        for _ in range(0, header.byte_count, SUBMISSION_PAYLOAD_CHUNK_BYTES):
            buffer.append(read_document(channel, SubmissionPayloadChunk, deadline=deadline))
        document = json.loads(
            buffer.finish(), object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        request = ProfileWorkerRequest.model_validate_json(canonical_json_bytes(document))
        if (
            not isinstance(request.root, ProfileWorkerLeaseRequest | ProfileWorkerHumanBindingRequest)
            or request.root.request_id != header.request_id
        ):
            raise ValueError("lease transfer command mismatch")
        return request
    except (ValueError, TypeError, RecursionError):
        channel.close()
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    except BaseException:
        channel.close()
        raise
    finally:
        buffer.close()
