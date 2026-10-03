"""Explicit native secret-store composition; no plugin discovery or fallback."""

from __future__ import annotations

import ctypes
import secrets
import sys
from typing import Any, Protocol, cast

from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from .automation_secret_target import require_automation_secret_target
from .zeroise import zeroise

_MAX_CREDENTIAL_BLOB_SIZE = 2560
_ERROR_NOT_FOUND = 1168


def _windows_last_error() -> int:
    """Read ctypes' saved Win32 error without exposing it beyond status mapping."""
    if sys.platform == "win32":
        return ctypes.get_last_error()
    raise OSError


class _WindowsCredentialApi(Protocol):
    """Raw-byte operations over the current user's Windows Credential Manager."""

    def read(self, target: str) -> bytes | None: ...

    def write(self, target: str, account: str, value: bytes) -> None: ...

    def delete(self, target: str) -> None: ...


class _WindowsCredentialError(Exception):
    """Retain only a native error code for internal status mapping."""

    def __init__(self, winerror: int) -> None:
        self.winerror = winerror
        super().__init__()


class _InvalidWindowsCredentialError(Exception):
    """A native record does not satisfy the local credential-blob contract."""


class _WindowsCredentialManager:
    """Call the wide Windows APIs while preserving their byte-oriented blob."""

    _credential_type: Any
    _credential_type_generic: int
    _credential_persist_local_machine: int
    _cred_read: Any
    _cred_write: Any
    _cred_delete: Any
    _cred_free: Any

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError

        from ctypes import wintypes

        class _FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class _CredentialAttribute(ctypes.Structure):
            _fields_ = [
                ("Keyword", wintypes.LPWSTR),
                ("Flags", wintypes.DWORD),
                ("ValueSize", wintypes.DWORD),
                ("Value", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        class _Credential(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", _FileTime),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.POINTER(_CredentialAttribute)),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        self._credential_type = _Credential
        self._credential_type_generic = 1
        self._credential_persist_local_machine = 2

        if sys.platform == "win32":
            advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        else:
            raise OSError
        self._cred_read = advapi32.CredReadW
        self._cred_read.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_Credential)),
        ]
        self._cred_read.restype = wintypes.BOOL

        self._cred_write = advapi32.CredWriteW
        self._cred_write.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
        self._cred_write.restype = wintypes.BOOL

        self._cred_delete = advapi32.CredDeleteW
        self._cred_delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._cred_delete.restype = wintypes.BOOL

        self._cred_free = advapi32.CredFree
        self._cred_free.argtypes = [ctypes.c_void_p]
        self._cred_free.restype = None

    def read(self, target: str) -> bytes | None:
        """Read the exact target and release the returned structure on every path."""
        credential_pointer = cast(Any, ctypes.POINTER(self._credential_type)())
        if not self._cred_read(
            target,
            self._credential_type_generic,
            0,
            ctypes.byref(credential_pointer),
        ):
            winerror = _windows_last_error()
            if winerror == _ERROR_NOT_FOUND:
                return None
            raise _WindowsCredentialError(winerror)
        if not credential_pointer:
            raise _InvalidWindowsCredentialError

        try:
            credential = credential_pointer.contents
            blob_size = int(credential.CredentialBlobSize)
            if blob_size > _MAX_CREDENTIAL_BLOB_SIZE or (blob_size and not credential.CredentialBlob):
                raise _InvalidWindowsCredentialError

            blob = bytearray(blob_size)
            try:
                if blob_size:
                    destination = (ctypes.c_ubyte * blob_size).from_buffer(blob)
                    ctypes.memmove(destination, credential.CredentialBlob, blob_size)
                return bytes(blob)
            finally:
                zeroise(blob)
        finally:
            # CredRead returns a caller-owned copy, so clear its blob before freeing it.
            try:
                if credential_pointer and credential_pointer.contents.CredentialBlob:
                    blob_size = int(credential_pointer.contents.CredentialBlobSize)
                    if 0 < blob_size <= _MAX_CREDENTIAL_BLOB_SIZE:
                        ctypes.memset(credential_pointer.contents.CredentialBlob, 0, blob_size)
            finally:
                self._cred_free(ctypes.cast(credential_pointer, ctypes.c_void_p))

    def write(self, target: str, account: str, value: bytes) -> None:
        """Write an exact byte blob and wipe the mutable staging buffer."""
        if not 0 < len(value) <= _MAX_CREDENTIAL_BLOB_SIZE:
            raise _InvalidWindowsCredentialError

        blob = bytearray(value)
        try:
            blob_array = (ctypes.c_ubyte * len(blob)).from_buffer(blob)
            credential = self._credential_type()
            credential.Flags = 0
            credential.Type = self._credential_type_generic
            credential.TargetName = target
            credential.CredentialBlobSize = len(blob)
            credential.CredentialBlob = ctypes.cast(blob_array, ctypes.POINTER(ctypes.c_ubyte))
            credential.Persist = self._credential_persist_local_machine
            credential.UserName = account
            if not self._cred_write(ctypes.byref(credential), 0):
                raise _WindowsCredentialError(_windows_last_error())
        finally:
            zeroise(blob)

    def delete(self, target: str) -> None:
        """Delete only the exact generic-credential target."""
        if not self._cred_delete(target, self._credential_type_generic, 0):
            raise _WindowsCredentialError(_windows_last_error())


def _windows_credential_api() -> _WindowsCredentialApi:
    """Create the native API wrapper only after the caller checks the platform."""
    return _WindowsCredentialManager()


class WindowsAutomationSecretStore:
    """Windows generic credentials, non-roaming and accessed without UI."""

    backend = NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER

    def _target(self, namespace: str, account: str) -> str:
        require_automation_secret_target(namespace, account)
        if sys.platform != "win32":
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        return namespace + ":" + account

    @staticmethod
    def _api() -> _WindowsCredentialApi:
        try:
            return _windows_credential_api()
        except OSError:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read only the exact generic credential, without enumeration or UI."""
        target = self._target(namespace, account)
        try:
            value = self._api().read(target)
        except _WindowsCredentialError as error:
            if error.winerror == _ERROR_NOT_FOUND:
                return None
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        except _InvalidWindowsCredentialError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        if value is None:
            return None
        if not isinstance(value, bytes) or len(value) > _MAX_CREDENTIAL_BLOB_SIZE:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return SecretBytes(value)

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Replace one native record and verify its exact bytes."""
        target = self._target(namespace, account)
        raw = value.get_secret_value()
        if not 0 < len(raw) <= _MAX_CREDENTIAL_BLOB_SIZE:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        try:
            self._api().write(target, account, raw)
        except _WindowsCredentialError:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        except _InvalidWindowsCredentialError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        observed = self.read(namespace, account)
        if observed is None or not secrets.compare_digest(observed.get_secret_value(), raw):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    def delete(self, namespace: str, account: str) -> None:
        """Delete only the named item and verify absence."""
        target = self._target(namespace, account)
        try:
            self._api().delete(target)
        except _WindowsCredentialError as error:
            if error.winerror != _ERROR_NOT_FOUND:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        if self.read(namespace, account) is not None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)


def native_automation_secret_store(backend: NativeSecretBackend) -> AutomationSecretStore:
    """Select only implemented native facilities on their matching platform."""
    if backend is NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER and sys.platform == "win32":
        return WindowsAutomationSecretStore()
    if backend is NativeSecretBackend.LINUX_DBUS and sys.platform == "linux":
        from .linux_secret_service_store import LinuxSecretServiceAutomationSecretStore

        return LinuxSecretServiceAutomationSecretStore()
    if backend is NativeSecretBackend.MACOS_KEYCHAIN and sys.platform == "darwin":
        from .macos_keychain_store import MacOSKeychainAutomationSecretStore

        return MacOSKeychainAutomationSecretStore()
    raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
