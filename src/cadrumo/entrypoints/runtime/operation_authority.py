"""Profile-worker binding from canonical operations to native runtime authority."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes

from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    ProfilePassphraseRotationOperationRequest,
)
from ...application.operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    resolve_operation_access,
)
from ...application.operations.models import OperationId, OperationIdentity, OperationRequest
from ...application.operations.provenance import OperationAdmissionProvenance
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from ...application.runtime.approval_binding import RuntimeApprovalBinding
from ...application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from ...application.runtime.worker_enrollment import WorkerApprovalPublicationPhase, WorkerApprovalRequest
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessSession,
    Availability,
    SessionKind,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_enrollment import AutomationInventory, EnrollmentTransition
from ...application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from ...application.user_profile.operation_access_policy import operation_scope_refusal
from ...application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from ...application.workbench_generation_operation import (
    WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
    WorkbenchGenerationOperationRequest,
)
from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts


@dataclass(frozen=True, slots=True)
class WorkerOperationBinding:
    """Ephemeral admission identity; it is never reconstructed from a journal ID."""

    session_id: UUID
    frontend: OperationFrontendProjection
    request: OperationRequest[BaseModel]
    provenance: OperationAdmissionProvenance | None = None


class ProfileWorkerOperationAuthority:
    """Resolve current registered policy at each execution/effect boundary."""

    def __init__(
        self,
        *,
        custody: ProfileWorkerCustody,
        client: WorkerAuthorizationClient,
        registry: OperationRegistry,
        authority_operation: PinnedAuthorityOperation,
    ) -> None:
        """Bind one profile and canonical registry without granting any operation."""
        self.custody, self.client, self.registry = custody, client, registry
        self._authority_operation = authority_operation
        self._bindings: dict[OperationId, WorkerOperationBinding] = {}
        self._held: dict[asyncio.Task[object], tuple[OperationIdentity, AccessAction]] = {}
        self._held_leases: dict[asyncio.Task[object], WorkerAuthorizationLease] = {}

    def workbench_session(
        self, identity: OperationIdentity, payload: WorkbenchGenerationOperationRequest
    ) -> AccessSession:
        """Resolve the original human lease for this exact generation invocation."""
        binding = self._bindings.get(identity.operation_id)
        if (
            binding is None
            or identity.definition_id != WORKBENCH_GENERATION_OPERATION_DEFINITION_ID
            or binding.request.payload != payload
            or payload.profile_id != self.custody.identity.binding.profile_id
            or binding.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        authorization = self._resolve(identity, AccessAction.START)
        lease = self.custody.require(authorization.session_id)
        if lease.kind is not SessionKind.HUMAN:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return lease

    def approval_binding(
        self, identity: OperationIdentity, *, profile_id: UUID, request_id: UUID, review_digest: str
    ) -> RuntimeApprovalBinding:
        """Capture the exact immutable invocation before constructing an approval proxy."""
        binding = self._bindings.get(identity.operation_id)
        if (
            binding is None
            or identity.definition_id
            not in {AUTOMATION_APPROVE_OPERATION_DEFINITION_ID, AUTOMATION_DECLINE_OPERATION_DEFINITION_ID}
            or not isinstance(binding.request.payload, AutomationOperationRequest)
            or binding.request.payload.profile_id != profile_id
            or binding.request.payload.request_id != request_id
            or binding.request.payload.review_digest != review_digest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        authorization = self._resolve(identity, AccessAction.START)
        worker = self.custody.identity
        return RuntimeApprovalBinding(
            worker_id=worker.worker_id,
            runtime_boot_id=worker.runtime_boot_id,
            profile_binding=worker.binding,
            connection_id=authorization.connection_id,
            session_id=authorization.session_id,
            operation_id=identity.operation_id,
            enrollment_request_id=request_id,
            review_digest=review_digest,
        )

    def approval_request(
        self,
        identity: OperationIdentity,
        binding: RuntimeApprovalBinding,
        phase: Literal["prepare", "inspect_recipient", "deliver_and_verify", "close"],
    ) -> WorkerApprovalRequest:
        """Resolve fresh current human authority for a nonpublication approval phase."""
        authorization = self._resolve(identity, AccessAction.START)
        return WorkerApprovalRequest(
            request_id=authorization.request_id,
            connection_id=authorization.connection_id,
            session_id=authorization.session_id,
            binding=binding,
            request=authorization.request,
            policy=authorization.policy,
            phase=phase,
        )

    async def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None = None) -> bool | None:
        """Use the exact parent endpoint; cleanup requests need no still-live local lease."""
        return await self.client.approval_phase(request, password)

    async def publish_approval(
        self,
        identity: OperationIdentity,
        binding: RuntimeApprovalBinding,
        phase: WorkerApprovalPublicationPhase,
    ) -> EnrollmentTransition | None:
        """Capture only this task's exact held COMMIT lease before dispatching blocking I/O."""
        task = asyncio.current_task()
        if task is None or self._held.get(task) != (identity, AccessAction.COMMIT):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        lease = self._held_leases.get(task)
        if lease is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        expected = (
            AUTOMATION_DECLINE_OPERATION_DEFINITION_ID
            if phase == "decline"
            else AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
        )
        if identity.definition_id != expected:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._resolve(identity, AccessAction.COMMIT)
        return await await_cancellation_complete(
            asyncio.to_thread(lease.publish_approval, binding, phase), task_name="worker-approval-publication"
        )

    def bind(self, operation_id: OperationId, binding: WorkerOperationBinding) -> None:
        """Record a validated session's invocation; refuse cross-session ID adoption."""
        self.custody.require(binding.session_id)
        current = self._bindings.get(operation_id)
        if current is not None and current != binding:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._bindings[operation_id] = binding

    def discard(self, operation_id: OperationId) -> None:
        """Release a failed pre-admission binding after canonical submission refused."""
        self._bindings.pop(operation_id, None)

    async def automation_inventory(self, identity: OperationIdentity, profile_id: UUID) -> AutomationInventory:
        """Read administration through the invocation's original connection binding."""
        if profile_id != self.custody.identity.binding.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        authorization = self._resolve(identity, AccessAction.START)
        request = WorkerAutomationInventoryRequest(
            request_id=authorization.request_id,
            connection_id=authorization.connection_id,
            session_id=authorization.session_id,
            operation_id=identity.operation_id,
            request=authorization.request,
            policy=authorization.policy,
        )
        # The parent holds its denial fence through receipt. Subsequent result
        # disclosure obtains its own fresh human and destination authorization.
        with self.custody.section(request.session_id):
            return await self.client.inventory(request)

    def capture_provenance(self, identity: OperationIdentity) -> OperationAdmissionProvenance:
        """Capture original intent only within this task's current SUBMIT fence."""
        task = asyncio.current_task()
        if task is None or self._held.get(task) != (identity, AccessAction.SUBMIT):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        held = self._held_leases.get(task)
        if held is None or not isinstance(held.request, WorkerAuthorizationRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        binding = self._bindings[identity.operation_id]
        lease = self.custody.require(binding.session_id)
        provenance = OperationAdmissionProvenance(
            identity=identity,
            profile_binding=self.custody.identity.binding,
            approved_scope=lease.scope,
            admitted_request=held.request.request,
            authority_generation=self._authority_operation.generation.logical_generation,
            request_fingerprint=content_hash_hex(binding.request.payload.model_dump(mode="json")),
        )
        self._bindings[identity.operation_id] = replace(binding, provenance=provenance)
        return provenance

    def bind_reentry(self, operation_id: OperationId, binding: WorkerOperationBinding) -> None:
        """Bind owner-loaded idle intent after the host's fresh RESUME guard.

        The host must first exclude live execution through the canonical owner.
        This does not reconstruct or transfer the original response capability.
        """
        self.custody.require(binding.session_id)
        previous = self._bindings.get(operation_id)
        if previous is not None and (
            previous.request.model_copy(update={"idempotency_key": None}) != binding.request
            or previous.provenance != binding.provenance
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._bindings[operation_id] = binding

    def _resolve(self, identity: OperationIdentity, action: AccessAction) -> WorkerAuthorityRequest:
        binding = self._bindings.get(identity.operation_id)
        if binding is None:
            raise ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        return self._resolve_binding(identity, action, binding)

    def _resolve_binding(
        self, identity: OperationIdentity, action: AccessAction, binding: WorkerOperationBinding
    ) -> WorkerAuthorityRequest:
        request = binding.request
        self._require_binding_identity(identity, request)
        lease = self.custody.require(binding.session_id)
        contract = self._public_contract(request.definition_id)
        provenance = self._require_invocation_provenance(identity, request, action, binding.provenance)
        resolution = self._resolve_access(request, action, binding, lease, contract, provenance)
        self._require_current_scope(action, resolution, provenance)
        return self._authorization_request(identity, action, lease, resolution)

    async def _resolve_binding_off_loop(
        self, identity: OperationIdentity, action: AccessAction, binding: WorkerOperationBinding
    ) -> WorkerAuthorityRequest:
        """Finish one fresh scope read without blocking custody control requests.

        The caller captures the immutable binding on its own task. A scope read
        can decode a complete private catalogue, so its thread must settle before
        cancellation unwinds the caller. Retirement may proceed meanwhile; check
        custody again before returning any request to the native authority guard.
        """
        request = await await_cancellation_complete(
            asyncio.to_thread(self._resolve_binding, identity, action, binding), task_name="worker-authority-scope-read"
        )
        self.custody.require(binding.session_id)
        return request

    @staticmethod
    def _require_binding_identity(identity: OperationIdentity, request: OperationRequest[BaseModel]) -> None:
        if identity.definition_id != request.definition_id or identity.subject_ref != request.subject_ref:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

    def _public_contract(self, definition_id: str) -> OperationPublicDefinitionContractV1:
        try:
            return self.registry.lookup_public_contract(definition_id)
        except KeyError:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    def _require_invocation_provenance(
        self,
        identity: OperationIdentity,
        request: OperationRequest[BaseModel],
        action: AccessAction,
        provenance: OperationAdmissionProvenance | None,
    ) -> OperationAdmissionProvenance | None:
        if action is AccessAction.SUBMIT:
            return provenance
        if (
            provenance is None
            or provenance.profile_binding.profile_id != self.custody.identity.binding.profile_id
            or provenance.authority_generation != self._authority_operation.generation.logical_generation
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        try:
            provenance.require_invocation(identity, request)
        except ValueError:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        return provenance

    def _resolve_access(
        self,
        request: OperationRequest[BaseModel],
        action: AccessAction,
        binding: WorkerOperationBinding,
        lease: AccessSession,
        contract: OperationPublicDefinitionContractV1,
        provenance: OperationAdmissionProvenance | None,
    ) -> ResolvedOperationAccess:
        # Resolving persisted scope can decode governed facts before the
        # execution guard is entered. It uses the same retained publication
        # as execution, including repository validation of calculation rows.
        with validating_governed_facts(self._authority_operation):
            return resolve_operation_access(
                registry=self.registry,
                request=request,
                context=OperationAccessContext(
                    profile_id=self.custody.identity.binding.profile_id,
                    destination_id=lease.client_id,
                    action=action,
                    frontend=binding.frontend,
                    contract=contract,
                    published_authority=Availability.AVAILABLE,
                    admitted_request=provenance.admitted_request if provenance is not None else None,
                    authority_operation=self._authority_operation,
                ),
            )

    def _require_current_scope(
        self,
        action: AccessAction,
        resolution: ResolvedOperationAccess,
        provenance: OperationAdmissionProvenance | None,
    ) -> None:
        if action is AccessAction.SUBMIT:
            return
        if provenance is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if action not in {AccessAction.START, AccessAction.RESUME, AccessAction.COMMIT, AccessAction.RESPOND}:
            return
        # Historical reads use fresh current disclosure authority. Old
        # credential generations must not execute again implicitly,
        # but they do not revoke the profile's own persisted history.
        if provenance.profile_binding != self.custody.identity.binding:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        refusal = operation_scope_refusal(
            request=resolution.request, policy=resolution.policy, scope=provenance.approved_scope
        )
        if refusal is not None:
            raise ProfileAccessRefusedError(refusal.code)

    @staticmethod
    def _authorization_request(
        identity: OperationIdentity,
        action: AccessAction,
        lease: AccessSession,
        resolution: ResolvedOperationAccess,
    ) -> WorkerAuthorityRequest:
        request_type = WorkerResponseScopeRequest if action is AccessAction.RESPOND else WorkerAuthorizationRequest
        return request_type(
            request_id=uuid4(),
            connection_id=lease.connection_id,
            session_id=lease.session_id,
            operation_id=identity.operation_id,
            request=resolution.request,
            policy=resolution.policy,
        )

    async def require[Payload: BaseModel](
        self, *, identity: OperationIdentity, request: OperationRequest[Payload], action: AccessAction
    ) -> None:
        """Reject altered operands before asking the runtime for fresh authority."""
        binding = self._bindings.get(identity.operation_id)
        if binding is None or binding.request.model_copy(update={"idempotency_key": None}) != request.model_copy(
            update={"idempotency_key": None}
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        task = asyncio.current_task()
        authorization = await self._resolve_binding_off_loop(identity, action, binding)
        if task is not None and self._held.get(task) == (identity, action):
            return
        async with self.client.guard(authorization):
            pass

    @asynccontextmanager
    async def guard(self, identity: OperationIdentity, action: AccessAction) -> AsyncGenerator[None]:
        """Keep one task's exact boundary authorized; child tasks inherit no permit."""
        binding = self._bindings.get(identity.operation_id)
        if binding is None:
            raise ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        async with self.guard_binding(identity, action, binding):
            yield

    @asynccontextmanager
    async def guard_binding(
        self, identity: OperationIdentity, action: AccessAction, binding: WorkerOperationBinding
    ) -> AsyncGenerator[WorkerAuthorityRequest]:
        """Authorize stored operands for an observer without retargeting execution."""
        task = asyncio.current_task()
        if task is None or task in self._held:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        request = await self._resolve_binding_off_loop(identity, action, binding)
        async with self.client.guard(request) as lease:
            with self.custody.section(request.session_id), validating_governed_facts(self._authority_operation):
                self._held[task] = (identity, action)
                self._held_leases[task] = lease
                try:
                    yield request
                finally:
                    del self._held[task]
                    del self._held_leases[task]

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        """Hold native authority and stable local custody through the effect body."""
        async with self.guard(identity, AccessAction.COMMIT):
            yield

    def retire_password_successor(self, identity: OperationIdentity, outcome: ProfilePassphraseRotationOutcome) -> None:
        """Retire a proven replacement only within its original task's COMMIT.

        Ordinary access checks intentionally reject the replaced generation.
        This denial-only completion checks the retained effect owner instead;
        it cannot issue a successor lease or authorize private result output.
        """
        task = asyncio.current_task()
        binding = self._bindings.get(identity.operation_id)
        if not self._owns_password_rotation_commit(task, identity):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        payload = self._password_retirement_payload(identity, binding)
        if payload is None or not self._preserves_password_profile(payload, outcome):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self.custody.retire_password_successor(password_generation=outcome.password_generation)

    def _owns_password_rotation_commit(self, task: asyncio.Task[object] | None, identity: OperationIdentity) -> bool:
        return (
            task is not None and self._held.get(task) == (identity, AccessAction.COMMIT) and task in self._held_leases
        )

    @staticmethod
    def _password_retirement_payload(
        identity: OperationIdentity, binding: WorkerOperationBinding | None
    ) -> ProfilePassphraseRotationOperationRequest | None:
        if (
            binding is None
            or identity.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
            or binding.request.definition_id != identity.definition_id
            or binding.request.subject_ref != identity.subject_ref
            or not isinstance(binding.request.payload, ProfilePassphraseRotationOperationRequest)
        ):
            return None
        return binding.request.payload

    def _preserves_password_profile(
        self, payload: ProfilePassphraseRotationOperationRequest, outcome: ProfilePassphraseRotationOutcome
    ) -> bool:
        return (
            payload.profile_id == self.custody.identity.binding.profile_id
            and outcome.profile_id == str(payload.profile_id)
            and outcome.dek_epoch_preserved
        )

    def require_owner(
        self,
        operation_id: OperationId,
        session_id: UUID,
        *,
        frontend: OperationFrontendProjection | None = None,
    ) -> None:
        """Refuse ID-only adoption even by another admitted same-profile session."""
        binding = self._bindings.get(operation_id)
        if (
            binding is None
            or binding.session_id != session_id
            or (frontend is not None and binding.frontend is not frontend)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self.custody.require(session_id)

    def identity(self, operation_id: OperationId, session_id: UUID) -> OperationIdentity:
        """Resolve a previously admitted identity only for its exact session owner."""
        self.require_owner(operation_id, session_id)
        request = self._bindings[operation_id].request
        return OperationIdentity(
            operation_id=operation_id, definition_id=request.definition_id, subject_ref=request.subject_ref
        )
