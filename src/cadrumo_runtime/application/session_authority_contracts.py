"""Trusted host observations and custody operations for session authority."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from threading import Event
from typing import Protocol
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import AccessEvaluationContext, AccessSession, ProfileAccessState
from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancellation
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome


@dataclass(frozen=True)
class SessionAuthorityFacts:
    """Fresh observations from the lifecycle and authenticated transport owners."""

    profile: ProfileAccessState
    context: AccessEvaluationContext


@dataclass
class HumanAdmissionControl:
    """One owner's cancellation and commit state, changed only on the admission fence."""

    cancelled: bool = False
    committed: bool = False
    cancelled_event: Event = field(default_factory=Event, repr=False)
    attempt_id: UUID = field(default_factory=uuid4)
    cancellation: ProfileProofCancellation = field(default_factory=ProfileProofCancellation, repr=False)

    def cancel(self) -> None:
        """Cancel an unpublished attempt without undoing a published sign-in."""
        if not self.committed and not self.cancelled:
            self.cancelled = True
            self.cancelled_event.set()
            self.cancellation.cancel()


class SessionAuthorityOwner(Protocol):
    """Trusted host integration; never a frontend request or alternate login service."""

    def admission_guard(self) -> AbstractContextManager[None]:
        """Share the denial fence with administration, revocation and private effects."""
        ...

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Reobserve the exact live connection, clocks, profile and OS login contexts."""
        ...

    @property
    def lost(self) -> bool:
        """Whether custody was irreversibly lost, as opposed to briefly unobservable."""
        ...

    @property
    def worker_lost(self) -> bool:
        """Whether the worker itself was positively lost: contained after a failure, exited or disconnected.

        A worker the runtime drained on purpose is lost to its owner too, but
        is not a worker loss.
        """
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
        """Attach this lease to the exact worker admitted by authenticate_human.

        A requested receipt stays pending: binding precedes publication, and a
        refusal before publication must leave no receipt.
        """
        ...

    def capture_human_sign_in(self, session_id: UUID) -> bool:
        """Durably establish, at publication, the sign-in generation of a pending receipt.

        Called under the admission guard right after the session is published.
        Return ``False``, writing nothing, when no receipt is pending.
        """
        ...

    def mint_human_receipt(self, session_id: UUID) -> None:
        """Mint the pending receipt, stamped with the generation captured at publication.

        Called under the admission guard, and only for a session still
        published. Nothing is written when that generation is no longer current.
        """
        ...

    def human_admission_deadline(self, connection_id: UUID) -> float:
        """Lend the original monotonic preparation bound for this exact candidate."""
        ...

    def authenticate_human(self, connection_id: UUID) -> AbstractContextManager[tuple[ProfileLoginOutcome, str] | None]:
        """Use the existing profile admission/login lifecycle in its bound worker.

        Lend its verified login outcome and originating native login identity.
        The call may reuse valid human admission but must never promote an API
        session, synthesize a login outcome or renew a deadline for automation activity.
        Release candidate custody on every exit unless bind_human committed it;
        a failed candidate must not retire another connection's existing custody.
        """
        ...
