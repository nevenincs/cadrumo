"""Durable local retirement intents and separately verified native credential cleanup."""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from .automation_control_storage import AutomationControlStorage
from .automation_crypto import (
    canonical_record,
)
from .automation_records import (
    AutomationRetirementIntent,
)
from .automation_secret_store import native_automation_secret_store
from .filesystem import (
    profile_custody_root_lock,
    write_profile_custody_local_record,
)
from .filesystem_primitives import anchor_directory


def retire_profile_automation(
    *, root: Path, profile_id: UUID, secrets_store: AutomationSecretStore | None = None
) -> bool:
    """Durably deny every local installation before a profile custody transition.

    Return whether native cleanup finished. Failure of optional native facilities
    leaves denial intents, allowing the password/recovery/delete transition to
    proceed. Failure to persist denial propagates before the transition commits.
    Portable capsules never include this external installation custody.
    """
    with profile_custody_root_lock(root), ExitStack() as anchors:
        base = root / ".automation-v1"
        if not os.path.lexists(base):
            return True
        anchor_directory(anchors, base)
        directories: list[Path] = []
        for installation in base.iterdir():
            try:
                installation_id = UUID(installation.name)
            except ValueError:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
            if str(installation_id) != installation.name:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            anchor_directory(anchors, installation)
            directory = installation / str(profile_id)
            if not os.path.lexists(directory):
                continue
            anchor_directory(anchors, directory)
            write_profile_custody_local_record(
                directory / "retirement.json",
                canonical_record(AutomationRetirementIntent(profile_id=profile_id, installation_id=installation_id)),
                publish_once=False,
            )
            directories.append(directory)
        if not directories:
            return True
        return _retire_profile_directories(root, directories, secrets_store)


def _retire_profile_directories(
    root: Path,
    directories: list[Path],
    secrets_store: AutomationSecretStore | None,
) -> bool:
    """Report optional native cleanup separately from already persisted denial intents."""
    try:
        backend = {
            "win32": NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER,
            "darwin": NativeSecretBackend.MACOS_KEYCHAIN,
            "linux": NativeSecretBackend.LINUX_DBUS,
        }.get(sys.platform)
        if secrets_store is None:
            if backend is None:
                return False
            secrets_store = native_automation_secret_store(backend)
        for directory in directories:
            AutomationControlStorage.retire_directory(root=root, directory=directory, secrets_store=secrets_store)
    except AutomationCustodyError:
        return False
    return True
