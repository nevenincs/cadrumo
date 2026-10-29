"""Profile-fixed custody lending for runtime-issued access leases."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from types import TracebackType
from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from .....application.user_profile.access_contracts import AccessSession, SessionKind, SessionState
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....application.user_profile.access_policy import intersect_scopes
from .....application.user_profile.profile_record_repository import close_active_profile_record_session
from .....core.async_cleanup import await_cancellation_complete
from .....core.diagnostic_log import diagnostic_phase
from .....core.logging import get_logger
from .....core.storage_taxonomy import StorageCategory
from .....core.time.clock import now
from .....core.time.utc import UtcInstant
from ..custody.automation_profile import validate_automation_profile_binding
from ..custody.change_witness import CustodyChangeWitness, WatchedDirectory
from ..custody.paths import profile_custody_path
from .active_session import bind_active_bucket_session, current_active_bucket_session, seal_active_bucket_session
from .bucket_session import KEY_RELEASE_PHASE_EVENT, BucketSession
from .profile_worker_binding import profile_worker_binding
from .timed_lock import TimedRLock

_log = get_logger(__name__)

_ENDED_MEMORY = 256
"""How many ended lease ids custody remembers, so a late request hears how its session ended."""

_PROOF_ATTEMPTS = 3
"""How many capsule reads one check takes while each failed read is overtaken by a section entry or a close."""


@dataclass(frozen=True, slots=True)
class _CapsuleProof:
    """One read of the committed capsule, taken outside the custody lock, and the custody epoch it began in.

    ``current`` is false only for a failure that a section entry or a close
    overtook on every attempt: it still refuses its caller, but it never
    closes custody.
    """

    epoch: int
    binding_error: BaseException | None = None
    material_error: BaseException | None = None
    current: bool = True

    @property
    def failed(self) -> bool:
        return self.binding_error is not None or self.material_error is not None

    def refuse_failure(self) -> None:
        for error in (self.binding_error, self.material_error):
            if error is not None:
                raise error


def _session_matches(previous: BucketSession | None, opened: datetime, deadline: datetime, dek: bytes) -> bool:
    return (
        previous is not None
        and not previous.sealed
        and previous.opened_at == opened
        and previous.idle_deadline == previous.absolute_deadline == deadline
        and previous.dek == dek
    )


class ProfileWorkerCustodySection:
    """One entered custody section, left exactly once by :meth:`close` or by leaving its ``with`` block."""

    def __init__(self, leave: Callable[[], None]) -> None:
        """Hold the owner's exit; the section is open until it is closed."""
        self._leave: Callable[[], None] | None = leave
        self._guard = Lock()

    def close(self) -> None:
        """Leave the section; the last one to leave applies any physical change deferred meanwhile."""
        with self._guard:
            leave, self._leave = self._leave, None
        if leave is not None:
            leave()

    def __enter__(self) -> ProfileWorkerCustodySection:
        """Use the already entered section as a context."""
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Leave the section with its body."""
        self.close()


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
        self._hold_nothing(identity, storage_root=storage_root, clock=clock, monotonic=monotonic)

    def _hold_nothing(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        clock: Callable[[], UtcInstant],
        monotonic: Callable[[], float],
    ) -> None:
        """Start with no lease or material, watching the committed capsule this binding names."""
        self.identity, self.root, self.clock, self.monotonic = identity, storage_root, clock, monotonic
        self._leases: dict[UUID, AccessSession] = {}
        self._ended: dict[UUID, AccessDenialCode] = {}
        self._lock = TimedRLock()
        # Sessions sealed under the lock whose engine pools close once the
        # outermost holder leaves it. Their keys are already zeroised.
        self._sealed: list[BucketSession] = []
        self._sealed_guard = Lock()
        self._closed = False
        self._sections = 0
        # Moves at every section entry and at close. A failed capsule read that
        # began in an older epoch may have seen a publication inside a section.
        self._epoch = 0
        self._material_update_pending = False
        profile_id = identity.binding.profile_id
        # Every guard proves the committed capsule still names this binding; the proof is kept until the capsule moves.
        self._capsule: CustodyChangeWitness[None] = CustodyChangeWitness(
            (
                WatchedDirectory(
                    profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=storage_root).parent,
                    subtree=False,
                ),
                WatchedDirectory(
                    profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_CUSTODY, root=storage_root),
                    subtree=True,
                ),
                WatchedDirectory(
                    profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_DATA, root=storage_root),
                    subtree=True,
                ),
            )
        )

    @contextmanager
    def _held(self, call_name: str) -> Generator[None]:
        """Hold the custody lock, then close the engines of sessions sealed meanwhile once it is left.

        Sealing zeroises the key and unbinds the session under the lock, so
        nothing can use the material after the holder's call answers. Closing
        the last connection to the profile's WAL database checkpoints and
        fsyncs it; that waits on the disk, so it runs after the outermost
        holder leaves, before the call returns, and no other custody request
        waits for it.
        """
        try:
            with self._lock.held(call_name):
                yield
        finally:
            if not self._lock.owned():
                self._dispose_sealed()

    def _dispose_sealed(self) -> None:
        with self._sealed_guard:
            sealed, self._sealed = self._sealed, []
        for session in sealed:
            session.dispose_engines()

    def _seal(self, session: BucketSession) -> None:
        """Seal ``session`` under the custody lock and leave its engines for :meth:`_held` to dispose."""
        with self._sealed_guard:
            self._sealed.append(session)
        session.seal()

    def _live(self, lease: AccessSession) -> bool:
        instant, elapsed = self.clock(), self.monotonic() - lease.issued_monotonic
        return (
            lease.state is SessionState.ACTIVE
            and lease.issued_at <= instant < lease.expires_at
            and 0 <= elapsed < (lease.expires_at - lease.issued_at).total_seconds()
        )

    def _validate_lease(self, lease: AccessSession) -> None:
        if (
            self._closed
            or lease.binding != self.identity.binding
            or lease.runtime_boot_id != self.identity.runtime_boot_id
            or not self._live(lease)
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _prove(self, dek: bytes | None = None) -> _CapsuleProof:
        """Read whether the committed capsule still names this binding, and opens with ``dek`` when given.

        Runs without the custody lock: the read can wait on the file system,
        and every control and operation request waits for that lock.
        """
        epoch = self._epoch
        try:
            self._capsule.observe(lambda: validate_automation_profile_binding(self.identity.binding, root=self.root))
        except BaseException as error:
            return _CapsuleProof(epoch, binding_error=error)
        if dek is None:
            return _CapsuleProof(epoch)
        try:
            validate_automation_profile_binding(self.identity.binding, root=self.root, dek=dek)
        except BaseException as error:
            return _CapsuleProof(epoch, material_error=error)
        return _CapsuleProof(epoch)

    def _checked[T](
        self,
        call_name: str,
        needed: Callable[[], bool],
        commit: Callable[[_CapsuleProof | None], T],
        *,
        dek: bytes | None = None,
    ) -> T:
        """Commit under the custody lock on a capsule proof read before taking it.

        ``needed`` and ``commit`` run under the lock. A successful read stays
        a proof whatever happens meanwhile, since the lease checks under the
        lock still see a close. A failed read that a section entry or a close
        overtook is read again, because a publication inside that section may
        have failed it.
        """
        with self._held(call_name):
            if not needed():
                return commit(None)
        attempts = 1
        while True:
            proof = self._prove(dek)
            with self._held(call_name):
                current = not proof.failed or proof.epoch == self._epoch
                if current or attempts == _PROOF_ATTEMPTS:
                    return commit(replace(proof, current=current))
            attempts += 1

    def _binding_due(self) -> bool:
        # A publication may replace its own envelope inside a held native
        # fence. Revalidate at the last section exit; each new require still
        # validates independently, so this cannot admit successor work.
        return bool(self._leases) and not self._sections

    def _has_leases(self) -> bool:
        return bool(self._leases)

    def install(self, lease: AccessSession, dek: bytearray) -> None:
        """Copy authenticated material from the verified runtime's borrowed buffer."""
        material = bytes(dek)
        self._checked("install", lambda: True, lambda proof: self._install_locked(lease, material, proof), dek=material)

    def _install_locked(self, lease: AccessSession, material: bytes, proof: _CapsuleProof | None) -> None:
        self._settle(proof)
        self._validate_lease(lease)
        if proof is not None:
            proof.refuse_failure()
        if lease.session_id in self._leases or lease.parent_session_id is not None:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        self._replace_key_session({**self._leases, lease.session_id: lease}, material)

    def share(self, lease: AccessSession) -> None:
        """Attach a runtime-authorized child without extending its parent custody."""
        self._checked("share", self._has_leases, lambda proof: self._share_locked(lease, proof))

    def _share_locked(self, lease: AccessSession, proof: _CapsuleProof | None) -> None:
        if lease.parent_session_id is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        parent = self._require_locked(lease.parent_session_id, proof)
        self._validate_lease(lease)
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
        """Replace only a live root human or API deadline after runtime reauthorization."""
        self._checked("refresh", self._has_leases, lambda proof: self._refresh_locked(lease, proof))

    def _refresh_locked(self, lease: AccessSession, proof: _CapsuleProof | None) -> None:
        previous = self._require_locked(lease.session_id, proof)
        self._validate_lease(lease)
        if lease.kind not in {SessionKind.HUMAN, SessionKind.API_KEY} or lease.parent_session_id is not None:
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
        return self._checked("require", self._has_leases, lambda proof: self._require_locked(session_id, proof))

    async def require_off_loop(self, session_id: UUID) -> AccessSession:
        """Run :meth:`require` on a worker thread, so an event loop never waits for the custody lock."""
        return await await_cancellation_complete(
            asyncio.to_thread(self.require, session_id), task_name="profile-custody-require"
        )

    def _require_locked(self, session_id: UUID, proof: _CapsuleProof | None) -> AccessSession:
        self._settle(proof)
        lease = self._leases.get(session_id)
        if lease is None:
            ended = self._ended.get(session_id)
            if ended is not None:
                # The session ended, by its lifetime or by a retirement such as a sign-out:
                # nothing presented was wrong, and only a lapse is reported as expiry.
                raise ProfileAccessRefusedError(ended)
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        self._validate_lease(lease)
        if proof is not None and proof.binding_error is not None:
            raise proof.binding_error
        return lease

    def section(self, session_id: UUID) -> ProfileWorkerCustodySection:
        """Keep physical material stable inside an independently authorized boundary until the section closes.

        The runtime's native permit must already be held. This borrow neither
        extends a lease nor authorizes new work; the runtime contains the worker
        if the permit expires before release. Retirements remove logical access
        immediately and defer physical replacement until the last body settles.
        The custody lock is held only while entering and while leaving.
        """
        return self._checked("section", self._has_leases, lambda proof: self._enter_section_locked(session_id, proof))

    @asynccontextmanager
    async def section_off_loop(self, session_id: UUID) -> AsyncGenerator[None]:
        """Hold a section across an asynchronous body, entering and leaving it on worker threads.

        No thread holds the custody lock across the body. A section that a
        cancelled entry still opened is left before the cancellation propagates.
        """
        entered: list[ProfileWorkerCustodySection] = []

        def enter() -> None:
            entered.append(self.section(session_id))

        try:
            await await_cancellation_complete(asyncio.to_thread(enter), task_name="profile-custody-section-enter")
            yield
        finally:
            for section in entered:
                await await_cancellation_complete(
                    asyncio.to_thread(section.close), task_name="profile-custody-section-exit"
                )

    def _enter_section_locked(self, session_id: UUID, proof: _CapsuleProof | None) -> ProfileWorkerCustodySection:
        self._require_locked(session_id, proof)
        self._sections += 1
        self._epoch += 1
        return ProfileWorkerCustodySection(self._leave_section)

    def _leave_section(self) -> None:
        with self._held("section_exit"):
            self._sections -= 1
            if self._sections:
                return
        self._checked("section_exit", self._binding_due, self._settle_sections)

    def _settle_sections(self, proof: _CapsuleProof | None) -> None:
        if self._sections:
            # A body entered after the last one left; its own exit settles.
            return
        self._settle(proof)
        if self._material_update_pending:
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
        self._checked("expire", self._binding_due, self._settle)

    def _settle(self, proof: _CapsuleProof | None) -> None:
        """Close custody on a current failed proof while one is due, then retire every lapsed lease.

        Runs under the custody lock. Every request, idle poll and final section
        exit proves the capsule again, from memory while it is unchanged.
        """
        if proof is not None and proof.binding_error is not None and proof.current and self._binding_due():
            self.close()
            raise proof.binding_error
        for identity in tuple(self._leases):
            if identity in self._leases and not self._live(self._leases[identity]):
                for lapsed in self.retire(identity):
                    self._ended[lapsed] = AccessDenialCode.SESSION_EXPIRED

    def retire(self, session_id: UUID) -> frozenset[UUID]:
        """Drop one lineage and name the leases it held; the process remains pinned after its last lease ends."""
        with self._held("retire"):
            dropped: set[UUID] = set()
            pending = {session_id}
            while pending:
                retired = pending
                pending = {lease.session_id for lease in self._leases.values() if lease.parent_session_id in retired}
                for identity in retired:
                    if self._leases.pop(identity, None) is not None:
                        dropped.add(identity)
                        # As the runtime's authority answers for a session it no longer holds.
                        self._ended[identity] = AccessDenialCode.AUTHENTICATION_REQUIRED
            while len(self._ended) > _ENDED_MEMORY:
                del self._ended[next(iter(self._ended))]
            if not dropped:
                # The worker's expiry sweep may already have retired this id.
                # Acknowledging the runtime's matching retirement is idempotent.
                return frozenset(dropped)
            if not self._leases:
                self._release_material()
            else:
                session = current_active_bucket_session()
                if session is None:
                    self.close()
                    raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                self._replace_key_session(self._leases.copy(), session.dek)
            return frozenset(dropped)

    def _replace_key_session(self, leases: dict[UUID, AccessSession], dek: bytes) -> None:
        if not leases:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if self._sections:
            self._leases = leases
            self._material_update_pending = True
            return
        opened = min(lease.issued_at for lease in leases.values())
        deadline = max(lease.expires_at for lease in leases.values())
        previous = current_active_bucket_session()
        if _session_matches(previous, opened, deadline, dek):
            # A child lapse does not change its parent's storage lifetime.
            # Keep the live engine and key session instead of disposing them
            # at every attended lease boundary.
            self._leases = leases
            self._material_update_pending = False
            return
        # Each request is admitted against its own lease, so a key session that
        # went idle sooner would refuse work a live lease still admits. A window
        # no shorter than the whole lease span clamps every storage access to
        # the latest lease expiry, which stays the only bound on this session.
        whole_minutes, remainder = divmod(deadline - opened, timedelta(minutes=1))
        successor = BucketSession.open_resumed(
            bucket_id=str(self.identity.binding.profile_id),
            dek=dek,
            idle_minutes=max(1, whole_minutes + (1 if remainder else 0)),
            opened_at=opened,
            idle_deadline=deadline,
            absolute_deadline=deadline,
            storage_root=self.root,
        )
        try:
            bind_active_bucket_session(successor)
            if previous is not None:
                self._seal(previous)
            self._leases = leases
            self._material_update_pending = False
        except BaseException:
            self._seal(successor)
            self.close()
            raise

    def live_sessions(self) -> tuple[UUID, ...]:
        """Observe only revalidated lease identifiers, never key material."""
        return self._checked("live_sessions", self._binding_due, self._live_sessions_locked)

    def _live_sessions_locked(self, proof: _CapsuleProof | None) -> tuple[UUID, ...]:
        self._settle(proof)
        return tuple(sorted(self._leases))

    def seconds_until_expiry(self) -> float | None:
        """Seconds until the earliest held lease lapses on either clock, or ``None`` while none is held."""
        with self._held("seconds_until_expiry"):
            instant, elapsed = self.clock(), self.monotonic()
            remaining = [
                min(
                    (lease.expires_at - instant).total_seconds(),
                    lease.issued_monotonic + (lease.expires_at - lease.issued_at).total_seconds() - elapsed,
                )
                for lease in self._leases.values()
            ]
        return max(0.0, min(remaining)) if remaining else None

    def retire_password_successor(self, *, password_generation: int) -> None:
        """Retire old leases after verifying one committed, same-key successor.

        The operation owner must retain its native COMMIT fence and persist any
        encrypted outcome before calling this door. This grants no successor
        authority: the worker remains permanently bound to its old identity.
        Physical material survives only until its already-held sections exit.
        The successor is proved without the custody lock; the caller's own
        section keeps the material it was proved with in place meanwhile.
        """
        with self._held("retire_password_successor"):
            self._require_password_successor(password_generation)
            session = current_active_bucket_session()
            if session is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            dek = session.dek
        successor = self.identity.binding.model_copy(update={"custody_generation": password_generation})
        validate_automation_profile_binding(successor, root=self.root, dek=dek)
        with self._held("retire_password_successor"):
            self._require_password_successor(password_generation)
            # Clear logical authority before the generic section cleanup. Its
            # old-binding validation must not misreport this proven transition
            # as a failed operation after the password was already replaced.
            self.close()

    def _require_password_successor(self, password_generation: int) -> None:
        if (
            self._closed
            or not self._sections
            or not self._leases
            or password_generation != self.identity.binding.custody_generation + 1
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)

    def close(self) -> None:
        """Fence further installation and release all process custody."""
        with self._held("close"):
            self._closed = True
            self._epoch += 1
            self._leases.clear()
            self._capsule.close()
            self._release_material()

    def _release_material(self) -> None:
        if self._sections:
            self._material_update_pending = True
            return
        self._material_update_pending = False
        try:
            with diagnostic_phase(_log, KEY_RELEASE_PHASE_EVENT, "record_authority_zeroise"):
                close_active_profile_record_session()
        finally:
            with diagnostic_phase(_log, KEY_RELEASE_PHASE_EVENT, "bucket_session_seal"):
                session = seal_active_bucket_session()
                if session is not None:
                    with self._sealed_guard:
                        self._sealed.append(session)
