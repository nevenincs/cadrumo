"""Portable native-contract detectors; real macOS custody acceptance is separate."""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from typing import cast, override

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import macos_keychain_store as native
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)

from .. import macos_core_foundation, macos_keychain_contracts, macos_keychain_policy, macos_login_keychain

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.automation.client"
_ACCOUNT = "synthetic-exact-account"
_KEYCHAIN = "/Users/synthetic/Library/Keychains/login.keychain-db"
_IDENTITY = macos_keychain_contracts.KeychainItemIdentity(_NAMESPACE, _ACCOUNT, _KEYCHAIN)


class _MemoryNativeApi:
    """Isolate the byte-oriented native port; never attest an OS facility."""

    def __init__(self) -> None:
        self.item: macos_keychain_contracts.KeychainItem | None = None
        self.calls: list[tuple[str, macos_keychain_contracts.KeychainItemIdentity]] = []
        self.updates: list[int] = []
        self.add_status = macos_keychain_contracts.SUCCESS
        self.delete_status = macos_keychain_contracts.SUCCESS
        self.corrupt_write = False
        self.retain_delete = False
        self.session_error: AutomationCustodyCode | None = None
        self.read_error: AutomationCustodyCode | None = None
        self.restore_failure = False
        self.sessions = 0
        self.closed_sessions = 0

    @contextmanager
    def session(self) -> Generator[str]:
        if self.session_error is not None:
            raise AutomationCustodyError(self.session_error)
        self.sessions += 1
        try:
            yield _KEYCHAIN
        finally:
            self.closed_sessions += 1
            if self.restore_failure:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def read(
        self, identity: macos_keychain_contracts.KeychainItemIdentity
    ) -> macos_keychain_contracts.KeychainItem | None:
        self.calls.append(("read", identity))
        if self.read_error is not None:
            raise AutomationCustodyError(self.read_error)
        return self.item

    def update(self, identity: macos_keychain_contracts.KeychainItemIdentity, value: bytes) -> int:
        self.calls.append(("update", identity))
        status = (
            self.updates.pop(0)
            if self.updates
            else (macos_keychain_contracts.NOT_FOUND if self.item is None else macos_keychain_contracts.SUCCESS)
        )
        if status == macos_keychain_contracts.SUCCESS:
            self.item = macos_keychain_contracts.KeychainItem(
                identity, True, b"synthetic-mismatch" if self.corrupt_write else value
            )
        return status

    def add(self, identity: macos_keychain_contracts.KeychainItemIdentity, value: bytes) -> int:
        self.calls.append(("add", identity))
        if self.add_status in (macos_keychain_contracts.SUCCESS, macos_keychain_contracts.DUPLICATE):
            self.item = macos_keychain_contracts.KeychainItem(
                identity, True, b"synthetic-mismatch" if self.corrupt_write else value
            )
        return self.add_status

    def delete(self, identity: macos_keychain_contracts.KeychainItemIdentity) -> int:
        self.calls.append(("delete", identity))
        if self.delete_status == macos_keychain_contracts.SUCCESS and not self.retain_delete:
            self.item = None
        return self.delete_status


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> _MemoryNativeApi:
    api = _MemoryNativeApi()
    monkeypatch.setattr(macos_keychain_policy.sys, "platform", "darwin")
    monkeypatch.setattr(native, "_native_api", lambda: api)
    return api


def test_exact_binary_replace_read_delete_and_composition(api: _MemoryNativeApi) -> None:
    store = native_automation_secret_store(NativeSecretBackend.MACOS_KEYCHAIN)
    assert isinstance(store, native.MacOSKeychainAutomationSecretStore)
    assert store.backend is NativeSecretBackend.MACOS_KEYCHAIN
    assert store.read(_NAMESPACE, _ACCOUNT) is None
    for raw in (b"\x00\xffbinary\x00", b"\xfe\x00replacement", bytes(range(256)) * 10):
        store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(raw))
        observed = store.read(_NAMESPACE, _ACCOUNT)
        assert observed is not None and observed.get_secret_value() == raw
    assert all(identity == _IDENTITY for _, identity in api.calls)
    assert sum(action == "add" for action, _ in api.calls) == 1
    assert all(action != "delete" for action, _ in api.calls)
    store.delete(_NAMESPACE, _ACCOUNT)
    assert store.read(_NAMESPACE, _ACCOUNT) is None
    api.delete_status = macos_keychain_contracts.NOT_FOUND
    store.delete(_NAMESPACE, _ACCOUNT)
    assert api.sessions == api.closed_sessions


@pytest.mark.parametrize("defect", ["namespace", "account", "keychain", "acl", "empty", "oversize"])
def test_bad_native_binding_refuses_release_and_mutation(api: _MemoryNativeApi, defect: str) -> None:
    item = macos_keychain_contracts.KeychainItem(_IDENTITY, True, b"synthetic-opaque-secret")
    if defect == "namespace":
        item = replace(item, identity=replace(_IDENTITY, namespace="wrong"))
    elif defect == "account":
        item = replace(item, identity=replace(_IDENTITY, account="wrong"))
    elif defect == "keychain":
        item = replace(item, identity=replace(_IDENTITY, keychain_path="/foreign/login.keychain-db"))
    elif defect == "acl":
        item = replace(item, account_access=False)
    else:
        item = replace(item, data=b"" if defect == "empty" else b"x" * 2561)
    api.item = item
    store = native.MacOSKeychainAutomationSecretStore()
    for action in (
        lambda: store.read(_NAMESPACE, _ACCOUNT),
        lambda: store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"replacement")),
        lambda: store.delete(_NAMESPACE, _ACCOUNT),
    ):
        with pytest.raises(AutomationCustodyError) as caught:
            action()
        assert caught.value.reason is AutomationCustodyCode.INVALID
        assert "opaque-secret" not in str(caught.value)
    assert all(action == "read" for action, _ in api.calls)
    assert api.sessions == api.closed_sessions


@pytest.mark.parametrize(
    "native_status,reason",
    [
        (macos_keychain_contracts.INTERACTION_NOT_ALLOWED, AutomationCustodyCode.NEEDS_USER),
        (macos_keychain_contracts.AUTH_FAILED, AutomationCustodyCode.NEEDS_USER),
        (macos_keychain_contracts.INTERACTION_REQUIRED, AutomationCustodyCode.NEEDS_USER),
        (-25291, AutomationCustodyCode.UNAVAILABLE),
    ],
)
def test_native_failures_have_only_safe_typed_codes(
    api: _MemoryNativeApi, native_status: int, reason: AutomationCustodyCode
) -> None:
    api.item = macos_keychain_contracts.KeychainItem(_IDENTITY, True, b"synthetic")
    api.updates = [native_status]
    with pytest.raises(AutomationCustodyError) as caught:
        native.MacOSKeychainAutomationSecretStore().replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"replacement"))
    assert caught.value.reason is reason
    assert str(native_status) not in str(caught.value)
    assert all(action != "add" for action, _ in api.calls)


@pytest.mark.parametrize("reason", [AutomationCustodyCode.NEEDS_USER, AutomationCustodyCode.UNAVAILABLE])
def test_locked_or_unavailable_login_precedes_every_item_call(
    api: _MemoryNativeApi, reason: AutomationCustodyCode
) -> None:
    api.session_error = reason
    store = native.MacOSKeychainAutomationSecretStore()
    for action in (
        lambda: store.read(_NAMESPACE, _ACCOUNT),
        lambda: store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"value")),
        lambda: store.delete(_NAMESPACE, _ACCOUNT),
    ):
        with pytest.raises(AutomationCustodyError) as caught:
            action()
        assert caught.value.reason is reason
    assert not api.calls


def test_restore_failure_prevents_successful_private_release(api: _MemoryNativeApi) -> None:
    api.item = macos_keychain_contracts.KeychainItem(_IDENTITY, True, b"synthetic")
    api.restore_failure = True
    with pytest.raises(AutomationCustodyError) as caught:
        native.MacOSKeychainAutomationSecretStore().read(_NAMESPACE, _ACCOUNT)
    assert caught.value.reason is AutomationCustodyCode.UNAVAILABLE
    assert api.closed_sessions == 1


def test_add_race_is_bounded_and_never_deletes(api: _MemoryNativeApi) -> None:
    api.add_status = macos_keychain_contracts.DUPLICATE
    store = native.MacOSKeychainAutomationSecretStore()
    store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-replacement"))
    assert [action for action, _ in api.calls] == ["read", "update", "add", "read", "update", "read"]
    api.item = None
    api.calls.clear()
    api.updates = [macos_keychain_contracts.NOT_FOUND, macos_keychain_contracts.NOT_FOUND]
    with pytest.raises(AutomationCustodyError) as caught:
        store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"value"))
    assert caught.value.reason is AutomationCustodyCode.CONFLICT
    assert sum(action == "update" for action, _ in api.calls) == 2
    assert all(action != "delete" for action, _ in api.calls)


def test_readback_and_absence_are_authoritative(api: _MemoryNativeApi) -> None:
    api.corrupt_write = True
    store = native.MacOSKeychainAutomationSecretStore()
    with pytest.raises(AutomationCustodyError) as caught:
        store.replace(_NAMESPACE, _ACCOUNT, SecretBytes(b"synthetic-value"))
    assert caught.value.reason is AutomationCustodyCode.INVALID
    assert api.item is not None  # A refusal does not claim native rollback.
    api.retain_delete = True
    with pytest.raises(AutomationCustodyError) as caught:
        store.delete(_NAMESPACE, _ACCOUNT)
    assert caught.value.reason is AutomationCustodyCode.INVALID


def test_wrong_platform_and_invalid_target_never_open_native_facility(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_api() -> macos_keychain_contracts.KeychainApi:
        pytest.fail("invalid platform/target must not enter the native API")

    monkeypatch.setattr(native, "_native_api", forbidden_api)
    monkeypatch.setattr(macos_keychain_policy.sys, "platform", "linux")
    with pytest.raises(AutomationCustodyError) as caught:
        native_automation_secret_store(NativeSecretBackend.MACOS_KEYCHAIN)
    assert caught.value.reason is AutomationCustodyCode.UNSUPPORTED
    with pytest.raises(AutomationCustodyError) as caught:
        native.MacOSKeychainAutomationSecretStore().read(_NAMESPACE, _ACCOUNT)
    assert caught.value.reason is AutomationCustodyCode.UNSUPPORTED
    monkeypatch.setattr(macos_keychain_policy.sys, "platform", "darwin")
    for namespace, account in (
        ("foreign", _ACCOUNT),
        (_NAMESPACE, ""),
        (_NAMESPACE, "bad\x00account"),
        (_NAMESPACE, "bad\ud800"),
    ):
        with pytest.raises(AutomationCustodyError) as caught:
            native.MacOSKeychainAutomationSecretStore().read(namespace, account)
        assert caught.value.reason is AutomationCustodyCode.INVALID


class _UiState:
    def __init__(self) -> None:
        self.allowed = 1
        self.get_calls = 0
        self.set_calls: list[int] = []
        self.fail_disable = False
        self.fail_restore = False
        self.ignore_disable = False
        self.ignore_restore = False


class _UiGet:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, state: _UiState) -> None:
        self.state = state

    def __call__(self, *args: object) -> int | None:
        self.state.get_calls += 1
        result = ctypes.cast(cast(ctypes.c_void_p, args[0]), ctypes.POINTER(ctypes.c_ubyte))
        result.contents.value = self.state.allowed
        return 0


class _UiSet:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, state: _UiState) -> None:
        self.state = state

    def __call__(self, *args: object) -> int | None:
        (value,) = args
        assert isinstance(value, int)
        self.state.set_calls.append(value)
        if value == 0:
            if not self.state.ignore_disable:
                self.state.allowed = value
            return macos_keychain_contracts.AUTH_FAILED if self.state.fail_disable else 0
        if not self.state.ignore_restore:
            self.state.allowed = value
        return macos_keychain_contracts.AUTH_FAILED if self.state.fail_restore else 0


class _UiNative(macos_login_keychain.LoginKeychain):
    def __init__(self, state: _UiState) -> None:
        self.ui_get = _UiGet(state)
        self.ui_set = _UiSet(state)


def test_noninteractive_scope_restores_original_flag_after_refusal() -> None:
    for original in (0, 1):
        state = _UiState()
        state.allowed = original
        api = _UiNative(state)
        with pytest.raises(AutomationCustodyError) as caught, api._noninteractive():
            assert state.allowed == 0
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        assert caught.value.reason is AutomationCustodyCode.NEEDS_USER
        assert state.allowed == original
        assert state.set_calls == [0, original]


@pytest.mark.parametrize("defect", ["disable-error", "disable-ignored", "restore-error", "restore-ignored"])
def test_noninteractive_native_flag_failures_are_typed_and_attempt_restore(defect: str) -> None:
    state = _UiState()
    state.fail_disable = defect == "disable-error"
    state.ignore_disable = defect == "disable-ignored"
    state.fail_restore = defect == "restore-error"
    state.ignore_restore = defect == "restore-ignored"
    with pytest.raises(AutomationCustodyError) as caught, _UiNative(state)._noninteractive():
        assert state.allowed == 0
    expected = AutomationCustodyCode.NEEDS_USER if state.fail_disable else AutomationCustodyCode.UNAVAILABLE
    assert caught.value.reason is expected
    assert state.set_calls == [0, 1]


def test_cooperating_native_callers_cannot_restore_ui_during_another_call() -> None:
    state = _UiState()
    first, second = _UiNative(state), _UiNative(state)
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()

    def hold() -> None:
        with first._noninteractive():
            entered.set()
            assert release.wait(2)
            assert state.allowed == 0

    def follow() -> None:
        attempted.set()
        with second._noninteractive():
            assert state.allowed == 0

    with ThreadPoolExecutor(max_workers=2) as pool:
        holding = pool.submit(hold)
        assert entered.wait(2)
        following = pool.submit(follow)
        try:
            assert attempted.wait(2)
            assert state.get_calls == 2  # The second caller has not read shared UI state.
        finally:
            release.set()
        holding.result(timeout=2)
        following.result(timeout=2)
    assert state.allowed == 1
    assert state.set_calls == [0, 1, 0, 1]


@pytest.mark.parametrize(
    "authorizations",
    [
        frozenset(),
        frozenset({"decrypt"}),
        frozenset({"any"}),
        macos_keychain_contracts.RESTRICTED_AUTHORIZATIONS | {"change_acl"},
        frozenset({"foreign"}),
    ],
)
def test_unexplained_native_authorization_role_refuses(authorizations: frozenset[str]) -> None:
    with pytest.raises(AutomationCustodyError) as caught:
        macos_keychain_policy.keychain_acl_role(authorizations)
    assert caught.value.reason is AutomationCustodyCode.INVALID


class _DictionarySet:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, dictionaries: dict[int, dict[int, int]]) -> None:
        self.dictionaries = dictionaries

    def __call__(self, *args: object) -> int | None:
        pointer, key, value = args
        assert isinstance(pointer, int) and isinstance(key, int) and isinstance(value, int)
        self.dictionaries[pointer][key] = value
        return None


class _QueryCF(macos_core_foundation.CoreFoundation):
    """Track native query decisions and ownership of the enclosing CF values."""

    def __init__(self) -> None:
        self.true = 1
        self.false = 2
        self.dictionaries: dict[int, dict[int, int]] = {}
        self.strings_by_pointer: dict[int, str] = {}
        self.arrays: dict[int, tuple[int, ...]] = {}
        self.closed: list[int] = []
        self.dictionary_set = _DictionarySet(self.dictionaries)

    @contextmanager
    @override
    def string(self, value: str) -> Generator[int]:
        pointer = 1000 + len(self.strings_by_pointer)
        self.strings_by_pointer[pointer] = value
        try:
            yield pointer
        finally:
            self.closed.append(pointer)

    @contextmanager
    @override
    def array(self, values: tuple[int, ...]) -> Generator[int]:
        pointer = 7000 + len(self.arrays)
        self.arrays[pointer] = values
        try:
            yield pointer
        finally:
            self.closed.append(pointer)

    @contextmanager
    @override
    def dictionary(self) -> Generator[int]:
        pointer = 5000 + len(self.dictionaries)
        self.dictionaries[pointer] = {}
        try:
            yield pointer
        finally:
            self.closed.append(pointer)

    @contextmanager
    @override
    def data(self, raw: bytes) -> Generator[int]:
        try:
            yield 8000
        finally:
            self.closed.append(8000)


class _QueryNative(macos_login_keychain.LoginKeychain):
    def __init__(self, cf: _QueryCF) -> None:
        self.cf = cf
        self.path = _KEYCHAIN
        self.keychain = 9000
        self.constants = {
            name: index + 10
            for index, name in enumerate(
                (
                    "kSecClass",
                    "kSecClassGenericPassword",
                    "kSecAttrService",
                    "kSecAttrAccount",
                    "kSecMatchSearchList",
                    "kSecUseKeychain",
                    "kSecValueData",
                    "kSecAttrAccess",
                )
            )
        }
        self.update_item = _ResultFunction(0)
        self.add_item = _ResultFunction(0)
        self.delete_item = _ResultFunction(0)

    @override
    def _validate_keychain(self, keychain: int, path: str) -> None:
        assert keychain == 9000 and path == _KEYCHAIN

    @contextmanager
    @override
    def _access(self) -> Generator[int]:
        yield 6000


def test_actual_native_query_is_exact_login_bound_and_closes_on_failure() -> None:
    cf = _QueryCF()
    api = _QueryNative(cf)
    with pytest.raises(RuntimeError, match="synthetic pre-call failure"), api._query(_IDENTITY):
        expected = {
            "kSecClass": api.constants["kSecClassGenericPassword"],
            "kSecAttrService": 1000,
            "kSecAttrAccount": 1001,
            "kSecMatchSearchList": 7000,
        }
        assert cf.dictionaries[5000] == {api.constants[key]: value for key, value in expected.items()}
        assert cf.strings_by_pointer == {1000: _NAMESPACE, 1001: _ACCOUNT}
        assert cf.arrays[7000] == (9000,)
        raise RuntimeError("synthetic pre-call failure")
    assert cf.closed == [5000, 7000, 1001, 1000]


@pytest.mark.parametrize("action", ["update", "add", "delete"])
def test_actual_native_mutation_pins_login_and_only_new_item_receives_access(action: str) -> None:
    cf = _QueryCF()
    api = _QueryNative(cf)
    if action == "update":
        assert api.update(_IDENTITY, b"synthetic") == 0
    elif action == "add":
        assert api.add(_IDENTITY, b"synthetic") == 0
    else:
        assert api.delete(_IDENTITY) == 0
    query = cf.dictionaries[5000]
    assert cf.strings_by_pointer[query[api.constants["kSecAttrService"]]] == _NAMESPACE
    assert cf.strings_by_pointer[query[api.constants["kSecAttrAccount"]]] == _ACCOUNT
    if action == "add":
        assert query[api.constants["kSecUseKeychain"]] == 9000
        assert query[api.constants["kSecAttrAccess"]] == 6000
    else:
        assert cf.arrays[query[api.constants["kSecMatchSearchList"]]] == (9000,)
        assert api.constants["kSecAttrAccess"] not in query
    if action != "delete":
        attributes = cf.dictionaries[5001] if action == "update" else query
        assert attributes[api.constants["kSecValueData"]] == 8000
        if action == "update":
            assert set(attributes) == {api.constants["kSecValueData"]}
    assert 5000 in cf.closed
    assert cf.closed[-3:] == [7000, 1001, 1000]


class _CopyPath:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, path: str) -> None:
        self.raw = path.encode() + b"\x00"

    def __call__(self, *args: object) -> int | None:
        _, size, buffer = args
        assert isinstance(buffer, ctypes.Array)
        ctypes.memmove(buffer, self.raw, len(self.raw))
        ctypes.cast(cast(ctypes.c_void_p, size), ctypes.POINTER(ctypes.c_uint32)).contents.value = len(self.raw)
        return 0


class _KeychainState:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, state: int, status: int = 0) -> None:
        self.state = state
        self.status = status

    def __call__(self, *args: object) -> int | None:
        _, result = args
        ctypes.cast(cast(ctypes.c_void_p, result), ctypes.POINTER(ctypes.c_uint32)).contents.value = self.state
        return self.status


class _OpenKeychain:
    argtypes: list[object] = []
    restype: object = None

    def __call__(self, *args: object) -> int | None:
        _, result = args
        ctypes.cast(cast(ctypes.c_void_p, result), ctypes.POINTER(ctypes.c_void_p)).contents.value = 9000
        return 0


class _BindingNative(macos_login_keychain.LoginKeychain):
    def __init__(self, cf: _QueryCF, state: _UiState, *, observed_path: str, unlocked: bool) -> None:
        self.cf = cf
        self.path = _KEYCHAIN
        self.keychain = None
        self.ui_get = _UiGet(state)
        self.ui_set = _UiSet(state)
        self.open_keychain = _OpenKeychain()
        self.keychain_path = _CopyPath(observed_path)
        self.keychain_status = _KeychainState(1 if unlocked else 0)
        cf.release = _ReleaseForQuery(cf)


class _ReleaseForQuery:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, cf: _QueryCF) -> None:
        self.cf = cf

    def __call__(self, *args: object) -> int | None:
        (pointer,) = args
        assert isinstance(pointer, int)
        self.cf.closed.append(pointer)
        return None


@pytest.mark.parametrize("defect", ["foreign-path", "locked"])
def test_actual_native_session_checks_path_and_lock_before_publishing_binding(defect: str) -> None:
    cf, state = _QueryCF(), _UiState()
    api = _BindingNative(
        cf,
        state,
        observed_path="/foreign/login.keychain-db" if defect == "foreign-path" else _KEYCHAIN,
        unlocked=defect != "locked",
    )
    with pytest.raises(AutomationCustodyError) as caught, api.session():
        pytest.fail("unproven native binding must not be handed to item calls")
    assert caught.value.reason is (
        AutomationCustodyCode.INVALID if defect == "foreign-path" else AutomationCustodyCode.NEEDS_USER
    )
    assert api.keychain is None
    assert cf.closed == [9000]
    assert state.allowed == 1


def test_actual_native_binding_is_fresh_and_cannot_be_used_after_session_close() -> None:
    cf, state = _QueryCF(), _UiState()
    api = _BindingNative(cf, state, observed_path=_KEYCHAIN, unlocked=True)
    with api.session() as path:
        assert path == _KEYCHAIN
        assert api._bound_keychain(_IDENTITY) == 9000
        api.keychain_status = _KeychainState(0)
        with pytest.raises(AutomationCustodyError) as caught:
            api._bound_keychain(_IDENTITY)
        assert caught.value.reason is AutomationCustodyCode.NEEDS_USER
    assert state.allowed == 1
    assert cf.closed == [9000]
    with pytest.raises(AutomationCustodyError):
        api._bound_keychain(_IDENTITY)


class _AccessCF(macos_core_foundation.CoreFoundation):
    def __init__(self, count: int) -> None:
        self.entries = tuple(range(100, 100 + count))
        self.array_count = _AccessArrayCount(self.entries)
        self.array_get = _AccessArrayGet(self.entries)
        self.array_type = _ResultFunction(1)

    @override
    def require_type(self, pointer: int | None, expected: macos_keychain_contracts.NativeKeychainFunction) -> int:
        assert isinstance(pointer, int)
        assert pointer in {500, 600}
        return pointer

    @override
    def text(self, pointer: int | None) -> str:
        assert pointer == 701
        return macos_keychain_contracts.DESCRIPTION


class _AccessArrayCount:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, entries: tuple[int, ...]) -> None:
        self.entries = entries

    def __call__(self, *args: object) -> int | None:
        (pointer,) = args
        return len(self.entries) if pointer == 500 else 0


class _AccessArrayGet:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, entries: tuple[int, ...]) -> None:
        self.entries = entries

    def __call__(self, *args: object) -> int | None:
        _, index = args
        assert isinstance(index, int)
        return self.entries[index]


class _SetAcl:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, applications: dict[int, int | None]) -> None:
        self.applications = applications
        self.calls: list[int] = []

    def __call__(self, *args: object) -> int | None:
        acl, apps, description, selector = args
        assert isinstance(acl, int) and apps is None and description == 701 and selector == 0
        self.calls.append(acl)
        self.applications[acl] = None
        return 0


class _AccessNative(macos_login_keychain.LoginKeychain):
    """Exercise actual ACL validation without pretending an OS response exists."""

    def __init__(self) -> None:
        self.tags: dict[int, frozenset[str]] = {
            100: frozenset({"change_acl"}),
            101: frozenset({"encrypt"}),
            102: macos_keychain_contracts.RESTRICTED_AUTHORIZATIONS,
        }
        self.apps: dict[int, int | None] = {100: 600, 101: None, 102: None}
        self.cf = _AccessCF(3)
        self.acl_list = _ResultFunction(0)
        setter = _SetAcl(self.apps)
        self.acl_set = setter
        self.changed = setter.calls

    @contextmanager
    @override
    def _copied(self, function: macos_keychain_contracts.NativeKeychainFunction, *args: object) -> Generator[int]:
        yield 500

    @override
    def _acl_authorizations(self, acl: int) -> frozenset[str]:
        return self.tags[acl]

    @contextmanager
    @override
    def _acl_content(self, acl: int) -> Generator[tuple[int | None, int]]:
        yield self.apps[acl], 701


def test_actual_acl_validation_preserves_owner_and_only_configures_new_restricted_entry() -> None:
    api = _AccessNative()
    api.apps[102] = 601  # SecAccessCreate(NULL) initially trusts the calling app.
    api._validate_access(900, configure_new=True)
    api._validate_access(900)
    assert api.changed == [102]
    assert api.apps == {100: 600, 101: None, 102: None}


@pytest.mark.parametrize(
    "defect", ["empty-restricted", "all-owner", "trusted-safe", "extra-owner", "unknown", "missing"]
)
def test_actual_acl_validation_refuses_unexplained_existing_access_without_widening(defect: str) -> None:
    api = _AccessNative()
    if defect == "empty-restricted":
        api.apps[102] = 600  # Empty means nobody, never all apps.
    elif defect == "all-owner":
        api.apps[100] = None
    elif defect == "trusted-safe":
        api.apps[101] = 600
    elif defect == "extra-owner":
        api.tags[102] = macos_keychain_contracts.RESTRICTED_AUTHORIZATIONS | {"change_acl"}
    elif defect == "unknown":
        api.tags[101] = frozenset({"foreign"})
    else:
        api.cf = _AccessCF(2)
    with pytest.raises(AutomationCustodyError) as caught:
        api._validate_access(900)
    assert caught.value.reason is AutomationCustodyCode.INVALID
    assert not api.changed


class _ResultFunction:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, result: int | None) -> None:
        self.result = result

    def __call__(self, *args: object) -> int | None:
        return self.result


class _ReadCF(macos_core_foundation.CoreFoundation):
    def __init__(self, *, native_type: int, size: int, address: int | None) -> None:
        self.type_id = _ResultFunction(native_type)
        self.data_type = _ResultFunction(1)
        self.data_length = _ResultFunction(size)
        self.data_pointer = _ResultFunction(address)


class _CopyString:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self, value: str) -> None:
        self.raw = value.encode("utf-8") + b"\x00"

    def __call__(self, *args: object) -> int | None:
        _, buffer, size, _ = args
        assert isinstance(buffer, ctypes.Array) and isinstance(size, int)
        assert len(self.raw) <= size
        ctypes.memmove(buffer, self.raw, len(self.raw))
        return 1


class _TextCF(macos_core_foundation.CoreFoundation):
    def __init__(self, value: str) -> None:
        self.type_id = _ResultFunction(1)
        self.string_type = _ResultFunction(1)
        self.string_length = _ResultFunction(len(value.encode("utf-16-le")) // 2)
        self.string_get = _CopyString(value)


def test_native_cf_identity_never_accepts_embedded_nul_truncation() -> None:
    with pytest.raises(AutomationCustodyError) as caught:
        _TextCF("synthetic-account\x00other-account").text(100)
    assert caught.value.reason is AutomationCustodyCode.INVALID
    for value in ("synthetic-account", "synthetic-\U0001f512", "synthetic-e\u0301"):
        assert _TextCF(value).text(100) == value


@pytest.mark.parametrize("native_type,size,address", [(2, 1, 1), (1, -1, 1), (1, 0, 1), (1, 2561, 1), (1, 1, None)])
def test_native_cf_type_and_size_refuse_before_dereferencing(native_type: int, size: int, address: int | None) -> None:
    cf = _ReadCF(native_type=native_type, size=size, address=address)
    with pytest.raises(AutomationCustodyError) as caught:
        cf.read_data(100)
    assert caught.value.reason is AutomationCustodyCode.INVALID


class _CreateData:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self) -> None:
        self.array: ctypes.Array[ctypes.c_ubyte] | None = None

    def __call__(self, *args: object) -> int | None:
        _, array, size = args
        assert isinstance(array, ctypes.Array) and isinstance(size, int)
        self.array = cast(ctypes.Array[ctypes.c_ubyte], array)
        assert bytes(self.array) == b"\x00\xffsynthetic"
        assert size == len(self.array)
        return 8000


class _Release:
    argtypes: list[object] = []
    restype: object = None

    def __init__(self) -> None:
        self.closed: list[int] = []

    def __call__(self, *args: object) -> int | None:
        (pointer,) = args
        assert isinstance(pointer, int)
        self.closed.append(pointer)
        return None


class _DataCF(macos_core_foundation.CoreFoundation):
    def __init__(self, creator: _CreateData, release: _Release) -> None:
        self.data_create = creator
        self.release = release


def test_actual_cf_data_owner_releases_and_wipes_staging_on_failure() -> None:
    creator = _CreateData()
    release = _Release()
    cf = _DataCF(creator, release)
    with pytest.raises(RuntimeError, match="synthetic write failure"), cf.data(b"\x00\xffsynthetic"):
        raise RuntimeError("synthetic write failure")
    assert release.closed == [8000]
    assert creator.array is not None
    assert bytes(creator.array) == b"\x00" * len(creator.array)
