"""Access management keeps proof separate from correlated nonsecret documents."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Condition
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
)
from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.profile_access import RuntimeRequest, RuntimeSecretReady
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from cadrumo.application.user_profile.automation_lifecycle_service import AutomationResumeReceipt

from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake, read_document, read_secret, write_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class MemoryChannel:
    """Small synchronized byte-channel port with inspectable outbound frames."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._data = bytearray()
        self._closed = False
        self._other: MemoryChannel | None = None
        self.writes: list[bytes] = []
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)

    def pair(self, other: MemoryChannel) -> None:
        self._other = other
        other._other = self

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self._condition:
            while len(self._data) < count:
                if self._closed or (self._other is not None and self._other._closed):
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                self._condition.wait(remaining)
            result = bytes(self._data[:count])
            del self._data[:count]
            return result

    def read_ready(self) -> bool:
        with self._condition:
            return bool(self._data) or self._closed or (self._other is not None and self._other._closed)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        other = self._other
        if other is None or time.monotonic() >= deadline:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        with other._condition:
            if self._closed or other._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            self.writes.append(bytes(payload))
            other._data.extend(payload)
            other._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._other is not None:
            with self._other._condition:
                self._other._condition.notify_all()


def _channels() -> tuple[MemoryChannel, MemoryChannel, RuntimeServerHello]:
    client, server = MemoryChannel(), MemoryChannel()
    client.pair(server)
    identity = RuntimeServerHello(product_version="access-test", storage_identity="a" * 64, boot_id=uuid4())
    return client, server, identity


def _client(channel: MemoryChannel, identity: RuntimeServerHello) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        channel,
        expected=RuntimeClientHello(
            product_version=identity.product_version, storage_identity=identity.storage_identity
        ),
        deadline=time.monotonic() + 5,
    )


def test_management_exchanges_keep_password_only_in_secret_frame() -> None:
    client_channel, server_channel, identity = _channels()
    profile_id, session_id, connection_id = uuid4(), uuid4(), uuid4()
    grant_id = uuid4()
    recovery = RuntimeProfileRecoveryPrepare(
        request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
    )
    denial = RuntimeAutomationDeny(
        request_id=uuid4(), profile_id=profile_id, session_id=session_id, kind=AutomationDenialKind.ALL
    )
    resume = RuntimeProfileResume(
        request_id=uuid4(),
        profile_id=profile_id,
        frontend=OperationFrontendProjection.CLI,
        lock_generation=2,
        grants=frozenset({grant_id}),
    )
    inventory = RuntimeSessionInventory(request_id=uuid4(), profile_id=profile_id, session_id=session_id)
    password = bytearray(b"synthetic-private-password")

    def serve() -> None:
        try:
            accept_runtime_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            assert read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root == recovery
            write_document(
                server_channel,
                RuntimeProfileRecoveryPrepared(
                    request_id=recovery.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    profile_id=profile_id,
                    lock_generation=2,
                    globally_locked=True,
                ),
                deadline=time.monotonic() + 5,
            )
            assert read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root == denial
            write_document(
                server_channel,
                RuntimeAutomationDenied(
                    request_id=denial.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    receipt=AutomationDenialReceipt(
                        request_id=denial.request_id,
                        profile_id=profile_id,
                        access_denied=True,
                        cleanup_pending=False,
                        revision=1,
                        profile_lock_generation=2,
                    ),
                ),
                deadline=time.monotonic() + 5,
            )
            assert read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root == resume
            write_document(
                server_channel,
                RuntimeSecretReady(
                    request_id=resume.request_id, runtime_boot_id=identity.boot_id, connection_id=connection_id
                ),
                deadline=time.monotonic() + 5,
            )
            with read_secret(server_channel, deadline=time.monotonic() + 5) as received:
                assert received == b"synthetic-private-password"
            write_document(
                server_channel,
                RuntimeProfileResumed(
                    request_id=resume.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    receipt=AutomationResumeReceipt(
                        request_id=resume.request_id,
                        profile_id=profile_id,
                        revision=2,
                        lock_generation=2,
                        reactivated_grants=frozenset({grant_id}),
                    ),
                ),
                deadline=time.monotonic() + 5,
            )
            assert read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root == inventory
            write_document(
                server_channel,
                RuntimeSessionInventoryReply(
                    request_id=inventory.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    sessions=(),
                ),
                deadline=time.monotonic() + 5,
            )
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = _client(client_channel, identity)
        try:
            prepared = connection.recovery_prepare(recovery, deadline=time.monotonic() + 5)
            assert isinstance(prepared, RuntimeProfileRecoveryPrepared) and prepared.lock_generation == 2
            denied = connection.deny_automation(denial, deadline=time.monotonic() + 5)
            assert isinstance(denied, RuntimeAutomationDenied) and denied.receipt.access_denied
            resumed = connection.resume_profile(resume, password, deadline=time.monotonic() + 5)
            assert isinstance(resumed, RuntimeProfileResumed) and resumed.receipt.reactivated_grants == {grant_id}
            assert isinstance(
                connection.session_inventory(inventory, deadline=time.monotonic() + 5), RuntimeSessionInventoryReply
            )
            assert not any(password)
            assert all(
                b"synthetic-private-password" not in frame for frame in client_channel.writes if frame[:1] == b"J"
            )
            assert any(frame[:1] == b"S" for frame in client_channel.writes)
            serving.result(timeout=5)
        finally:
            connection.close()


def test_wrong_resume_generation_closes_channel_and_wipes_password() -> None:
    client_channel, server_channel, identity = _channels()
    profile_id, connection_id = uuid4(), uuid4()
    request = RuntimeProfileResume(
        request_id=uuid4(),
        profile_id=profile_id,
        frontend=OperationFrontendProjection.TUI,
        lock_generation=3,
        grants=frozenset(),
    )
    password = bytearray(b"synthetic-private-password")

    def serve() -> None:
        accept_runtime_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
        assert read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root == request
        write_document(
            server_channel,
            RuntimeSecretReady(
                request_id=request.request_id, runtime_boot_id=identity.boot_id, connection_id=connection_id
            ),
            deadline=time.monotonic() + 5,
        )
        with read_secret(server_channel, deadline=time.monotonic() + 5):
            pass
        write_document(
            server_channel,
            RuntimeProfileResumed(
                request_id=request.request_id,
                runtime_boot_id=identity.boot_id,
                connection_id=connection_id,
                receipt=AutomationResumeReceipt(
                    request_id=request.request_id,
                    profile_id=profile_id,
                    revision=1,
                    lock_generation=4,
                    reactivated_grants=frozenset(),
                ),
            ),
            deadline=time.monotonic() + 5,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = _client(client_channel, identity)
        with pytest.raises(RuntimeRefusalError) as refusal:
            connection.resume_profile(request, password, deadline=time.monotonic() + 5)
        assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME
        assert not any(password)
        with pytest.raises(RuntimeRefusalError) as closed:
            connection.recovery_prepare(
                RuntimeProfileRecoveryPrepare(
                    request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                ),
                deadline=time.monotonic() + 5,
            )
        assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        serving.result(timeout=5)


def test_uncorrelated_readiness_never_receives_password() -> None:
    client_channel, server_channel, identity = _channels()
    request = RuntimeProfileResume(
        request_id=uuid4(),
        profile_id=uuid4(),
        frontend=OperationFrontendProjection.CLI,
        lock_generation=0,
        grants=frozenset(),
    )
    password = bytearray(b"synthetic-private-password")

    def serve() -> None:
        accept_runtime_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
        assert read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root == request
        write_document(
            server_channel,
            RuntimeSecretReady(request_id=uuid4(), runtime_boot_id=identity.boot_id, connection_id=uuid4()),
            deadline=time.monotonic() + 5,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = _client(client_channel, identity)
        with pytest.raises(RuntimeRefusalError) as refusal:
            connection.resume_profile(request, password, deadline=time.monotonic() + 5)
        assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME
        assert not any(password)
        assert not any(frame[:1] == b"S" for frame in client_channel.writes)
        serving.result(timeout=5)
