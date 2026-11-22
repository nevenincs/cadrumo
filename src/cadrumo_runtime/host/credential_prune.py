"""Runtime-owned removal of OS credential-store entries this storage root no longer names."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cadrumo.adapters.persistence.storage.custody.acceleration_session_prune import (
    ProfileSessionPruneOutcome,
    profile_session_prune_has_work,
    prune_profile_session_entries,
)
from cadrumo.adapters.persistence.storage.custody.automation_retirement import (
    AutomationPruneOutcome,
    automation_prune_without_work,
    prune_unowned_automation_entries,
)
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyLockContendedError
from cadrumo.adapters.persistence.storage.custody.filesystem import profile_custody_root_lock
from cadrumo.adapters.persistence.storage.errors import StorageError
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger

_LOGGER = get_logger(__name__)

_ROOT_LOCK_BUDGET_SECONDS = 0.05
"""Never wait behind a custody transaction: a contended pass is skipped and the next one retries."""


@dataclass(frozen=True, slots=True)
class CredentialPruneReport:
    """One completed pass over both entry families; counts and typed reasons only."""

    profile_sessions: ProfileSessionPruneOutcome
    automation: AutomationPruneOutcome


@dataclass(frozen=True, slots=True)
class CredentialPruneSkipped:
    """A pass that did not run to the end; it names only the reason and an exception's type name."""

    reason: Literal["root_lock_contended", "root_unreadable", "unexpected_error"]
    error_type: str | None


def prune_owned_credentials(root: Path) -> CredentialPruneReport | CredentialPruneSkipped:
    """Remove this root's profile-session and automation entries that no record names, without raising.

    The pass holds the custody root lock every mint and publication holds,
    so no entry is in its pre-publication window. Startup and sign-in call
    it, so every failure becomes a typed skip that carries no message. An
    unavailable keychain is a typed outcome inside the report. Only counts
    and reasons are logged, never an account or a secret.

    Whether there is anything to prune is read first without the lock, so a
    root that records no minted session and that no automation entry names
    is left untouched: startup on an empty root creates nothing in it. When
    there is work, the locked pass reads everything again before deleting.
    """
    try:
        sessions_pending = profile_session_prune_has_work(root)
        settled_automation = automation_prune_without_work(root=root)
        if not sessions_pending and settled_automation is not None:
            sessions = ProfileSessionPruneOutcome(removed=(), retained=(), unavailability=None)
            automation = settled_automation
        else:
            with profile_custody_root_lock(root, timeout_seconds=_ROOT_LOCK_BUDGET_SECONDS):
                sessions = prune_profile_session_entries(root)
                automation = prune_unowned_automation_entries(root=root)
    except ProfileCustodyLockContendedError:
        return _skipped(CredentialPruneSkipped(reason="root_lock_contended", error_type=None))
    except (OSError, StorageError) as error:
        return _skipped(CredentialPruneSkipped(reason="root_unreadable", error_type=type(error).__name__))
    except Exception as error:
        return _skipped(CredentialPruneSkipped(reason="unexpected_error", error_type=type(error).__name__))
    report = CredentialPruneReport(profile_sessions=sessions, automation=automation)
    diagnostic_event(
        _LOGGER,
        "credential_prune",
        fields={
            "profile_sessions_removed": len(sessions.removed),
            "profile_sessions_left": len(sessions.retained),
            "profile_sessions_unavailability": None
            if sessions.unavailability is None
            else sessions.unavailability.value,
            "automation_removed": automation.removed,
            "automation_left": automation.retained,
            "automation_failure": None if automation.failure is None else automation.failure.value,
        },
        level=logging.INFO,
    )
    return report


def _skipped(skipped: CredentialPruneSkipped) -> CredentialPruneSkipped:
    diagnostic_event(
        _LOGGER,
        "credential_prune_skipped",
        fields={"reason": skipped.reason, "error_type": skipped.error_type},
        level=logging.DEBUG if skipped.reason == "root_lock_contended" else logging.WARNING,
    )
    return skipped
