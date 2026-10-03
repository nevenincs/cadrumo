"""Bounded byte framing and nonsecret readiness before profile credential delivery."""

from __future__ import annotations

import asyncio
import base64
import json
import struct
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import RLock
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, SecretBytes, ValidationError

from ...application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
    RuntimeSessionInventoryTransfer,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.enrollment_access import (
    EnrollmentCredentialBinding,
    RuntimeEnrollmentClientReply,
    RuntimeEnrollmentDelivery,
    RuntimeEnrollmentIdle,
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContractReply,
    RuntimeOperationManaged,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationPayloadReady,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
    RuntimeOperationSubmitted,
)
from ...application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeProfileStatusTransfer,
    RuntimeReply,
    RuntimeSecretReady,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SUBMISSION_PAYLOAD_MAX_BYTES,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from ...application.runtime.transport import RuntimeStatusRequest, RuntimeTransportStatus
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...core.async_cleanup import AsyncResourceCleanupError, attach_async_cleanup_error
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex

MAXIMUM_FRAME_BYTES = 64 * 1024
MAXIMUM_SECRET_BYTES = 64 * 1024
_DOCUMENT = b"J"
_SECRET = b"S"

type _SecretBearingRequest = (
    RuntimeProfileLogin | RuntimeProfileResume | RuntimeOperationSecret | RuntimeEnrollmentSubmit
)


class RuntimeTransportResource(Protocol):
    """Native transport ownership with synchronous release."""

    def close(self) -> None:
        """Release the owned channel, connection or listener."""
        ...


class RuntimeTransportCleanup:
    """Retain native transport release, with success-only close bookkeeping."""

    def __init__(self, resource: RuntimeTransportResource) -> None:
        """Keep native transport ownership until its release succeeds."""
        self.resource = resource
        self._released = False
        self._close_guard = RLock()

    def close_now(self, *, deadline: float | None = None) -> None:
        """Release synchronously at the owning native failure boundary."""
        if deadline is None:
            self._close_guard.acquire()
        elif not self._close_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            if not self._released:
                self.resource.close()
                self._released = True
        finally:
            self._close_guard.release()

    @property
    def released(self) -> bool:
        """Report successful release for its enclosing connection owner."""
        return self._released

    async def close(self) -> None:
        """Keep blocking native release off the event loop, including retries."""
        await asyncio.to_thread(self.close_now)


def close_runtime_transport_after_failure(
    resource: RuntimeByteChannel | VerifiedRuntimeConnection, error: BaseException
) -> None:
    """Preserve a primary refusal and retain its failed native release for retry."""
    retained = error.__dict__.get("_runtime_transport_cleanup")
    if isinstance(retained, RuntimeTransportCleanup) and retained.resource is resource:
        return
    owner = RuntimeTransportCleanup(resource)
    error.__dict__["_runtime_transport_cleanup"] = owner
    try:
        owner.close_now()
    except BaseException as cleanup_failure:
        cleanup_error = AsyncResourceCleanupError(
            (owner,), (cleanup_failure,), retry_task_name="runtime-transport-cleanup", close_attempts=1
        )
        attach_async_cleanup_error(
            error,
            cleanup_error,
            note="Transport cleanup also failed; retry through the attached async_cleanup_error",
        )


def _read_frame_payload(channel: RuntimeByteChannel, *, kind: bytes, deadline: float) -> bytes:
    header = channel.read_exact(5, deadline=deadline)
    size = struct.unpack("!I", header[1:])[0]
    if header[:1] != kind or not 0 < size <= MAXIMUM_FRAME_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return channel.read_exact(size, deadline=deadline)


def _read_frame(channel: RuntimeByteChannel, *, kind: bytes, deadline: float) -> bytes:
    try:
        return _read_frame_payload(channel, kind=kind, deadline=deadline)
    except BaseException as error:
        # A partial frame cannot be safely resumed as another document.
        close_runtime_transport_after_failure(channel, error)
        raise


def _decode_document[Model: BaseModel](payload: bytes, model: type[Model]) -> Model:
    try:
        document = json.loads(
            payload, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        return model.model_validate_json(canonical_json_bytes(document))
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None


def read_document[Model: BaseModel](channel: RuntimeByteChannel, model: type[Model], *, deadline: float) -> Model:
    """Validate strict typed JSON without copying rejected input into errors."""
    payload = _read_frame(channel, kind=_DOCUMENT, deadline=deadline)
    try:
        return _decode_document(payload, model)
    except RuntimeRefusalError as error:
        close_runtime_transport_after_failure(channel, error)
        raise


def _document_frame(document: BaseModel) -> bytes:
    payload = canonical_json_bytes(document.model_dump(mode="json"))
    if not 0 < len(payload) <= MAXIMUM_FRAME_BYTES:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return _DOCUMENT + struct.pack("!I", len(payload)) + payload


def write_document(channel: RuntimeByteChannel, document: BaseModel, *, deadline: float) -> None:
    """Write one credential-free typed document through the bounded protocol."""
    frame = _document_frame(document)
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


class VerifiedRuntimeConnection:
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
            channel.write_all(_document_frame(expected), deadline=deadline)
            hello = _decode_document(
                _read_frame_payload(channel, kind=_DOCUMENT, deadline=deadline), RuntimeServerHello
            )
            if hello.product_version != expected.product_version:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            if hello.storage_identity != expected.storage_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
            self.hello = hello
            self._closed = False
        except BaseException as error:
            self._close_after_failure(error)
            raise

    def _close_after_failure(self, error: BaseException) -> None:
        retained = error.__dict__.get("_runtime_transport_cleanup")
        if isinstance(retained, RuntimeTransportCleanup) and retained.resource is self._channel:
            # An inner frame failure already attempted this native release.
            # Fence exchanges now, and let its retained owner retry through
            # the connection's success-only channel-close bookkeeping.
            self._closed = True
            self._channel_closed = retained.released
            retained.resource = self
            return
        close_runtime_transport_after_failure(self, error)

    @contextmanager
    def _exchange(self, *, deadline: float, secret: bytearray | None = None) -> Generator[None]:
        """Include queueing in the total budget without closing another caller's exchange."""
        try:
            remaining = remaining_budget(deadline)
            if not self._exchange_lock.acquire(timeout=remaining):
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            try:
                yield
            finally:
                self._exchange_lock.release()
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))

    @property
    def connection_id(self) -> UUID | None:
        """Return the last verified non-bearer connection identity, if any."""
        with self._exchange_lock:
            return self._connection_id

    def status(self, request: RuntimeStatusRequest, *, deadline: float) -> RuntimeTransportStatus:
        """Read transport facts without treating readiness as profile authentication."""
        with self._exchange(deadline=deadline):
            if self._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            try:
                write_document(self._channel, request, deadline=deadline)
                result = read_document(self._channel, RuntimeTransportStatus, deadline=deadline)
                self._verify_reply(request.request_id, result.request_id, result.runtime_boot_id, result.connection_id)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def send_secret(self, secret: bytearray, *, deadline: float) -> None:
        """Consume a one-shot secret buffer after peer and cohort verification."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_secret(self._channel, secret, deadline=deadline)
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def owner_control(
        self, request: RuntimeStopPreviewRequest | RuntimeStopConfirm, *, deadline: float
    ) -> RuntimeStopPreview | RuntimeStopAccepted | RuntimeAccessRefusal:
        """Use a dedicated OS-owner connection, independently of profile proof."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if isinstance(result, RuntimeAccessRefusal):
                    return result
                if (isinstance(request, RuntimeStopPreviewRequest) and isinstance(result, RuntimeStopPreview)) or (
                    isinstance(request, RuntimeStopConfirm) and isinstance(result, RuntimeStopAccepted)
                ):
                    return result
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _reply(self, request_id: UUID, *, deadline: float) -> RuntimeReply:
        if self._closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        result = read_document(self._channel, RuntimeReply, deadline=deadline)
        self._verify_reply(request_id, result.root.request_id, result.root.runtime_boot_id, result.root.connection_id)
        if isinstance(result.root, RuntimeProfileStatusTransfer):
            result = RuntimeReply(read_profile_status(self._channel, result.root, deadline=deadline))
        elif isinstance(result.root, RuntimeSessionInventoryTransfer):
            result = RuntimeReply(read_session_inventory(self._channel, result.root, deadline=deadline))
        return result

    def _verify_reply(self, expected: UUID, received: UUID, boot: UUID, connection: UUID) -> None:
        if (
            expected != received
            or boot != self.hello.boot_id
            or (self._connection_id is not None and self._connection_id != connection)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._connection_id = connection

    def _deliver_secret(
        self, request: _SecretBearingRequest, secret: bytearray, *, deadline: float
    ) -> tuple[RuntimeSecretReady, RuntimeReply] | RuntimeAccessRefusal:
        """Send one request, then its secret only after the peer's correlated readiness.

        A refusal before readiness is returned without consuming the secret.
        Otherwise the readiness document and the peer's final reply come back.
        """
        write_document(self._channel, request, deadline=deadline)
        ready = self._reply(request.request_id, deadline=deadline).root
        if isinstance(ready, RuntimeAccessRefusal):
            return ready
        if not isinstance(ready, RuntimeSecretReady):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self.send_secret(secret, deadline=deadline)
        return ready, self._reply(request.request_id, deadline=deadline)

    def login(
        self, request: RuntimeProfileLogin, secret: bytearray, *, deadline: float
    ) -> RuntimeProfileStatus | RuntimeAccessRefusal:
        """Consume credentials only after the exact peer accepts this login request."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                ready, reply_document = delivered
                result = reply_document.root
                if (
                    not isinstance(result, (RuntimeProfileStatus, RuntimeAccessRefusal))
                    or result.connection_id != ready.connection_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def session(
        self, request: RuntimeSessionRequest, *, deadline: float
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal:
        """Use one current connection's lease; copied IDs confer no authority."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(result, (RuntimeProfileStatus, RuntimeSessionsLocked, RuntimeAccessRefusal)):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def recovery_prepare(
        self, request: RuntimeProfileRecoveryPrepare, *, deadline: float
    ) -> RuntimeProfileRecoveryPrepared | RuntimeAccessRefusal:
        """Read exact nonsecret lock state before a separate human proof."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeProfileRecoveryPrepared | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeProfileRecoveryPrepared) and reply.profile_id != request.profile_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def deny_automation(
        self, request: RuntimeAutomationDeny, *, deadline: float
    ) -> RuntimeAutomationDenied | RuntimeAccessRefusal:
        """Return only the durable denial receipt for this exact profile change."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeAutomationDenied | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeAutomationDenied) and (
                    reply.receipt.request_id != request.request_id or reply.receipt.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def resume_profile(
        self, request: RuntimeProfileResume, password: bytearray, *, deadline: float
    ) -> RuntimeProfileResumed | RuntimeAccessRefusal:
        """Send proof only after correlated readiness and verify the selected generation."""
        with self._exchange(deadline=deadline, secret=password):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, password, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                _, reply_document = delivered
                reply = reply_document.root
                if not isinstance(reply, RuntimeProfileResumed | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeProfileResumed) and (
                    reply.receipt.request_id != request.request_id
                    or reply.receipt.profile_id != request.profile_id
                    or reply.receipt.lock_generation != request.lock_generation
                    or not reply.receipt.reactivated_grants <= request.grants
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                password[:] = bytes(len(password))

    def session_inventory(
        self, request: RuntimeSessionInventory, *, deadline: float
    ) -> RuntimeSessionInventoryReply | RuntimeAccessRefusal:
        """Read an allowlisted inventory for exactly this profile."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeSessionInventoryReply | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeSessionInventoryReply) and any(
                    session.profile_id != request.profile_id for session in reply.sessions
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def operation_secret(
        self, request: RuntimeOperationSecret, secret: bytearray, *, deadline: float
    ) -> RuntimeOperationAcknowledged | RuntimeAccessRefusal:
        """Deliver bytes only after current authority accepts this exact requirement."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                _, reply_document = delivered
                result = reply_document.root
                if not isinstance(result, RuntimeOperationAcknowledged | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(result, RuntimeOperationAcknowledged) and (
                    result.operation_id != request.requirement.identity.operation_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def enrollment_prepare(
        self, request: RuntimeEnrollmentPrepare, *, deadline: float
    ) -> RuntimeEnrollmentPrepared | RuntimeAccessRefusal:
        """Mint a request only on this verified native connection."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeEnrollmentPrepared | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if (
                    isinstance(reply, RuntimeEnrollmentPrepared)
                    and reply.profile_binding.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_submit(
        self, request: RuntimeEnrollmentSubmit, proposal: bytearray, *, deadline: float
    ) -> RuntimeEnrollmentRecorded | RuntimeAccessRefusal:
        """Submit proposal bytes only after one correlated secret-ready document."""
        with self._exchange(deadline=deadline, secret=proposal):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, proposal, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                _, reply_document = delivered
                reply = reply_document.root
                if not isinstance(reply, RuntimeEnrollmentRecorded | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeEnrollmentRecorded) and (
                    reply.receipt.request_id != request.enrollment_request_id
                    or reply.receipt.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_inspect(
        self, request: RuntimeEnrollmentInspect | RuntimeEnrollmentReconcile, *, deadline: float
    ) -> RuntimeEnrollmentRecorded | RuntimeEnrollmentIdle | RuntimeAccessRefusal:
        """Read an exact receipt through its live offer or fresh root admission."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeEnrollmentRecorded | RuntimeEnrollmentIdle | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeEnrollmentRecorded) and (
                    reply.receipt.request_id != request.enrollment_request_id
                    or reply.receipt.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_poll(
        self,
        request: RuntimeEnrollmentPoll,
        *,
        store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
        possession: Callable[[EnrollmentCredentialBinding], SecretBytes | None],
        deadline: float,
    ) -> RuntimeEnrollmentDelivery | RuntimeEnrollmentIdle | RuntimeAccessRefusal:
        """Finish one bound client command, including its secret frame and final reply."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, RuntimeEnrollmentIdle | RuntimeAccessRefusal):
                    return reply
                if not isinstance(reply, RuntimeEnrollmentDelivery) or (
                    reply.credential.profile_binding.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                proof: SecretBytes | None = None
                if reply.action == "store":
                    with read_secret(self._channel, deadline=deadline) as candidate:
                        try:
                            store(reply.credential, SecretBytes(bytes(candidate)))
                        except AutomationCustodyError as error:
                            response = RuntimeEnrollmentClientReply(
                                command_id=reply.command_id, outcome="refused", code=error.reason
                            )
                        else:
                            response = RuntimeEnrollmentClientReply(command_id=reply.command_id, outcome="stored")
                else:
                    try:
                        proof = possession(reply.credential)
                    except AutomationCustodyError as error:
                        response = RuntimeEnrollmentClientReply(
                            command_id=reply.command_id, outcome="refused", code=error.reason
                        )
                    else:
                        response = RuntimeEnrollmentClientReply(
                            command_id=reply.command_id, outcome="present" if proof is not None else "missing"
                        )
                write_document(self._channel, response, deadline=deadline)
                if response.outcome == "present":
                    if proof is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                    self.send_secret(bytearray(proof.get_secret_value()), deadline=deadline)
                final = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(final, RuntimeEnrollmentIdle | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply if isinstance(final, RuntimeEnrollmentIdle) else final
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def close(self) -> None:
        """Stop exchanges immediately and retry failed owned channel cleanup."""
        with self._exchange_lock:
            self._closed = True
            if not self._channel_closed:
                self._channel.close()
                self._channel_closed = True

    def operation(
        self, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply | RuntimeAccessRefusal:
        """Use only registered operation doors bound to this live profile connection."""
        if isinstance(request, RuntimeOperationSecret | RuntimeOperationSubmitPayload):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                if isinstance(request, RuntimeOperationSubmit):
                    try:
                        streamed = len(canonical_json_bytes(request.model_dump(mode="json"))) > MAXIMUM_FRAME_BYTES
                    except (UnicodeError, ValueError):
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
                    if streamed:
                        return self._submit_payload(request, deadline=deadline)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(
                    result,
                    RuntimeOperationSubmitted
                    | RuntimeOperationAcknowledged
                    | RuntimeOperationObserved
                    | RuntimeOperationContractReply
                    | RuntimeOperationProjected
                    | RuntimeOperationPage
                    | RuntimeOperationManaged
                    | RuntimeAccessRefusal,
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _submit_payload(
        self, request: RuntimeOperationSubmit, *, deadline: float
    ) -> RuntimeOperationSubmitted | RuntimeAccessRefusal:
        """Stream private UTF-8 under the existing exchange lock and exact readiness."""
        try:
            content = bytearray(request.payload_json, "utf-8")
        except UnicodeError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        try:
            if not 2 <= len(content) <= SUBMISSION_PAYLOAD_MAX_BYTES:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            descriptor = SubmissionPayloadDescriptor(byte_count=len(content), payload_digest=sha256_hex(bytes(content)))
            begin = RuntimeOperationSubmitPayload(
                request_id=request.request_id,
                profile_id=request.profile_id,
                session_id=request.session_id,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
                idempotency_key=request.idempotency_key,
                descriptor=descriptor,
            )
            write_document(self._channel, begin, deadline=deadline)
            ready = self._reply(request.request_id, deadline=deadline).root
            if isinstance(ready, RuntimeAccessRefusal):
                return ready
            if not isinstance(ready, RuntimeOperationPayloadReady) or ready.descriptor != descriptor:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            for offset in range(0, len(content), SUBMISSION_PAYLOAD_CHUNK_BYTES):
                write_secret(
                    self._channel, content[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES], deadline=deadline
                )
            submitted = self._reply(request.request_id, deadline=deadline).root
            if not isinstance(submitted, RuntimeOperationSubmitted | RuntimeAccessRefusal):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return submitted
        finally:
            content[:] = bytes(len(content))


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
    except BaseException as error:
        close_runtime_transport_after_failure(channel, error)
        raise
