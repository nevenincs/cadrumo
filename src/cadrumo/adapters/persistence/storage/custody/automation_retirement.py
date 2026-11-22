"""Durable local retirement intents and separately verified native credential cleanup."""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from .....application.user_profile.automation_custody_port import AutomationSecretStore, NativeSecretBackend
from .automation_control_storage import AutomationControlStorage
from .automation_crypto import (
    MAX_CONTROL_BYTES,
    canonical_record,
    parse_record,
)
from .automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE, automation_root_digest
from .automation_records import (
    AutomationRetirementIntent,
    ProfileGlobalLockRecord,
)
from .automation_secret_store import WindowsAutomationSecretStore, native_automation_secret_store
from .errors import ProfileCustodyRecordError
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


class AutomationSecretListing(Protocol):
    """The native-store calls an ownership prune needs: names-only listing and verified deletion."""

    def list_accounts(self, namespace: str, account_prefix: str) -> tuple[str, ...]:
        """Return the account names under ``namespace`` that start with ``account_prefix``; never a secret."""
        ...

    def delete(self, namespace: str, account: str) -> None:
        """Delete one owned item and verify absence."""
        ...


@dataclass(frozen=True, slots=True)
class AutomationPruneOutcome:
    """How many unowned native automation entries one pass removed, and why it stopped early if it did.

    ``retained`` counts the unowned entries a failure left for the next pass.
    """

    removed: int
    retained: int
    failure: AutomationCustodyCode | None


_ACCOUNT_PARTS = {CONTROL_NAMESPACE: 3, WRAP_NAMESPACE: 4}
"""Control anchors name ``<root>/<installation>/<profile>``; grant wraps add ``/<wrap>``."""


def _unowned_by_root(account: str, *, root_digest: str, parts: int, base: Path) -> bool:
    """Return whether a root-scoped account names an automation directory that is positively absent.

    A malformed account, or a directory whose absence cannot be observed, is
    not proven unowned and is kept.
    """
    fields = account.split("/")
    if len(fields) != parts or fields[0] != root_digest:
        return False
    try:
        identities = [UUID(field) for field in fields[1:]]
    except ValueError:
        return False
    if any(str(identity) != field for identity, field in zip(identities, fields[1:], strict=True)):
        return False
    try:
        (base / fields[1] / fields[2]).lstat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def automation_prune_without_work(
    *, root: Path, secrets_store: AutomationSecretListing | None = None
) -> AutomationPruneOutcome | None:
    """Return the settled pass outcome when no native automation entry names ``root``, else ``None``.

    Read without the custody root lock, so a root with nothing to prune is
    left untouched. ``None`` sends the caller to the locked pass, which lists
    the entries again under the lock before deleting any; an entry published
    after this read is published under that lock with its directory, and the
    locked pass keeps it. A listing that cannot answer also returns ``None``,
    so the locked pass reports its typed failure.
    """
    if secrets_store is None:
        if sys.platform != "win32":
            return AutomationPruneOutcome(removed=0, retained=0, failure=AutomationCustodyCode.UNSUPPORTED)
        secrets_store = WindowsAutomationSecretStore()
    root_digest = automation_root_digest(root)
    try:
        if any(secrets_store.list_accounts(namespace, root_digest + "/") for namespace in _ACCOUNT_PARTS):
            return None
    except (AutomationCustodyError, OSError):
        return None
    return AutomationPruneOutcome(removed=0, retained=0, failure=None)


def prune_unowned_automation_entries(
    *, root: Path, secrets_store: AutomationSecretListing | None = None
) -> AutomationPruneOutcome:
    """Delete this root's control-anchor and grant-wrap entries whose automation directory is gone.

    Only accounts that start with this root's own digest are listed, so no
    other root's entry is touched. A live directory's anchor and wraps stay:
    its publication intents and retirement own them. Client keys carry no root
    or profile and are never pruned here. Every publication holds the custody
    root lock and creates its directory before its native entries, so under
    that lock an entry without a directory belongs to nothing.
    """
    if secrets_store is None:
        if sys.platform != "win32":
            return AutomationPruneOutcome(removed=0, retained=0, failure=AutomationCustodyCode.UNSUPPORTED)
        secrets_store = WindowsAutomationSecretStore()
    candidates: list[tuple[str, str]] = []
    try:
        with profile_custody_root_lock(root):
            root_digest = automation_root_digest(root)
            base = root / ".automation-v1"
            for namespace, parts in _ACCOUNT_PARTS.items():
                candidates.extend(
                    (namespace, account)
                    for account in secrets_store.list_accounts(namespace, root_digest + "/")
                    if _unowned_by_root(account, root_digest=root_digest, parts=parts, base=base)
                )
            for index, (namespace, account) in enumerate(candidates):
                try:
                    secrets_store.delete(namespace, account)
                except AutomationCustodyError as error:
                    return AutomationPruneOutcome(removed=index, retained=len(candidates) - index, failure=error.reason)
    except AutomationCustodyError as error:
        return AutomationPruneOutcome(removed=0, retained=len(candidates), failure=error.reason)
    except (OSError, ProfileCustodyRecordError):
        return AutomationPruneOutcome(removed=0, retained=len(candidates), failure=AutomationCustodyCode.UNAVAILABLE)
    return AutomationPruneOutcome(removed=len(candidates), retained=0, failure=None)
