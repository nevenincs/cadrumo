"""Compose exact-profile session authority, committed custody and installed workers."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import override
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.automation_store import AutomationControlStore
from ...adapters.persistence.storage.profile_custody import build_profile_custody_port
from ...application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID
from ...application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.runtime.approval_binding import RuntimeApprovalBinding
from ...application.runtime.approval_sessions import RuntimeApprovalSessions
from ...application.runtime.contracts import RuntimeRefusalError, RuntimeShutdownIncompleteError
from ...application.runtime.login import RuntimeLoginEvidence
from ...application.runtime.profile_access import RuntimeHumanProof
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from ...application.runtime.worker_enrollment import (
    WorkerApprovalPublication,
    WorkerApprovalPublicationPhase,
    WorkerApprovalRequest,
)
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessEvaluationContext,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationResponseScopeAllowed,
    ProfileAccessState,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_administration import enrollment_review_digest, inspect_automation_inventory
from ...application.user_profile.automation_administration_service import AutomationAdministrationService
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import (
    AdministrationFacts,
    EnrollmentCustodyPort,
    EnrollmentRequester,
    EnrollmentTransition,
    ProtectedEnrollmentRecipient,
)
from ...application.user_profile.automation_lifecycle import ProfileGlobalLockState
from ...application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
)
from ...application.user_profile.custody_ports import bind_profile_custody_port
from ...application.user_profile.session_authority import ProfileSessionAuthority
from ...application.user_profile.session_authority_contracts import SessionAuthorityFacts
from ...core.operations import profile_operation_subject
from ...core.time.clock import now
from .session_owner import ProfileWorkerSessionOwner


@dataclass
class ProfileConnection:
    """Host-owned connection state, excluded from all wire and persisted documents."""

    context: RuntimeConnectionContext
    login: RuntimeLoginEvidence
    client_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    session_id: UUID | None = None
    method: str = "password"
    human_secret: bytearray | None = field(default=None, repr=False)
    persist_human_receipt: bool = False
    recovery_generation: int | None = None


@dataclass(frozen=True)
class RuntimeAutomationInventoryOwner:
    """A live authority binding supplied by the authenticated runtime callback."""

    authority: ProfileSessionAuthority
    connection_id: UUID
    session_id: UUID

    def facts(self) -> AdministrationFacts:
        """Reobserve this exact session and its originating native login."""
        return self.authority.human_administration_facts(connection_id=self.connection_id, session_id=self.session_id)

    @contextmanager
    def administration_guard(self) -> Generator[None]:
        """Share the same lifecycle fence as operation execution and disclosure."""
        with self.authority.owner.admission_guard():
            yield


@dataclass(frozen=True)
class RuntimeAutomationAdministrationOwner(RuntimeAutomationInventoryOwner):
    """Bind canonical approval to human facts and a separately owned recipient."""

    recipient_lookup: Callable[[EnrollmentRequester], ProtectedEnrollmentRecipient]
    approval_binding: RuntimeApprovalBinding
    custody: EnrollmentCustodyPort

    @override
    def facts(self) -> AdministrationFacts:
        """Apply the owner's delegation ceiling to this exact reviewed recipient.

        Ordinary human operation authority keeps its original destination. Only
        this request-bound administration view may delegate its registered
        projection permissions to the recipient whose consent digest was reviewed.
        No permission is copied from the proposal itself.
        """
        with self.administration_guard():
            current = super().facts()
            state = self.custody.enrollment_state()
            record = next(
                (item for item in state.requests if item.request_id == self.approval_binding.enrollment_request_id),
                None,
            )
            if (
                state.binding != self.approval_binding.profile_binding
                or record is None
                or record.binding != state.binding
                or not secrets.compare_digest(enrollment_review_digest(record), self.approval_binding.review_digest)
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            permissions = frozenset(
                permission.model_copy(update={"destination_id": record.requester.destination_id})
                for permission in current.profile.scope.disclosures
                if permission.destination_id == current.context.authenticated_client_id
            )
            scope = current.profile.scope.model_copy(update={"disclosures": permissions})
            return current.model_copy(update={"profile": current.profile.model_copy(update={"scope": scope})})

    def requester(self) -> EnrollmentRequester:
        """Derive requester coordinates from the original live human connection."""
        facts = self.facts()
        return EnrollmentRequester(
            runtime_boot_id=facts.context.runtime_boot_id,
            connection_id=self.connection_id,
            client_id=facts.context.authenticated_client_id,
            destination_id=facts.context.authenticated_client_id,
        )

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        """Resolve the exact original requesting client through protected transport."""
        return self.recipient_lookup(requester)


class RuntimeProfileHost:
    """One profile's shared admission guard, independent leases and immutable worker."""

    def __init__(
        self,
        *,
        store: AutomationControlStore,
        runtime_boot_id: UUID,
        registry: OperationRegistry,
        connected: Callable[[UUID], ProfileConnection],
        logins: Callable[[], tuple[RuntimeLoginEvidence, ...]],
        admitting: Callable[[], bool],
        recipient: Callable[[EnrollmentRequester], ProtectedEnrollmentRecipient] | None = None,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
    ) -> None:
        """Compose existing authorities without opening keys or selecting a profile."""
        self.store, self._registry = store, registry
        self._contracts = registry.public_contract_set
        self._connected, self._logins, self._admitting = connected, logins, admitting
        self._recipient = recipient
        self._wall_clock = wall_clock
        self.guard = RLock()
        self._lock_fence: ProfileGlobalLockState | None = None
        self._password_rotation: OperationIdentity | None = None
        self.issuer = CustodyAutomationKeyIssuer()
        self.owner = ProfileWorkerSessionOwner(
            ProfileWorkerIdentity(worker_id=uuid4(), runtime_boot_id=runtime_boot_id, binding=store.binding),
            storage_root=store.root,
            observe=self.facts,
            human_secret=self._human_proof,
            guard=self.guard,
            authorization=self,
            worker_script=worker_script,
            wall_clock=wall_clock,
        )
        self.authority = ProfileSessionAuthority(
            binding=store.binding,
            runtime_boot_id=runtime_boot_id,
            owner=self.owner,
            custody=store,
            issuer=self.issuer,
        )
        self.approvals = RuntimeApprovalSessions(worker=self.owner.identity, service=self._approval_service)

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
        if connection.method == "api_key":
            snapshot = self.store.snapshot()
            permissions = frozenset(
                permission
                for grant in snapshot.grants
                if grant.client_id == connection.client_id
                for permission in grant.scope.disclosures
            )
        else:
            permissions = frozenset(
                DisclosurePermission(
                    destination_id=connection.client_id, projection_id=schema.schema_id, category=category
                )
                for contract in self._contracts.definitions
                for schema in (
                    contract.result_schema,
                    contract.review_projection_schema,
                    contract.workspace_refresh_target_schema,
                )
                if schema is not None
                for category in DisclosureCategory
            )
            permissions |= frozenset(
                (
                    DisclosurePermission(
                        destination_id=connection.client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
        return AccessScope(
            operations=frozenset(item.definition_id for item in self._contracts.definitions),
            actions=frozenset(AccessAction),
            disclosures=permissions,
            periods=None,
            allow_period_independent=True,
            allow_delegation=True,
        )

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Observe committed profile fencing and current native dependencies per call."""
        connection = self._connected(connection_id)
        if connection.profile_id != self.store.binding.profile_id:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        lock = self.profile_lock_state()
        available, enabled = Availability.UNAVAILABLE, False
        try:
            snapshot = self.store.enrollment_state()
            available, enabled = Availability.AVAILABLE, snapshot.automation_enabled
        except AutomationCustodyError:
            # Password admission remains independent of the optional subsystem.
            if connection.method == "api_key":
                raise
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
            current = self.store.profile_lock_state()
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
            else:
                committed = self.store.profile_lock_state()
                if committed.generation != generation or committed.globally_locked or generation < current.generation:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                self._lock_fence = None

    @contextmanager
    def _human_proof(self, connection_id: UUID) -> Generator[RuntimeHumanProof]:
        connection = self._connected(connection_id)
        if connection.method not in {"password", "receipt"} or connection.human_secret is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        yield RuntimeHumanProof(
            method="password" if connection.method == "password" else "receipt",
            secret=connection.human_secret,
            originating_login_id=connection.login.login_id,
            persist_receipt=connection.persist_human_receipt,
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
                finally:
                    self.approvals.close()

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
        if not self.guard.acquire(blocking=False):
            return None
        try:
            if self.owner.lost:
                return False
            binding = self.store.binding
            try:
                current = current_automation_profile_binding(
                    profile_id=binding.profile_id,
                    installation_id=binding.installation_id,
                    os_owner_id=binding.os_owner_id,
                    root=self.store.root,
                )
            except AutomationCustodyError:
                current = None
            if current == binding:
                return False
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
            with suppress(RuntimeRefusalError, AutomationCustodyError, ProfileAccessRefusedError):
                try:
                    if current is not None and self._password_rotation is not None:
                        worker.settlement(
                            self._password_rotation, timeout=max(0.001, min(5.0, deadline - time.monotonic()))
                        )
                finally:
                    worker.drain(deadline=deadline)
        if not self.owner.wait_construction(deadline=deadline):
            raise RuntimeShutdownIncompleteError()
        self.owner.settle(deadline=deadline)
        asyncio.run(self.authority.close())
        return True
