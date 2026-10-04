"""Native Windows pipe ownership, peer identity and bounded protocol behavior."""

from __future__ import annotations

import os
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)

from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake
from ..windows import WindowsRuntimeEndpoint
from ..worker_native_identity import verify_worker_native_pid

if TYPE_CHECKING:
    from _win32typing import PyHANDLE


pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows named pipes and process tokens"),
]


def test_first_instance_survives_client_disconnect_and_releases_on_close(tmp_path: Path) -> None:
    owner = WindowsRuntimeEndpoint(storage_root=tmp_path)
    competitor = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        owner.listen()
        for _ in range(2):
            client = competitor.connect(expected_image=Path(sys.base_prefix) / "python.exe")
            server = owner.accept(timeout=1)
            try:
                assert client.peer.process_id == server.peer.process_id == os.getpid()
                assert client.peer.os_owner_id == server.peer.os_owner_id
                with pytest.raises(RuntimeRefusalError) as caught:
                    competitor.listen()
                assert caught.value.reason is RuntimeRefusalCode.OWNER_BUSY
            finally:
                client.close()
                server.close()
        with pytest.raises(RuntimeRefusalError):
            competitor.listen()
    finally:
        owner.close()
        competitor.close()
    replacement = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        replacement.listen()
    finally:
        replacement.close()


def test_ready_peer_receives_secret_only_after_handshake(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    identity = RuntimeServerHello(
        product_version="synthetic-cohort", storage_identity=endpoint.storage_identity, boot_id=uuid4()
    )
    expected = RuntimeClientHello(product_version=identity.product_version, storage_identity=identity.storage_identity)
    secret = bytearray(b"synthetic-pipe-secret")

    def serve() -> bytes:
        channel = endpoint.accept(timeout=2)
        try:
            deadline = time.monotonic() + 2
            accept_runtime_handshake(channel, identity=identity, deadline=deadline)
            header = channel.read_exact(5, deadline=deadline)
            assert header[:1] == b"S"
            return channel.read_exact(struct.unpack("!I", header[1:])[0], deadline=deadline)
        finally:
            channel.close()

    try:
        endpoint.listen()
        with ThreadPoolExecutor(max_workers=1) as pool:
            serving = pool.submit(serve)
            connection = VerifiedRuntimeConnection(
                endpoint.connect(expected_image=Path(sys.base_prefix) / "python.exe"),
                expected=expected,
                deadline=time.monotonic() + 2,
            )
            try:
                connection.send_secret(secret, deadline=time.monotonic() + 2)
                assert not any(secret)
                assert serving.result(timeout=3) == b"synthetic-pipe-secret"
                assert connection.hello.boot_id == identity.boot_id
            finally:
                connection.close()
    finally:
        endpoint.close()


def test_wrong_executable_refused_before_protocol_io(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
        with pytest.raises(RuntimeRefusalError) as caught:
            endpoint.connect(expected_image=tmp_path / "not-the-running-process.exe")
        assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    finally:
        endpoint.close()


def test_read_deadline_cancels_pending_io_and_channel_remains_usable(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
        client = endpoint.connect()
        server = endpoint.accept(timeout=1)
        try:
            with pytest.raises(RuntimeRefusalError) as caught:
                client.read_exact(1, deadline=time.monotonic() + 0.05)
            assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
            server.write_all(b"x", deadline=time.monotonic() + 1)
            assert client.read_exact(1, deadline=time.monotonic() + 1) == b"x"
        finally:
            client.close()
            server.close()
    finally:
        endpoint.close()


def test_accept_deadline_can_be_retried(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
        with pytest.raises(RuntimeRefusalError) as caught:
            endpoint.accept(timeout=0.05)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        client = endpoint.connect()
        server = endpoint.accept(timeout=1)
        client.close()
        server.close()
    finally:
        endpoint.close()


def test_independent_clients_do_not_share_buffers_or_disconnect(tmp_path: Path) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
        client_a = endpoint.connect()
        server_a = endpoint.accept(timeout=1)
        client_b = endpoint.connect()
        server_b = endpoint.accept(timeout=1)
        try:
            client_a.write_all(b"a", deadline=time.monotonic() + 1)
            client_b.write_all(b"b", deadline=time.monotonic() + 1)
            assert server_a.read_exact(1, deadline=time.monotonic() + 1) == b"a"
            client_a.close()
            server_a.close()
            assert server_b.read_exact(1, deadline=time.monotonic() + 1) == b"b"
        finally:
            client_a.close()
            server_a.close()
            client_b.close()
            server_b.close()
    finally:
        endpoint.close()


def test_pipe_security_is_protected_owner_only_with_noninherited_client_handle(tmp_path: Path) -> None:
    import win32api
    import win32file
    import win32security

    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
        # The observer requests only security-descriptor read access. It does
        # not mutate the pipe or impersonate another account.
        handle = win32file.CreateFile(endpoint.pipe_name, 0x00020000, 0, None, win32file.OPEN_EXISTING, 0, None)
        try:
            descriptor = win32security.GetSecurityInfo(
                int(handle),
                win32security.SE_KERNEL_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION,
            )
            owner = descriptor.GetSecurityDescriptorOwner()
            dacl = descriptor.GetSecurityDescriptorDacl()
            assert dacl is not None and dacl.GetAceCount() == 1
            (kind, _flags), access, principal = dacl.GetAce(0)
            assert kind == win32security.ACCESS_ALLOWED_ACE_TYPE
            assert principal == owner
            # Precisely mapped read/write/create-instance server rights; no
            # Everyone, network, generic-write or generic-all ACE is present.
            assert access == 0x0012019F
            control, _revision = descriptor.GetSecurityDescriptorControl()
            assert control & win32security.SE_DACL_PROTECTED
            assert win32api.GetHandleInformation(int(handle)) & 1 == 0
        finally:
            handle.Close()
    finally:
        endpoint.close()


@pytest.mark.asyncio
async def test_retained_pipe_peer_verifier_accepts_exact_process_and_refuses_other_or_closed(tmp_path: Path) -> None:
    """Real process objects, not mocked PID or creation-time values, bind the peer."""
    import win32api
    import win32con

    from cadrumo.core.async_cleanup import AsyncCloseable, async_cleanup_failures, close_async_resources

    from ..runtime_transport_cleanup import RuntimeTransportCleanup
    from ..windows_process import WindowsOwnedProcess, WindowsProcessScope, unreturned_windows_process_scope

    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    owners = [RuntimeTransportCleanup(endpoint)]
    scope: WindowsProcessScope | None = None
    owned_scopes: list[WindowsProcessScope] = []
    primary: list[BaseException] = []
    try:
        endpoint.listen()
        client = endpoint.connect()
        client_owner = RuntimeTransportCleanup(client)
        owners.append(client_owner)
        server = endpoint.accept(timeout=2)
        owners.append(RuntimeTransportCleanup(server))
        correct_native = cast(
            "PyHANDLE",
            cast(
                object,
                win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, os.getpid()),
            ),
        )
        correct_handle = int(correct_native.Detach())
        owners.append(RuntimeTransportCleanup(WindowsOwnedProcess(handle=correct_handle, pid=os.getpid())))
        client.verify_peer_process(correct_handle)
        server.verify_peer_process(correct_handle)
        try:
            scope = WindowsProcessScope()
        except BaseException as error:
            scope = unreturned_windows_process_scope(error)
            if scope is not None:
                owned_scopes.append(scope)
            raise
        owned_scopes.append(scope)
        child = scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-c", "import time; time.sleep(30)"),
            directory=tmp_path,
            environment={"SystemRoot": os.environ["SYSTEMROOT"], "PYDANTIC_DISABLE_PLUGINS": "__all__"},
        )
        wrong_native = cast(
            "PyHANDLE",
            cast(
                object,
                win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, child.pid),
            ),
        )
        wrong_handle = int(wrong_native.Detach())
        owners.append(RuntimeTransportCleanup(WindowsOwnedProcess(handle=wrong_handle, pid=child.pid)))
        assert scope.contains_process(wrong_handle)
        with pytest.raises(RuntimeRefusalError) as outside_job:
            verify_worker_native_pid(client, scope, client.peer.os_owner_id)
        assert outside_job.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
        with pytest.raises(RuntimeRefusalError) as wrong:
            client.verify_peer_process(wrong_handle)
        assert wrong.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
        client_owner.close_now()
        with pytest.raises(RuntimeRefusalError) as closed:
            client.verify_peer_process(correct_handle)
        assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    except BaseException as error:
        primary.append(error)
        raise
    finally:
        resources: dict[int, AsyncCloseable] = {id(owner): owner for owner in (*owned_scopes, *owners)}
        if primary:
            for failure in async_cleanup_failures(primary[0]):
                for owner in failure.resources:
                    resources[id(owner)] = owner
        await close_async_resources(
            *resources.values(),
            task_name="pipe-retained-peer-detector-close",
            primary_error=primary[0] if primary else None,
        )
