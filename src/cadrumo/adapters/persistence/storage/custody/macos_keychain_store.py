"""Explicit noninteractive native login-Keychain custody for ordinary CLI hosts.

The OS account owns this encrypted Keychain. Its item ACL permits that account's
applications; no signing entitlement or hostile same-user isolation is claimed.
Existing items with another binding or unexplained ACL refuse rather than having
their permissions changed. Password login remains independent. Native calls are
synchronous, so a timeout proves neither cancellation nor rollback. Immutable
secret copies cannot reliably be wiped; mutable staging and CF objects are freed.
"""

from __future__ import annotations

import ctypes
import os
import secrets
import sys
import threading
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from .automation_secret_target import require_automation_secret_target
from .zeroise import zeroise

_SECURITY = "/System/Library/Frameworks/Security.framework/Security"
_CORE_FOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
_MAX_SECRET_BYTES = 2560
_UTF8 = 0x08000100
_SUCCESS = 0
_NOT_FOUND = -25300
_DUPLICATE = -25299
_INTERACTION_NOT_ALLOWED = -25308
_AUTH_FAILED = -25293
_INTERACTION_REQUIRED = -25315
_UI_LOCK = threading.RLock()
_DESCRIPTION = "Cadrumo automation"
_RESTRICTED_AUTHORIZATIONS = frozenset({"decrypt", "sign", "mac", "derive", "export_clear", "export_wrapped"})
_SAFE_AUTHORIZATIONS = frozenset({"encrypt"})
_OWNER_AUTHORIZATIONS = frozenset({"change_acl"})
_INTEGRITY_AUTHORIZATIONS = frozenset({"integrity"})
_PARTITION_AUTHORIZATIONS = frozenset({"partition"})
_AUTHORIZATIONS = {
    "kSecACLAuthorizationDecrypt": "decrypt",
    "kSecACLAuthorizationSign": "sign",
    "kSecACLAuthorizationMAC": "mac",
    "kSecACLAuthorizationDerive": "derive",
    "kSecACLAuthorizationExportClear": "export_clear",
    "kSecACLAuthorizationExportWrapped": "export_wrapped",
    "kSecACLAuthorizationEncrypt": "encrypt",
    "kSecACLAuthorizationChangeACL": "change_acl",
    "kSecACLAuthorizationIntegrity": "integrity",
    "kSecACLAuthorizationPartitionID": "partition",
}
_AclRole = Literal["restricted", "safe", "owner", "integrity", "partition"]


def _refuse(code: AutomationCustodyCode = AutomationCustodyCode.INVALID) -> AutomationCustodyError:
    return AutomationCustodyError(code)


def _status(status: int) -> None:
    if status == _SUCCESS:
        return
    if status in (_INTERACTION_NOT_ALLOWED, _AUTH_FAILED, _INTERACTION_REQUIRED):
        raise _refuse(AutomationCustodyCode.NEEDS_USER)
    raise _refuse(AutomationCustodyCode.UNAVAILABLE)


def _target(namespace: str, account: str) -> None:
    require_automation_secret_target(namespace, account)
    if sys.platform != "darwin":
        raise _refuse(AutomationCustodyCode.UNSUPPORTED)


def _login_path() -> str:
    """Select the OS user's canonical login database without environment input."""
    if sys.platform != "darwin":
        raise _refuse(AutomationCustodyCode.UNSUPPORTED)
    import pwd

    uid = os.getuid()
    if uid != os.geteuid():
        raise _refuse(AutomationCustodyCode.UNAVAILABLE)
    home = Path(pwd.getpwuid(uid).pw_dir)
    path = home / "Library" / "Keychains" / "login.keychain-db"
    if not home.is_absolute() or len(os.fsencode(path)) >= 4096:
        raise _refuse(AutomationCustodyCode.UNAVAILABLE)
    return str(path)


def _acl_role(authorizations: frozenset[str]) -> _AclRole:
    """Recognize the native default roles; an extra permission is unexplained."""
    if authorizations == _RESTRICTED_AUTHORIZATIONS:
        return "restricted"
    if authorizations == _SAFE_AUTHORIZATIONS:
        return "safe"
    if authorizations == _OWNER_AUTHORIZATIONS:
        return "owner"
    if authorizations == _INTEGRITY_AUTHORIZATIONS:
        return "integrity"
    if authorizations == _PARTITION_AUTHORIZATIONS:
        return "partition"
    raise _refuse()


@dataclass(frozen=True)
class _ItemIdentity:
    namespace: str
    account: str
    keychain_path: str


@dataclass(frozen=True, repr=False)
class _Item:
    identity: _ItemIdentity
    account_access: bool
    data: bytes


class _KeychainApi(Protocol):
    """Native decisions isolated for portable protocol tests, never a fallback."""

    def session(self) -> AbstractContextManager[str]: ...

    def read(self, identity: _ItemIdentity) -> _Item | None: ...

    def update(self, identity: _ItemIdentity, value: bytes) -> int: ...

    def add(self, identity: _ItemIdentity, value: bytes) -> int: ...

    def delete(self, identity: _ItemIdentity) -> int: ...


class _NativeFunction(Protocol):
    argtypes: list[object]
    restype: object

    def __call__(self, *args: object) -> int | None: ...


class _DictionaryKeyCallbacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
        ("hash", ctypes.c_void_p),
    ]


class _DictionaryValueCallbacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
    ]


def _bind(library: ctypes.CDLL, name: str, args: list[object], result: object) -> _NativeFunction:
    function = cast(_NativeFunction, getattr(library, name))
    function.argtypes = args
    function.restype = result
    return function


def _integer(value: int | None) -> int:
    if value is None:
        raise _refuse()
    return value


class _CoreFoundation:
    """Small typed CF bridge with ownership explicit at each Create/Copy."""

    def __init__(self) -> None:
        self.library = ctypes.CDLL(_CORE_FOUNDATION)
        pointer = ctypes.c_void_p
        index = ctypes.c_long
        self.release = _bind(self.library, "CFRelease", [pointer], None)
        self.type_id = _bind(self.library, "CFGetTypeID", [pointer], ctypes.c_ulong)
        self.string_type = _bind(self.library, "CFStringGetTypeID", [], ctypes.c_ulong)
        self.array_type = _bind(self.library, "CFArrayGetTypeID", [], ctypes.c_ulong)
        self.data_type = _bind(self.library, "CFDataGetTypeID", [], ctypes.c_ulong)
        self.dictionary_type = _bind(self.library, "CFDictionaryGetTypeID", [], ctypes.c_ulong)
        self.number_type = _bind(self.library, "CFNumberGetTypeID", [], ctypes.c_ulong)
        self.boolean_type = _bind(self.library, "CFBooleanGetTypeID", [], ctypes.c_ulong)
        self.string_create = _bind(
            self.library, "CFStringCreateWithBytes", [pointer, pointer, index, ctypes.c_uint32, ctypes.c_ubyte], pointer
        )
        self.string_length = _bind(self.library, "CFStringGetLength", [pointer], index)
        self.string_get = _bind(
            self.library, "CFStringGetCString", [pointer, pointer, index, ctypes.c_uint32], ctypes.c_ubyte
        )
        self.array_count = _bind(self.library, "CFArrayGetCount", [pointer], index)
        self.array_get = _bind(self.library, "CFArrayGetValueAtIndex", [pointer, index], pointer)
        self.array_create = _bind(self.library, "CFArrayCreate", [pointer, pointer, index, pointer], pointer)
        self.dictionary_create = _bind(
            self.library, "CFDictionaryCreateMutable", [pointer, index, pointer, pointer], pointer
        )
        self.dictionary_set = _bind(self.library, "CFDictionarySetValue", [pointer, pointer, pointer], None)
        self.dictionary_get = _bind(self.library, "CFDictionaryGetValue", [pointer, pointer], pointer)
        self.data_create = _bind(self.library, "CFDataCreate", [pointer, pointer, index], pointer)
        self.data_length = _bind(self.library, "CFDataGetLength", [pointer], index)
        self.data_pointer = _bind(self.library, "CFDataGetBytePtr", [pointer], pointer)
        self.number_get = _bind(self.library, "CFNumberGetValue", [pointer, ctypes.c_int, pointer], ctypes.c_ubyte)
        self.boolean_get = _bind(self.library, "CFBooleanGetValue", [pointer], ctypes.c_ubyte)
        self.equal = _bind(self.library, "CFEqual", [pointer, pointer], ctypes.c_ubyte)
        self.true = self.constant(self.library, "kCFBooleanTrue")
        self.false = self.constant(self.library, "kCFBooleanFalse")
        self.key_callbacks = _DictionaryKeyCallbacks.in_dll(self.library, "kCFTypeDictionaryKeyCallBacks")
        self.value_callbacks = _DictionaryValueCallbacks.in_dll(self.library, "kCFTypeDictionaryValueCallBacks")

    @staticmethod
    def constant(library: ctypes.CDLL, name: str) -> int:
        pointer = ctypes.c_void_p.in_dll(library, name).value
        if not pointer:
            raise _refuse(AutomationCustodyCode.UNAVAILABLE)
        return pointer

    def require_type(self, pointer: int | None, expected: _NativeFunction) -> int:
        if not pointer or self.type_id(pointer) != expected():
            raise _refuse()
        return pointer

    @contextmanager
    def string(self, value: str) -> Generator[int]:
        encoded = value.encode("utf-8")
        pointer = _integer(self.string_create(None, encoded, len(encoded), _UTF8, 0))
        if not pointer:
            raise _refuse(AutomationCustodyCode.UNAVAILABLE)
        try:
            yield pointer
        finally:
            self.release(pointer)

    def text(self, pointer: int | None) -> str:
        pointer = self.require_type(pointer, self.string_type)
        length = _integer(self.string_length(pointer))
        if not 0 <= length <= 1024:
            raise _refuse()
        buffer = ctypes.create_string_buffer(length * 4 + 1)
        if not self.string_get(pointer, buffer, len(buffer), _UTF8):
            raise _refuse()
        raw: object = buffer.value
        if not isinstance(raw, bytes):
            raise _refuse()
        try:
            value = raw.decode("utf-8", errors="strict")
            # CFStringGetCString permits embedded NULs. Never accept a truncated
            # service/account as an exact identity match.
            if len(value.encode("utf-16-le")) // 2 != length:
                raise _refuse()
            return value
        except UnicodeError:
            raise _refuse() from None

    def strings(self, pointer: int | None) -> tuple[str, ...]:
        pointer = self.require_type(pointer, self.array_type)
        count = _integer(self.array_count(pointer))
        if not 0 < count <= 32:
            raise _refuse(AutomationCustodyCode.UNAVAILABLE)
        return tuple(self.text(self.array_get(pointer, index)) for index in range(count))

    def field(self, dictionary: int, key: int) -> int | None:
        self.require_type(dictionary, self.dictionary_type)
        return self.dictionary_get(dictionary, key)

    @contextmanager
    def array(self, values: tuple[int, ...]) -> Generator[int]:
        """Own an array while its already-owned native elements remain live."""
        elements = (ctypes.c_void_p * len(values))(*values)
        pointer = _integer(self.array_create(None, elements, len(values), None))
        if not pointer:
            raise _refuse(AutomationCustodyCode.UNAVAILABLE)
        try:
            yield pointer
        finally:
            self.release(pointer)

    def number(self, pointer: int | None) -> int:
        pointer = self.require_type(pointer, self.number_type)
        value = ctypes.c_int64()
        if not self.number_get(pointer, 4, ctypes.byref(value)):
            raise _refuse()
        return value.value

    def boolean(self, pointer: int | None) -> bool:
        pointer = self.require_type(pointer, self.boolean_type)
        return bool(self.boolean_get(pointer))

    @contextmanager
    def dictionary(self) -> Generator[int]:
        pointer = _integer(
            self.dictionary_create(None, 0, ctypes.byref(self.key_callbacks), ctypes.byref(self.value_callbacks))
        )
        if not pointer:
            raise _refuse(AutomationCustodyCode.UNAVAILABLE)
        try:
            yield pointer
        finally:
            self.release(pointer)

    @contextmanager
    def data(self, raw: bytes) -> Generator[int]:
        staging = bytearray(raw)
        array = (ctypes.c_ubyte * len(staging)).from_buffer(staging)
        try:
            pointer = _integer(self.data_create(None, array, len(staging)))
            if not pointer:
                raise _refuse(AutomationCustodyCode.UNAVAILABLE)
            try:
                yield pointer
            finally:
                self.release(pointer)
        finally:
            zeroise(staging)

    def read_data(self, pointer: int | None) -> bytes:
        pointer = self.require_type(pointer, self.data_type)
        length = _integer(self.data_length(pointer))
        address = self.data_pointer(pointer)
        if not 0 < length <= _MAX_SECRET_BYTES or not address:
            raise _refuse()
        return ctypes.string_at(address, length)


class _LoginKeychain:
    """Explicit encrypted OS login store; no entitlement or search-list fallback."""

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise _refuse(AutomationCustodyCode.UNSUPPORTED)
        self.path = _login_path()
        self.keychain: int | None = None
        self.cf = _CoreFoundation()
        self.security = ctypes.CDLL(_SECURITY)
        pointer = ctypes.c_void_p
        output = ctypes.POINTER(pointer)
        self.copy = _bind(self.security, "SecItemCopyMatching", [pointer, output], ctypes.c_int32)
        self.update_item = _bind(self.security, "SecItemUpdate", [pointer, pointer], ctypes.c_int32)
        self.add_item = _bind(self.security, "SecItemAdd", [pointer, output], ctypes.c_int32)
        self.delete_item = _bind(self.security, "SecItemDelete", [pointer], ctypes.c_int32)
        self.ui_get = _bind(
            self.security, "SecKeychainGetUserInteractionAllowed", [ctypes.POINTER(ctypes.c_ubyte)], ctypes.c_int32
        )
        self.ui_set = _bind(self.security, "SecKeychainSetUserInteractionAllowed", [ctypes.c_ubyte], ctypes.c_int32)
        self.open_keychain = _bind(self.security, "SecKeychainOpen", [ctypes.c_char_p, output], ctypes.c_int32)
        self.keychain_path = _bind(
            self.security, "SecKeychainGetPath", [pointer, ctypes.POINTER(ctypes.c_uint32), pointer], ctypes.c_int32
        )
        self.keychain_status = _bind(
            self.security, "SecKeychainGetStatus", [pointer, ctypes.POINTER(ctypes.c_uint32)], ctypes.c_int32
        )
        self.access_create = _bind(self.security, "SecAccessCreate", [pointer, pointer, output], ctypes.c_int32)
        self.acl_list = _bind(self.security, "SecAccessCopyACLList", [pointer, output], ctypes.c_int32)
        self.authorizations = _bind(self.security, "SecACLCopyAuthorizations", [pointer], pointer)
        self.acl_contents = _bind(
            self.security,
            "SecACLCopyContents",
            [pointer, output, output, ctypes.POINTER(ctypes.c_uint16)],
            ctypes.c_int32,
        )
        self.acl_set = _bind(
            self.security, "SecACLSetContents", [pointer, pointer, pointer, ctypes.c_uint16], ctypes.c_int32
        )
        self.item_access = _bind(self.security, "SecKeychainItemCopyAccess", [pointer, output], ctypes.c_int32)
        self.item_keychain = _bind(self.security, "SecKeychainItemCopyKeychain", [pointer, output], ctypes.c_int32)
        names = (
            "kSecClass",
            "kSecClassGenericPassword",
            "kSecAttrService",
            "kSecAttrAccount",
            "kSecMatchSearchList",
            "kSecUseKeychain",
            "kSecMatchLimit",
            "kSecMatchLimitOne",
            "kSecReturnData",
            "kSecReturnAttributes",
            "kSecReturnRef",
            "kSecValueData",
            "kSecValueRef",
            "kSecAttrAccess",
            *_AUTHORIZATIONS,
        )
        self.constants = {name: self.cf.constant(self.security, name) for name in names}

    def _constant(self, name: str) -> int:
        return self.constants[name]

    @contextmanager
    def _copied(self, function: _NativeFunction, *args: object) -> Generator[int]:
        result = ctypes.c_void_p()
        try:
            _status(_integer(function(*args, ctypes.byref(result))))
            if not result.value:
                raise _refuse(AutomationCustodyCode.UNAVAILABLE)
            yield result.value
        finally:
            if result.value:
                self.cf.release(result.value)

    @contextmanager
    def _noninteractive(self) -> Generator[None]:
        # The file-based implementation uses a process-global UI switch. All
        # cooperating automation-store callers share this lock for the whole
        # native session, including mutation read-back and error cleanup.
        with _UI_LOCK:
            previous = ctypes.c_ubyte()
            _status(_integer(self.ui_get(ctypes.byref(previous))))
            if previous.value not in (0, 1):
                raise _refuse(AutomationCustodyCode.UNAVAILABLE)
            try:
                _status(_integer(self.ui_set(0)))
                observed = ctypes.c_ubyte(1)
                _status(_integer(self.ui_get(ctypes.byref(observed))))
                if observed.value != 0:
                    raise _refuse(AutomationCustodyCode.UNAVAILABLE)
                yield
            finally:
                restored = ctypes.c_ubyte()
                if (
                    self.ui_set(previous.value) != _SUCCESS
                    or self.ui_get(ctypes.byref(restored)) != _SUCCESS
                    or restored.value != previous.value
                ):
                    # Failure to restore shared native UI state is facility
                    # unavailability; it must also prevent a prepared read
                    # result from being released as successful.
                    raise _refuse(AutomationCustodyCode.UNAVAILABLE)

    def _validate_keychain(self, keychain: int, path: str) -> None:
        buffer = ctypes.create_string_buffer(4096)
        size = ctypes.c_uint32(len(buffer))
        _status(_integer(self.keychain_path(keychain, ctypes.byref(size), buffer)))
        raw: object = buffer.value
        if (
            not isinstance(raw, bytes)
            or not 0 < size.value < len(buffer)
            or os.fsdecode(raw) != path
            or path != self.path
        ):
            raise _refuse()
        state = ctypes.c_uint32()
        _status(_integer(self.keychain_status(keychain, ctypes.byref(state))))
        # This observation is advisory; every actual call still handles a
        # concurrent lock/access refusal. Never attempt to unlock the store.
        if state.value & 1 == 0:
            raise _refuse(AutomationCustodyCode.NEEDS_USER)

    @contextmanager
    def session(self) -> Generator[str]:
        """Own one fresh native login binding and a noninteractive call scope."""
        with self._noninteractive(), self._copied(self.open_keychain, os.fsencode(self.path)) as keychain:
            self._validate_keychain(keychain, self.path)
            self.keychain = keychain
            try:
                yield self.path
            finally:
                self.keychain = None

    def _bound_keychain(self, identity: _ItemIdentity) -> int:
        if self.keychain is None or identity.keychain_path != self.path:
            raise _refuse()
        self._validate_keychain(self.keychain, identity.keychain_path)
        return self.keychain

    @contextmanager
    def _query(self, identity: _ItemIdentity, *, adding: bool = False) -> Generator[int]:
        keychain = self._bound_keychain(identity)
        with (
            self.cf.string(identity.namespace) as service,
            self.cf.string(identity.account) as account,
            self.cf.array((keychain,)) as search,
            self.cf.dictionary() as query,
        ):
            for key, value in (
                ("kSecClass", self._constant("kSecClassGenericPassword")),
                ("kSecAttrService", service),
                ("kSecAttrAccount", account),
                ("kSecUseKeychain" if adding else "kSecMatchSearchList", keychain if adding else search),
            ):
                self.cf.dictionary_set(query, self._constant(key), value)
            yield query

    def _acl_authorizations(self, acl: int) -> frozenset[str]:
        pointer = self.authorizations(acl)
        if not pointer:
            raise _refuse()
        try:
            self.cf.require_type(pointer, self.cf.array_type)
            count = _integer(self.cf.array_count(pointer))
            if not 0 < count <= len(_AUTHORIZATIONS):
                raise _refuse()
            observed: set[str] = set()
            for index in range(count):
                tag = self.cf.require_type(self.cf.array_get(pointer, index), self.cf.string_type)
                matched = [
                    meaning
                    for name, meaning in _AUTHORIZATIONS.items()
                    if self.cf.equal(tag, self._constant(name)) == 1
                ]
                if len(matched) != 1 or matched[0] in observed:
                    raise _refuse()
                observed.add(matched[0])
            return frozenset(observed)
        finally:
            self.cf.release(pointer)

    @contextmanager
    def _acl_content(self, acl: int) -> Generator[tuple[int | None, int]]:
        applications, description = ctypes.c_void_p(), ctypes.c_void_p()
        selector = ctypes.c_uint16()
        try:
            _status(
                _integer(
                    self.acl_contents(
                        acl, ctypes.byref(applications), ctypes.byref(description), ctypes.byref(selector)
                    )
                )
            )
            if not description.value:
                raise _refuse()
            self.cf.require_type(description.value, self.cf.string_type)
            if applications.value:
                self.cf.require_type(applications.value, self.cf.array_type)
            yield applications.value, description.value
        finally:
            if applications.value:
                self.cf.release(applications.value)
            if description.value:
                self.cf.release(description.value)

    def _validate_access(self, access: int, *, configure_new: bool = False) -> None:
        with self._copied(self.acl_list, access) as entries:
            self.cf.require_type(entries, self.cf.array_type)
            count = _integer(self.cf.array_count(entries))
            if not 3 <= count <= 5:
                raise _refuse()
            seen: set[_AclRole] = set()
            for index in range(count):
                acl = _integer(self.cf.array_get(entries, index))
                role = _acl_role(self._acl_authorizations(acl))
                if role in seen:
                    raise _refuse()
                seen.add(role)
                if role in {"integrity", "partition"}:
                    # Published native storage-integrity/partition entries are
                    # platform-owned. Never rewrite their content or mistake
                    # them for a data-read or ChangeACL authorization.
                    continue
                with self._acl_content(acl) as (applications, description):
                    if self.cf.text(description) != _DESCRIPTION:
                        raise _refuse()
                    if role == "owner":
                        # Empty means NO trusted apps. NULL would grant ALL.
                        # Retain the default owner rule; never widen it.
                        if applications is None or self.cf.array_count(applications) != 0:
                            raise _refuse()
                    elif role == "restricted" and configure_new:
                        # SecAccessCreate(NULL) trusts the calling app only.
                        # SecACLSetContents(NULL) explicitly trusts all apps
                        # inside the approved OS-account boundary.
                        _status(_integer(self.acl_set(acl, None, description, 0)))
                    elif applications is not None:
                        raise _refuse()
            if not {"restricted", "safe", "owner"} <= seen:
                raise _refuse()

    @contextmanager
    def _access(self) -> Generator[int]:
        with self.cf.string(_DESCRIPTION) as description, self._copied(self.access_create, description, None) as access:
            self._validate_access(access, configure_new=True)
            self._validate_access(access)
            yield access

    def read(self, identity: _ItemIdentity) -> _Item | None:
        with self._query(identity) as query:
            for key, value in (
                ("kSecReturnData", self.cf.true),
                ("kSecReturnAttributes", self.cf.true),
                ("kSecReturnRef", self.cf.true),
                ("kSecMatchLimit", self._constant("kSecMatchLimitOne")),
            ):
                self.cf.dictionary_set(query, self._constant(key), value)
            result = ctypes.c_void_p()
            try:
                status = _integer(self.copy(query, ctypes.byref(result)))
                if status == _NOT_FOUND:
                    return None
                _status(status)
                record = self.cf.require_type(result.value, self.cf.dictionary_type)
                observed = _ItemIdentity(
                    self.cf.text(self.cf.field(record, self._constant("kSecAttrService"))),
                    self.cf.text(self.cf.field(record, self._constant("kSecAttrAccount"))),
                    identity.keychain_path,
                )
                if observed != identity:
                    raise _refuse()
                item = _integer(self.cf.field(record, self._constant("kSecValueRef")))
                with self._copied(self.item_keychain, item) as keychain:
                    if self.keychain is None or self.cf.equal(keychain, self.keychain) != 1:
                        raise _refuse()
                    self._validate_keychain(keychain, identity.keychain_path)
                with self._copied(self.item_access, item) as access:
                    self._validate_access(access)
                return _Item(
                    observed,
                    True,
                    self.cf.read_data(self.cf.field(record, self._constant("kSecValueData"))),
                )
            finally:
                if result.value:
                    self.cf.release(result.value)

    def update(self, identity: _ItemIdentity, value: bytes) -> int:
        with self._query(identity) as query, self.cf.data(value) as data, self.cf.dictionary() as attributes:
            self.cf.dictionary_set(attributes, self._constant("kSecValueData"), data)
            return _integer(self.update_item(query, attributes))

    def add(self, identity: _ItemIdentity, value: bytes) -> int:
        with self._query(identity, adding=True) as query, self.cf.data(value) as data, self._access() as access:
            self.cf.dictionary_set(query, self._constant("kSecValueData"), data)
            self.cf.dictionary_set(query, self._constant("kSecAttrAccess"), access)
            return _integer(self.add_item(query, None))

    def delete(self, identity: _ItemIdentity) -> int:
        with self._query(identity) as query:
            return _integer(self.delete_item(query))


def _native_api() -> _KeychainApi:
    try:
        return _LoginKeychain()
    except (OSError, AttributeError, ValueError, KeyError):
        raise _refuse(AutomationCustodyCode.UNAVAILABLE) from None


class MacOSKeychainAutomationSecretStore:
    """Exact encrypted login-Keychain custody under the current OS account."""

    backend = NativeSecretBackend.MACOS_KEYCHAIN

    @staticmethod
    @contextmanager
    def _bound(namespace: str, account: str) -> Generator[tuple[_KeychainApi, _ItemIdentity]]:
        _target(namespace, account)
        try:
            api = _native_api()
            with api.session() as path:
                yield api, _ItemIdentity(namespace, account, path)
        except (OSError, AttributeError, ValueError, KeyError):
            raise _refuse(AutomationCustodyCode.UNAVAILABLE) from None

    @staticmethod
    def _read(api: _KeychainApi, identity: _ItemIdentity) -> SecretBytes | None:
        item = api.read(identity)
        if item is None:
            return None
        if (
            item.identity != identity
            or item.account_access is not True
            or not isinstance(item.data, bytes)
            or not 0 < len(item.data) <= _MAX_SECRET_BYTES
        ):
            raise _refuse()
        return SecretBytes(item.data)

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read one exact-bound native item with authentication UI disabled."""
        with self._bound(namespace, account) as (api, identity):
            return self._read(api, identity)

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Update or add then read-back-verify; never delete before replacement."""
        _target(namespace, account)
        raw = value.get_secret_value()
        if not 0 < len(raw) <= _MAX_SECRET_BYTES:
            raise _refuse()
        with self._bound(namespace, account) as (api, identity):
            self._read(api, identity)
            status = api.update(identity, raw)
            if status == _NOT_FOUND:
                status = api.add(identity, raw)
                if status == _DUPLICATE:
                    self._read(api, identity)
                    status = api.update(identity, raw)
            if status in (_NOT_FOUND, _DUPLICATE):
                raise _refuse(AutomationCustodyCode.CONFLICT)
            _status(status)
            observed = self._read(api, identity)
            if observed is None or not secrets.compare_digest(observed.get_secret_value(), raw):
                raise _refuse()

    def delete(self, namespace: str, account: str) -> None:
        """Delete only a validated exact item and verify its absence."""
        with self._bound(namespace, account) as (api, identity):
            self._read(api, identity)
            status = api.delete(identity)
            if status != _NOT_FOUND:
                _status(status)
            if self._read(api, identity) is not None:
                raise _refuse()
