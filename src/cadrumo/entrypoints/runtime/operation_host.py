"""Lazy canonical operation composition within one immutable profile worker."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from uuid import UUID

from pydantic import BaseModel

from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.persistence.storage.errors import RepositoryError
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.operations.composition import OperationComposedServices, OperationSubmission
from ...application.operations.errors import OperationSubjectBusyError
from ...application.operations.frontend_requests import OperationObservationRequestV1, OperationObservationResultV1
from ...application.operations.models import (
    OperationId,
    OperationIdentity,
    OperationRequest,
    OperationStoredInvocation,
    new_operation_id,
)
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from ...application.runtime.worker_authorization import WorkerAuthorizationRequest
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ..operation_composition import compose_operation_dependencies
from .operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding


class ProfileWorkerOperationHost:
    """Own the existing services and publication lease, never a second dispatcher."""

    def __init__(self, custody: ProfileWorkerCustody, *, authorization: WorkerAuthorizationClient) -> None:
        """Defer publication and backend loading until a governed capability needs it."""
        self.custody = custody
        self._lifetime = ExitStack()
        self._authority: PinnedAuthorityOperation | None = None
        self._services: OperationComposedServices | None = None
        self._client = authorization
        self._execution: ProfileWorkerOperationAuthority | None = None
        self._closed = False
        self._submissions: dict[OperationId, OperationSubmission] = {}

    def _bind_execution(self, registry: OperationRegistry) -> ProfileWorkerOperationAuthority:
        self._execution = ProfileWorkerOperationAuthority(custody=self.custody, client=self._client, registry=registry)
        return self._execution

    def _composed(self) -> OperationComposedServices:
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        if self._services is None:
            self._services = compose_operation_dependencies(
                authority_operation=self._pinned(), execution_authority_factory=self._bind_execution
            )
        return self._services

    def _pinned(self) -> PinnedAuthorityOperation:
        if self._authority is None:
            self._authority = self._lifetime.enter_context(bundled_indexed_authority().operation())
        return self._authority

    def profile_decode_context(self) -> ProfileDecodeContext:
        """Use the same publication for password candidates and hosted operations."""
        return self._pinned().profile_decode_context()

    def contract(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionContractV1:
        """Resolve an allowed definition from the real production service inventory."""
        lease = self.custody.require(session_id)
        if definition_id not in lease.scope.operations:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        for definition in self._composed().public_contracts.definitions:
            if definition.definition_id == definition_id:
                self.custody.require(session_id)
                return definition
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    async def submit(
        self, *, session_id: UUID, frontend: OperationFrontendProjection, request: OperationRequest[BaseModel]
    ) -> OperationSubmission:
        """Admit a fresh invocation through the canonical supervisor and live authority."""
        self.custody.require(session_id)
        services = self._composed()
        execution = self._execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        operation_id = new_operation_id()
        execution.bind(operation_id, WorkerOperationBinding(session_id, frontend, request))
        try:
            identity = OperationIdentity(
                operation_id=operation_id, definition_id=request.definition_id, subject_ref=request.subject_ref
            )
            async with execution.guard(identity, AccessAction.SUBMIT):
                submitted = await services.submission.submit(
                    request, actor_ref=f"session:{session_id}", operation_id=operation_id
                )
                if submitted.receipt.operation_id == operation_id:
                    self._submissions[operation_id] = submitted
                else:
                    # The canonical journal verified exact request replay. A
                    # retry receives no execution binding or response proof.
                    execution.discard(operation_id)
                return submitted
        except (RepositoryError, OperationSubjectBusyError):
            execution.discard(operation_id)
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        except BaseException:
            execution.discard(operation_id)
            raise

    async def start(self, operation_id: OperationId, session_id: UUID) -> OperationId:
        """Start only an invocation already bound by this worker's admission door."""
        self._require_owner(operation_id, session_id)
        try:
            return await self._composed().submission.start(operation_id)
        except (RepositoryError, ValueError):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    async def resume(
        self, operation_id: OperationId, session_id: UUID, *, frontend: OperationFrontendProjection
    ) -> OperationId:
        """Reauthorize stored intent and let its existing owner reconcile before entry."""
        self.custody.require(session_id)
        services = self._composed()
        invocation = await self._stored_invocation(operation_id, require_idle=True)
        execution = self._execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        binding = WorkerOperationBinding(session_id, frontend, invocation.request)
        async with execution.guard_binding(invocation.identity, AccessAction.RESUME, binding):
            execution.bind_reentry(operation_id, binding)
        try:
            # START/RESUME at actual entry and COMMIT each acquire fresh guards.
            return await services.submission.continue_operation(operation_id)
        except (RepositoryError, ValueError):
            execution.discard(operation_id)
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    @asynccontextmanager
    async def observe(
        self, session_id: UUID, request: OperationObservationRequestV1, *, frontend: OperationFrontendProjection
    ) -> AsyncGenerator[tuple[OperationObservationResultV1, WorkerAuthorizationRequest]]:
        """Lend a canonical projection only while its native disclosure guard is held."""
        async with self.release(session_id, request.operation_id, frontend, AccessAction.OBSERVE) as authorization:
            yield await self._composed().observation.observe(request), authorization

    @asynccontextmanager
    async def release(
        self, session_id: UUID, operation_id: OperationId, frontend: OperationFrontendProjection, action: AccessAction
    ) -> AsyncGenerator[WorkerAuthorizationRequest]:
        """Bind each internal projection to policy the runtime must recheck on final output."""
        self.custody.require(session_id)
        self._composed()
        execution = self._execution
        if execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        invocation = await self._stored_invocation(operation_id)
        binding = WorkerOperationBinding(session_id, frontend, invocation.request)
        async with execution.guard_binding(invocation.identity, action, binding) as authorization:
            yield authorization

    async def _stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        try:
            return await self._composed().submission.stored_invocation(operation_id, require_idle=require_idle)
        except (RepositoryError, KeyError, ValueError):
            # Unknown, damaged, foreign-profile and stale-contract records have
            # the same safe refusal. Their contents never become a projection.
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None

    def _require_owner(self, operation_id: OperationId, session_id: UUID) -> None:
        if self._execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._execution.require_owner(operation_id, session_id)

    async def submit_payload(
        self,
        *,
        session_id: UUID,
        frontend: OperationFrontendProjection,
        definition_id: str,
        subject_ref: str,
        payload_json: str,
        idempotency_key: str | None = None,
    ) -> OperationSubmission:
        """Decode through the exact registered model after exact-profile custody."""
        self.contract(session_id, definition_id)
        if self._execution is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        try:
            payload = self._execution.registry.decode_request_payload(definition_id, payload_json)
        except (ValueError, TypeError, RecursionError):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        return await self.submit(
            session_id=session_id,
            frontend=frontend,
            request=OperationRequest(
                definition_id=definition_id,
                subject_ref=subject_ref,
                payload=payload,
                idempotency_key=idempotency_key,
            ),
        )

    async def close(self) -> None:
        """Settle canonical services before releasing their publication lease."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._services is not None:
                await self._services.shutdown()
        finally:
            self._lifetime.close()
