"""Frontend management uses its bound profile and leaves recovery unadmitted."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Condition
from uuid import UUID, uuid4

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
from ..frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class MemoryChannel:
    """Explicit synchronized wire port; no runtime policy is simulated."""

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
    identity = RuntimeServerHello(product_version="frontend-management", storage_identity="a" * 64, boot_id=uuid4())
    return client, server, identity


def _client(channel: MemoryChannel, identity: RuntimeServerHello, profile_id: UUID) -> RuntimeFrontendClient:
    connection = VerifiedRuntimeConnection(
        channel,
        expected=RuntimeClientHello(
            product_version=identity.product_version, storage_identity=identity.storage_identity
        ),
        deadline=time.monotonic() + 5,
    )
    return RuntimeFrontendClient(connection, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)


def test_recovery_uses_one_generation_and_never_admits_a_session() -> None:
    client_channel, server_channel, identity = _channels()
    profile_id, connection_id, grant_id = uuid4(), uuid4(), uuid4()
    password = bytearray(b"synthetic-recovery-password")

    def serve() -> None:
        try:
            accept_runtime_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            prepared = read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root
            assert isinstance(prepared, RuntimeProfileRecoveryPrepare)
            assert prepared.profile_id == profile_id and prepared.frontend is OperationFrontendProjection.CLI
            write_document(
                server_channel,
                RuntimeProfileRecoveryPrepared(
                    request_id=prepared.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    profile_id=profile_id,
                    lock_generation=4,
                    globally_locked=True,
                ),
                deadline=time.monotonic() + 5,
            )
            resume = read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root
            assert isinstance(resume, RuntimeProfileResume)
            assert resume.profile_id == profile_id and resume.lock_generation == 4 and resume.grants == {grant_id}
            write_document(
                server_channel,
                RuntimeSecretReady(
                    request_id=resume.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                ),
                deadline=time.monotonic() + 5,
            )
            with read_secret(server_channel, deadline=time.monotonic() + 5) as received:
                assert received == b"synthetic-recovery-password"
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
                        lock_generation=4,
                        reactivated_grants=frozenset({grant_id}),
                    ),
                ),
                deadline=time.monotonic() + 5,
            )
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        client = _client(client_channel, identity, profile_id)
        try:
            receipt = client.recover_profile(password, grants=frozenset({grant_id}), timeout=5)
            assert receipt.reactivated_grants == {grant_id}
            assert not any(password)
            assert all(
                b"synthetic-recovery-password" not in frame for frame in client_channel.writes if frame[:1] == b"J"
            )
            with pytest.raises(RuntimeFrontendRefusedError):
                _ = client.session_id
            serving.result(timeout=5)
        finally:
            client.close()


def test_inventory_and_denial_use_current_session_then_profile_lock_retires_it() -> None:
    client_channel, server_channel, identity = _channels()
    profile_id, session_id, connection_id = uuid4(), uuid4(), uuid4()

    def serve() -> None:
        try:
            accept_runtime_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            inventory = read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root
            assert isinstance(inventory, RuntimeSessionInventory)
            assert inventory.profile_id == profile_id and inventory.session_id == session_id
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
            denial = read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root
            assert isinstance(denial, RuntimeAutomationDeny)
            assert denial.profile_id == profile_id and denial.session_id == session_id
            assert denial.kind is AutomationDenialKind.PROFILE_LOCK
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
                        revision=2,
                        profile_lock_generation=1,
                    ),
                ),
                deadline=time.monotonic() + 5,
            )
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        client = _client(client_channel, identity, profile_id)
        try:
            # The unit seam begins after a valid runtime admission; the wire still
            # decides whether this test-owned identity may observe or deny.
            client._session_id = session_id
            client._connection_purpose = "admission"
            assert client.sessions(timeout=5) == ()
            receipt = client.deny_automation(AutomationDenialKind.PROFILE_LOCK, timeout=5)
            assert receipt.access_denied and receipt.profile_lock_generation == 1
            with pytest.raises(RuntimeFrontendRefusedError):
                _ = client.session_id
            replay_password = bytearray(b"never-sent")
            with pytest.raises(RuntimeFrontendRefusedError):
                client.recover_profile(replay_password, timeout=5)
            assert not any(replay_password)
            serving.result(timeout=5)
        finally:
            client.close()
