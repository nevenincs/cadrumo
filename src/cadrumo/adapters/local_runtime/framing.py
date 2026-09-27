"""Bounded byte framing and nonsecret readiness before profile credential delivery."""

from __future__ import annotations

import json
import struct
from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContractReply,
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmitted,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeReply,
    RuntimeSecretReady,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.transport import RuntimeStatusRequest, RuntimeTransportStatus
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant

MAXIMUM_FRAME_BYTES = 64 * 1024
MAXIMUM_SECRET_BYTES = 64 * 1024
_DOCUMENT = b"J"
_SECRET = b"S"


def _read_frame(channel: RuntimeByteChannel, *, kind: bytes, deadline: float) -> bytes:
    try:
        header = channel.read_exact(5, deadline=deadline)
        size = struct.unpack("!I", header[1:])[0]
        if header[:1] != kind or not 0 < size <= MAXIMUM_FRAME_BYTES:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return channel.read_exact(size, deadline=deadline)
    except BaseException:
        # A partial frame cannot be safely resumed as another document.
        channel.close()
        raise


def read_document[Model: BaseModel](channel: RuntimeByteChannel, model: type[Model], *, deadline: float) -> Model:
    """Validate strict typed JSON without copying rejected input into errors."""
    payload = _read_frame(channel, kind=_DOCUMENT, deadline=deadline)
    try:
        document = json.loads(
            payload, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        return model.model_validate_json(canonical_json_bytes(document))
    except (ValueError, TypeError, RecursionError, ValidationError):
        channel.close()
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


def write_document(channel: RuntimeByteChannel, document: BaseModel, *, deadline: float) -> None:
    """Write one credential-free typed document through the bounded protocol."""
    payload = canonical_json_bytes(document.model_dump(mode="json"))
    if not 0 < len(payload) <= MAXIMUM_FRAME_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    try:
        channel.write_all(_DOCUMENT + struct.pack("!I", len(payload)) + payload, deadline=deadline)
    except BaseException:
        channel.close()
        raise


def write_secret(channel: RuntimeByteChannel, secret: bytearray, *, deadline: float) -> None:
    """Consume a borrowed buffer on an already authenticated internal channel."""
    try:
        if not 0 < len(secret) <= MAXIMUM_SECRET_BYTES:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        channel.write_all(_SECRET + struct.pack("!I", len(secret)), deadline=deadline)
        channel.write_all(secret, deadline=deadline)
    except BaseException:
        channel.close()
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


class VerifiedRuntimeConnection:
    """A peer-verified, cohort-matched connection with a distinct secret channel.

    Construction completes the nonsecret handshake. Application session
    authority still requires the existing profile admission owner.
    """

    def __init__(self, channel: RuntimeByteChannel, *, expected: RuntimeClientHello, deadline: float) -> None:
        """Complete readiness on a native peer-verified channel or close it."""
        self._channel = channel
        self._closed = True
        self._connection_id: UUID | None = None
        try:
            write_document(channel, expected, deadline=deadline)
            hello = read_document(channel, RuntimeServerHello, deadline=deadline)
            if hello.product_version != expected.product_version:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            if hello.storage_identity != expected.storage_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
            self.hello = hello
            self._closed = False
        except BaseException:
            channel.close()
            raise

    def status(self, request: RuntimeStatusRequest, *, deadline: float) -> RuntimeTransportStatus:
        """Read transport facts without treating readiness as profile authentication."""
        if self._closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        try:
            write_document(self._channel, request, deadline=deadline)
            result = read_document(self._channel, RuntimeTransportStatus, deadline=deadline)
            self._verify_reply(request.request_id, result.request_id, result.runtime_boot_id, result.connection_id)
            return result
        except BaseException:
            self.close()
            raise

    def send_secret(self, secret: bytearray, *, deadline: float) -> None:
        """Consume a one-shot secret buffer after peer and cohort verification."""
        try:
            if self._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            write_secret(self._channel, secret, deadline=deadline)
        except BaseException:
            self.close()
            raise
        finally:
            secret[:] = bytes(len(secret))

    def _reply(self, request_id: UUID, *, deadline: float) -> RuntimeReply:
        if self._closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        result = read_document(self._channel, RuntimeReply, deadline=deadline)
        self._verify_reply(request_id, result.root.request_id, result.root.runtime_boot_id, result.root.connection_id)
        return result

    def _verify_reply(self, expected: UUID, received: UUID, boot: UUID, connection: UUID) -> None:
        if (
            expected != received
            or boot != self.hello.boot_id
            or (self._connection_id is not None and self._connection_id != connection)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._connection_id = connection

    def login(
        self, request: RuntimeProfileLogin, secret: bytearray, *, deadline: float
    ) -> RuntimeProfileStatus | RuntimeAccessRefusal:
        """Consume credentials only after the exact peer accepts this login request."""
        try:
            if self._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            write_document(self._channel, request, deadline=deadline)
            ready = self._reply(request.request_id, deadline=deadline).root
            if isinstance(ready, RuntimeAccessRefusal):
                return ready
            if not isinstance(ready, RuntimeSecretReady):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            self.send_secret(secret, deadline=deadline)
            result = self._reply(request.request_id, deadline=deadline).root
            if (
                not isinstance(result, (RuntimeProfileStatus, RuntimeAccessRefusal))
                or result.connection_id != ready.connection_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return result
        except BaseException:
            self.close()
            raise
        finally:
            secret[:] = bytes(len(secret))

    def session(
        self, request: RuntimeSessionRequest, *, deadline: float
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal:
        """Use one current connection's lease; copied IDs confer no authority."""
        try:
            if self._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            write_document(self._channel, request, deadline=deadline)
            result = self._reply(request.request_id, deadline=deadline).root
            if not isinstance(result, (RuntimeProfileStatus, RuntimeSessionsLocked, RuntimeAccessRefusal)):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return result
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """Close this connection without changing another client's lifetime."""
        self._closed = True
        self._channel.close()

    def operation(
        self, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply | RuntimeAccessRefusal:
        """Use only registered operation doors bound to this live profile connection."""
        try:
            if self._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            write_document(self._channel, request, deadline=deadline)
            result = self._reply(request.request_id, deadline=deadline).root
            if not isinstance(
                result,
                RuntimeOperationSubmitted
                | RuntimeOperationAcknowledged
                | RuntimeOperationObserved
                | RuntimeOperationContractReply
                | RuntimeAccessRefusal,
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return result
        except BaseException:
            self.close()
            raise


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
        if hello.product_version != identity.product_version:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        if hello.storage_identity != identity.storage_identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        return hello
    except BaseException:
        channel.close()
        raise
