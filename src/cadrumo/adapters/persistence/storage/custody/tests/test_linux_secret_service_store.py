"""Focused native-protocol decisions; positive installed custody is tested separately."""

from __future__ import annotations

import asyncio
import socket
import stat
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import linux_secret_service_store as native
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.linux_secret_service_store import (
    LinuxSecretServiceAutomationSecretStore,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux native dependency and kernel contract"),
]

_NAMESPACE = "cadrumo.automation.client"
_ACCOUNT = "synthetic-account"
_COLLECTION = "/org/freedesktop/secrets/collection/login"
_ITEM = _COLLECTION + "/1"
_SESSION = "/org/freedesktop/secrets/session/s1"
_KEY = b"0123456789abcdef"
_ATTRIBUTES = {
    "application": "cadrumo",
    "namespace": _NAMESPACE,
    "account": _ACCOUNT,
    "xdg:schema": "org.freedesktop.Secret.Generic",
}


def _encrypted(raw: bytes) -> tuple[str, bytes, bytes, str]:
    iv = bytes(range(16))
    padder = padding.PKCS7(128).padder()
    padded = padder.update(raw) + padder.finalize()
    encryptor = Cipher(algorithms.AES(_KEY), modes.CBC(iv)).encryptor()
    return _SESSION, iv, encryptor.update(padded) + encryptor.finalize(), "application/octet-stream"


class _ProtocolReplies:
    """Synthetic method replies isolate selection, validation and prompt decisions."""

    def __init__(self) -> None:
        self.item: bytes | None = None
        self.attributes: dict[str, str] = dict(_ATTRIBUTES)
        self.paths: list[str] | None = None
        self.collection = _COLLECTION
        self.collection_locked = False
        self.item_locked = False
        self.prompt = "/"
        self.content_type = "application/octet-stream"
        self.corrupt_write = False
        self.retain_deleted = False
        self.calls: list[tuple[str, str, str]] = []
        self.closed = 0
        self.verified = 0
        self.failure: Exception | None = None
        self.protection_reason: AutomationCustodyCode | None = None
        self.protection_checks = 0
        self.secret_sessions = 0

    def verify_owner(self) -> None:
        self.verified += 1

    def close(self) -> None:
        self.closed += 1

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
        self.calls.append((path, interface, method))
        if self.failure is not None:
            raise self.failure
        if method == "ReadAlias":
            assert body == ("default",)
            return (self.collection,)
        if method == "Get":
            if body[1] == "Locked":
                return (("b", self.collection_locked if path == _COLLECTION else self.item_locked),)
            assert path == _ITEM and body[1] == "Attributes"
            return (("a{ss}", self.attributes),)
        if method == "SearchItems":
            assert path == _COLLECTION and body == (_ATTRIBUTES,)
            return (self.paths if self.paths is not None else ([_ITEM] if self.item is not None else []),)
        if method == "CreateItem":
            properties, secret, replace = body
            assert replace is True
            assert properties[native._ITEM_IFACE + ".Attributes"] == ("a{ss}", _ATTRIBUTES)
            assert secret[0] == _SESSION
            assert secret[3] == "application/octet-stream"
            if self.prompt == "/":
                session = SimpleNamespace(object_path=_SESSION, aes_key=_KEY)
                secret_bus = SimpleNamespace(call=lambda *args: (secret,))
                self.item = native._read_item(cast(native._DeadlineBus, secret_bus), _ITEM, session)
                if self.corrupt_write:
                    self.item = b"synthetic-corruption"
            return (_ITEM if self.prompt == "/" else "/", self.prompt)
        if method == "GetSecret":
            assert path == _ITEM and self.item is not None
            secret = _encrypted(self.item)
            return ((*secret[:3], self.content_type),)
        if method == "Delete":
            assert path == _ITEM
            if self.prompt == "/" and not self.retain_deleted:
                self.item = None
            return (self.prompt,)
        raise AssertionError(method)


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> _ProtocolReplies:
    bus = _ProtocolReplies()
    monkeypatch.setattr(native.sys, "platform", "linux")
    monkeypatch.setattr(native, "_user_bus_path", lambda: Path("/synthetic/bus"))
    monkeypatch.setattr(native, "_DeadlineBus", lambda *args: bus)

    def protected(owned_bus: Any, collection: str) -> None:
        assert owned_bus is bus and collection == _COLLECTION
        bus.protection_checks += 1
        if bus.protection_reason is not None:
            raise AutomationCustodyError(bus.protection_reason)

    monkeypatch.setattr(native, "require_protected_gnome_collection", protected)

    @contextmanager
    def session(owned_bus: Any) -> Generator[SimpleNamespace]:
        assert owned_bus is bus
        bus.secret_sessions += 1
        yield SimpleNamespace(object_path=_SESSION, aes_key=_KEY, encrypted=True)

    monkeypatch.setattr(native, "_session", session)
    return bus


def test_missing_exact_item_is_absent_and_existing_collection_is_never_created(replies: _ProtocolReplies) -> None:
    assert LinuxSecretServiceAutomationSecretStore().read(_NAMESPACE, _ACCOUNT) is None
    assert all(method not in {"CreateCollection", "Unlock", "Prompt", "OpenSession"} for _, _, method in replies.calls)
    assert replies.closed == 1 and replies.verified == 2
    assert replies.protection_checks == 1


def test_atomic_replacement_and_verified_deletion(replies: _ProtocolReplies) -> None:
    store = LinuxSecretServiceAutomationSecretStore()
    first = SecretBytes(b"synthetic-first-secret\0\xff")
    second = SecretBytes(b"synthetic-replacement-secret")
    store.replace(_NAMESPACE, _ACCOUNT, first)
    assert store.read(_NAMESPACE, _ACCOUNT) == first
    store.replace(_NAMESPACE, _ACCOUNT, second)
    assert store.read(_NAMESPACE, _ACCOUNT) == second
    store.delete(_NAMESPACE, _ACCOUNT)
    store.delete(_NAMESPACE, _ACCOUNT)
    assert store.read(_NAMESPACE, _ACCOUNT) is None
    assert replies.closed == 7
    assert replies.protection_checks == 7


@pytest.mark.parametrize("operation", ["read", "replace", "delete"])
@pytest.mark.parametrize("reason", [AutomationCustodyCode.UNAVAILABLE, AutomationCustodyCode.NEEDS_USER])
def test_unsuitable_collection_refuses_before_items_sessions_or_values(
    replies: _ProtocolReplies, operation: str, reason: AutomationCustodyCode
) -> None:
    replies.item = b"synthetic-existing"
    replies.protection_reason = reason
    store = LinuxSecretServiceAutomationSecretStore()
    with pytest.raises(AutomationCustodyError) as refused:
        if operation == "replace":
            store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-new"))
        else:
            getattr(store, operation)(_NAMESPACE, _ACCOUNT)
    assert refused.value.reason is reason
    assert replies.protection_checks == 1 and replies.secret_sessions == 0
    assert not {"SearchItems", "OpenSession", "GetSecret", "CreateItem", "Delete"} & {
        method for _, _, method in replies.calls
    }
    assert replies.item == b"synthetic-existing" and replies.closed == 1


def test_gnome_text_mime_readback_preserves_binary_secret(replies: _ProtocolReplies) -> None:
    replies.content_type = "text/plain"
    value = SecretBytes(b"synthetic-binary-secret\0\xff\x80")
    store = LinuxSecretServiceAutomationSecretStore()
    store.replace(_NAMESPACE, _ACCOUNT, value)
    assert store.read(_NAMESPACE, _ACCOUNT) == value


@pytest.mark.parametrize("condition", ["collection_locked", "item_locked", "missing_collection"])
def test_locked_or_missing_collection_requires_user_without_unlock(replies: _ProtocolReplies, condition: str) -> None:
    replies.item = b"synthetic-secret"
    if condition == "missing_collection":
        replies.collection = "/"
    else:
        setattr(replies, condition, True)
    with pytest.raises(AutomationCustodyError) as refused:
        LinuxSecretServiceAutomationSecretStore().read(_NAMESPACE, _ACCOUNT)
    assert refused.value.reason is AutomationCustodyCode.NEEDS_USER
    assert not {"Unlock", "Prompt", "CreateCollection"} & {method for _, _, method in replies.calls}
    assert replies.closed == 1


@pytest.mark.parametrize("operation", ["read", "replace", "delete"])
@pytest.mark.parametrize(
    "defect", ["duplicate", "foreign_path", "extra_attribute", "wrong_account", "wrong_schema", "missing_schema"]
)
def test_ambiguous_and_malformed_matches_refuse_before_secret_access(
    replies: _ProtocolReplies, operation: str, defect: str
) -> None:
    replies.item = b"synthetic-secret"
    if defect == "duplicate":
        replies.paths = [_ITEM, _ITEM]
    elif defect == "foreign_path":
        replies.paths = ["/org/freedesktop/secrets/collection/foreign/1"]
    elif defect == "extra_attribute":
        replies.attributes["unexpected"] = "extra"
    elif defect == "wrong_schema":
        replies.attributes["xdg:schema"] = "other.product.Secret"
    elif defect == "missing_schema":
        del replies.attributes["xdg:schema"]
    else:
        replies.attributes["account"] = "other-account"
    store = LinuxSecretServiceAutomationSecretStore()
    with pytest.raises(AutomationCustodyError) as refused:
        if operation == "replace":
            store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-replacement"))
        else:
            getattr(store, operation)(_NAMESPACE, _ACCOUNT)
    expected = AutomationCustodyCode.CONFLICT if defect == "duplicate" else AutomationCustodyCode.INVALID
    assert refused.value.reason is expected
    assert not {"GetSecret", "CreateItem", "Delete"} & {method for _, _, method in replies.calls}
    assert replies.closed == 1


@pytest.mark.parametrize("operation", ["replace", "delete"])
def test_returned_prompt_is_refused_and_never_executed(replies: _ProtocolReplies, operation: str) -> None:
    replies.item = b"synthetic-existing"
    replies.prompt = "/org/freedesktop/secrets/prompt/p1"
    store = LinuxSecretServiceAutomationSecretStore()
    with pytest.raises(AutomationCustodyError) as refused:
        if operation == "replace":
            store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-new"))
        else:
            store.delete(_NAMESPACE, _ACCOUNT)
    assert refused.value.reason is AutomationCustodyCode.NEEDS_USER
    assert replies.item == b"synthetic-existing"
    assert all(method != "Prompt" for _, _, method in replies.calls)


@pytest.mark.parametrize("operation", ["replace", "delete"])
def test_failed_native_readback_refuses_success(replies: _ProtocolReplies, operation: str) -> None:
    replies.item = b"synthetic-existing"
    replies.corrupt_write = True
    replies.retain_deleted = True
    store = LinuxSecretServiceAutomationSecretStore()
    with pytest.raises(AutomationCustodyError) as refused:
        if operation == "replace":
            store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-new"))
        else:
            store.delete(_NAMESPACE, _ACCOUNT)
    assert refused.value.reason is AutomationCustodyCode.INVALID


@pytest.mark.parametrize("failure", [TimeoutError("synthetic-secret"), OSError("synthetic-secret")])
def test_native_failures_are_typed_redacted_and_close_connection(replies: _ProtocolReplies, failure: Exception) -> None:
    replies.failure = failure
    with pytest.raises(AutomationCustodyError) as refused:
        LinuxSecretServiceAutomationSecretStore().read(_NAMESPACE, _ACCOUNT)
    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE
    assert "synthetic-secret" not in str(refused.value)
    assert refused.value.__suppress_context__
    assert replies.closed == 1


@pytest.mark.parametrize("defect", ["session", "iv", "size", "content_type", "padding"])
def test_malformed_encrypted_secret_is_rejected(defect: str) -> None:
    secret = list(_encrypted(b"synthetic-secret"))
    if defect == "session":
        secret[0] = "/org/freedesktop/secrets/session/other"
    elif defect == "iv":
        secret[1] = b"short"
    elif defect == "size":
        secret[2] = b"short"
    elif defect == "content_type":
        secret[3] = "text/plain; charset=utf-8"
    else:
        encryptor = Cipher(algorithms.AES(_KEY), modes.CBC(cast(bytes, secret[1]))).encryptor()
        secret[2] = encryptor.update(b"invalid-padding!") + encryptor.finalize()
    bus = SimpleNamespace(call=lambda *args: (tuple(secret),))
    session = SimpleNamespace(object_path=_SESSION, aes_key=_KEY)
    with pytest.raises((AutomationCustodyError, ValueError)):
        native._read_item(cast(native._DeadlineBus, bus), _ITEM, session)


@pytest.mark.parametrize("content_type", ["", "application/json", None, b"text/plain", {}])
def test_unrecognized_or_nonstring_native_content_type_is_rejected(content_type: object) -> None:
    secret = (*_encrypted(b"synthetic-secret")[:3], content_type)
    bus = SimpleNamespace(call=lambda *args: (secret,))
    session = SimpleNamespace(object_path=_SESSION, aes_key=_KEY)
    with pytest.raises(AutomationCustodyError) as refused:
        native._read_item(cast(native._DeadlineBus, bus), _ITEM, session)
    assert refused.value.reason is AutomationCustodyCode.INVALID


@pytest.mark.parametrize("namespace,account", [("other.product", _ACCOUNT), (_NAMESPACE, ""), (_NAMESPACE, "\0")])
def test_invalid_target_never_connects(monkeypatch: pytest.MonkeyPatch, namespace: str, account: str) -> None:
    def unexpected() -> Any:
        pytest.fail("invalid target attempted native connection")

    monkeypatch.setattr(native, "_native_bus", unexpected)
    with pytest.raises(AutomationCustodyError) as refused:
        LinuxSecretServiceAutomationSecretStore().read(namespace, account)
    assert refused.value.reason is AutomationCustodyCode.INVALID


def test_linux_factory_reaches_native_adapter_read_without_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native.sys, "platform", "linux")
    connections = 0
    missing_bus = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def unavailable_bus() -> Path:
        nonlocal connections
        connections += 1
        raise missing_bus

    monkeypatch.setattr(native, "_user_bus_path", unavailable_bus)
    store = native_automation_secret_store(NativeSecretBackend.LINUX_DBUS)
    assert isinstance(store, LinuxSecretServiceAutomationSecretStore)
    assert store.backend is NativeSecretBackend.LINUX_DBUS
    with pytest.raises(AutomationCustodyError) as refused:
        store.read(_NAMESPACE, _ACCOUNT)
    assert refused.value is missing_bus
    assert connections == 1


@pytest.mark.parametrize(
    "platform,backend",
    [
        ("win32", NativeSecretBackend.LINUX_DBUS),
        ("darwin", NativeSecretBackend.LINUX_DBUS),
        ("linux", NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER),
        ("linux", NativeSecretBackend.MACOS_KEYCHAIN),
    ],
)
def test_native_factory_refuses_platform_backend_mismatch(
    monkeypatch: pytest.MonkeyPatch, platform: str, backend: NativeSecretBackend
) -> None:
    monkeypatch.setattr(native.sys, "platform", platform)
    with pytest.raises(AutomationCustodyError) as refused:
        native_automation_secret_store(backend)
    assert refused.value.reason is AutomationCustodyCode.UNSUPPORTED


def test_linux_native_adapter_refuses_wrong_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native.sys, "platform", "win32")
    with pytest.raises(AutomationCustodyError) as refused:
        LinuxSecretServiceAutomationSecretStore().replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic"))
    assert refused.value.reason is AutomationCustodyCode.UNSUPPORTED


def test_encrypted_session_uses_pinned_codec_and_closes_without_plain_fallback() -> None:
    if sys.platform != "linux":
        pytest.skip("Linux Secret Service codec dependency")
    session_calls: list[str] = []
    client_public = 0

    def reply(
        path: str, interface: str, method: str, signature: str = "", body: tuple[Any, ...] = ()
    ) -> tuple[Any, ...]:
        nonlocal client_public
        session_calls.append(method)
        if method == "OpenSession":
            assert body[0] == "dh-ietf1024-sha256-aes128-cbc-pkcs7"
            assert body[1][0] == "ay"
            client_public = int.from_bytes(body[1][1], "big")
            return (("ay", b"\x04"), _SESSION)
        assert method == "Close" and path == _SESSION
        return ()

    bus = SimpleNamespace(call=reply)
    with native._session(cast(native._DeadlineBus, bus)) as session:
        from secretstorage.dhcrypto import DH_PRIME_1024

        common = pow(client_public, 2, DH_PRIME_1024).to_bytes(128, "big")
        expected = HKDF(algorithm=hashes.SHA256(), length=16, salt=None, info=b"").derive(common)
        assert session.aes_key == expected
        assert session.object_path == _SESSION
    assert session_calls == ["OpenSession", "Close"]
    assert session.aes_key is None and session.my_private_key == 0


@pytest.mark.parametrize("peer", [b"", b"\x00", b"\x01", b"\x02" * 129])
def test_malformed_session_negotiation_is_rejected(peer: bytes) -> None:
    bus = SimpleNamespace(call=lambda *args: (("ay", peer), _SESSION))
    with pytest.raises(AutomationCustodyError) as refused, native._session(cast(native._DeadlineBus, bus)):
        pytest.fail("invalid session was admitted")
    assert refused.value.reason is AutomationCustodyCode.INVALID


@pytest.mark.parametrize(
    "defect", ["none", "directory_mode", "directory_owner", "directory_link", "bus_owner", "bus_link"]
)
def test_user_bus_selection_rejects_untrusted_paths_and_ignores_ambient_address(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    monkeypatch.setattr(native.os, "getuid", lambda: 1001, raising=False)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "tcp:host=untrusted.invalid,port=1")

    def metadata(path: Path) -> SimpleNamespace:
        owner, mode = (0, stat.S_IFDIR | 0o755)
        if str(path) == "/run/user/1001":
            owner, mode = 1001, stat.S_IFDIR | 0o700
            if defect == "directory_mode":
                mode = stat.S_IFDIR | 0o755
            elif defect == "directory_owner":
                owner = 1002
            elif defect == "directory_link":
                mode = stat.S_IFLNK | 0o700
        elif str(path) == "/run/user/1001/bus":
            owner, mode = 1001, stat.S_IFSOCK | 0o666
            if defect == "bus_owner":
                owner = 1002
            elif defect == "bus_link":
                mode = stat.S_IFLNK | 0o700
        return SimpleNamespace(st_uid=owner, st_mode=mode)

    monkeypatch.setattr(Path, "lstat", metadata)
    if defect == "none":
        assert native._user_bus_path() == Path("/run/user/1001/bus")
    else:
        with pytest.raises(AutomationCustodyError) as refused:
            native._user_bus_path()
        assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE


@pytest.mark.parametrize("stage", ["authentication", "hello"])
def test_native_socket_deadline_covers_authentication_and_hello(tmp_path: Path, stage: str) -> None:
    if sys.platform != "linux":
        pytest.skip("Linux native Unix socket contract")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    path = tmp_path / "bus"
    listener.bind(str(path))
    listener.listen(1)
    release = threading.Event()
    failures: list[Exception] = []

    def stall() -> None:
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(2)
                connection.recv(1024)
                if stage == "hello":
                    connection.sendall(b"OK " + b"0" * 32 + b"\r\n")
                    connection.recv(4096)
                release.wait(2)
        except Exception as error:
            failures.append(error)

    server = threading.Thread(target=stall)
    server.start()
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            native._DeadlineBus(path, started + 0.1)
        assert time.monotonic() - started < 1
    finally:
        release.set()
        server.join(timeout=2)
        listener.close()
    assert not server.is_alive()
    assert not failures


class _ConsumedSocketClosePort:
    """Explicit socket port whose first native close consumes its capability."""

    def __init__(self, primary: BaseException, cleanup: BaseException) -> None:
        self.primary = primary
        self.cleanup = cleanup
        self.closed = False
        self.close_calls = 0

    def settimeout(self, timeout: float) -> None:
        del timeout

    def connect(self, path: str) -> None:
        del path
        raise self.primary

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.close_calls += 1
            raise self.cleanup


@pytest.mark.parametrize("stage", ["parser", "connect"])
@pytest.mark.parametrize("mode", ["typed", "cancel", "native"])
def test_native_bus_constructor_preserves_primary_when_socket_close_fails(
    monkeypatch: pytest.MonkeyPatch, stage: str, mode: str
) -> None:
    if sys.platform != "linux":
        pytest.skip("Linux native Unix socket contract")
    import jeepney

    primary: BaseException = (
        AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        if mode == "typed"
        else asyncio.CancelledError("synthetic constructor cancellation")
        if mode == "cancel"
        else OSError("synthetic native construction failure")
    )
    cleanup = OSError("synthetic consumed socket close failure")
    port = _ConsumedSocketClosePort(primary, cleanup)
    monkeypatch.setattr(
        native,
        "socket",
        SimpleNamespace(AF_UNIX=socket.AF_UNIX, SOCK_STREAM=socket.SOCK_STREAM, socket=lambda *_: port),
    )
    if stage == "parser":

        def failed_parser() -> None:
            raise primary

        monkeypatch.setattr(jeepney, "Parser", failed_parser)
    with pytest.raises(BaseException) as caught:
        native._DeadlineBus(Path("/synthetic/bus"), time.monotonic() + 1)
    assert caught.value is primary
    assert caught.value.__dict__["cleanup_error"] is cleanup
    assert port.closed and port.close_calls == 1
    port.close()
    assert port.close_calls == 1


def _failing_bus_close(monkeypatch: pytest.MonkeyPatch, replies: _ProtocolReplies, cleanup: BaseException) -> None:
    consumed = False

    def close() -> None:
        nonlocal consumed
        if not consumed:
            consumed = True
            replies.closed += 1
            raise cleanup

    monkeypatch.setattr(replies, "close", close)


@pytest.mark.parametrize("mode", ["typed", "cancel", "native"])
def test_native_bus_body_failure_preserves_primary_and_close_diagnostic(
    monkeypatch: pytest.MonkeyPatch, replies: _ProtocolReplies, mode: str
) -> None:
    primary: BaseException = (
        AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        if mode == "typed"
        else asyncio.CancelledError("synthetic operation cancellation")
        if mode == "cancel"
        else OSError("synthetic native operation failure")
    )
    cleanup = OSError("synthetic consumed socket close failure")

    def fail(*args: object, **kwargs: object) -> tuple[Any, ...]:
        del args, kwargs
        raise primary

    monkeypatch.setattr(replies, "call", fail)
    _failing_bus_close(monkeypatch, replies, cleanup)
    with pytest.raises(BaseException) as caught:
        LinuxSecretServiceAutomationSecretStore().delete(_NAMESPACE, _ACCOUNT)
    if mode == "native":
        assert isinstance(caught.value, AutomationCustodyError)
        assert caught.value.reason is AutomationCustodyCode.UNAVAILABLE
        assert "synthetic native operation failure" not in str(caught.value)
    else:
        assert caught.value is primary
    assert caught.value.__dict__["cleanup_error"] is cleanup
    assert replies.closed == 1
    replies.close()
    assert replies.closed == 1


def test_successful_native_delete_refuses_when_socket_close_fails(
    monkeypatch: pytest.MonkeyPatch, replies: _ProtocolReplies
) -> None:
    cleanup = OSError("synthetic consumed socket close failure")
    _failing_bus_close(monkeypatch, replies, cleanup)
    with pytest.raises(AutomationCustodyError) as caught:
        LinuxSecretServiceAutomationSecretStore().delete(_NAMESPACE, _ACCOUNT)
    assert caught.value.reason is AutomationCustodyCode.UNAVAILABLE
    assert replies.closed == 1
    assert any(method == "SearchItems" for _, _, method in replies.calls)
    assert "synthetic consumed socket close failure" not in str(caught.value)


class _EarlierBusCleanupOwner:
    def __init__(self) -> None:
        self.calls = 0
        self.failing = True

    async def close(self) -> None:
        self.calls += 1
        if self.failing:
            raise OSError("synthetic earlier owner failure")


@pytest.mark.parametrize("mode", ["typed", "cancel", "aliased"])
def test_bus_close_failure_keeps_only_the_earlier_actual_retry_owner(
    monkeypatch: pytest.MonkeyPatch, replies: _ProtocolReplies, mode: str
) -> None:
    owner = _EarlierBusCleanupOwner()
    primary: BaseException = (
        asyncio.CancelledError("synthetic operation cancellation")
        if mode == "cancel"
        else AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    )
    try:
        asyncio.run(close_async_resources(owner, task_name="earlier-bus-cleanup", primary_error=primary))
    except asyncio.CancelledError as caught:
        assert caught is primary
    field = "cleanup_error" if mode == "cancel" else "async_cleanup_error"
    previous = primary.__dict__[field]
    assert isinstance(previous, AsyncResourceCleanupError)
    if mode == "aliased":
        primary.__dict__["cleanup_error"] = previous

    def fail(*args: object, **kwargs: object) -> tuple[Any, ...]:
        del args, kwargs
        raise primary

    monkeypatch.setattr(replies, "call", fail)
    cleanup = OSError("synthetic consumed socket close failure")
    _failing_bus_close(monkeypatch, replies, cleanup)
    with pytest.raises(BaseException) as caught:
        LinuxSecretServiceAutomationSecretStore().replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-value"))
    assert caught.value is primary
    retained = caught.value.__dict__[field]
    assert isinstance(retained, AsyncResourceCleanupError)
    assert retained.resources == (owner,)
    if mode == "typed":
        assert retained is previous
        assert caught.value.__dict__["cleanup_error"] is cleanup
    else:
        assert retained.__cause__ is cleanup
    if mode == "aliased":
        assert caught.value.__dict__["cleanup_error"] is retained
    owner.failing = False
    asyncio.run(retained.retry_cleanup())
    assert owner.calls == 2
    assert replies.closed == 1


def test_bus_close_failure_preserves_an_earlier_raw_cancellation_diagnostic(
    monkeypatch: pytest.MonkeyPatch, replies: _ProtocolReplies
) -> None:
    primary = asyncio.CancelledError("synthetic operation cancellation")
    previous = OSError("synthetic earlier cleanup diagnostic")

    async def failed_cleanup() -> None:
        raise previous

    with pytest.raises(asyncio.CancelledError) as prepared:
        asyncio.run(
            await_cancellation_complete(failed_cleanup(), task_name="earlier-bus-diagnostic", cancellation=primary)
        )
    assert prepared.value is primary
    assert primary.__dict__["cleanup_error"] is previous

    def fail(*args: object, **kwargs: object) -> tuple[Any, ...]:
        del args, kwargs
        raise primary

    monkeypatch.setattr(replies, "call", fail)
    cleanup = OSError("synthetic consumed socket close failure")
    _failing_bus_close(monkeypatch, replies, cleanup)
    with pytest.raises(asyncio.CancelledError) as caught:
        LinuxSecretServiceAutomationSecretStore().read(_NAMESPACE, _ACCOUNT)
    assert caught.value is primary
    retained = caught.value.__dict__["cleanup_error"]
    assert isinstance(retained, BaseExceptionGroup)
    assert retained.exceptions == (previous, cleanup)
    assert replies.closed == 1


def test_native_bus_preserves_an_escaping_canonical_cleanup_aggregate(
    monkeypatch: pytest.MonkeyPatch, replies: _ProtocolReplies
) -> None:
    owner = _EarlierBusCleanupOwner()
    with pytest.raises(AsyncResourceCleanupError) as prepared:
        asyncio.run(close_async_resources(owner, task_name="earlier-bus-aggregate", primary_error=None))
    primary = prepared.value

    def fail(*args: object, **kwargs: object) -> tuple[Any, ...]:
        del args, kwargs
        raise primary

    monkeypatch.setattr(replies, "call", fail)
    cleanup = OSError("synthetic consumed socket close failure")
    _failing_bus_close(monkeypatch, replies, cleanup)
    with pytest.raises(AsyncResourceCleanupError) as caught:
        LinuxSecretServiceAutomationSecretStore().read(_NAMESPACE, _ACCOUNT)
    assert caught.value is primary
    assert primary.resources == (owner,)
    assert primary.__dict__["cleanup_error"] is cleanup
    owner.failing = False
    asyncio.run(primary.retry_cleanup())
    assert owner.calls == 2
    assert replies.closed == 1


class _FailingSessionClose:
    """Actual encrypted negotiation with an explicit terminal close-failure port."""

    def __init__(self, failure: BaseException) -> None:
        self.failure = failure
        self.calls: list[str] = []

    def call(
        self, path: str, interface: str, method: str, signature: str = "", body: tuple[Any, ...] = ()
    ) -> tuple[Any, ...]:
        self.calls.append(method)
        if method == "OpenSession":
            assert path == native._ROOT and interface == native._SERVICE_IFACE
            assert signature == "sv" and body[0] == native._ALGORITHM
            assert body[1][0] == "ay" and len(body[1][1]) == 128
            return (("ay", b"\x04"), _SESSION)
        assert method == "Close" and path == _SESSION and interface == native._SESSION_IFACE
        raise self.failure


@pytest.mark.parametrize("mode", ["typed", "cancel", "clean"])
def test_encrypted_session_close_preserves_body_primary_and_wipes_keys(mode: str) -> None:
    primary: BaseException | None = (
        AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        if mode == "typed"
        else asyncio.CancelledError("synthetic original session cancellation")
        if mode == "cancel"
        else None
    )
    cleanup = (
        OSError("synthetic session close failure")
        if primary is None
        else asyncio.CancelledError("synthetic terminal session close cancellation")
    )
    bus = _FailingSessionClose(cleanup)
    captured: list[Any] = []
    with pytest.raises(BaseException) as caught, native._session(cast(native._DeadlineBus, bus)) as session:
        captured.append(session)
        assert session.aes_key is not None and session.my_private_key != 0
        if primary is not None:
            raise primary
    assert caught.value is (cleanup if primary is None else primary)
    if primary is not None:
        assert primary.__dict__["cleanup_error"] is cleanup
    assert bus.calls == ["OpenSession", "Close"]
    assert captured[0].aes_key is None and captured[0].my_private_key == 0


@pytest.mark.parametrize("kind", ["aliased", "aggregate", "raw"])
def test_encrypted_session_close_retains_previous_cleanup_identity(kind: str) -> None:
    owner = _EarlierBusCleanupOwner()
    with pytest.raises(AsyncResourceCleanupError) as prepared:
        asyncio.run(close_async_resources(owner, task_name="earlier-session-cleanup", primary_error=None))
    previous = prepared.value
    primary: BaseException = previous if kind == "aggregate" else AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    raw = OSError("synthetic earlier session diagnostic")
    if kind == "aliased":
        primary.__dict__["cleanup_error"] = previous
        primary.__dict__["async_cleanup_error"] = previous
    elif kind == "raw":
        primary.__dict__["cleanup_error"] = raw
        primary.__dict__["async_cleanup_error"] = previous
    cleanup = asyncio.CancelledError("synthetic terminal session close cancellation")
    bus = _FailingSessionClose(cleanup)
    captured: list[Any] = []
    with pytest.raises(BaseException) as caught, native._session(cast(native._DeadlineBus, bus)) as session:
        captured.append(session)
        raise primary
    assert caught.value is primary
    retained = primary.__dict__["cleanup_error"]
    if kind == "aliased":
        assert isinstance(retained, AsyncResourceCleanupError)
        assert primary.__dict__["async_cleanup_error"] is retained
        assert retained.resources == (owner,) and retained.__cause__ is cleanup
    elif kind == "raw":
        assert isinstance(retained, BaseExceptionGroup)
        assert retained.exceptions == (raw, cleanup)
        assert primary.__dict__["async_cleanup_error"] is previous
        retained = previous
    else:
        assert isinstance(primary, AsyncResourceCleanupError)
        assert retained is cleanup and primary.resources == (owner,)
        retained = primary
    owner.failing = False
    asyncio.run(retained.retry_cleanup())
    assert owner.calls == 2
    assert bus.calls == ["OpenSession", "Close"]
    assert captured[0].aes_key is None and captured[0].my_private_key == 0
