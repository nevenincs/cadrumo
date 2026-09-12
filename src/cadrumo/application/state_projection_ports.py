"""Application-owned read contracts for the operator state projection.

The projection producer needs a small, profile-scoped view of persistence.  It
does not need to know which catalogue repositories or storage-runtime
inspection serve that view.  This module owns the DTOs and the required port
bundle that an outer composition root supplies for one profile session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain.user_profile.values import UserProfileRecord


@dataclass(frozen=True, slots=True)
class StateProjectionWorkspaceRead:
    """Counters and integrity facts read from one profile workspace."""

    transactions: int
    invoices: int
    drafts: int
    work_units: int
    discarded_work_units: int
    calculation_revisions: int
    unreadable_rows: int


@dataclass(frozen=True, slots=True)
class StateProjectionProfileRead:
    """The profile bucket and current record used by readiness evaluation."""

    bucket_id: str
    record: UserProfileRecord


class StateProjectionWorkspaceReadPort(Protocol):
    """Read the workspace counters for an explicitly selected bucket."""

    def read_workspace(self, *, bucket_id: str) -> StateProjectionWorkspaceRead:
        """Return translated workspace facts for ``bucket_id``."""
        ...


class StateProjectionProfileReadPort(Protocol):
    """Read the current profile record for an active profile identifier."""

    def read_profile(self, *, profile_id: str) -> StateProjectionProfileRead | None:
        """Return the selected profile facts, or no pointer when absent."""
        ...


class StateProjectionReadError(RuntimeError):
    """Stable application error raised when a projection read cannot complete."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"state projection {operation} read failed")


@dataclass(frozen=True, slots=True)
class StateProjectionReadPorts:
    """Required persistence reads for one operator state projection."""

    workspace: StateProjectionWorkspaceReadPort
    profile: StateProjectionProfileReadPort


__all__ = [
    "StateProjectionProfileRead",
    "StateProjectionProfileReadPort",
    "StateProjectionReadError",
    "StateProjectionReadPorts",
    "StateProjectionWorkspaceRead",
    "StateProjectionWorkspaceReadPort",
]
