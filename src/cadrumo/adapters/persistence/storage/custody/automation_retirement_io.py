"""Verified native wrapper deletion and final local control record cleanup."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from .automation_native_identity import WRAP_NAMESPACE
from .filesystem import (
    clear_profile_custody_local_record,
)


def retire_wrap_keys(secrets_store: AutomationSecretStore, account: str, wraps: set[UUID]) -> None:
    """Delete each witnessed native wrapper and refuse any surviving credential."""
    for identity in wraps:
        target = account + "/" + str(identity)
        secrets_store.delete(WRAP_NAMESPACE, target)
        if secrets_store.read(WRAP_NAMESPACE, target) is not None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)


def clear_retired_control_files(directory: Path) -> None:
    """Remove local recovery pointers only after native retirement has been verified."""
    for name in ("current.json", "publication.json", "denial.json", "profile-lock.json", "retirement.json"):
        clear_profile_custody_local_record(directory / name)
