"""Durable local retirement intents and separately verified native credential cleanup."""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from .....application.user_profile.automation_custody_port import AutomationSecretStore, NativeSecretBackend
from .automation_control_storage import AutomationControlStorage
from .automation_crypto import (
    MAX_CONTROL_BYTES,
    canonical_record,
    parse_record,
)
from .automation_records import (
    AutomationRetirementIntent,
    ProfileGlobalLockRecord,
)
from .automation_secret_store import native_automation_secret_store
from .filesystem import (
    profile_custody_root_lock,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from .filesystem_primitives import anchor_directory

_PROFILE_LOCK = "profile-lock.json"


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


def profile_automation_enrolled(*, root: Path, profile_id: UUID) -> bool:
    """Report whether a custody transition of this profile would retire anything the person relies on.

    A hosted profile's directory exists, empty, before anything is enrolled,
    and completed retirement clears it again. An unlocked profile-lock record
    is left behind by locking and unlocking without any enrollment; retiring
    it loses nothing. Any other record means custody is enrolled, being
    published or denied, still being retired, or a lock the person holds,
    which a custody transition would retire or clear. An unreadable lock
    record and a malformed installation entry count as well, so a caller that
    must not retire custody declines rather than guesses.
    """
    with profile_custody_root_lock(root):
        base = root / ".automation-v1"
        if not os.path.lexists(base):
            return False
        return any(
            not _canonical_installation(installation) or _holds_records(installation / str(profile_id))
            for installation in base.iterdir()
        )


def _canonical_installation(installation: Path) -> bool:
    try:
        return str(UUID(installation.name)) == installation.name and installation.is_dir()
    except ValueError:
        return False


def _holds_records(directory: Path) -> bool:
    if not os.path.lexists(directory):
        return False
    if not directory.is_dir() or directory.is_symlink():
        return True
    return any(entry.name != _PROFILE_LOCK or not _unlocked(entry) for entry in directory.iterdir())


def _unlocked(record: Path) -> bool:
    try:
        raw = read_optional_profile_custody_local_record(record, maximum_bytes=MAX_CONTROL_BYTES)
        return raw is not None and not parse_record(ProfileGlobalLockRecord, raw).globally_locked
    except (AutomationCustodyError, OSError):
        return False


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
