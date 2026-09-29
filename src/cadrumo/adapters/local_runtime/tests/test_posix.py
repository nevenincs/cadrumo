"""Real POSIX endpoint ownership, native peers and bounded readiness exchange."""

from __future__ import annotations

import contextlib
import os
import socket
import struct
import sys
import tempfile
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.management_status import RuntimeListenerState

from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake, read_document
from ..management_status import probe_runtime_listener
from ..posix import PosixRuntimeChannel, PosixRuntimeEndpoint, posix_storage_identity

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.skipif(sys.platform == "win32", reason="requires native POSIX peer credentials and flock"),
]


@pytest.fixture
def namespace() -> Iterator[Path]:
    # Unix socket path limits apply to the entire path, including pytest's name.
    with tempfile.TemporaryDirectory(prefix="cr-ipc-", dir=Path("/") / "tmp") as root:
        yield Path(root) / "ipc"


def test_root_aliases_converge_and_owner_lock_survives_client_disconnect(tmp_path: Path, namespace: Path) -> None:
    alias = tmp_path / "alias"
    root = tmp_path / "storage"
    root.mkdir()
    alias.symlink_to(root, target_is_directory=True)
    assert posix_storage_identity(alias) == posix_storage_identity(root)
    owner = PosixRuntimeEndpoint(storage_root=root, namespace=namespace)
    competitor = PosixRuntimeEndpoint(storage_root=alias, namespace=namespace)
    try:
        owner.listen()
        client = competitor.connect()
        server = owner.accept()
        assert client.peer.os_owner_id == server.peer.os_owner_id
        assert client.peer.process_id == server.peer.process_id == os.getpid()
        client.close()
        server.close()
        with pytest.raises(RuntimeRefusalError) as caught:
            competitor.listen()
        assert caught.value.reason is RuntimeRefusalCode.OWNER_BUSY
    finally:
        competitor.close()
        owner.close()
    replacement = PosixRuntimeEndpoint(storage_root=root, namespace=namespace)
    try:
        replacement.listen()
    finally:
        replacement.close()


@pytest.mark.parametrize("substitution", ["regular_file", "symlink", "live_socket", "stale_socket"])
def test_endpoint_recovery_only_removes_proven_stale_owned_socket(
    tmp_path: Path, namespace: Path, substitution: str
) -> None:
    if sys.platform == "win32":
        pytest.skip("requires Unix sockets")
    endpoint = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
    path = namespace / (endpoint.storage_identity[:32] + ".sock")
    socket_owner: socket.socket | None = None
    try:
        if substitution == "regular_file":
            path.write_bytes(b"unrelated")
        elif substitution == "symlink":
            target = tmp_path / "untouched"
            target.write_bytes(b"unrelated")
            path.symlink_to(target)
        else:
            socket_owner = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            socket_owner.bind(str(path))
            if substitution == "live_socket":
                socket_owner.listen(1)
            else:
                socket_owner.close()
        if substitution == "stale_socket":
            endpoint.listen()
        else:
            with pytest.raises(RuntimeRefusalError):
                endpoint.listen()
            assert path.exists()
            if substitution in {"regular_file", "symlink"}:
                assert path.read_bytes() == b"unrelated"
    finally:
        endpoint.close()
        if socket_owner is not None:
            socket_owner.close()


def test_namespace_permission_and_symlink_substitution_refused(tmp_path: Path, namespace: Path) -> None:
    namespace.mkdir(mode=0o755)
    with pytest.raises(RuntimeRefusalError) as caught:
        PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
    assert caught.value.reason is RuntimeRefusalCode.ENDPOINT_UNTRUSTED
    namespace.rmdir()
    namespace.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeRefusalError):
        PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)


def test_passive_endpoint_does_not_create_missing_namespace(tmp_path: Path, namespace: Path) -> None:
    endpoint = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace, create_namespace=False)
    try:
        assert not namespace.exists()
        expected = RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity)
        assert probe_runtime_listener(endpoint, expected=expected, timeout=0.1) is RuntimeListenerState.UNAVAILABLE
        with pytest.raises(RuntimeRefusalError) as caught:
            endpoint.connect(timeout=0.1)
        assert caught.value.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY
        with pytest.raises(RuntimeRefusalError) as caught:
            endpoint.listen()
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
        assert not namespace.exists()
    finally:
        endpoint.close()
    assert not namespace.exists()


def test_passive_endpoint_verifies_namespace_created_after_construction(tmp_path: Path, namespace: Path) -> None:
    passive = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace, create_namespace=False)
    owner = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
    try:
        owner.listen()
        client = passive.connect(timeout=1)
        server = owner.accept(timeout=1)
        client.close()
        server.close()
    finally:
        passive.close()
        owner.close()


def test_passive_endpoint_refuses_symlink_without_replacing_target(tmp_path: Path, namespace: Path) -> None:
    target = tmp_path / "untouched"
    target.mkdir()
    namespace.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeRefusalError) as caught:
        PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace, create_namespace=False)
    assert caught.value.reason is RuntimeRefusalCode.ENDPOINT_UNTRUSTED
    assert namespace.is_symlink() and target.is_dir()


@pytest.mark.parametrize("substitution", ["symlink", "fifo", "public_file", "hardlink"])
def test_lock_substitution_refuses_without_opening_or_replacing_target(
    tmp_path: Path, namespace: Path, substitution: str
) -> None:
    if sys.platform == "win32":
        pytest.skip("requires native POSIX filesystem protection")
    endpoint = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
    lock = namespace / (endpoint.storage_identity[:32] + ".lock")
    target = tmp_path / "untouched"
    target.write_bytes(b"synthetic unrelated content")
    if substitution == "symlink":
        lock.symlink_to(target)
    elif substitution == "fifo":
        os.mkfifo(lock, 0o600)
    elif substitution == "hardlink":
        os.link(target, lock)
    else:
        lock.write_bytes(b"untrusted")
        lock.chmod(0o644)
    original = lock.lstat()
    try:
        with pytest.raises(RuntimeRefusalError) as caught:
            endpoint.listen()
        assert caught.value.reason is RuntimeRefusalCode.ENDPOINT_UNTRUSTED
        assert lock.lstat().st_ino == original.st_ino
        assert target.read_bytes() == b"synthetic unrelated content"
    finally:
        endpoint.close()


def _identity(endpoint: PosixRuntimeEndpoint, *, version: str = "test-cohort") -> RuntimeServerHello:
    return RuntimeServerHello(product_version=version, storage_identity=endpoint.storage_identity, boot_id=uuid4())


def test_readiness_precedes_distinct_secret_frame_and_consumes_client_buffer(tmp_path: Path, namespace: Path) -> None:
    endpoint = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
    identity = _identity(endpoint)
    expected = RuntimeClientHello(product_version=identity.product_version, storage_identity=identity.storage_identity)
    sentinel = bytearray(b"synthetic-channel-secret")
    received: list[bytes] = []

    def serve() -> None:
        channel = endpoint.accept()
        try:
            deadline = time.monotonic() + 5
            accept_runtime_handshake(channel, identity=identity, deadline=deadline)
            header = channel.read_exact(5, deadline=deadline)
            assert header[:1] == b"S"
            received.append(channel.read_exact(struct.unpack("!I", header[1:])[0], deadline=deadline))
        finally:
            channel.close()

    try:
        endpoint.listen()
        with ThreadPoolExecutor(max_workers=1) as pool:
            serving = pool.submit(serve)
            connection = VerifiedRuntimeConnection(endpoint.connect(), expected=expected, deadline=time.monotonic() + 5)
            try:
                assert connection.hello.boot_id == identity.boot_id
                connection.send_secret(sentinel, deadline=time.monotonic() + 5)
                assert not any(sentinel)
                serving.result(timeout=6)
            finally:
                connection.close()
        assert received == [b"synthetic-channel-secret"]
    finally:
        endpoint.close()


def test_version_mismatch_closes_before_any_secret_frame(tmp_path: Path, namespace: Path) -> None:
    endpoint = PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
    identity = _identity(endpoint)
    expected = RuntimeClientHello(product_version="incompatible", storage_identity=identity.storage_identity)

    def serve() -> RuntimeRefusalCode:
        channel = endpoint.accept()
        try:
            with pytest.raises(RuntimeRefusalError) as caught:
                accept_runtime_handshake(channel, identity=identity, deadline=time.monotonic() + 5)
            return caught.value.reason
        finally:
            channel.close()

    try:
        endpoint.listen()
        with ThreadPoolExecutor(max_workers=1) as pool:
            serving = pool.submit(serve)
            with pytest.raises(RuntimeRefusalError):
                VerifiedRuntimeConnection(endpoint.connect(), expected=expected, deadline=time.monotonic() + 5)
            assert serving.result(timeout=6) is RuntimeRefusalCode.VERSION_MISMATCH
    finally:
        endpoint.close()


@pytest.mark.parametrize(
    "payload",
    [b'{"kind":"client_hello","kind":"client_hello"}', b'{"unexpected":"synthetic-private-input"}', b"NaN"],
)
def test_malformed_frames_refuse_without_echoing_input(payload: bytes) -> None:
    left, right = socket.socketpair()
    channel = PosixRuntimeChannel(left)
    try:
        right.sendall(b"J" + struct.pack("!I", len(payload)) + payload)
        with pytest.raises(RuntimeRefusalError) as caught:
            read_document(channel, RuntimeClientHello, deadline=time.monotonic() + 1)
        assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
        assert "synthetic-private-input" not in str(caught.value)
    finally:
        channel.close()
        right.close()


def test_oversize_is_refused_from_header_without_waiting_for_body() -> None:
    left, right = socket.socketpair()
    channel = PosixRuntimeChannel(left)
    try:
        right.sendall(b"J" + struct.pack("!I", 65537))
        with pytest.raises(RuntimeRefusalError) as caught:
            read_document(channel, RuntimeClientHello, deadline=time.monotonic() + 1)
        assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    finally:
        channel.close()
        right.close()


def test_deadline_bounds_partial_frame() -> None:
    left, right = socket.socketpair()
    channel = PosixRuntimeChannel(left)
    try:
        right.sendall(b"J")
        with pytest.raises(RuntimeRefusalError) as caught:
            read_document(channel, RuntimeClientHello, deadline=time.monotonic() + 0.05)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    finally:
        channel.close()
        with contextlib.suppress(OSError):
            right.close()
