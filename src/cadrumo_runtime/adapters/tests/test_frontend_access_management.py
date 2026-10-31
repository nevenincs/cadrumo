"""Frontend management uses its bound profile and leaves recovery unadmitted."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from cadrumo_client.contracts.access_management import (
    AutomationDenied,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileRecoveryPrepared,
    ProfileResume,
    ProfileResumed,
    SessionInventory,
    SessionInventoryReply,
)
from cadrumo_client.contracts.automation_lifecycle import AutomationResumeReceipt
from cadrumo_client.contracts.contracts import ClientHello, ServerHello
from cadrumo_client.contracts.profile_access import Request, SecretReady
from cadrumo_client.transport.frame_io import read_document, read_secret, write_document
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.tests.memory_channel import MemoryChannel
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _channels() -> tuple[MemoryChannel, MemoryChannel, ServerHello]:
    client, server = MemoryChannel(), MemoryChannel()
    client.pair(server)
    identity = ServerHello(product_version="frontend-management", storage_identity="a" * 64, boot_id=uuid4())
    return client, server, identity


def _client(channel: MemoryChannel, identity: ServerHello, profile_id: UUID) -> FrontendClient:
    connection = VerifiedConnection(
        channel,
        expected=ClientHello(product_version=identity.product_version, storage_identity=identity.storage_identity),
        deadline=time.monotonic() + 5,
    )
    return FrontendClient(connection, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)


def test_recovery_uses_one_generation_and_never_admits_a_session() -> None:
    client_channel, server_channel, identity = _channels()
    profile_id, connection_id, grant_id = uuid4(), uuid4(), uuid4()
    password = bytearray(b"synthetic-recovery-password")

    def serve() -> None:
        try:
            accept_connection_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            prepared = read_document(server_channel, Request, deadline=time.monotonic() + 5).root
            assert isinstance(prepared, ProfileRecoveryPrepare)
            assert prepared.profile_id == profile_id and prepared.frontend is OperationFrontendProjection.CLI
            write_document(
                server_channel,
                ProfileRecoveryPrepared(
                    request_id=prepared.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    profile_id=profile_id,
                    lock_generation=4,
                    globally_locked=True,
                ),
                deadline=time.monotonic() + 5,
            )
            resume = read_document(server_channel, Request, deadline=time.monotonic() + 5).root
            assert isinstance(resume, ProfileResume)
            assert resume.profile_id == profile_id and resume.lock_generation == 4 and resume.grants == {grant_id}
            write_document(
                server_channel,
                SecretReady(
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
                ProfileResumed(
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
            with pytest.raises(FrontendRefusedError):
                _ = client.session_id
            serving.result(timeout=5)
        finally:
            client.close()


def test_inventory_and_denial_use_current_session_then_profile_lock_retires_it() -> None:
    client_channel, server_channel, identity = _channels()
    profile_id, session_id, connection_id = uuid4(), uuid4(), uuid4()

    def serve() -> None:
        try:
            accept_connection_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            inventory = read_document(server_channel, Request, deadline=time.monotonic() + 5).root
            assert isinstance(inventory, SessionInventory)
            assert inventory.profile_id == profile_id and inventory.session_id == session_id
            write_document(
                server_channel,
                SessionInventoryReply(
                    request_id=inventory.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    sessions=(),
                ),
                deadline=time.monotonic() + 5,
            )
            denial = read_document(server_channel, Request, deadline=time.monotonic() + 5).root
            assert isinstance(denial, AutomationDeny)
            assert denial.profile_id == profile_id and denial.session_id == session_id
            assert denial.kind is AutomationDenialKind.PROFILE_LOCK
            write_document(
                server_channel,
                AutomationDenied(
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
            with pytest.raises(FrontendRefusedError):
                _ = client.session_id
            replay_password = bytearray(b"never-sent")
            with pytest.raises(FrontendRefusedError):
                client.recover_profile(replay_password, timeout=5)
            assert not any(replay_password)
            serving.result(timeout=5)
        finally:
            client.close()
