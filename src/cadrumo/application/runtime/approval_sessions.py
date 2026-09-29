"""Bounded ownership of transient approval proof across native worker phases.

This inventory owns resources only. The canonical administration service still
decides consent, credential possession and publication. Its caller must retain
the exact worker's operation authorization for every publication phase.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

from pydantic import SecretBytes

from ..operations.models import OperationId
from ..user_profile.access_contracts import ACCESS_LEASE_MAXIMUM
from ..user_profile.automation_administration import ApprovalSession, AutomationAdministrationService
from ..user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ..user_profile.automation_enrollment import EnrollmentTransition
from .approval_binding import RuntimeApprovalBinding
from .profile_worker import ProfileWorkerIdentity

APPROVAL_SESSION_LIMIT = 8


@dataclass(slots=True)
class _OwnedApproval:
    binding: RuntimeApprovalBinding
    session: ApprovalSession = field(repr=False)
    expires_at: float
    busy: bool = True
    retired: bool = False


class RuntimeApprovalSessions:
    """Keep proof until its active phase settles, without blocking denial fences.

    Map locking never spans application calls or acquisition of a profile guard.
    Retirement prevents later phases immediately; an already running phase owns
    cleanup until it returns. Containing the worker does not stop a parent KDF
    thread, so the host must also settle its native callback owner.
    """

    def __init__(
        self,
        *,
        worker: ProfileWorkerIdentity,
        service: Callable[[RuntimeApprovalBinding], AutomationAdministrationService],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Bind one immutable worker and a trusted exact-human service factory."""
        self._worker, self._service, self._clock = worker, service, clock
        self._lock = Lock()
        self._entries: dict[OperationId, _OwnedApproval] = {}
        self._closed = False

    def _instant(self) -> float:
        instant = self._clock()
        if not math.isfinite(instant):
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return instant

    def _reap_locked(self, instant: float) -> None:
        for operation_id, entry in tuple(self._entries.items()):
            entry.retired |= instant >= entry.expires_at
            if entry.retired and not entry.busy:
                # ApprovalSession.close only drops local references; it does
                # not acquire application locks or invoke recipient callbacks.
                entry.session.close()
                del self._entries[operation_id]

    def _finished(self, entry: _OwnedApproval, *, failed: bool) -> None:
        with self._lock:
            entry.busy = False
            entry.retired |= failed
            self._reap_locked(self._instant())

    @contextmanager
    def _phase(self, binding: RuntimeApprovalBinding) -> Generator[ApprovalSession]:
        with self._lock:
            self._reap_locked(self._instant())
            entry = self._entries.get(binding.operation_id)
            if self._closed or entry is None or entry.retired or entry.binding != binding:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            if entry.busy:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            entry.busy = True
        failed = True
        try:
            yield entry.session
            failed = False
        finally:
            self._finished(entry, failed=failed)

    def prepare(self, binding: RuntimeApprovalBinding, password: SecretBytes) -> None:
        """Own the exact approval before expensive proof; dispose it on any failure."""
        if (
            binding.worker_id != self._worker.worker_id
            or binding.runtime_boot_id != self._worker.runtime_boot_id
            or binding.profile_binding != self._worker.binding
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        # Service construction must not retain the password or start proof.
        session = self._service(binding).approval(binding.enrollment_request_id, review_digest=binding.review_digest)
        inserted = False
        try:
            with self._lock:
                instant = self._instant()
                self._reap_locked(instant)
                if self._closed:
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
                if binding.operation_id in self._entries:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                if len(self._entries) >= APPROVAL_SESSION_LIMIT:
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
                entry = _OwnedApproval(binding, session, instant + ACCESS_LEASE_MAXIMUM.total_seconds())
                self._entries[binding.operation_id] = entry
                inserted = True
            failed = True
            try:
                session.prepare(password)
                failed = False
            finally:
                self._finished(entry, failed=failed)
        finally:
            if not inserted:
                session.close()

    def commit_review(self, binding: RuntimeApprovalBinding) -> EnrollmentTransition | None:
        """Run the canonical review while the caller holds the exact COMMIT fence."""
        with self._phase(binding) as session:
            return session.commit_review()

    def inspect_recipient(self, binding: RuntimeApprovalBinding) -> bool:
        """Inspect the bound client outside the publication fence."""
        with self._phase(binding) as session:
            return session.inspect_recipient()

    def publish_candidate(self, binding: RuntimeApprovalBinding) -> EnrollmentTransition:
        """Publish an inactive candidate within the caller's exact COMMIT fence."""
        with self._phase(binding) as session:
            return session.publish_candidate()

    def deliver_and_verify(self, binding: RuntimeApprovalBinding) -> None:
        """Complete client-side delivery outside the publication fence."""
        with self._phase(binding) as session:
            session.deliver_and_verify()

    def activate(self, binding: RuntimeApprovalBinding) -> EnrollmentTransition:
        """Activate verified possession within the caller's exact COMMIT fence."""
        with self._phase(binding) as session:
            return session.activate()

    def retire(self, binding: RuntimeApprovalBinding) -> None:
        """Close this exact invocation; a busy phase retains cleanup responsibility."""
        with self._lock:
            entry = self._entries.get(binding.operation_id)
            if entry is not None:
                if entry.binding != binding:
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                entry.retired = True
            self._reap_locked(self._instant())

    def expire(self) -> None:
        """Release idle expired proofs during the host's existing lifecycle tick."""
        with self._lock:
            self._reap_locked(self._instant())

    def retire_sessions(self, session_ids: tuple[UUID, ...]) -> None:
        """Release proofs for retired human leases without affecting other sessions."""
        with self._lock:
            for entry in self._entries.values():
                if entry.binding.session_id in session_ids:
                    entry.retired = True
            self._reap_locked(self._instant())

    def retire_connection(self, connection_id: UUID) -> None:
        """Fence proofs owned by one disconnected native client."""
        with self._lock:
            for entry in self._entries.values():
                if entry.binding.connection_id == connection_id:
                    entry.retired = True
            self._reap_locked(self._instant())

    def close(self) -> int:
        """Fence future phases and report active callbacks still owning cleanup."""
        with self._lock:
            self._closed = True
            for entry in self._entries.values():
                entry.retired = True
            self._reap_locked(self._instant())
            return len(self._entries)
