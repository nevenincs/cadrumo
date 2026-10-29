"""Owned candidates and cleanup for a session admission attempt."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from cadrumo.application.user_profile.access_contracts import AccessSession, ApiKeyRecord, AutomationGrant
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodySnapshot
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

from .session_authority_contracts import HumanAdmissionControl, SessionAuthorityFacts, SessionAuthorityOwner


class ProspectiveSessionRetirement:
    """Retain one prospective lease whose original physical retirement failed."""

    def __init__(self, owner: SessionAuthorityOwner, release: Callable[[], None]) -> None:
        """Retain the cleanup port and its original release callback."""
        self.owner, self._release = owner, release
        self._released = False
        self.binding_attempted = False
        self.committed = False

    def close_now(self) -> None:
        """Release physical custody once under the admission guard."""
        with self.owner.admission_guard():
            if not self._released:
                self._release()
                self._released = True

    async def close(self) -> None:
        """Retry the same cleanup owner off the event loop."""
        await asyncio.to_thread(self.close_now)

    def retain_failure(self, primary: BaseException, cleanup: AsyncResourceCleanupError) -> None:
        """Attach the retained cleanup to the original failure."""
        seen: set[int] = set()
        for field in ("async_cleanup_error", "cleanup_error"):
            previous = primary.__dict__.get(field)
            if isinstance(previous, AsyncResourceCleanupError) and id(previous) not in seen:
                seen.add(id(previous))
                cleanup = previous.merged_with(cleanup)
        primary.__dict__["async_cleanup_error"] = cleanup
        primary.add_note("Prospective session retirement failed; cleanup owner retained")
        if isinstance(primary, asyncio.CancelledError):
            primary.__dict__["cleanup_error"] = cleanup

    def close_if_uncommitted(self, primary: BaseException | None, *, retry_task_name: str) -> None:
        """Retire a candidate unless publication committed it."""
        if not self.binding_attempted or self.committed:
            return
        try:
            self.close_now()
        except BaseException as failure:
            cleanup = AsyncResourceCleanupError((self,), (failure,), retry_task_name=retry_task_name, close_attempts=1)
            if primary is not None:
                self.retain_failure(primary, cleanup)
            else:
                raise cleanup from failure


@dataclass(frozen=True)
class ApiKeyAdmissionCandidate:
    """Validated key, grant, session and native facts awaiting publication."""

    connection_id: UUID
    facts: SessionAuthorityFacts
    snapshot: AutomationCustodySnapshot
    grant: AutomationGrant
    key: ApiKeyRecord
    session: AccessSession
    rebinding: bool = False


@dataclass(frozen=True)
class HumanAdmissionCandidate:
    """A human candidate and the exact owned proof deadline."""

    deadline: float
    session: AccessSession
    generation: int
    rebinding: bool = False
    control: HumanAdmissionControl | None = None
