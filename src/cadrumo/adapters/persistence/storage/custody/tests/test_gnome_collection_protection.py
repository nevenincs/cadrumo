"""GNOME collection identity, read-only wire bounds and suitability refusals."""

from __future__ import annotations

import os
import socket
import stat
import struct
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody import gnome_collection_protection as protection
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux native metadata and kernel contract"),
]

_COLLECTION = "/org/freedesktop/secrets/collection/login"
_SESSION = 42


def _uid() -> int:
    if sys.platform == "linux":
        return os.getuid()
    pytest.skip("Linux native metadata and kernel contract")


class _SocketDouble:
    """Declared socket subset used by the production metadata transport."""

    def __init__(
        self,
        response: bytes = b"",
        *,
        peer_pid: int = 123,
        peer_uid: int | None = None,
        may_send: bool = True,
        fragment_limit: int = 65536,
    ) -> None:
        self.response = bytearray(response)
        self.peer_pid = peer_pid
        self.peer_uid = _uid() if peer_uid is None else peer_uid
        self.may_send = may_send
        self.fragment_limit = fragment_limit
        self.sent: list[bytes] = []
        self.closed = False

    def settimeout(self, value: float | None) -> None:
        pass

    def connect(self, address: str) -> None:
        assert address == "/proc/self/fd/99/pkcs11"

    def getsockopt(self, level: int, option: int, length: int) -> bytes:
        if sys.platform != "linux":
            raise RuntimeError("Linux peer credentials require Linux")
        assert level == socket.SOL_SOCKET and option == socket.SO_PEERCRED and length == 12
        return struct.pack("3i", self.peer_pid, self.peer_uid, 0)

    def sendall(self, data: bytes) -> None:
        if not self.may_send:
            pytest.fail("refused metadata connection sent protocol data")
        self.sent.append(data)

    def recv(self, length: int) -> bytes:
        count = min(length, self.fragment_limit)
        result = bytes(self.response[:count])
        del self.response[:count]
        return result

    def close(self) -> None:
        self.closed = True


class _RepliesRpc:
    """Native-format metadata replies with no credential operations available."""

    def __init__(self, *, identifier: bytes = b"login") -> None:
        self.identifier = identifier
        self.values = {
            protection._CLASS: struct.pack("@L", protection._COLLECTION_CLASS),
            protection._ID: identifier,
            protection._TOKEN: b"\x01",
            protection._TRANSIENT: b"\0",
            protection._TRUSTED: b"\x01",
            protection._LOCKED: b"\0",
        }
        self.calls: list[str] = []
        self.matches: tuple[int, ...] = (17,)
        self.token_serial = b"1:SECRET:MAIN"
        self.closed = False
        self.failure: Exception | None = None

    def call(self, name: str, payload: bytes = b"") -> protection._Reader:
        self.calls.append(name)
        assert name in protection._CALLS
        if name == "C_Initialize":
            assert payload == b"\x01" + protection._blob(protection._HANDSHAKE)
        elif name == "C_GetSlotList":
            assert payload == b"\x01" + protection._u32(protection._MAX_SLOTS)
            return protection._Reader(b"\x01" + protection._u32(1) + protection._ulong(9))
        elif name == "C_GetTokenInfo":
            assert payload == protection._ulong(9)
            data = b"".join(
                protection._blob(value.ljust(length, b" "))
                for value, length in (
                    (b"Secret Store", 32),
                    (b"Gnome Keyring", 32),
                    (b"", 16),
                    (self.token_serial, 16),
                )
            )
            return protection._Reader(data + b"\0" * (11 * 8 + 4) + protection._blob(b" " * 16))
        elif name == "C_OpenSession":
            assert payload == protection._ulong(9) + protection._ulong(4)
            return protection._Reader(protection._ulong(_SESSION))
        elif name == "C_FindObjectsInit":
            reader = protection._Reader(payload)
            assert reader.number(8) == _SESSION and reader.number() == 2
            for kind, value in (
                (protection._CLASS, struct.pack("@L", protection._COLLECTION_CLASS)),
                (protection._ID, self.identifier),
            ):
                assert reader.number() == kind and reader.take(1) == b"\x01"
                assert reader.number() == len(value) and reader.blob() == value
            reader.finish()
        elif name == "C_FindObjects":
            assert payload == protection._ulong(_SESSION) + protection._u32(2)
            data = b"\x01" + protection._u32(len(self.matches))
            return protection._Reader(data + b"".join(protection._ulong(value) for value in self.matches))
        elif name == "C_FindObjectsFinal":
            assert payload == protection._ulong(_SESSION)
        elif name == "C_GetAttributeValue":
            if self.failure is not None:
                raise self.failure
            reader = protection._Reader(payload)
            assert reader.number(8) == _SESSION and reader.number(8) == self.matches[0]
            assert reader.number() == 6
            requested = [(reader.number(), reader.number()) for _ in range(6)]
            reader.finish()
            assert [kind for kind, _ in requested] == [
                protection._CLASS,
                protection._ID,
                protection._TOKEN,
                protection._TRANSIENT,
                protection._TRUSTED,
                protection._LOCKED,
            ]
            data = protection._u32(6)
            for kind, _length in requested:
                data += protection._u32(kind)
                if kind not in self.values:
                    data += b"\0"
                else:
                    value = self.values[kind]
                    data += b"\x01" + protection._u32(len(value)) + protection._blob(value)
            return protection._Reader(data + protection._ulong(0))
        elif name == "C_CloseSession":
            assert payload == protection._ulong(_SESSION)
        elif name == "C_Finalize":
            assert payload == b""
        else:
            pytest.fail(f"unexpected metadata call {name}")
        return protection._Reader(b"")

    def empty(self, name: str, payload: bytes = b"") -> None:
        self.call(name, payload).finish()

    def close(self) -> None:
        self.closed = True


class _Bus:
    """Already selected native owner; only public metadata queries are allowed."""

    def __init__(self) -> None:
        self.deadline = time.monotonic() + 5
        self.owner: str | None = ":1.9"
        self.gnome_owner = self.owner
        self.alias = _COLLECTION
        self.locked = False
        self.owner_changes = False
        self.verified = 0
        self.calls: list[str] = []

    def verify_owner(self) -> None:
        self.verified += 1
        if self.owner_changes and self.verified == 2:
            self.owner = ":1.10"

    def call(
        self,
        path: str,
        interface: str,
        method: str,
        signature: str = "",
        body: tuple[Any, ...] = (),
        *,
        destination: str | None = None,
    ) -> tuple[Any, ...]:
        self.calls.append(method)
        if method == "GetNameOwner":
            assert body == ("org.gnome.keyring",) and destination == protection._BUS
            return (self.gnome_owner,)
        if method == "GetConnectionUnixProcessID":
            assert body == (self.owner,) and destination == protection._BUS
            return (123,)
        if method == "GetControlDirectory":
            assert path == "/org/gnome/keyring/daemon" and destination is None
            return ("/synthetic/control",)
        if method == "ReadAlias":
            assert body == ("default",)
            return (self.alias,)
        assert method == "Get" and path == _COLLECTION and body[1] == "Locked"
        return (("b", self.locked),)


@pytest.fixture
def native_metadata(monkeypatch: pytest.MonkeyPatch) -> tuple[_Bus, _RepliesRpc]:
    bus, rpc = _Bus(), _RepliesRpc()
    monkeypatch.setattr(protection, "_control_directory", lambda control: (Path(control), 99))
    monkeypatch.setattr(protection.os, "close", lambda descriptor: None)

    def connection(directory_fd: int, *, provider_pid: int, deadline: float) -> _RepliesRpc:
        assert directory_fd == 99 and provider_pid == 123 and deadline == bus.deadline
        return rpc

    monkeypatch.setattr(protection, "_MetadataRpc", connection)
    return bus, rpc


@pytest.mark.parametrize("suffix,identifier", [("login", b"login"), ("a_5fb_2fc", b"a_b/c"), ("_c3_a9", b"\xc3\xa9")])
def test_collection_id_uses_canonical_gnome_byte_escaping(suffix: str, identifier: bytes) -> None:
    assert protection.gnome_collection_id(protection._PREFIX + suffix) == identifier


@pytest.mark.parametrize("suffix", ["", "login/1", "bare_", "_00", "_61", "_AF", "_gg", "Ã©"])
def test_unsupported_collection_identity_is_refused(suffix: str) -> None:
    with pytest.raises(AutomationCustodyError):
        protection.gnome_collection_id(protection._PREFIX + suffix)


def test_protected_metadata_uses_exact_read_only_subset_and_original_deadline(
    native_metadata: tuple[_Bus, _RepliesRpc],
) -> None:
    bus, rpc = native_metadata
    before = bus.deadline
    protection.require_protected_gnome_collection(bus, _COLLECTION)
    assert bus.deadline == before and bus.verified == 2 and rpc.closed
    assert rpc.calls == [
        "C_Initialize",
        "C_GetSlotList",
        "C_GetTokenInfo",
        "C_OpenSession",
        "C_FindObjectsInit",
        "C_FindObjects",
        "C_FindObjectsFinal",
        "C_GetAttributeValue",
        "C_CloseSession",
        "C_Finalize",
    ]
    assert set(bus.calls) == {"GetNameOwner", "GetConnectionUnixProcessID", "GetControlDirectory", "ReadAlias", "Get"}


@pytest.mark.parametrize(
    "kind,value,reason",
    [
        (protection._TRUSTED, b"\0", AutomationCustodyCode.NEEDS_USER),
        (protection._LOCKED, b"\x01", AutomationCustodyCode.NEEDS_USER),
        (protection._TOKEN, b"\0", AutomationCustodyCode.UNAVAILABLE),
        (protection._TRANSIENT, b"\x01", AutomationCustodyCode.UNAVAILABLE),
        (protection._TRUSTED, b"\x02", AutomationCustodyCode.INVALID),
        (protection._ID, b"other", AutomationCustodyCode.INVALID),
    ],
)
def test_unsuitable_or_malformed_collection_refuses_after_own_session_cleanup(
    native_metadata: tuple[_Bus, _RepliesRpc], kind: int, value: bytes, reason: AutomationCustodyCode
) -> None:
    bus, rpc = native_metadata
    rpc.values[kind] = value
    with pytest.raises(AutomationCustodyError) as refused:
        protection.require_protected_gnome_collection(bus, _COLLECTION)
    assert refused.value.reason is reason
    assert rpc.calls[-2:] == ["C_CloseSession", "C_Finalize"] and rpc.closed


@pytest.mark.parametrize("defect", ["missing_attribute", "duplicate_collection", "missing_collection", "wrong_token"])
def test_missing_or_ambiguous_native_capability_is_unavailable(
    native_metadata: tuple[_Bus, _RepliesRpc], defect: str
) -> None:
    bus, rpc = native_metadata
    if defect == "missing_attribute":
        del rpc.values[protection._TRUSTED]
    elif defect == "duplicate_collection":
        rpc.matches = (17, 18)
    elif defect == "missing_collection":
        rpc.matches = ()
    else:
        rpc.token_serial = b"other"
    with pytest.raises(AutomationCustodyError) as refused:
        protection.require_protected_gnome_collection(bus, _COLLECTION)
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE and rpc.closed
    assert rpc.calls[-1] == "C_Finalize"
    assert "C_GetAttributeValue" not in rpc.calls or defect == "missing_attribute"


@pytest.mark.parametrize("defect", ["gnome_owner", "owner_change", "alias_change", "locked_after_metadata"])
def test_native_owner_and_alias_remain_bound_to_selected_collection(
    native_metadata: tuple[_Bus, _RepliesRpc], defect: str
) -> None:
    bus, rpc = native_metadata
    if defect == "gnome_owner":
        bus.gnome_owner = ":1.99"
    elif defect == "owner_change":
        bus.owner_changes = True
    elif defect == "alias_change":
        bus.alias = protection._PREFIX + "foreign"
    else:
        bus.locked = True
    with pytest.raises(AutomationCustodyError) as refused:
        protection.require_protected_gnome_collection(bus, _COLLECTION)
    expected = (
        AutomationCustodyCode.NEEDS_USER if defect == "locked_after_metadata" else AutomationCustodyCode.UNAVAILABLE
    )
    assert refused.value.reason is expected
    if defect == "gnome_owner":
        assert rpc.calls == []
    else:
        assert rpc.closed


def test_native_error_is_redacted_and_finalizes_only_owned_session(native_metadata: tuple[_Bus, _RepliesRpc]) -> None:
    bus, rpc = native_metadata
    rpc.failure = OSError("synthetic-private-provider-text")
    with pytest.raises(AutomationCustodyError) as refused:
        protection.require_protected_gnome_collection(bus, _COLLECTION)
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE
    assert "synthetic-private-provider-text" not in str(refused.value) and refused.value.__suppress_context__
    assert rpc.calls[-2:] == ["C_CloseSession", "C_Finalize"] and rpc.closed


def test_unsupported_native_metadata_maps_to_missing_capability(
    native_metadata: tuple[_Bus, _RepliesRpc],
) -> None:
    bus, rpc = native_metadata
    rpc.failure = AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    with pytest.raises(AutomationCustodyError) as refused:
        protection.require_protected_gnome_collection(bus, _COLLECTION)
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE and rpc.closed


@pytest.mark.parametrize("defect", ["parent_link", "parent_owner", "parent_writable", "control_link", "control_mode"])
def test_control_directory_refuses_symlinks_foreign_owners_and_unsafe_modes(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    def metadata(path: Path) -> SimpleNamespace:
        owner, mode = _uid(), stat.S_IFDIR | 0o700
        if path == Path("/synthetic"):
            if defect == "parent_link":
                mode = stat.S_IFLNK | 0o700
            elif defect == "parent_owner":
                owner = _uid() + 1
            elif defect == "parent_writable":
                mode |= 0o022
        elif path == Path("/synthetic/control"):
            if defect == "control_link":
                mode = stat.S_IFLNK | 0o700
            elif defect == "control_mode":
                mode |= 0o077
        return SimpleNamespace(st_uid=owner, st_mode=mode)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(AutomationCustodyError) as refused:
        protection._control_directory("/synthetic/control")
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE


@pytest.mark.parametrize("defect", ["socket_link", "socket_owner", "socket_mode", "peer_pid", "peer_uid", "inode"])
def test_pkcs11_endpoint_requires_exact_native_peer_and_unchanged_owned_socket(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    uid = _uid()
    observed = 0

    def metadata(path: str, *, dir_fd: int, follow_symlinks: bool) -> SimpleNamespace:
        nonlocal observed
        assert path == "pkcs11" and dir_fd == 99 and follow_symlinks is False
        observed += 1
        return SimpleNamespace(
            st_uid=uid + (defect == "socket_owner"),
            st_mode=(stat.S_IFLNK if defect == "socket_link" else stat.S_IFSOCK)
            | (0o666 if defect == "socket_mode" else 0o600),
            st_dev=1,
            st_ino=2 + (defect == "inode" and observed == 2),
        )

    fake = _SocketDouble(peer_pid=123 + (defect == "peer_pid"), peer_uid=uid + (defect == "peer_uid"), may_send=False)
    monkeypatch.setattr(protection.os, "stat", metadata)
    monkeypatch.setattr(protection.socket, "socket", lambda *args: fake)
    with pytest.raises(AutomationCustodyError) as refused:
        protection._MetadataRpc(99, provider_pid=123, deadline=time.monotonic() + 5)
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE and fake.closed


@pytest.mark.parametrize(
    "response",
    [
        protection._u32(protection._MAX_FRAME + 1),
        protection._u32(8) + protection._u32(99) + protection._blob(b""),
        protection._u32(12) + protection._u32(0) + protection._ulong(0),
    ],
)
def test_wire_rejects_unbounded_uncorrelated_and_malformed_error_frames(response: bytes) -> None:
    rpc = object.__new__(protection._MetadataRpc)
    rpc.deadline = time.monotonic() + 5
    rpc.sock = _SocketDouble(response)
    with pytest.raises(AutomationCustodyError) as refused:
        rpc.empty("C_Finalize")
    assert refused.value.reason is AutomationCustodyCode.INVALID


def test_wire_accepts_correlated_fragmented_reply_and_redacts_public_native_failure() -> None:
    rpc = object.__new__(protection._MetadataRpc)
    rpc.deadline = time.monotonic() + 5
    fake = _SocketDouble(protection._u32(8) + protection._u32(2) + protection._blob(b""), fragment_limit=2)
    rpc.sock = fake
    rpc.empty("C_Finalize")
    assert fake.sent == [protection._u32(8) + protection._u32(2) + protection._blob(b"")]
    fake.response.extend(protection._u32(12) + protection._u32(0) + protection._ulong(0x101))
    with pytest.raises(AutomationCustodyError) as refused:
        rpc.empty("C_Finalize")
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE


def test_expired_rpc_deadline_and_disallowed_call_never_send_protocol_data() -> None:
    rpc = object.__new__(protection._MetadataRpc)
    rpc.deadline = time.monotonic() - 1
    rpc.sock = _SocketDouble(may_send=False)
    with pytest.raises(AutomationCustodyError) as refused:
        rpc.call("C_Login")
    assert refused.value.reason is AutomationCustodyCode.INVALID
    with pytest.raises(AutomationCustodyError) as expired:
        rpc.call("C_Finalize")
    assert expired.value.reason is AutomationCustodyCode.UNAVAILABLE
