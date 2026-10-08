"""Select only the platform's explicit non-prompting automation credential port."""

from __future__ import annotations

import sys

from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)


def installed_automation_secret_store() -> AutomationSecretStore:
    """Refuse unsupported facilities without plugin discovery or store fallback."""
    backend = {
        "win32": NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER,
        "darwin": NativeSecretBackend.MACOS_KEYCHAIN,
        "linux": NativeSecretBackend.LINUX_DBUS,
    }.get(sys.platform)
    if backend is None:
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    return native_automation_secret_store(backend)
