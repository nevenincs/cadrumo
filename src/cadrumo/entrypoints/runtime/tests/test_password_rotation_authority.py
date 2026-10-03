"""A password successor may retire custody only from its original COMMIT task.

The resolver and permit here are test-only. Production rotation admission is
deliberately absent; the custody successor proof has its own subprocess tests.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import override
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.tests.profile_worker_support import changed, lease, worker_profiles
from cadrumo.adapters.local_runtime.worker_authorization_client import (
    WorkerAuthorizationClient,
    WorkerAuthorizationLease,
)
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    ProfilePassphraseRotationOperationRequest,
    build_auth_operation_definitions,
)
from cadrumo.application.operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, new_operation_id
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from cadrumo.core.config import override_settings
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.operation_composition import build_auth_operation_ports
from cadrumo.entrypoints.runtime.operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class WitnessCustody(ProfileWorkerCustody):
    """Retain real section checks while recording the final custody call."""

    def __init__(self, identity: ProfileWorkerIdentity, *, storage_root: Path) -> None:
        super().__init__(identity, storage_root=storage_root)
        self.retirement_generations: list[int] = []

    @override
    def retire_password_successor(self, *, password_generation: int) -> None:
        self.retirement_generations.append(password_generation)


class HeldPermitClient(WorkerAuthorizationClient):
    """Supply an explicit held callback without claiming native admission."""

    def __init__(self, *, identity: ProfileWorkerIdentity, root: Path) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.released = 0

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        try:
            yield WorkerAuthorizationLease(
                identity=self.identity,
                root=self.root,
                parent_pid=self.parent_pid,
                request=request,
            )
        finally:
            self.released += 1


def _rotation_access(request: OperationRequest[BaseModel], context: OperationAccessContext) -> ResolvedOperationAccess:
    """Allow only the bound synthetic profile; this is not a product resolver."""
    if (
        request.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
        or not isinstance(request.payload, ProfilePassphraseRotationOperationRequest)
        or request.payload.profile_id != context.profile_id
        or request.subject_ref != profile_operation_subject(str(context.profile_id))
    ):
        raise ValueError("test rotation request does not match its profile")
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )


def _registry() -> OperationRegistry:
    definition = next(
        definition
        for definition in build_auth_operation_definitions(ports=build_auth_operation_ports())
        if definition.definition_id == PROFILE_ROTATION_OPERATION_DEFINITION_ID
    )
    registration = OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=definition,
        request_schema_id="auth.profile.passphrase-rotate.request",
        access_resolver=_rotation_access,
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


@contextmanager
def _authority(
    tmp_path: Path,
) -> Iterator[tuple[ProfileWorkerOperationAuthority, HeldPermitClient, OperationIdentity, WitnessCustody]]:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((worker, key), _) = profiles
        with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(worker.binding.profile_id)):
            custody = WitnessCustody(worker, storage_root=root)
            original = lease(worker)
            session = changed(
                original,
                kind=SessionKind.HUMAN,
                originating_login_id="synthetic-login",
                grant_id=None,
                grant_generation=None,
                key_id=None,
                key_generation=None,
                scope=AccessScope(
                    operations=frozenset({PROFILE_ROTATION_OPERATION_DEFINITION_ID}),
                    actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                ),
            )
            custody.install(session, bytearray(key))
            client = HeldPermitClient(identity=worker, root=root)
            with bundled_indexed_authority().lease_operation() as pinned:
                authority = ProfileWorkerOperationAuthority(
                    custody=custody, client=client, registry=_registry(), authority_operation=pinned
                )
                request = OperationRequest(
                    definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(worker.binding.profile_id)),
                    payload=ProfilePassphraseRotationOperationRequest(profile_id=worker.binding.profile_id),
                )
                identity = OperationIdentity(
                    operation_id=new_operation_id(),
                    definition_id=request.definition_id,
                    subject_ref=request.subject_ref,
                )
                authority.bind(
                    identity.operation_id,
                    WorkerOperationBinding(
                        session_id=session.session_id, frontend=OperationFrontendProjection.CLI, request=request
                    ),
                )
                try:
                    yield authority, client, identity, custody
                finally:
                    custody.close()


@pytest.mark.asyncio
async def test_rotation_retirement_requires_the_exact_held_commit_task_and_outcome(tmp_path: Path) -> None:
    with _authority(tmp_path) as (authority, client, identity, custody):
        async with authority.guard(identity, AccessAction.SUBMIT):
            authority.capture_provenance(identity)
        outcome = ProfilePassphraseRotationOutcome(
            profile_id=str(custody.identity.binding.profile_id),
            password_generation=custody.identity.binding.custody_generation + 1,
            dek_epoch_preserved=True,
            recovery_enrollment_retained=False,
        )

        with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
            authority.retire_password_successor(identity, outcome)
        async with authority.commit_guard(identity):

            async def child() -> None:
                authority.retire_password_successor(identity, outcome)

            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                await asyncio.create_task(child())
            wrong_operation = identity.model_copy(update={"operation_id": new_operation_id()})
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                authority.retire_password_successor(wrong_operation, outcome)
            wrong_definition = identity.model_copy(update={"definition_id": "auth.session.logout"})
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                authority.retire_password_successor(wrong_definition, outcome)
            wrong_profile = outcome.model_copy(update={"profile_id": str(uuid4())})
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                authority.retire_password_successor(identity, wrong_profile)
            false_preservation = outcome.model_copy(update={"dek_epoch_preserved": False})
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                authority.retire_password_successor(identity, false_preservation)
            assert custody.retirement_generations == []
            authority.retire_password_successor(identity, outcome)
            assert custody.retirement_generations == [outcome.password_generation]
        async with authority.guard(identity, AccessAction.START):
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                authority.retire_password_successor(identity, outcome)
        with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
            authority.retire_password_successor(identity, outcome)
        assert custody.retirement_generations == [outcome.password_generation]
        assert client.released == 3
