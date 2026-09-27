"""Compose exact-profile session authority, committed custody and installed workers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4

from ...adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from ...adapters.persistence.storage.custody.automation_store import AutomationControlStore
from ...application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.runtime.login import RuntimeLoginEvidence
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.runtime.worker_authorization import WorkerAuthorizationRequest
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessEvaluationContext,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessState,
)
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.session_authority import ProfileSessionAuthority, SessionAuthorityFacts
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
    password: bytearray | None = None


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
    ) -> None:
        """Compose existing authorities without opening keys or selecting a profile."""
        self.store, self._registry = store, registry
        self._contracts = registry.public_contract_set
        self._connected, self._logins, self._admitting = connected, logins, admitting
        self.guard = RLock()
        self.issuer = CustodyAutomationKeyIssuer()
        self.owner = ProfileWorkerSessionOwner(
            ProfileWorkerIdentity(worker_id=uuid4(), runtime_boot_id=runtime_boot_id, binding=store.binding),
            storage_root=store.root,
            observe=self.facts,
            human_secret=self._password,
            guard=self.guard,
            authorization=self,
        )
        self.authority = ProfileSessionAuthority(
            binding=store.binding,
            runtime_boot_id=runtime_boot_id,
            owner=self.owner,
            custody=store,
            issuer=self.issuer,
        )

    @contextmanager
    def authorize(self, request: WorkerAuthorizationRequest) -> Generator[AccessAllowed]:
        """Retain fresh profile authority for a kernel-verified owned worker."""
        with self.authority.operation_guard(
            connection_id=request.connection_id,
            session_id=request.session_id,
            request=request.request,
            policy=request.policy,
            registry=self._registry,
        ) as allowed:
            yield allowed

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
        lock = self.store.profile_lock_state()
        available, enabled = Availability.UNAVAILABLE, False
        try:
            snapshot = self.store.snapshot()
            available, enabled = Availability.AVAILABLE, snapshot.automation_enabled
        except AutomationCustodyError:
            # Password admission remains independent of the optional subsystem.
            if connection.method == "api_key":
                raise
        scope = self.scope(connection)
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
                now=now(),
                monotonic_now=time.monotonic(),
                clock_rollback_detected=False,
                runtime_boot_id=connection.context.runtime_boot_id,
                connection_id=connection_id,
                authenticated_client_id=connection.client_id,
                login_contexts=tuple(login.observe(credential_facilities=available) for login in self._logins()),
                private_work_available=self._admitting(),
            ),
        )

    @contextmanager
    def _password(self, connection_id: UUID) -> Generator[tuple[bytearray, str]]:
        connection = self._connected(connection_id)
        if connection.method != "password" or connection.password is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        yield connection.password, connection.login.login_id

    def close(self) -> None:
        """Retire authority and then terminate remaining owned profile processes."""
        try:
            asyncio.run(self.authority.close())
        finally:
            try:
                self.owner.close()
            finally:
                self.owner.settle()
