"""Profile-worker binding from canonical operations to native runtime authority."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import BaseModel

from ...adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.models import OperationId, OperationIdentity, OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.runtime.worker_authorization import WorkerAuthorizationRequest
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError


@dataclass(frozen=True, slots=True)
class WorkerOperationBinding:
    """Ephemeral admission identity; it is never reconstructed from a journal ID."""

    session_id: UUID
    frontend: OperationFrontendProjection
    request: OperationRequest[BaseModel]


class ProfileWorkerOperationAuthority:
    """Resolve current registered policy at each execution/effect boundary."""

    def __init__(
        self, *, custody: ProfileWorkerCustody, client: WorkerAuthorizationClient, registry: OperationRegistry
    ) -> None:
        """Bind one profile and canonical registry without granting any operation."""
        self.custody, self.client, self.registry = custody, client, registry
        self._bindings: dict[OperationId, WorkerOperationBinding] = {}
        self._held: dict[asyncio.Task[object], tuple[OperationIdentity, AccessAction]] = {}

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

    def bind_reentry(self, operation_id: OperationId, binding: WorkerOperationBinding) -> None:
        """Bind owner-loaded idle intent after the host's fresh RESUME guard.

        The host must first exclude live execution through the canonical owner.
        This does not reconstruct or transfer the original response capability.
        """
        self.custody.require(binding.session_id)
        previous = self._bindings.get(operation_id)
        if previous is not None and previous.request.model_copy(update={"idempotency_key": None}) != binding.request:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self._bindings[operation_id] = binding

    def _resolve(self, identity: OperationIdentity, action: AccessAction) -> WorkerAuthorizationRequest:
        binding = self._bindings.get(identity.operation_id)
        if binding is None:
            raise ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        return self._resolve_binding(identity, action, binding)

    def _resolve_binding(
        self, identity: OperationIdentity, action: AccessAction, binding: WorkerOperationBinding
    ) -> WorkerAuthorizationRequest:
        request = binding.request
        if identity.definition_id != request.definition_id or identity.subject_ref != request.subject_ref:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        lease = self.custody.require(binding.session_id)
        try:
            contract = self.registry.lookup_public_contract(request.definition_id)
        except KeyError:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        resolution = resolve_operation_access(
            registry=self.registry,
            request=request,
            context=OperationAccessContext(
                profile_id=self.custody.identity.binding.profile_id,
                destination_id=lease.client_id,
                action=action,
                frontend=binding.frontend,
                contract=contract,
                # This owner is composed only within a pinned publication lease.
                published_authority=Availability.AVAILABLE,
            ),
        )
        return WorkerAuthorizationRequest(
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
        if task is not None and self._held.get(task) == (identity, action):
            self._resolve(identity, action)
            return
        async with self.client.guard(self._resolve(identity, action)):
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
    ) -> AsyncGenerator[WorkerAuthorizationRequest]:
        """Authorize stored operands for an observer without retargeting execution."""
        task = asyncio.current_task()
        if task is None or task in self._held:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        request = self._resolve_binding(identity, action, binding)
        async with self.client.guard(request):
            with self.custody.section(request.session_id):
                self._held[task] = (identity, action)
                try:
                    yield request
                finally:
                    del self._held[task]

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        """Hold native authority and stable local custody through the effect body."""
        async with self.guard(identity, AccessAction.COMMIT):
            yield

    def require_owner(self, operation_id: OperationId, session_id: UUID) -> None:
        """Refuse ID-only adoption even by another admitted same-profile session."""
        binding = self._bindings.get(operation_id)
        if binding is None or binding.session_id != session_id:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        self.custody.require(session_id)

    def identity(self, operation_id: OperationId, session_id: UUID) -> OperationIdentity:
        """Resolve a previously admitted identity only for its exact session owner."""
        self.require_owner(operation_id, session_id)
        request = self._bindings[operation_id].request
        return OperationIdentity(
            operation_id=operation_id, definition_id=request.definition_id, subject_ref=request.subject_ref
        )
