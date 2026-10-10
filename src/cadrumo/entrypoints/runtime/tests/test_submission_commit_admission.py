"""A submission refused for its missing COMMIT door stores nothing and holds no subject.

The worker authority, the registered resolver, the access policy, the
supervisor and its encrypted journal, lease and operand stores are real. Only
the native hop to the runtime parent is replaced: the client answers each
authority request with the policy evaluation the parent performs for it, over
explicit session, grant and login facts.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.errors import OperationSubjectBusyError
from cadrumo.application.operations.models import OperationId, OperationRequest, new_operation_id
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.operation_access_policy import evaluate_operation_access
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
)
from cadrumo.core.operations import OperationLifecycle, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.runtime.operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
_ALL_ACTIONS = frozenset(AccessAction)


@dataclass(frozen=True)
class _Caller:
    """One delegated key session with the grant, key, profile and login facts that back it."""

    session: AccessSession
    grant: AutomationGrant
    key: ApiKeyRecord
    profile: ProfileAccessState
    context: AccessEvaluationContext


def _scope(actions: frozenset[AccessAction]) -> AccessScope:
    return AccessScope(
        operations=frozenset({PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID}),
        actions=actions,
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _caller(identity: ProfileWorkerIdentity, *, actions: frozenset[AccessAction]) -> _Caller:
    """Enroll one key whose grant and session hold exactly ``actions``."""
    binding = identity.binding
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=uuid4(),
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=_scope(actions),
        valid_from=_NOW - timedelta(days=1),
        expires_at=_NOW + timedelta(days=364),
        unattended=True,
        allow_os_lock=True,
    )
    key = ApiKeyRecord(
        key_id=uuid4(),
        grant_id=grant.grant_id,
        binding=binding,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=identity.runtime_boot_id,
        connection_id=uuid4(),
        client_id=grant.client_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=grant.scope,
        grant_id=grant.grant_id,
        grant_generation=grant.generation,
        key_id=key.key_id,
        key_generation=key.generation,
        issued_at=_NOW,
        expires_at=_NOW + ACCESS_LEASE_MAXIMUM,
        issued_monotonic=100.0,
    )
    return _Caller(
        session=session,
        grant=grant,
        key=key,
        profile=ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=_scope(_ALL_ACTIONS),
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        context=AccessEvaluationContext(
            now=_NOW,
            monotonic_now=100.0,
            clock_rollback_detected=False,
            runtime_boot_id=identity.runtime_boot_id,
            connection_id=session.connection_id,
            authenticated_client_id=grant.client_id,
            login_contexts=(
                OsLoginContext(
                    login_id="login-a",
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    lock_state=OsLockState.UNLOCKED,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        ),
    )


class _SessionCustody(ProfileWorkerCustody):
    """Name the live session leases without installing or borrowing any key."""

    def __init__(self, identity: ProfileWorkerIdentity, root: Path, sessions: tuple[AccessSession, ...]) -> None:
        self.identity, self.root = identity, root
        self._sessions = {session.session_id: session for session in sessions}

    @override
    def require(self, session_id: UUID) -> AccessSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return session


class _RuntimePolicyClient(WorkerAuthorizationClient):
    """Answer each authority request with the runtime parent's own policy evaluation."""

    def __init__(
        self, identity: ProfileWorkerIdentity, root: Path, registry: OperationRegistry, callers: tuple[_Caller, ...]
    ) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self._registry = registry
        self._callers = {caller.session.session_id: caller for caller in callers}

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        caller = self._callers[request.session_id]
        decision = evaluate_operation_access(
            request=request.request,
            policy=request.policy,
            registry=self._registry,
            session=caller.session,
            ancestors=(),
            grant=caller.grant,
            key=caller.key,
            profile=caller.profile,
            context=caller.context,
        )
        if isinstance(decision, AccessDenied):
            raise ProfileAccessRefusedError(decision.code)
        yield WorkerAuthorizationLease(
            identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
        )


def test_a_refused_committing_submission_stores_nothing_and_leaves_its_subject_free(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        profile_id = UUID(profile.bucket_id)
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=uuid4(),
            binding=ProfileAccessBinding(
                profile_id=profile_id,
                installation_id=uuid4(),
                os_owner_id="synthetic-owner",
                custody_generation=1,
                dek_epoch=uuid4(),
            ),
        )
        without_commit = _caller(identity, actions=_ALL_ACTIONS - {AccessAction.COMMIT})
        with_commit = _caller(identity, actions=_ALL_ACTIONS)
        registry = OperationRegistry(
            definitions=USER_PROFILE_OPERATION_DEFINITIONS,
            public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
        )
        authority = ProfileWorkerOperationAuthority(
            custody=_SessionCustody(identity, tmp_path, (without_commit.session, with_commit.session)),
            client=_RuntimePolicyClient(identity, tmp_path, registry, (without_commit, with_commit)),
            registry=registry,
            authority_operation=authority_operation,
        )
        operations_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=operations_root)
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=operations_root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=10),
            cleanup_timeout=timedelta(minutes=1),
            execution_authority=authority,
        )
        request = OperationRequest[BaseModel](
            definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=ProfileFieldMutationOperationRequest(
                profile_id=profile_id,
                expected_revision=1,
                expected_content_digest="0" * 64,
                path="preferences.output_language",
                value="es",
            ),
        )

        async def submit(caller: _Caller) -> OperationId:
            operation_id = new_operation_id()
            authority.bind(
                operation_id,
                WorkerOperationBinding(caller.session.session_id, OperationFrontendProjection.MCP, request),
            )
            try:
                return await supervisor.submit(request, operation_id=operation_id)
            except BaseException:
                authority.discard(operation_id)
                raise

        def stored_records() -> set[str]:
            """Name every journal and lease record; both are JSON files under the operations root."""
            return {path.name for path in operations_root.rglob("*.json")}

        async def exercise() -> None:
            try:
                with pytest.raises(ProfileAccessRefusedError) as refused:
                    await submit(without_commit)
                assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
                assert supervisor.in_flight_operation_count() == 0
                assert stored_records() == set()

                admitted = await submit(with_commit)
                assert (await journal.load(admitted)).lifecycle is OperationLifecycle.CREATED
                assert supervisor.in_flight_operation_count() == 1
                records = stored_records()
                assert f"{admitted}.json" in records
                assert any(name.endswith(".lease.json") for name in records)
                # The admitted, unsettled submission holds the subject the refused one never took.
                with pytest.raises(OperationSubjectBusyError):
                    await submit(with_commit)
            finally:
                await supervisor.shutdown()

        asyncio.run(exercise())
