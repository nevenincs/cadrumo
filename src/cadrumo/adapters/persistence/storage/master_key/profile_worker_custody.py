"""Profile-fixed custody lending for runtime-issued access leases."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from uuid import UUID

from .....application.runtime.profile_worker import ProfileWorkerIdentity
from .....application.user_profile.access_contracts import AccessSession, SessionKind, SessionState
from .....application.user_profile.access_policy import intersect_scopes
from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .....application.user_profile.profile_record_repository import close_active_profile_record_session
from .....core.time.clock import now
from .....core.time.utc import UtcInstant
from ..custody.automation_profile import validate_automation_profile_binding
from .active_session import bind_active_bucket_session, close_active_bucket_session, current_active_bucket_session
from .bucket_session import BucketSession
from .profile_worker_binding import profile_worker_binding


class ProfileWorkerCustody:
    """Own one process's key session; execution authority still belongs to the runtime.

    Every operation must also pass the runtime's live permission and commit/output
    guards. This component proves exact custody and expires physical key access;
    it does not turn a lease-shaped client document into authorization.
    """

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        clock: Callable[[], UtcInstant] = now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Pin an empty worker before any profile material can be delivered."""
        if current_active_bucket_session() is not None:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        profile_worker_binding.bind(identity, storage_root=storage_root)
        self.identity, self.root, self.clock, self.monotonic = identity, storage_root, clock, monotonic
        self._leases: dict[UUID, AccessSession] = {}
        self._lock = RLock()
        self._closed = False
        self._sections = 0
        self._material_update_pending = False

    def _live(self, lease: AccessSession) -> bool:
        instant, elapsed = self.clock(), self.monotonic() - lease.issued_monotonic
        return (
            lease.state is SessionState.ACTIVE
            and lease.issued_at <= instant < lease.expires_at
            and 0 <= elapsed < (lease.expires_at - lease.issued_at).total_seconds()
        )

    def _validate(self, lease: AccessSession) -> None:
        if (
            self._closed
            or lease.binding != self.identity.binding
            or lease.runtime_boot_id != self.identity.runtime_boot_id
            or not self._live(lease)
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        validate_automation_profile_binding(self.identity.binding, root=self.root)

    def install(self, lease: AccessSession, dek: bytearray) -> None:
        """Copy authenticated material from the verified runtime's borrowed buffer."""
        with self._lock:
            self.expire()
            self._validate(lease)
            validate_automation_profile_binding(self.identity.binding, root=self.root, dek=bytes(dek))
            if lease.session_id in self._leases or lease.parent_session_id is not None:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._replace_key_session({**self._leases, lease.session_id: lease}, bytes(dek))

    def share(self, lease: AccessSession) -> None:
        """Attach a runtime-authorized child without extending its parent custody."""
        with self._lock:
            if lease.parent_session_id is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            parent = self.require(lease.parent_session_id)
            self._validate(lease)
            if (
                lease.session_id in self._leases
                or lease.expires_at > parent.expires_at
                or lease.scope != intersect_scopes((lease.scope, parent.scope))
                or lease.profile_lock_generation != parent.profile_lock_generation
                or lease.originating_login_id != parent.originating_login_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._leases[lease.session_id] = lease

    def refresh(self, lease: AccessSession) -> None:
        """Replace only a live root API deadline after runtime reauthorization."""
        with self._lock:
            previous = self.require(lease.session_id)
            self._validate(lease)
            if lease.kind is not SessionKind.API_KEY or lease.parent_session_id is not None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            mutable = {"issued_at", "issued_monotonic", "expires_at"}
            if any(
                getattr(previous, field) != getattr(lease, field)
                for field in AccessSession.model_fields
                if field not in mutable
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            session = current_active_bucket_session()
            if session is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            material = session.dek
            self._replace_key_session({**self._leases, lease.session_id: lease}, material)

    def require(self, session_id: UUID) -> AccessSession:
        """Revalidate exact custody and local lease lifetime before worker access."""
        with self._lock:
            self.expire()
            lease = self._leases.get(session_id)
            if lease is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            self._validate(lease)
            return lease

    @contextmanager
    def section(self, session_id: UUID) -> Generator[None]:
        """Keep physical material stable inside an independently authorized boundary.

        The runtime's native permit must already be held. This borrow neither
        extends a lease nor authorizes new work; the runtime contains the worker
        if the permit expires before release. Retirements remove logical access
        immediately and defer physical replacement until the last body settles.
        """
        with self._lock:
            self.require(session_id)
            self._sections += 1
        try:
            yield
        finally:
            with self._lock:
                self._sections -= 1
                if not self._sections:
                    self.expire()
                    if self._material_update_pending:
                        self._material_update_pending = False
                        if not self._leases:
                            self._release_material()
                        else:
                            session = current_active_bucket_session()
                            if session is None:
                                self.close()
                                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                            self._replace_key_session(self._leases.copy(), session.dek)

    def expire(self) -> None:
        """Release expired custody during idle polling as well as before requests."""
        with self._lock:
            if self._leases:
                try:
                    validate_automation_profile_binding(self.identity.binding, root=self.root)
                except BaseException:
                    self.close()
                    raise
            for identity in tuple(self._leases):
                if identity in self._leases and not self._live(self._leases[identity]):
                    self.retire(identity)

    def retire(self, session_id: UUID) -> None:
        """Drop one lineage; the process remains pinned after its last lease ends."""
        with self._lock:
            pending = {session_id}
            while pending:
                retired = pending
                pending = {lease.session_id for lease in self._leases.values() if lease.parent_session_id in retired}
                for identity in retired:
                    self._leases.pop(identity, None)
            if not self._leases:
                self._release_material()
            else:
                session = current_active_bucket_session()
                if session is None:
                    self.close()
                    raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                self._replace_key_session(self._leases.copy(), session.dek)

    def _replace_key_session(self, leases: dict[UUID, AccessSession], dek: bytes) -> None:
        if not leases:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if self._sections:
            self._leases = leases
            self._material_update_pending = True
            return
        opened = min(lease.issued_at for lease in leases.values())
        deadline = max(lease.expires_at for lease in leases.values())
        successor = BucketSession.open_resumed(
            bucket_id=str(self.identity.binding.profile_id),
            dek=dek,
            idle_minutes=5,
            opened_at=opened,
            idle_deadline=deadline,
            absolute_deadline=deadline,
            storage_root=self.root,
        )
        previous = current_active_bucket_session()
        try:
            bind_active_bucket_session(successor)
            if previous is not None:
                previous.close()
            self._leases = leases
        except BaseException:
            successor.close()
            self.close()
            raise

    def live_sessions(self) -> tuple[UUID, ...]:
        """Observe only revalidated lease identifiers, never key material."""
        with self._lock:
            self.expire()
            return tuple(sorted(self._leases))

    def close(self) -> None:
        """Fence further installation and release all process custody."""
        with self._lock:
            self._closed = True
            self._leases.clear()
            self._release_material()

    def _release_material(self) -> None:
        if self._sections:
            self._material_update_pending = True
            return
        try:
            close_active_profile_record_session()
        finally:
            close_active_bucket_session()
