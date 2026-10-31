"""Compose exact-profile session authority, committed custody and installed workers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Final
from uuid import UUID, uuid4

from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import (
    ReceiptDeletion,
    inspect_profile_session,
    revoke_profile_sign_in,
)
from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.automation_profile import CommittedProfileBindingWatch
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGeneration, SignInGenerationCustody
from cadrumo.adapters.persistence.storage.errors import StorageError
from cadrumo.adapters.persistence.storage.master_key.timed_lock import TimedRLock
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID
from cadrumo.application.operations.models import OperationId, OperationIdentity
from cadrumo.application.operations.registry import (
    OperationRegistry,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessEvaluationContext,
    AccessSession,
    OsLockState,
    ProfileAccessState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_administration import (
    inspect_automation_inventory,
)
from cadrumo.application.user_profile.automation_administration_service import AutomationAdministrationService
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentRequester,
    EnrollmentTransition,
    ProtectedEnrollmentRecipient,
)
from cadrumo.application.user_profile.automation_lifecycle import ProfileGlobalLockState
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
)
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.session_retirement import SessionRetirement, SessionRetirementKind
from cadrumo.core.operations import profile_operation_subject
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode, OperationResponseScopeAllowed
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    Availability,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalError, ShutdownIncompleteError
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.model_runs import ModelRunOutcome, ModelRunRefusalCode
from cadrumo_client.contracts.profile_access import HumanProof
from cadrumo_client.contracts.session_events import SessionEvent
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerModelRun,
    WorkerResponseScopeRequest,
)
from cadrumo_runtime.contracts.worker_enrollment import (
    WorkerApprovalPublication,
    WorkerApprovalPublicationPhase,
    WorkerApprovalRequest,
)

from ..application.approval_binding import RuntimeApprovalBinding
from ..application.approval_sessions import RuntimeApprovalSessions
from ..application.session_authority import ProfileSessionAuthority
from ..application.session_authority_contracts import SessionAuthorityFacts
from ..application.session_authority_core import CustodyRecoveryPolicy
from .automation_owner import RuntimeAutomationAdministrationOwner, RuntimeAutomationInventoryOwner
from .profile_connection import ProfileConnection
from .profile_lock_observation import locked_login_ids
from .profile_scope import delegated_profile_scope, person_profile_scope
from .session_owner import ProfileWorkerSessionOwner

_GUARD_SLOW_SECONDS: Final = 1.0
"""A wait for, or a hold of, the profile guard this long is reported with the code that entered it."""


class RuntimeProfileHost:
    """One profile's shared admission guard, independent leases and immutable worker."""

    def __init__(
        self,
        *,
        store: AutomationControlStore,
        runtime_boot_id: UUID,
        registry: OperationRegistry,
        connected: Callable[[UUID], ProfileConnection],
        logins: Callable[[], tuple[LoginEvidence, ...]],
        admitting: Callable[[], bool],
        recipient: Callable[[EnrollmentRequester], ProtectedEnrollmentRecipient] | None = None,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
        retired: Callable[[SessionEvent], None] | None = None,
        operations_advanced: Callable[[tuple[OperationId, ...], bool], None] | None = None,
        model_runs: Callable[[WorkerModelRun, bytearray], tuple[ModelRunOutcome, bytearray]] | None = None,
        suspended: Callable[[tuple[AccessSession, ...]], None] | None = None,
        rebound: Callable[[tuple[AccessSession, ...]], None] | None = None,
        recovery: CustodyRecoveryPolicy | None = None,
        worker_lost: Callable[[], None] | None = None,
    ) -> None:
        """Compose existing authorities without opening keys or selecting a profile.

        A positive worker loss suspends this profile's leases under a fresh
        worker owner; ``suspended`` and ``rebound`` hear which leases wait and
        which returned after a fresh proof. ``worker_lost`` hears a loss
        established outside any request, which a lifecycle pass then sweeps.
        """
        self.store, self._registry = store, registry
        self._contracts = registry.public_contract_set
        self._connected, self._logins, self._admitting = connected, logins, admitting
        self._recipient = recipient
        self._wall_clock = wall_clock
        self.guard = TimedRLock(slow_seconds=_GUARD_SLOW_SECONDS, event="profile_guard_slow")
        self._replacement_retirement_guard = Lock()
        self._committed_binding = CommittedProfileBindingWatch(
            profile_id=store.binding.profile_id,
            installation_id=store.binding.installation_id,
            os_owner_id=store.binding.os_owner_id,
            root=store.root,
        )
        self._lock_fence: ProfileGlobalLockState | None = None
        self._password_rotation: OperationIdentity | None = None
        self._locked_logins: set[str] = set()
        self._retired_event = retired
        self._operations_advanced = operations_advanced
        self._model_runs = model_runs
        self._sign_in_generation: SignInGeneration | None = None
        self.issuer = CustodyAutomationKeyIssuer()
        self._runtime_boot_id, self._worker_script = runtime_boot_id, worker_script
        self._worker_lost = worker_lost
        # Owners of lost workers, kept until their containment and callbacks settle.
        self._lost_owners: list[ProfileWorkerSessionOwner] = []
        self._owner = self._new_owner()
        self.authority = ProfileSessionAuthority(
            binding=store.binding,
            runtime_boot_id=runtime_boot_id,
            owner=self._owner,
            custody=store,
            issuer=self.issuer,
            retired=self._session_retired,
            replace_lost_owner=self._replace_lost_owner,
            suspended=suspended,
            rebound=rebound,
            recovery=recovery,
        )
        self.approvals = RuntimeApprovalSessions(worker=self._owner.identity, service=self._approval_service)

    @property
    def owner(self) -> ProfileWorkerSessionOwner:
        """The owner of this profile's current worker incarnation."""
        return self._owner

    def _new_owner(self) -> ProfileWorkerSessionOwner:
        return ProfileWorkerSessionOwner(
            ProfileWorkerIdentity(worker_id=uuid4(), runtime_boot_id=self._runtime_boot_id, binding=self.store.binding),
            storage_root=self.store.root,
            observe=self.facts,
            human_secret=self._human_proof,
            guard=self.guard,
            authorization=self,
            worker_script=self._worker_script,
            wall_clock=self._wall_clock,
            lost=self._worker_lost,
        )

    def _replace_lost_owner(self) -> ProfileWorkerSessionOwner:
        """Start a fresh, empty worker incarnation after a positive worker loss; the caller holds the guard.

        Approval proof of the lost worker is fenced: work in flight at the
        loss never resumes under the replacement.
        """
        self._lost_owners.append(self._owner)
        self._owner = self._new_owner()
        lost_approvals, self.approvals = (
            self.approvals,
            RuntimeApprovalSessions(worker=self._owner.identity, service=self._approval_service),
        )
        lost_approvals.close()
        return self._owner

    def settle_lost_owners(self, *, deadline: float) -> None:
        """Prove containment of lost worker incarnations; one that cannot settle yet is kept for a later pass."""
        with self.guard:
            lost = tuple(self._lost_owners)
        failures: list[Exception] = []
        for owner in lost:
            try:
                owner.settle(deadline=deadline)
            except Exception as error:
                failures.append(error)
            else:
                with self.guard:
                    self._lost_owners.remove(owner)
        if failures:
            raise ExceptionGroup("lost worker settlement failed", failures)

    def _session_retired(self, retirement: SessionRetirement) -> None:
        """Publish committed retirement metadata; the queue never performs transport I/O."""
        if self._retired_event is None:
            return
        generation = self._sign_in_generation
        self._retired_event(
            SessionEvent(
                runtime_boot_id=self.owner.identity.runtime_boot_id,
                connection_id=retirement.connection_id,
                profile_id=retirement.profile_id,
                session_id=retirement.session_id,
                event=retirement.kind,
                reason=retirement.reason,
                generation_lineage=None if generation is None else generation.lineage,
                generation=None if generation is None else generation.generation,
            )
        )

    def _require_approval_binding(self, binding: RuntimeApprovalBinding) -> None:
        if (
            binding.worker_id != self.owner.identity.worker_id
            or binding.runtime_boot_id != self.owner.identity.runtime_boot_id
            or binding.profile_binding != self.store.binding
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

    def _approval_service(self, binding: RuntimeApprovalBinding) -> AutomationAdministrationService:
        self._require_approval_binding(binding)
        return AutomationAdministrationService(
            custody=self.store,
            owner=RuntimeAutomationAdministrationOwner(
                self.authority, binding.connection_id, binding.session_id, self._approval_recipient, binding, self.store
            ),
            issuer=self.issuer,
            storage_root=self.store.root,
        )

    def _approval_recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        if self._recipient is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return self._recipient(requester)

    def operations_advanced(self, operation_ids: tuple[OperationId, ...], *, records_changed: bool = False) -> None:
        """Hand the worker's report of committed operations to whoever cues their observers."""
        if self._operations_advanced is not None:
            self._operations_advanced(operation_ids, records_changed)

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        """Validate the exact worker and current human before any password frame."""
        self._require_approval_binding(request.binding)
        if request.phase == "close":
            # Cleanup must remain available after session expiry or disconnect.
            return
        connection = self._connected(request.connection_id)
        if (
            connection.session_id != request.session_id
            or connection.profile_id != self.store.binding.profile_id
            or connection.frontend is not request.request.frontend
            or connection.client_id != request.request.destination_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        with self.authority.operation_guard(
            connection_id=request.connection_id,
            session_id=request.session_id,
            request=request.request,
            policy=request.policy,
            registry=self._registry,
        ):
            self.authority.human_administration_facts(
                connection_id=request.connection_id, session_id=request.session_id
            )

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        """Keep expensive proof and recipient exchange outside COMMIT authority."""
        self.approval_preflight(request)
        if (request.phase == "prepare") != (password is not None):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        if request.phase == "prepare":
            if password is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            # Native callback threads do not inherit the worker's context-local
            # application ports. Compose only exact password custody here;
            # this never opens an ambient profile session in the parent.
            with bind_profile_custody_port(build_profile_custody_port()):
                self.approvals.prepare(request.binding, password)
        elif request.phase == "inspect_recipient":
            return self.approvals.inspect_recipient(request.binding)
        elif request.phase == "deliver_and_verify":
            self.approvals.deliver_and_verify(request.binding)
        else:
            self.approvals.retire(request.binding)
        return None

    def model_run(
        self, authority: WorkerAuthorizationRequest, command: WorkerModelRun, body: bytearray
    ) -> tuple[ModelRunOutcome, bytearray]:
        """Relay one model run of this profile's worker to the profile's admitted agent service.

        The START permit it arrives under was authorized for this exact worker's
        profile, so only the profile is rechecked here.
        """
        if authority.request.profile_id != self.store.binding.profile_id or self._model_runs is None:
            body[:] = bytes(len(body))
            return ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE), bytearray()
        return self._model_runs(command, body)

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        """Publish on the existing fence thread, retaining exact invocation identity."""
        binding = command.binding
        self._require_approval_publication_authority(authority, binding, command.phase)
        # Reentrant only on the native thread already holding the same guard.
        with self.authorize(authority):
            return self._apply_approval_publication(binding, command)

    def _require_approval_publication_authority(
        self,
        authority: WorkerAuthorizationRequest,
        binding: RuntimeApprovalBinding,
        phase: WorkerApprovalPublicationPhase,
    ) -> None:
        self._require_approval_binding(binding)
        expected = (
            AUTOMATION_DECLINE_OPERATION_DEFINITION_ID
            if phase == "decline"
            else AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
        )
        if (
            authority.connection_id != binding.connection_id
            or authority.session_id != binding.session_id
            or authority.operation_id != binding.operation_id
            or authority.request.action is not AccessAction.COMMIT
            or authority.request.definition_id != expected
            or not authority.policy.requires_human
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

    def _apply_approval_publication(
        self, binding: RuntimeApprovalBinding, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        if command.phase == "decline":
            return self._approval_service(binding).decline(
                binding.enrollment_request_id, review_digest=binding.review_digest
            )
        if command.phase == "commit_review":
            return self.approvals.commit_review(binding)
        if command.phase == "publish_candidate":
            return self.approvals.publish_candidate(binding)
        return self.approvals.activate(binding)

    @contextmanager
    def authorize(self, request: WorkerAuthorityRequest) -> Generator[AccessAllowed | OperationResponseScopeAllowed]:
        """Retain fresh profile authority for a kernel-verified owned worker."""
        guard = (
            self.authority.response_scope_guard
            if isinstance(request, WorkerResponseScopeRequest)
            else self.authority.operation_guard
        )
        with guard(
            connection_id=request.connection_id,
            session_id=request.session_id,
            request=request.request,
            policy=request.policy,
            registry=self._registry,
        ) as allowed:
            if (
                isinstance(request, WorkerAuthorizationRequest)
                and request.request.definition_id == PROFILE_ROTATION_OPERATION_DEFINITION_ID
                and request.request.action is AccessAction.COMMIT
            ):
                self._password_rotation = OperationIdentity(
                    operation_id=request.operation_id,
                    definition_id=request.request.definition_id,
                    subject_ref=profile_operation_subject(str(self.store.binding.profile_id)),
                )
            yield allowed

    @contextmanager
    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> Generator[WorkerAutomationInventoryAllowed]:
        """Read protected control state for the exact human-owned worker invocation."""
        connection = self._connected(request.connection_id)
        if (
            connection.session_id != request.session_id
            or connection.profile_id != self.store.binding.profile_id
            or request.request.frontend is not connection.frontend
            or request.request.destination_id != connection.client_id
            or not request.policy.requires_human
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        with self.authority.operation_guard(
            connection_id=request.connection_id,
            session_id=request.session_id,
            request=request.request,
            policy=request.policy,
            registry=self._registry,
        ) as allowed:
            inventory = inspect_automation_inventory(
                custody=self.store,
                owner=RuntimeAutomationInventoryOwner(self.authority, request.connection_id, request.session_id),
            )
            yield WorkerAutomationInventoryAllowed(expires_at=allowed.expires_at, inventory=inventory)

    def scope(self, connection: ProfileConnection) -> AccessScope:
        """Derive the owner ceiling from the current canonical operation contracts."""
        cached = connection.owner_scope
        if (
            connection.method != "api_key"
            and cached is not None
            and cached[0] is self._contracts
            and cached[1] == connection.client_id
        ):
            # Only the immutable owner ceiling is reusable. facts() still reads
            # current locks, custody, logins and availability at every boundary;
            # delegated scopes always reread their live grants below.
            return cached[2]
        if connection.method == "api_key":
            scope = delegated_profile_scope(self._contracts, self.store.snapshot(), connection.client_id)
        else:
            scope = person_profile_scope(self._contracts, connection.client_id)
        if connection.method != "api_key":
            connection.owner_scope = (self._contracts, connection.client_id, scope)
        return scope

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Observe committed profile fencing and native dependencies as their OS-invalidated observations stand."""
        connection = self._connected(connection_id)
        if connection.disconnecting:
            raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        if connection.profile_id != self.store.binding.profile_id:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        available, enabled = Availability.UNAVAILABLE, False
        try:
            committed, snapshot = self.store.observed_access_state()
            available, enabled = Availability.AVAILABLE, snapshot.automation_enabled
        except AutomationCustodyError:
            # Read apart, as before observation: the lock still refuses, and
            # password admission remains independent of the optional subsystem.
            committed = self.store.profile_lock_state()
            try:
                enabled = self.store.enrollment_state().automation_enabled
                available = Availability.AVAILABLE
            except AutomationCustodyError:
                if connection.method == "api_key":
                    raise
        lock = self._fenced(committed)
        scope = self.scope(connection)
        logins = self._logins()
        return SessionAuthorityFacts(
            ProfileAccessState(
                binding=self.store.binding,
                lock_generation=lock.generation,
                globally_locked=lock.globally_locked,
                automation_enabled=enabled,
                scope=scope,
                storage=Availability.AVAILABLE,
                automation_custody=available,
            ),
            AccessEvaluationContext(
                now=self._wall_clock(),
                monotonic_now=time.monotonic(),
                clock_rollback_detected=False,
                runtime_boot_id=connection.context.runtime_boot_id,
                connection_id=connection_id,
                authenticated_client_id=connection.client_id,
                login_contexts=tuple(login.observe(credential_facilities=available) for login in logins),
                private_work_available=self._admitting(),
            ),
        )

    def profile_lock_state(self) -> ProfileGlobalLockState:
        """Retain a denial fence even if durable publication fails after live retirement."""
        with self.guard:
            return self._fenced(self.store.profile_lock_state())

    def _fenced(self, current: ProfileGlobalLockState) -> ProfileGlobalLockState:
        with self.guard:
            fence = self._lock_fence
            if fence is not None and fence.generation >= current.generation and fence.globally_locked:
                return fence
            return current

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        """Apply only the current lifecycle service's denial or proven durable unlock."""
        with self.guard:
            current = self.profile_lock_state()
            if locked:
                if generation != current.generation + 1:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                self._lock_fence = ProfileGlobalLockState(
                    binding=self.store.binding, generation=generation, globally_locked=True
                )
                self.revoke_human_sign_in(
                    reason=AccessDenialCode.PROFILE_LOCKED, kind=SessionRetirementKind.PROFILE_LOCKED
                )
            else:
                committed = self.store.profile_lock_state()
                if committed.generation != generation or committed.globally_locked or generation < current.generation:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                self._lock_fence = None

    def revoke_human_sign_in(
        self,
        *,
        reason: AccessDenialCode = AccessDenialCode.AUTHENTICATION_REQUIRED,
        kind: SessionRetirementKind = SessionRetirementKind.SIGNED_OUT,
    ) -> tuple[ReceiptDeletion, tuple[UUID, ...]]:
        """Commit the durable fence before receipt deletion and live human retirement."""
        with self.guard:
            custody = SignInGenerationCustody(root=self.store.root, binding=self.store.binding)
            deletion = revoke_profile_sign_in(custody)
            self._sign_in_generation = custody.observe().current
            try:
                return deletion, self.authority.retire_human_sessions(reason=reason, kind=kind)
            finally:
                self._sign_in_generation = None

    def observe_human_lock_down(self) -> tuple[UUID, ...]:
        """Revoke on newly positive lock/logout evidence; unknown preserves the receipt."""
        with self.guard:
            observed = tuple(login.observe(credential_facilities=Availability.UNAVAILABLE) for login in self._logins())
            relevant = self.authority.human_login_ids()
            try:
                receipt = inspect_profile_session(
                    storage_root=self.store.root, profile_id=self.store.binding.profile_id
                )
            except (OSError, ValueError, StorageError, ProfileCustodyRecordError):
                receipt = None
            positive = locked_login_ids(observed, relevant, self.store.binding.os_owner_id, receipt)
            unlocked = {login.login_id for login in observed if login.active and login.unlocked}
            self._locked_logins.difference_update(unlocked)
            if positive <= self._locked_logins:
                return ()
            reason = (
                AccessDenialCode.OS_LOCKED
                if any(login.login_id in positive and login.lock_state is OsLockState.LOCKED for login in observed)
                else AccessDenialCode.OS_SESSION_UNAVAILABLE
            )
            _, retired = self.revoke_human_sign_in(reason=reason, kind=SessionRetirementKind.REVOKED)
            self._locked_logins.update(positive)
            return retired

    @contextmanager
    def _human_proof(self, connection_id: UUID) -> Generator[HumanProof]:
        connection = self._connected(connection_id)
        if connection.method not in {"password", "receipt"} or connection.human_secret is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        yield HumanProof(
            method="password" if connection.method == "password" else "receipt",
            secret=connection.human_secret,
            originating_login_id=connection.login.login_id,
            persist_receipt=connection.persist_human_receipt,
            timeout_deadline=connection.human_admission_deadline,
            attempt_id=connection.human_proof_attempt_id,
            cancellation=connection.human_proof_cancellation,
        )

    def close(self) -> None:
        """Contain the owned process, then retire in-memory authority and callbacks."""
        self.approvals.close()
        try:
            self.owner.close()
        finally:
            try:
                asyncio.run(self.authority.close())
            finally:
                try:
                    self.owner.settle()
                    for lost in tuple(self._lost_owners):
                        lost.settle()
                        self._lost_owners.remove(lost)
                finally:
                    self.approvals.close()
                    self.store.custody_witness.close()

    def lifecycle_due(self) -> float | None:
        """Return the monotonic instant this profile must be observed again even if nothing happens."""
        instants = (
            self.authority.revalidation_due(monotonic_now=time.monotonic(), wall_now=self._wall_clock()),
            self.approvals.next_expiry(),
        )
        return min((instant for instant in instants if instant is not None), default=None)

    def retire_replaced_binding(self, *, deadline: float) -> bool | None:
        """Drain an obsolete incarnation before permitting a fresh profile owner.

        The same guard protects commit bodies. Never interrupt an in-flight
        publication just because its envelope has already changed on disk.
        Once the body releases its guard, remove live admission first and let
        the canonical supervisor settle before containing the worker. Neither
        this retirement nor a drain receipt establishes a domain outcome.
        ``None`` means a held fence prevented this observation; polling must
        leave that invocation alone. An unreadable binding also retires access
        without claiming that a successor was committed.
        """
        # Only one caller may prove retirement. Another admission must not
        # mistake the denial fence for completed process containment.
        if not self._replacement_retirement_guard.acquire(blocking=False):
            return None
        try:
            if not self.guard.acquire(blocking=False):
                return None
            try:
                binding = self.store.binding
                try:
                    current = self._committed_binding.current()
                except AutomationCustodyError:
                    current = None
                if current == binding:
                    return False
                if current is not None:
                    # The mutation's commit guard has been released. Fence and
                    # clean the obsolete receipt against proven successor custody;
                    # an unreadable binding never authorizes destructive cleanup.
                    sign_in = SignInGenerationCustody(root=self.store.root, binding=current)
                    revoke_profile_sign_in(sign_in)
                    self._sign_in_generation = sign_in.observe().current
                worker = self.owner.begin_drain()
            finally:
                self.guard.release()
            # Worker callbacks may still need the profile guard to release their
            # exact permit. No host or connection lock is held while waiting here.
            self.approvals.close()
            if worker is not None:
                # An independently fenced or crashed worker may supply no receipt.
                # It still must pass the containment and callback checks below;
                # its persisted operations retain their reconciliation obligations.
                with suppress(RefusalError, AutomationCustodyError, ProfileAccessRefusedError):
                    try:
                        if current is not None and self._password_rotation is not None:
                            worker.settlement(
                                self._password_rotation, timeout=max(0.001, min(5.0, deadline - time.monotonic()))
                            )
                    finally:
                        worker.drain(deadline=deadline)
            if not self.owner.wait_construction(deadline=deadline):
                raise ShutdownIncompleteError()
            self.owner.settle(deadline=deadline)
            asyncio.run(self.authority.close(reason=AccessDenialCode.CUSTODY_CHANGED))
            return True
        finally:
            self._sign_in_generation = None
            self._replacement_retirement_guard.release()
