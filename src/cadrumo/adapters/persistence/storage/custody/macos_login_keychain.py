"""Explicit login-Keychain native sessions, owner access admission, and item mutations."""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
)
from .macos_core_foundation import CoreFoundation, bind_native_function, native_integer
from .macos_keychain_contracts import (
    AUTHORIZATIONS,
    DESCRIPTION,
    NOT_FOUND,
    SECURITY,
    SUCCESS,
    UI_LOCK,
    KeychainAclRole,
    KeychainItem,
    KeychainItemIdentity,
    NativeKeychainFunction,
)
from .macos_keychain_policy import keychain_acl_role, keychain_refusal, login_keychain_path, require_keychain_status


class LoginKeychain:
    """Explicit encrypted OS login store; no entitlement or search-list fallback."""

    path: str
    cf: CoreFoundation
    security: ctypes.CDLL
    keychain: int | None
    constants: dict[str, int]
    copy: NativeKeychainFunction
    update_item: NativeKeychainFunction
    add_item: NativeKeychainFunction
    delete_item: NativeKeychainFunction
    ui_get: NativeKeychainFunction
    ui_set: NativeKeychainFunction
    open_keychain: NativeKeychainFunction
    keychain_path: NativeKeychainFunction
    keychain_status: NativeKeychainFunction
    access_create: NativeKeychainFunction
    acl_list: NativeKeychainFunction
    authorizations: NativeKeychainFunction
    acl_contents: NativeKeychainFunction
    acl_set: NativeKeychainFunction
    item_access: NativeKeychainFunction
    item_keychain: NativeKeychainFunction

    def __init__(self) -> None:
        """Bind one explicit login-Keychain and all native capabilities before use."""
        if sys.platform != "darwin":
            raise keychain_refusal(AutomationCustodyCode.UNSUPPORTED)
        self.path = login_keychain_path()
        self.keychain: int | None = None
        self.cf = CoreFoundation()
        self.security = ctypes.CDLL(SECURITY)
        pointer = ctypes.c_void_p
        output = ctypes.POINTER(pointer)
        self.copy = bind_native_function(self.security, "SecItemCopyMatching", [pointer, output], ctypes.c_int32)
        self.update_item = bind_native_function(self.security, "SecItemUpdate", [pointer, pointer], ctypes.c_int32)
        self.add_item = bind_native_function(self.security, "SecItemAdd", [pointer, output], ctypes.c_int32)
        self.delete_item = bind_native_function(self.security, "SecItemDelete", [pointer], ctypes.c_int32)
        self.ui_get = bind_native_function(
            self.security, "SecKeychainGetUserInteractionAllowed", [ctypes.POINTER(ctypes.c_ubyte)], ctypes.c_int32
        )
        self.ui_set = bind_native_function(
            self.security, "SecKeychainSetUserInteractionAllowed", [ctypes.c_ubyte], ctypes.c_int32
        )
        self.open_keychain = bind_native_function(
            self.security, "SecKeychainOpen", [ctypes.c_char_p, output], ctypes.c_int32
        )
        self.keychain_path = bind_native_function(
            self.security, "SecKeychainGetPath", [pointer, ctypes.POINTER(ctypes.c_uint32), pointer], ctypes.c_int32
        )
        self.keychain_status = bind_native_function(
            self.security, "SecKeychainGetStatus", [pointer, ctypes.POINTER(ctypes.c_uint32)], ctypes.c_int32
        )
        self.access_create = bind_native_function(
            self.security, "SecAccessCreate", [pointer, pointer, output], ctypes.c_int32
        )
        self.acl_list = bind_native_function(self.security, "SecAccessCopyACLList", [pointer, output], ctypes.c_int32)
        self.authorizations = bind_native_function(self.security, "SecACLCopyAuthorizations", [pointer], pointer)
        self.acl_contents = bind_native_function(
            self.security,
            "SecACLCopyContents",
            [pointer, output, output, ctypes.POINTER(ctypes.c_uint16)],
            ctypes.c_int32,
        )
        self.acl_set = bind_native_function(
            self.security, "SecACLSetContents", [pointer, pointer, pointer, ctypes.c_uint16], ctypes.c_int32
        )
        self.item_access = bind_native_function(
            self.security, "SecKeychainItemCopyAccess", [pointer, output], ctypes.c_int32
        )
        self.item_keychain = bind_native_function(
            self.security, "SecKeychainItemCopyKeychain", [pointer, output], ctypes.c_int32
        )
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
            *AUTHORIZATIONS,
        )
        self.constants = {name: self.cf.constant(self.security, name) for name in names}

    def _constant(self, name: str) -> int:
        return self.constants[name]

    @contextmanager
    def _copied(self, function: NativeKeychainFunction, *args: object) -> Generator[int]:
        result = ctypes.c_void_p()
        try:
            require_keychain_status(native_integer(function(*args, ctypes.byref(result))))
            if not result.value:
                raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
            yield result.value
        finally:
            if result.value:
                self.cf.release(result.value)

    @contextmanager
    def _noninteractive(self) -> Generator[None]:
        # The file-based implementation uses a process-global UI switch. All
        # cooperating automation-store callers share this lock for the whole
        # native session, including mutation read-back and error cleanup.
        with UI_LOCK:
            previous = ctypes.c_ubyte()
            require_keychain_status(native_integer(self.ui_get(ctypes.byref(previous))))
            if previous.value not in (0, 1):
                raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
            try:
                require_keychain_status(native_integer(self.ui_set(0)))
                observed = ctypes.c_ubyte(1)
                require_keychain_status(native_integer(self.ui_get(ctypes.byref(observed))))
                if observed.value != 0:
                    raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)
                yield
            finally:
                restored = ctypes.c_ubyte()
                if (
                    self.ui_set(previous.value) != SUCCESS
                    or self.ui_get(ctypes.byref(restored)) != SUCCESS
                    or restored.value != previous.value
                ):
                    # Failure to restore shared native UI state is facility
                    # unavailability; it must also prevent a prepared read
                    # result from being released as successful.
                    raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE)

    def _validate_keychain(self, keychain: int, path: str) -> None:
        buffer = ctypes.create_string_buffer(4096)
        size = ctypes.c_uint32(len(buffer))
        require_keychain_status(native_integer(self.keychain_path(keychain, ctypes.byref(size), buffer)))
        raw: object = buffer.value
        if (
            not isinstance(raw, bytes)
            or not 0 < size.value < len(buffer)
            or os.fsdecode(raw) != path
            or path != self.path
        ):
            raise keychain_refusal()
        state = ctypes.c_uint32()
        require_keychain_status(native_integer(self.keychain_status(keychain, ctypes.byref(state))))
        # This observation is advisory; every actual call still handles a
        # concurrent lock/access refusal. Never attempt to unlock the store.
        if state.value & 1 == 0:
            raise keychain_refusal(AutomationCustodyCode.NEEDS_USER)

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

    def _bound_keychain(self, identity: KeychainItemIdentity) -> int:
        if self.keychain is None or identity.keychain_path != self.path:
            raise keychain_refusal()
        self._validate_keychain(self.keychain, identity.keychain_path)
        return self.keychain

    @contextmanager
    def _query(self, identity: KeychainItemIdentity, *, adding: bool = False) -> Generator[int]:
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
            raise keychain_refusal()
        try:
            self.cf.require_type(pointer, self.cf.array_type)
            count = native_integer(self.cf.array_count(pointer))
            if not 0 < count <= len(AUTHORIZATIONS):
                raise keychain_refusal()
            observed: set[str] = set()
            for index in range(count):
                tag = self.cf.require_type(self.cf.array_get(pointer, index), self.cf.string_type)
                matched = [
                    meaning for name, meaning in AUTHORIZATIONS.items() if self.cf.equal(tag, self._constant(name)) == 1
                ]
                if len(matched) != 1 or matched[0] in observed:
                    raise keychain_refusal()
                observed.add(matched[0])
            return frozenset(observed)
        finally:
            self.cf.release(pointer)

    @contextmanager
    def _acl_content(self, acl: int) -> Generator[tuple[int | None, int]]:
        applications, description = ctypes.c_void_p(), ctypes.c_void_p()
        selector = ctypes.c_uint16()
        try:
            require_keychain_status(
                native_integer(
                    self.acl_contents(
                        acl, ctypes.byref(applications), ctypes.byref(description), ctypes.byref(selector)
                    )
                )
            )
            if not description.value:
                raise keychain_refusal()
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
            count = native_integer(self.cf.array_count(entries))
            if not 3 <= count <= 5:
                raise keychain_refusal()
            seen: set[KeychainAclRole] = set()
            for index in range(count):
                acl = native_integer(self.cf.array_get(entries, index))
                role = keychain_acl_role(self._acl_authorizations(acl))
                if role in seen:
                    raise keychain_refusal()
                seen.add(role)
                if role in {"integrity", "partition"}:
                    # Published native storage-integrity/partition entries are
                    # platform-owned. Never rewrite their content or mistake
                    # them for a data-read or ChangeACL authorization.
                    continue
                self._validate_acl_content(acl, role, configure_new)
            if not {"restricted", "safe", "owner"} <= seen:
                raise keychain_refusal()

    def _validate_acl_content(self, acl: int, role: KeychainAclRole, configure_new: bool) -> None:
        """Admit one exact native ACL role and widen only a newly owned restricted entry."""
        with self._acl_content(acl) as (applications, description):
            if self.cf.text(description) != DESCRIPTION:
                raise keychain_refusal()
            if role == "owner":
                # Empty means NO trusted apps. NULL would grant ALL.
                # Retain the default owner rule; never widen it.
                if applications is None or self.cf.array_count(applications) != 0:
                    raise keychain_refusal()
            elif role == "restricted" and configure_new:
                # SecAccessCreate(NULL) trusts the calling app only.
                # SecACLSetContents(NULL) explicitly trusts all apps
                # inside the approved OS-account boundary.
                require_keychain_status(native_integer(self.acl_set(acl, None, description, 0)))
            elif applications is not None:
                raise keychain_refusal()

    @contextmanager
    def _access(self) -> Generator[int]:
        with self.cf.string(DESCRIPTION) as description, self._copied(self.access_create, description, None) as access:
            self._validate_access(access, configure_new=True)
            self._validate_access(access)
            yield access

    def read(self, identity: KeychainItemIdentity) -> KeychainItem | None:
        """Read one exact native item after Keychain, identity and ACL admission."""
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
                status = native_integer(self.copy(query, ctypes.byref(result)))
                if status == NOT_FOUND:
                    return None
                require_keychain_status(status)
                record = self.cf.require_type(result.value, self.cf.dictionary_type)
                observed = KeychainItemIdentity(
                    self.cf.text(self.cf.field(record, self._constant("kSecAttrService"))),
                    self.cf.text(self.cf.field(record, self._constant("kSecAttrAccount"))),
                    identity.keychain_path,
                )
                if observed != identity:
                    raise keychain_refusal()
                item = native_integer(self.cf.field(record, self._constant("kSecValueRef")))
                with self._copied(self.item_keychain, item) as keychain:
                    if self.keychain is None or self.cf.equal(keychain, self.keychain) != 1:
                        raise keychain_refusal()
                    self._validate_keychain(keychain, identity.keychain_path)
                with self._copied(self.item_access, item) as access:
                    self._validate_access(access)
                return KeychainItem(
                    observed,
                    True,
                    self.cf.read_data(self.cf.field(record, self._constant("kSecValueData"))),
                )
            finally:
                if result.value:
                    self.cf.release(result.value)

    def update(self, identity: KeychainItemIdentity, value: bytes) -> int:
        """Update the selected item through the held noninteractive native session."""
        with self._query(identity) as query, self.cf.data(value) as data, self.cf.dictionary() as attributes:
            self.cf.dictionary_set(attributes, self._constant("kSecValueData"), data)
            return native_integer(self.update_item(query, attributes))

    def add(self, identity: KeychainItemIdentity, value: bytes) -> int:
        """Add one exact item with the newly owned and verified access policy."""
        with self._query(identity, adding=True) as query, self.cf.data(value) as data, self._access() as access:
            self.cf.dictionary_set(query, self._constant("kSecValueData"), data)
            self.cf.dictionary_set(query, self._constant("kSecAttrAccess"), access)
            return native_integer(self.add_item(query, None))

    def delete(self, identity: KeychainItemIdentity) -> int:
        """Delete one exact item through its immutable native identity query."""
        with self._query(identity) as query:
            return native_integer(self.delete_item(query))
