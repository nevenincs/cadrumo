"""Trusted host observations and custody operations for session authority."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from .access_contracts import AccessEvaluationContext, AccessSession, ProfileAccessState
from .login_session import ProfileLoginOutcome


@dataclass(frozen=True)
class SessionAuthorityFacts:
    """Fresh observations from the lifecycle and authenticated transport owners."""

    profile: ProfileAccessState
    context: AccessEvaluationContext


class SessionAuthorityOwner(Protocol):
    """Trusted host integration; never a frontend request or alternate login service."""

    def admission_guard(self) -> AbstractContextManager[None]:
        """Share the denial fence with administration, revocation and private effects."""
        ...

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Reobserve the exact live connection, clocks, profile and OS login contexts."""
        ...

    def prepare_api_admission(self, connection_id: UUID) -> AbstractContextManager[float]:
        """Prepare the exact worker without keys or leases; lend its original deadline.

        Preparation leaves the shared denial guard. Activation must use that same
        worker and connection, within the remaining original preparation budget.
        Exiting this context never publishes an application lease.
        """
        ...

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        """Copy borrowed material into exact-profile worker custody or raise.

        Failure must retire any partially installed worker custody. The borrowed
        buffer is wiped by the caller; it must not be retained. No active-profile
        selector or process-global human deadline may be changed here.
        """
        ...

    def retire(self, session_id: UUID) -> None:
        """Fence and release lease custody; an uninstalled/already retired ID is a no-op."""
        ...

    def share(self, session: AccessSession, parent: AccessSession) -> None:
        """Attach a narrowed child to the parent's profile custody or raise atomically."""
        ...

    def refresh(self, session: AccessSession) -> None:
        """Apply the reauthorized root lease to its existing exact-profile worker."""
        ...

    def bind_human(self, session: AccessSession) -> None:
        """Attach this lease to the exact worker admitted by authenticate_human."""
        ...

    def human_admission_deadline(self, connection_id: UUID) -> float:
        """Lend the original monotonic preparation bound for this exact candidate."""
        ...

    def authenticate_human(self, connection_id: UUID) -> AbstractContextManager[tuple[ProfileLoginOutcome, str] | None]:
        """Use the existing profile admission/login lifecycle in its bound worker.

        Lend its verified login outcome and originating native login identity.
        The call may reuse valid human admission but must never promote an API
        session, synthesize a login outcome or renew a deadline for agent activity.
        Release candidate custody on every exit unless bind_human committed it;
        a failed candidate must not retire another connection's existing custody.
        """
        ...
