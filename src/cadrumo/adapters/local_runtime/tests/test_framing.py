"""Verified connection cleanup retries retain closed request admission."""

from __future__ import annotations

import base64
import struct
import time
from datetime import UTC, datetime
from typing import override
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.access_management import (
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
    RuntimeSessionInventoryTransfer,
)
from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.profile_access import (
    RuntimeProfileStatus,
    RuntimeProfileStatusTransfer,
    RuntimeSessionRequest,
)
from cadrumo.application.runtime.submission_payload import SUBMISSION_PAYLOAD_CHUNK_BYTES, SubmissionPayloadChunk
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessStatus,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex

from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake
from ..frontend_client import RuntimeFrontendClient
from ..runtime_frame_io import (
    MAXIMUM_FRAME_BYTES,
    read_document,
    read_profile_status,
    read_session_inventory,
    write_document,
    write_profile_status,
    write_secret,
    write_session_inventory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class CleanupChannel:
    """Byte-channel port with an explicit fail-once resource release."""

    def __init__(self, *, close_failures: int) -> None:
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.reads = 0
        self.close_calls = 0
        self.close_failures = close_failures
        self.released = False

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > time.monotonic()
        assert len(self.inbound) >= count
        self.reads += 1
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def read_ready(self) -> bool:
        return bool(self.inbound)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > time.monotonic()
        self.writes.append(bytes(payload))

    def close(self) -> None:
        self.close_calls += 1
        if self.close_calls <= self.close_failures:
            raise OSError("synthetic channel cleanup failure")
        self.released = True


def _connection(channel: CleanupChannel) -> VerifiedRuntimeConnection:
    hello = RuntimeServerHello(product_version="cleanup-test", storage_identity="a" * 64, boot_id=uuid4())
    write_document(channel, hello, deadline=time.monotonic() + 5)
    channel.inbound.extend(b"".join(channel.writes))
    channel.writes.clear()
    return VerifiedRuntimeConnection(
        channel,
        expected=RuntimeClientHello(product_version=hello.product_version, storage_identity=hello.storage_identity),
        deadline=time.monotonic() + 5,
    )


@pytest.mark.parametrize("frontend_owner", [False, True], ids=["verified-connection", "frontend-client"])
def test_close_failure_retries_cleanup_without_reopening_exchanges(frontend_owner: bool) -> None:
    channel = CleanupChannel(close_failures=1)
    connection = _connection(channel)
    owner = (
        RuntimeFrontendClient(connection, profile_id=uuid4(), frontend=OperationFrontendProjection.MCP)
        if frontend_owner
        else connection
    )
    reads_before_close = channel.reads
    writes_before_close = tuple(channel.writes)

    with pytest.raises(OSError, match="synthetic channel cleanup failure"):
        owner.close()
    assert channel.close_calls == 1
    assert channel.released is False

    with pytest.raises(RuntimeRefusalError) as refused:
        connection.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 5,
        )
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert channel.reads == reads_before_close
    assert tuple(channel.writes) == writes_before_close
    assert channel.close_calls == 1

    owner.close()
    assert channel.close_calls == 2
    assert channel.released is True
    owner.close()
    assert channel.close_calls == 2

    secret = bytearray(b"synthetic-never-transmitted-secret")
    with pytest.raises(RuntimeRefusalError) as refused:
        connection.send_secret(secret, deadline=time.monotonic() + 5)
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert not any(secret)
    assert channel.reads == reads_before_close
    assert tuple(channel.writes) == writes_before_close
    assert channel.close_calls == 2


@pytest.mark.parametrize("frontend_owner", [False, True], ids=["verified-connection", "frontend-client"])
def test_successful_close_is_idempotent(frontend_owner: bool) -> None:
    channel = CleanupChannel(close_failures=0)
    connection = _connection(channel)
    owner = (
        RuntimeFrontendClient(connection, profile_id=uuid4(), frontend=OperationFrontendProjection.MCP)
        if frontend_owner
        else connection
    )
    owner.close()
    owner.close()
    assert channel.close_calls == 1
    assert channel.released is True


def _cleanup(error: BaseException) -> AsyncResourceCleanupError:
    cleanup = error.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    return cleanup


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["version", "root", "invalid_header", "invalid_document"])
async def test_rejected_handshake_retains_failed_close_without_replacing_refusal(failure: str) -> None:
    channel = CleanupChannel(close_failures=1)
    hello = RuntimeServerHello(
        product_version="foreign" if failure == "version" else "cleanup-test",
        storage_identity="b" * 64 if failure == "root" else "a" * 64,
        boot_id=uuid4(),
    )
    write_document(channel, hello, deadline=time.monotonic() + 5)
    channel.inbound.extend(b"".join(channel.writes))
    channel.writes.clear()
    if failure == "invalid_header":
        channel.inbound[:] = b"S" + struct.pack("!I", 1) + b"x"
    elif failure == "invalid_document":
        channel.inbound[:] = b"J" + struct.pack("!I", 1) + b"{"
    with pytest.raises(RuntimeRefusalError) as caught:
        VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(product_version="cleanup-test", storage_identity="a" * 64),
            deadline=time.monotonic() + 5,
        )
    expected = {
        "version": RuntimeRefusalCode.VERSION_MISMATCH,
        "root": RuntimeRefusalCode.ROOT_MISMATCH,
    }.get(failure, RuntimeRefusalCode.INVALID_FRAME)
    assert caught.value.reason is expected
    assert channel.close_calls == 1
    assert not channel.released
    cleanup = _cleanup(caught.value)
    await cleanup.retry_cleanup()
    await cleanup.retry_cleanup()
    assert channel.close_calls == 2
    assert channel.released


@pytest.mark.asyncio
@pytest.mark.parametrize("side", ["client", "server"])
async def test_previous_protocol_is_refused_before_secret_with_retryable_cleanup(side: str) -> None:
    channel = CleanupChannel(close_failures=1)
    identity = RuntimeServerHello(product_version="cleanup-test", storage_identity="a" * 64, boot_id=uuid4())
    expected = RuntimeClientHello(product_version=identity.product_version, storage_identity=identity.storage_identity)
    document = (identity if side == "client" else expected).model_dump(mode="json")
    document["protocol_version"] = 1
    payload = canonical_json_bytes(document)
    secret_frame = b"S" + struct.pack("!I", 6) + b"secret"
    channel.inbound.extend(b"J" + struct.pack("!I", len(payload)) + payload + secret_frame)

    with pytest.raises(RuntimeRefusalError) as caught:
        if side == "client":
            VerifiedRuntimeConnection(channel, expected=expected, deadline=time.monotonic() + 5)
        else:
            accept_runtime_handshake(channel, identity=identity, deadline=time.monotonic() + 5)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert channel.reads == 2
    assert bytes(channel.inbound) == secret_frame
    assert len(channel.writes) == (1 if side == "client" else 0)
    assert all(frame[:1] == b"J" for frame in channel.writes)
    assert channel.close_calls == 1
    assert not channel.released
    await _cleanup(caught.value).retry_cleanup()
    assert channel.close_calls == 2
    assert channel.released


class FaultChannel(CleanupChannel):
    """Explicit channel I/O failure; release remains independently faultable."""

    def __init__(self, *, direction: str, close_failures: int = 1) -> None:
        super().__init__(close_failures=close_failures)
        self.direction = direction
        self.failure = RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    @override
    def read_exact(self, count: int, *, deadline: float) -> bytes:
        if self.direction == "read":
            raise self.failure
        return super().read_exact(count, deadline=deadline)

    @override
    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        if self.direction == "write":
            raise self.failure
        super().write_all(payload, deadline=deadline)


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["read", "write"])
async def test_handshake_io_failure_preserves_exact_primary_and_retryable_owner(direction: str) -> None:
    channel = FaultChannel(direction=direction)
    with pytest.raises(RuntimeRefusalError) as caught:
        VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(product_version="cleanup-test", storage_identity="a" * 64),
            deadline=time.monotonic() + 5,
        )
    assert caught.value is channel.failure
    assert channel.close_calls == 1
    await _cleanup(caught.value).retry_cleanup()
    assert channel.close_calls == 2
    assert channel.released


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["read", "write", "secret"])
async def test_public_frame_failure_preserves_primary_and_retains_failed_release(operation: str) -> None:
    channel = FaultChannel(direction="read" if operation == "read" else "write")
    secret = bytearray(b"synthetic-proof")
    with pytest.raises(RuntimeRefusalError) as caught:
        if operation == "read":
            read_document(channel, RuntimeServerHello, deadline=time.monotonic() + 5)
        elif operation == "write":
            write_document(
                channel,
                RuntimeClientHello(product_version="cleanup-test", storage_identity="a" * 64),
                deadline=time.monotonic() + 5,
            )
        else:
            write_secret(channel, secret, deadline=time.monotonic() + 5)
    assert caught.value is channel.failure
    assert channel.close_calls == 1
    if operation == "secret":
        assert not any(secret)
    cleanup = _cleanup(caught.value)
    await cleanup.retry_cleanup()
    await cleanup.retry_cleanup()
    assert channel.close_calls == 2


@pytest.mark.asyncio
async def test_failed_exchange_retains_one_owner_fences_admission_and_retries_once() -> None:
    channel = FaultChannel(direction="none")
    connection = _connection(channel)
    channel.direction = "read"
    with pytest.raises(RuntimeRefusalError) as caught:
        connection.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 5,
        )
    assert caught.value is channel.failure
    assert channel.close_calls == 1
    writes = tuple(channel.writes)
    with pytest.raises(RuntimeRefusalError) as closed:
        connection.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 5,
        )
    assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert tuple(channel.writes) == writes
    assert channel.close_calls == 1
    await _cleanup(caught.value).retry_cleanup()
    connection.close()
    assert channel.close_calls == 2


class TransferFaultChannel(CleanupChannel):
    """A transfer I/O type failure with an independently failing owned close."""

    def __init__(self, *, direction: str, failure: BaseException, close_failures: int) -> None:
        super().__init__(close_failures=close_failures)
        self.direction = direction
        self.failure = failure

    @override
    def read_exact(self, count: int, *, deadline: float) -> bytes:
        if self.direction == "read":
            raise self.failure
        return super().read_exact(count, deadline=deadline)

    @override
    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        if self.direction == "write":
            raise self.failure
        super().write_all(payload, deadline=deadline)


def _large_profile_status() -> RuntimeProfileStatus:
    return RuntimeProfileStatus(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        status=ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=uuid4(),
            session_id=uuid4(),
            session_expires_at=datetime(2026, 10, 1, tzinfo=UTC),
            grant_state=None,
            grant_expires_at=None,
            grant_valid=False,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.NOT_REQUIRED,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NEEDS_USER,
            effective_scope=AccessScope(
                operations=frozenset(),
                actions=frozenset(),
                disclosures=frozenset(
                    DisclosurePermission(
                        destination_id=uuid4(), projection_id="synthetic.result", category=DisclosureCategory.TAX_VALUES
                    )
                    for _ in range(700)
                ),
                periods=None,
                allow_period_independent=False,
                allow_delegation=False,
            ),
            denial=None,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("close_failures", [1, 2])
@pytest.mark.parametrize(
    ("direction", "failure_type"),
    [("read", ValueError), ("read", TypeError), ("read", RecursionError), ("write", ValueError), ("write", TypeError)],
)
async def test_status_transfer_type_refusal_preserves_single_failed_cleanup_owner(
    direction: str, failure_type: type[Exception], close_failures: int
) -> None:
    status = _large_profile_status()
    payload = canonical_json_bytes(status.model_dump(mode="json"))
    assert len(payload) > MAXIMUM_FRAME_BYTES
    header = RuntimeProfileStatusTransfer(
        request_id=status.request_id,
        runtime_boot_id=status.runtime_boot_id,
        connection_id=status.connection_id,
        byte_count=len(payload),
        payload_digest=sha256_hex(payload),
    )
    channel = TransferFaultChannel(
        direction=direction, failure=failure_type("synthetic transfer failure"), close_failures=close_failures
    )
    with pytest.raises(RuntimeRefusalError) as caught:
        if direction == "read":
            read_profile_status(channel, header, deadline=time.monotonic() + 5)
        else:
            write_profile_status(channel, status, deadline=time.monotonic() + 5)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert channel.close_calls == 1
    assert not channel.released
    cleanup = _cleanup(caught.value)
    assert cleanup is _cleanup(channel.failure)
    if close_failures == 2:
        with pytest.raises(AsyncResourceCleanupError) as retry_failed:
            await cleanup.retry_cleanup()
        assert channel.close_calls == 2
        assert not channel.released
        cleanup = retry_failed.value
    await cleanup.retry_cleanup()
    await cleanup.retry_cleanup()
    await _cleanup(caught.value).retry_cleanup()
    assert channel.released
    assert channel.close_calls == close_failures + 1


def _large_session_inventory() -> RuntimeSessionInventoryReply:
    status = _large_profile_status()
    assert status.status.profile_id is not None
    assert status.status.effective_scope is not None
    return RuntimeSessionInventoryReply(
        request_id=status.request_id,
        runtime_boot_id=status.runtime_boot_id,
        connection_id=status.connection_id,
        sessions=(
            PublicAccessSession(
                session_id=uuid4(),
                profile_id=status.status.profile_id,
                client_id=uuid4(),
                parent_session_id=None,
                grant_id=None,
                key_id=None,
                kind=SessionKind.HUMAN,
                state=SessionState.ACTIVE,
                scope=status.status.effective_scope,
                expires_at=datetime(2026, 10, 1, tzinfo=UTC),
            ),
        ),
    )


@pytest.mark.parametrize("large", [False, True], ids=["single-frame", "complete-scope-transfer"])
def test_session_inventory_is_transparent_complete_and_individually_bounded(large: bool) -> None:
    channel = CleanupChannel(close_failures=0)
    connection = _connection(channel)
    inventory = _large_session_inventory()
    inventory = inventory.model_copy(
        update={"runtime_boot_id": connection.hello.boot_id, "sessions": inventory.sessions if large else ()}
    )
    request = RuntimeSessionInventory(
        request_id=inventory.request_id,
        profile_id=uuid4() if not large else inventory.sessions[0].profile_id,
        session_id=uuid4(),
    )
    channel.writes.clear()
    write_session_inventory(channel, inventory, deadline=time.monotonic() + 5)
    frames = tuple(channel.writes)
    assert all(frame[:1] == b"J" and len(frame) - 5 <= MAXIMUM_FRAME_BYTES for frame in frames)
    assert (len(frames) > 1) is large
    channel.inbound.extend(b"".join(frames))
    assert connection.session_inventory(request, deadline=time.monotonic() + 5) == inventory
    assert not channel.inbound
    assert channel.close_calls == 0
    connection.close()


@pytest.mark.parametrize("identity", ["request_id", "runtime_boot_id", "connection_id"])
def test_session_inventory_transfer_header_is_correlated_before_chunks(identity: str) -> None:
    channel = CleanupChannel(close_failures=0)
    connection = _connection(channel)
    inventory = _large_session_inventory().model_copy(update={"runtime_boot_id": connection.hello.boot_id})
    request = RuntimeSessionInventory(
        request_id=inventory.request_id, profile_id=inventory.sessions[0].profile_id, session_id=uuid4()
    )
    # Establish the exact connection identity through a preceding public reply.
    empty = inventory.model_copy(update={"sessions": ()})
    channel.writes.clear()
    write_session_inventory(channel, empty, deadline=time.monotonic() + 5)
    channel.inbound.extend(b"".join(channel.writes))
    assert connection.session_inventory(request, deadline=time.monotonic() + 5) == empty
    channel.writes.clear()
    payload = canonical_json_bytes(inventory.model_dump(mode="json"))
    header = RuntimeSessionInventoryTransfer(
        request_id=inventory.request_id,
        runtime_boot_id=inventory.runtime_boot_id,
        connection_id=inventory.connection_id,
        byte_count=len(payload),
        payload_digest=sha256_hex(payload),
    ).model_copy(update={identity: uuid4()})
    write_document(channel, header, deadline=time.monotonic() + 5)
    channel.inbound.extend(b"".join(channel.writes))
    with pytest.raises(RuntimeRefusalError) as caught:
        connection.session_inventory(request, deadline=time.monotonic() + 5)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert not channel.inbound  # No chunk was supplied or requested.
    assert channel.released


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["digest", "offset", "request_id", "runtime_boot_id", "connection_id", "kind", "duplicate"]
)
async def test_session_inventory_transfer_rejects_corruption_and_retains_failed_cleanup(failure: str) -> None:
    inventory = _large_session_inventory()
    payload = canonical_json_bytes(inventory.model_dump(mode="json"))
    if failure in {"request_id", "runtime_boot_id", "connection_id"}:
        payload = canonical_json_bytes(inventory.model_copy(update={failure: uuid4()}).model_dump(mode="json"))
    elif failure == "kind":
        payload = payload.replace(b'"session_inventory_reply"', b'"profile_status"', 1)
    elif failure == "duplicate":
        payload = b'{"kind":"session_inventory_reply",' + payload[1:]
    header = RuntimeSessionInventoryTransfer(
        request_id=inventory.request_id,
        runtime_boot_id=inventory.runtime_boot_id,
        connection_id=inventory.connection_id,
        byte_count=len(payload),
        payload_digest="0" * 64 if failure == "digest" else sha256_hex(payload),
    )
    channel = CleanupChannel(close_failures=1)
    for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
        write_document(
            channel,
            SubmissionPayloadChunk(
                offset=offset + 1 if failure == "offset" else offset,
                encoded=base64.b64encode(payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES]).decode("ascii"),
            ),
            deadline=time.monotonic() + 5,
        )
    channel.inbound.extend(b"".join(channel.writes))
    with pytest.raises(RuntimeRefusalError) as caught:
        read_session_inventory(channel, header, deadline=time.monotonic() + 5)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert channel.close_calls == 1
    await _cleanup(caught.value).retry_cleanup()
    assert channel.close_calls == 2
    assert channel.released


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["read", "write"])
async def test_session_inventory_transfer_type_failure_retains_one_cleanup_owner(direction: str) -> None:
    inventory = _large_session_inventory()
    payload = canonical_json_bytes(inventory.model_dump(mode="json"))
    assert len(payload) > MAXIMUM_FRAME_BYTES
    header = RuntimeSessionInventoryTransfer(
        request_id=inventory.request_id,
        runtime_boot_id=inventory.runtime_boot_id,
        connection_id=inventory.connection_id,
        byte_count=len(payload),
        payload_digest=sha256_hex(payload),
    )
    channel = TransferFaultChannel(
        direction=direction, failure=TypeError("synthetic transfer failure"), close_failures=1
    )
    with pytest.raises(RuntimeRefusalError) as caught:
        if direction == "read":
            read_session_inventory(channel, header, deadline=time.monotonic() + 5)
        else:
            write_session_inventory(channel, inventory, deadline=time.monotonic() + 5)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert channel.close_calls == 1
    assert _cleanup(caught.value) is _cleanup(channel.failure)
    await _cleanup(caught.value).retry_cleanup()
    assert channel.close_calls == 2
    assert channel.released


@pytest.mark.asyncio
async def test_frontend_cleanup_adopts_failed_connection_owner_without_duplicate_native_retry() -> None:
    channel = FaultChannel(direction="none", close_failures=3)
    connection = _connection(channel)
    client = RuntimeFrontendClient(connection, profile_id=uuid4(), frontend=OperationFrontendProjection.MCP)
    channel.direction = "read"
    primary: BaseException | None = None
    with pytest.raises(RuntimeRefusalError) as caught:
        try:
            connection.session(
                RuntimeSessionRequest(
                    action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                ),
                deadline=time.monotonic() + 5,
            )
        except BaseException as error:
            primary = error
            assert error is channel.failure
            assert channel.close_calls == 1
            raise
        finally:
            await close_async_resources(
                client.cleanup_owner(primary_error=primary),
                task_name="frontend-factory-close",
                primary_error=primary,
            )
    assert caught.value is channel.failure
    assert channel.close_calls == 2
    retained = _cleanup(caught.value)
    with pytest.raises(AsyncResourceCleanupError) as retry_failed:
        await retained.retry_cleanup()
    assert channel.close_calls == 3
    assert not channel.released
    await retry_failed.value.retry_cleanup()
    assert channel.close_calls == 4
    assert channel.released
    await retained.retry_cleanup()
    await retry_failed.value.retry_cleanup()
    client.close()
    assert channel.close_calls == 4


@pytest.mark.asyncio
async def test_frontend_cleanup_does_not_adopt_another_connections_failed_owner() -> None:
    foreign_channel = FaultChannel(direction="none")
    foreign_connection = _connection(foreign_channel)
    own_channel = CleanupChannel(close_failures=0)
    client = RuntimeFrontendClient(
        _connection(own_channel), profile_id=uuid4(), frontend=OperationFrontendProjection.MCP
    )
    foreign_channel.direction = "read"
    with pytest.raises(RuntimeRefusalError) as caught:
        foreign_connection.session(
            RuntimeSessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
            deadline=time.monotonic() + 5,
        )
    assert foreign_channel.close_calls == 1
    await close_async_resources(
        client.cleanup_owner(primary_error=caught.value),
        task_name="independent-frontend-close",
        primary_error=caught.value,
    )
    assert own_channel.released and own_channel.close_calls == 1
    assert not foreign_channel.released and foreign_channel.close_calls == 1
    await _cleanup(caught.value).retry_cleanup()
    assert foreign_channel.released and foreign_channel.close_calls == 2
    client.close()
    assert own_channel.close_calls == 1
