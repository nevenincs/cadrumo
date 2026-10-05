"""Strict bounded document and secret frames with complete projection transfers."""

from __future__ import annotations

import base64
import json
import struct
from collections.abc import Generator
from contextlib import contextmanager

from pydantic import BaseModel, ValidationError

from ...application.runtime.access_management import (
    RuntimeProfileResume,
    RuntimeSessionInventoryReply,
    RuntimeSessionInventoryTransfer,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.operation_access import (
    RuntimeOperationSecret,
)
from ...application.runtime.profile_access import (
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeProfileStatusTransfer,
)
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from .runtime_transport_cleanup import close_runtime_transport_after_failure

MAXIMUM_FRAME_BYTES = 64 * 1024


MAXIMUM_SECRET_BYTES = 64 * 1024


DOCUMENT_FRAME_KIND = b"J"


_SECRET = b"S"


type SecretBearingRequest = (
    RuntimeProfileLogin | RuntimeProfileResume | RuntimeOperationSecret | RuntimeEnrollmentSubmit
)


def read_frame_payload(channel: RuntimeByteChannel, *, kind: bytes, deadline: float) -> bytes:
    """Read exactly one kind-checked bounded frame before interpreting its content."""
    header = channel.read_exact(5, deadline=deadline)
    size = struct.unpack("!I", header[1:])[0]
    if header[:1] != kind or not 0 < size <= MAXIMUM_FRAME_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return channel.read_exact(size, deadline=deadline)


def _read_frame(channel: RuntimeByteChannel, *, kind: bytes, deadline: float) -> bytes:
    try:
        return read_frame_payload(channel, kind=kind, deadline=deadline)
    except BaseException as error:
        # A partial frame cannot be safely resumed as another document.
        close_runtime_transport_after_failure(channel, error)
        raise


def decode_document[Model: BaseModel](payload: bytes, model: type[Model]) -> Model:
    """Decode strict canonical JSON without retaining rejected document bytes."""
    try:
        document = json.loads(
            payload, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        return model.model_validate_json(canonical_json_bytes(document))
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


def read_document[Model: BaseModel](channel: RuntimeByteChannel, model: type[Model], *, deadline: float) -> Model:
    """Validate strict typed JSON without copying rejected input into errors."""
    payload = _read_frame(channel, kind=DOCUMENT_FRAME_KIND, deadline=deadline)
    try:
        return decode_document(payload, model)
    except RuntimeRefusalError as error:
        close_runtime_transport_after_failure(channel, error)
        raise


def document_frame(document: BaseModel) -> bytes:
    """Build one bounded credential-free JSON frame before channel ownership changes."""
    payload = canonical_json_bytes(document.model_dump(mode="json"))
    if not 0 < len(payload) <= MAXIMUM_FRAME_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return DOCUMENT_FRAME_KIND + struct.pack("!I", len(payload)) + payload


def write_document(channel: RuntimeByteChannel, document: BaseModel, *, deadline: float) -> None:
    """Write one credential-free typed document through the bounded protocol."""
    frame = document_frame(document)
    try:
        channel.write_all(frame, deadline=deadline)
    except BaseException as error:
        close_runtime_transport_after_failure(channel, error)
        raise


def write_profile_status(channel: RuntimeByteChannel, status: RuntimeProfileStatus, *, deadline: float) -> None:
    """Retain the complete effective scope while every individual frame stays bounded."""
    _write_bounded_reply(channel, status, RuntimeProfileStatusTransfer, deadline=deadline)


def write_session_inventory(
    channel: RuntimeByteChannel, inventory: RuntimeSessionInventoryReply, *, deadline: float
) -> None:
    """Retain every session and scope fact through the existing bounded transfer."""
    _write_bounded_reply(channel, inventory, RuntimeSessionInventoryTransfer, deadline=deadline)


def _write_bounded_reply(
    channel: RuntimeByteChannel,
    reply: RuntimeProfileStatus | RuntimeSessionInventoryReply,
    transfer_type: type[RuntimeProfileStatusTransfer] | type[RuntimeSessionInventoryTransfer],
    *,
    deadline: float,
) -> None:
    payload = canonical_json_bytes(reply.model_dump(mode="json"))
    if len(payload) <= MAXIMUM_FRAME_BYTES:
        write_document(channel, reply, deadline=deadline)
        return
    try:
        header = transfer_type(
            request_id=reply.request_id,
            runtime_boot_id=reply.runtime_boot_id,
            connection_id=reply.connection_id,
            byte_count=len(payload),
            payload_digest=sha256_hex(payload),
        )
        write_document(channel, header, deadline=deadline)
        for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
            write_document(
                channel,
                SubmissionPayloadChunk(
                    offset=offset,
                    encoded=base64.b64encode(payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES]).decode("ascii"),
                ),
                deadline=deadline,
            )
    except (ValueError, TypeError) as failure:
        error = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        for name in ("_runtime_transport_cleanup", "async_cleanup_error"):
            if name in failure.__dict__:
                error.__dict__[name] = failure.__dict__[name]
        close_runtime_transport_after_failure(channel, error)
        raise error from None
    except BaseException as error:
        close_runtime_transport_after_failure(channel, error)
        raise


def read_profile_status(
    channel: RuntimeByteChannel, header: RuntimeProfileStatusTransfer, *, deadline: float
) -> RuntimeProfileStatus:
    """Release only a complete, strictly decoded status matching its transfer identity."""
    return _read_bounded_reply(channel, header, RuntimeProfileStatus, deadline=deadline)


def read_session_inventory(
    channel: RuntimeByteChannel, header: RuntimeSessionInventoryTransfer, *, deadline: float
) -> RuntimeSessionInventoryReply:
    """Release only a complete inventory matching the admitted native reply identity."""
    return _read_bounded_reply(channel, header, RuntimeSessionInventoryReply, deadline=deadline)


def _read_bounded_reply[Reply: RuntimeProfileStatus | RuntimeSessionInventoryReply](
    channel: RuntimeByteChannel,
    header: RuntimeProfileStatusTransfer | RuntimeSessionInventoryTransfer,
    reply_type: type[Reply],
    *,
    deadline: float,
) -> Reply:
    buffer = SubmissionPayloadBuffer(
        SubmissionPayloadDescriptor(byte_count=header.byte_count, payload_digest=header.payload_digest)
    )
    try:
        for _ in range(0, header.byte_count, SUBMISSION_PAYLOAD_CHUNK_BYTES):
            buffer.append(read_document(channel, SubmissionPayloadChunk, deadline=deadline))
        document = json.loads(
            buffer.finish(), object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        reply = reply_type.model_validate_json(canonical_json_bytes(document))
        if (reply.request_id, reply.runtime_boot_id, reply.connection_id) != (
            header.request_id,
            header.runtime_boot_id,
            header.connection_id,
        ):
            raise ValueError("runtime reply transfer identity mismatch")
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


def write_secret(channel: RuntimeByteChannel, secret: bytearray, *, deadline: float) -> None:
    """Consume a borrowed buffer on an already authenticated internal channel."""
    try:
        if not 0 < len(secret) <= MAXIMUM_SECRET_BYTES:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        channel.write_all(_SECRET + struct.pack("!I", len(secret)), deadline=deadline)
        channel.write_all(secret, deadline=deadline)
    except BaseException as error:
        close_runtime_transport_after_failure(channel, error)
        raise
    finally:
        secret[:] = bytes(len(secret))


@contextmanager
def read_secret(channel: RuntimeByteChannel, *, deadline: float) -> Generator[bytearray]:
    """Lend one bounded secret frame and wipe its mutable copy on every exit."""
    secret = bytearray(_read_frame(channel, kind=_SECRET, deadline=deadline))
    try:
        yield secret
    finally:
        secret[:] = bytes(len(secret))
