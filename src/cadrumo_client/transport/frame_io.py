"""Strict bounded document and secret frames with complete projection transfers.

Every runtime peer frames through this module, the profile worker included, so
it imports only the frame contracts. The runtime's request and reply documents
are imported by the transfers that carry them.
"""

from __future__ import annotations

import base64
import json
import struct
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex

from ..contracts.contracts import ByteChannel, RefusalCode, RefusalError
from ..contracts.session_events import ConnectionEvent, EventFrame
from ..contracts.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from .transport_cleanup import close_transport_after_failure

if TYPE_CHECKING:
    from ..contracts.access_management import ProfileResume, SessionInventoryReply, SessionInventoryTransfer
    from ..contracts.bootstrap import PasswordReset
    from ..contracts.enrollment_access import EnrollmentSubmit
    from ..contracts.operation_access import OperationSecret
    from ..contracts.profile_access import ProfileLogin, ProfileStatus, ProfileStatusTransfer

MAXIMUM_FRAME_BYTES = 64 * 1024


MAXIMUM_SECRET_BYTES = 64 * 1024


DOCUMENT_FRAME_KIND = b"J"
SESSION_EVENT_FRAME_KIND = b"E"


_SECRET = b"S"


type SecretBearingRequest = ProfileLogin | ProfileResume | PasswordReset | OperationSecret | EnrollmentSubmit


def read_frame_payload(channel: ByteChannel, *, kind: bytes, deadline: float) -> bytes:
    """Read exactly one kind-checked bounded frame before interpreting its content."""
    header = channel.read_exact(5, deadline=deadline)
    size = struct.unpack("!I", header[1:])[0]
    if header[:1] != kind or not 0 < size <= MAXIMUM_FRAME_BYTES:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return channel.read_exact(size, deadline=deadline)


def _read_frame(channel: ByteChannel, *, kind: bytes, deadline: float) -> bytes:
    try:
        return read_frame_payload(channel, kind=kind, deadline=deadline)
    except BaseException as error:
        # A partial frame cannot be safely resumed as another document.
        close_transport_after_failure(channel, error)
        raise


def decode_document[Model: BaseModel](payload: bytes, model: type[Model]) -> Model:
    """Decode strict canonical JSON without retaining rejected document bytes."""
    try:
        document = json.loads(
            payload, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        return model.model_validate_json(canonical_json_bytes(document))
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise RefusalError(RefusalCode.INVALID_FRAME) from None


def read_document[Model: BaseModel](channel: ByteChannel, model: type[Model], *, deadline: float) -> Model:
    """Validate strict typed JSON without copying rejected input into errors."""
    payload = _read_frame(channel, kind=DOCUMENT_FRAME_KIND, deadline=deadline)
    try:
        return decode_document(payload, model)
    except RefusalError as error:
        close_transport_after_failure(channel, error)
        raise


def read_reply_or_event[Model: BaseModel](
    channel: ByteChannel, model: type[Model], *, deadline: float
) -> Model | ConnectionEvent:
    """Demultiplex only at a complete reply boundary, never inside a secret or transfer."""
    try:
        header = channel.read_exact(5, deadline=deadline)
        size = struct.unpack("!I", header[1:])[0]
        if header[:1] not in {DOCUMENT_FRAME_KIND, SESSION_EVENT_FRAME_KIND} or not 0 < size <= MAXIMUM_FRAME_BYTES:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        payload = channel.read_exact(size, deadline=deadline)
        if header[:1] == SESSION_EVENT_FRAME_KIND:
            return decode_document(payload, EventFrame).root
        return decode_document(payload, model)
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise


def write_session_event(channel: ByteChannel, event: ConnectionEvent, *, deadline: float) -> None:
    """Write a bounded event using the connection's existing sole writer."""
    frame = SESSION_EVENT_FRAME_KIND + document_frame(event)[1:]
    try:
        channel.write_all(frame, deadline=deadline)
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise


def _unnamed_optional_members(document: BaseModel) -> set[str]:
    """Name the members a document leaves out while they are unset.

    A peer built before such a member existed refuses a document that carries
    it, so the member travels only when it says something. The document's
    model declares those members as ``frame_omits_when_unset``.
    """
    omitted: object = getattr(type(document), "frame_omits_when_unset", frozenset())
    if not isinstance(omitted, frozenset):
        return set()
    return {name for name in omitted if isinstance(name, str) and getattr(document, name) is None}


def document_frame(document: BaseModel) -> bytes:
    """Build one bounded credential-free JSON frame before channel ownership changes."""
    payload = canonical_json_bytes(document.model_dump(mode="json", exclude=_unnamed_optional_members(document)))
    if not 0 < len(payload) <= MAXIMUM_FRAME_BYTES:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return DOCUMENT_FRAME_KIND + struct.pack("!I", len(payload)) + payload


def write_document(channel: ByteChannel, document: BaseModel, *, deadline: float) -> None:
    """Write one credential-free typed document through the bounded protocol."""
    frame = document_frame(document)
    try:
        channel.write_all(frame, deadline=deadline)
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise


def write_profile_status(channel: ByteChannel, status: ProfileStatus, *, deadline: float) -> None:
    """Retain the complete effective scope while every individual frame stays bounded."""
    from ..contracts.profile_access import ProfileStatusTransfer

    _write_bounded_reply(channel, status, ProfileStatusTransfer, deadline=deadline)


def write_session_inventory(channel: ByteChannel, inventory: SessionInventoryReply, *, deadline: float) -> None:
    """Retain every session and scope fact through the existing bounded transfer."""
    from ..contracts.access_management import SessionInventoryTransfer

    _write_bounded_reply(channel, inventory, SessionInventoryTransfer, deadline=deadline)


def _write_bounded_reply(
    channel: ByteChannel,
    reply: ProfileStatus | SessionInventoryReply,
    transfer_type: type[ProfileStatusTransfer] | type[SessionInventoryTransfer],
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
        error = RefusalError(RefusalCode.INVALID_FRAME)
        for name in ("_transport_cleanup", "async_cleanup_error"):
            if name in failure.__dict__:
                error.__dict__[name] = failure.__dict__[name]
        close_transport_after_failure(channel, error)
        raise error from None
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise


def read_profile_status(channel: ByteChannel, header: ProfileStatusTransfer, *, deadline: float) -> ProfileStatus:
    """Release only a complete, strictly decoded status matching its transfer identity."""
    from ..contracts.profile_access import ProfileStatus

    return _read_bounded_reply(channel, header, ProfileStatus, deadline=deadline)


def read_session_inventory(
    channel: ByteChannel, header: SessionInventoryTransfer, *, deadline: float
) -> SessionInventoryReply:
    """Release only a complete inventory matching the admitted native reply identity."""
    from ..contracts.access_management import SessionInventoryReply

    return _read_bounded_reply(channel, header, SessionInventoryReply, deadline=deadline)


def _read_bounded_reply[Reply: ProfileStatus | SessionInventoryReply](
    channel: ByteChannel,
    header: ProfileStatusTransfer | SessionInventoryTransfer,
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


def write_secret(channel: ByteChannel, secret: bytearray, *, deadline: float) -> None:
    """Consume a borrowed buffer on an already authenticated internal channel."""
    try:
        if not 0 < len(secret) <= MAXIMUM_SECRET_BYTES:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        channel.write_all(_SECRET + struct.pack("!I", len(secret)), deadline=deadline)
        channel.write_all(secret, deadline=deadline)
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise
    finally:
        secret[:] = bytes(len(secret))


@contextmanager
def read_secret(channel: ByteChannel, *, deadline: float) -> Generator[bytearray]:
    """Lend one bounded secret frame and wipe its mutable copy on every exit."""
    secret = bytearray(_read_frame(channel, kind=_SECRET, deadline=deadline))
    try:
        yield secret
    finally:
        secret[:] = bytes(len(secret))
