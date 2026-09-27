"""Explicit native secret-store composition; no plugin discovery or fallback."""

from __future__ import annotations

import secrets
import sys
from collections.abc import Callable
from typing import Protocol, cast

from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)


class _WindowsCredentialApi(Protocol):
    CRED_TYPE_GENERIC: int
    CRED_PERSIST_LOCAL_MACHINE: int

    CredRead: Callable[[str, int], dict[str, object]]
    CredWrite: Callable[[dict[str, object], int], None]
    CredDelete: Callable[[str, int, int], None]


class WindowsAutomationSecretStore:
    """Windows generic credentials, non-roaming and accessed without UI."""

    backend = NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER

    def _target(self, namespace: str, account: str) -> str:
        if not namespace.startswith("cadrumo.automation.") or not account or len(namespace + account) > 1024:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        if sys.platform != "win32":
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        return namespace + ":" + account

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read only the exact generic credential, without enumeration or UI."""
        target = self._target(namespace, account)
        try:
            import pywintypes
            import win32cred

            api = cast(_WindowsCredentialApi, win32cred)
            try:
                record = api.CredRead(target, api.CRED_TYPE_GENERIC)
            except pywintypes.error as error:
                if error.winerror == 1168:
                    return None
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
            value = record["CredentialBlob"]
            if not isinstance(value, bytes) or len(value) > 2560:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            return SecretBytes(value)
        except ImportError:
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED) from None

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Replace one native record and verify its bytes."""
        target = self._target(namespace, account)
        try:
            import pywintypes
            import win32cred

            api = cast(_WindowsCredentialApi, win32cred)
            if not 0 < len(value.get_secret_value()) <= 2560:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            try:
                api.CredWrite(
                    {
                        "Type": api.CRED_TYPE_GENERIC,
                        "TargetName": target,
                        "CredentialBlob": value.get_secret_value(),
                        "Persist": api.CRED_PERSIST_LOCAL_MACHINE,
                        "UserName": account,
                    },
                    0,
                )
            except pywintypes.error:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
            observed = self.read(namespace, account)
            if observed is None or not secrets.compare_digest(observed.get_secret_value(), value.get_secret_value()):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        except ImportError:
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED) from None

    def delete(self, namespace: str, account: str) -> None:
        """Delete only the named item and verify absence."""
        target = self._target(namespace, account)
        try:
            import pywintypes
            import win32cred

            api = cast(_WindowsCredentialApi, win32cred)
            try:
                api.CredDelete(target, api.CRED_TYPE_GENERIC, 0)
            except pywintypes.error as error:
                if error.winerror != 1168:
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
            if self.read(namespace, account) is not None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        except ImportError:
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED) from None


def native_automation_secret_store(backend: NativeSecretBackend) -> AutomationSecretStore:
    """Refuse unimplemented/nonmatching native facilities, including arbitrary keyring plugins.

    macOS and Linux ports require native non-prompting adapters and platform
    acceptance before composition can enable them; no installed support is implied.
    """
    if backend is NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER and sys.platform == "win32":
        return WindowsAutomationSecretStore()
    raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
