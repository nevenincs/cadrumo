"""Internal rotation terminal wait is exact and discloses no private result."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID
from cadrumo.application.operations.composition import OperationComposedServices, OperationSubmission
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.models import OperationIdentity, new_operation_id
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.runtime.profile_worker import (
    ProfileWorkerIdentity,
    ProfileWorkerReply,
    ProfileWorkerRequest,
    ProfileWorkerSettlement,
    ProfileWorkerSettlementRequest,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import OperationLifecycle, profile_operation_subject
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@dataclass(frozen=True)
class _Snapshot:
    identity: OperationIdentity
    lifecycle: OperationLifecycle


class _Supervisor:
    """A shielded settlement task models the canonical supervisor wait boundary."""

    def __init__(self, identity: OperationIdentity) -> None:
        self.identity = identity
        self.release = asyncio.Event()
        self.lifecycle = OperationLifecycle.TERMINAL
        self.task = asyncio.create_task(self._finish())

    async def _finish(self) -> OperationPersistedSnapshot:
        await self.release.wait()
        return cast(OperationPersistedSnapshot, _Snapshot(self.identity, self.lifecycle))

    async def inspect(self, _operation_id: str) -> OperationPersistedSnapshot:
        return cast(OperationPersistedSnapshot, _Snapshot(self.identity, OperationLifecycle.RUNNING))

    async def settled(self, _operation_id: str) -> OperationPersistedSnapshot:
        return await asyncio.shield(self.task)


def _host(identity: OperationIdentity, supervisor: _Supervisor) -> ProfileWorkerOperationHost:
    # This test isolates the internal wait contract. No custody method or native
    # authorization is permitted to run after a password successor is retired.
    host = ProfileWorkerOperationHost(
        cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
    )
    host._submissions[identity.operation_id] = (
        uuid4(),
        OperationSubmission(
            receipt=OperationSubmissionReceiptV1(operation_id=identity.operation_id, secret_requirement=None),
            response_capability=None,
        ),
    )
    host._services = cast(
        OperationComposedServices, cast(object, SimpleNamespace(submission=SimpleNamespace(supervisor=supervisor)))
    )
    return host


def _identity() -> OperationIdentity:
    profile_id = uuid4()
    return OperationIdentity(
        operation_id=new_operation_id(),
        definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
    )


@pytest.mark.asyncio
async def test_exact_rotation_wait_times_out_without_cancelling_settlement() -> None:
    identity = _identity()
    supervisor = _Supervisor(identity)
    host = _host(identity, supervisor)
    try:
        assert await host.settlement(identity, timeout=0.01) is False
        assert not supervisor.task.done()
        supervisor.release.set()
        assert await host.settlement(identity, timeout=1) is True
        assert supervisor.task.done() and not supervisor.task.cancelled()
    finally:
        supervisor.release.set()
        await supervisor.task


@pytest.mark.asyncio
async def test_rotation_wait_refuses_unknown_or_altered_identity_and_nonterminal_return() -> None:
    identity = _identity()
    supervisor = _Supervisor(identity)
    host = _host(identity, supervisor)
    try:
        wrong_id = identity.model_copy(update={"operation_id": new_operation_id()})
        wrong_subject = identity.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})
        wrong_definition = identity.model_copy(update={"definition_id": "auth.session.logout"})
        for candidate in (wrong_id, wrong_subject, wrong_definition):
            with pytest.raises(ProfileAccessRefusedError):
                await host.settlement(candidate, timeout=0.1)
        supervisor.lifecycle = OperationLifecycle.RUNNING
        supervisor.release.set()
        with pytest.raises(ProfileAccessRefusedError) as refused:
            await host.settlement(identity, timeout=1)
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    finally:
        supervisor.release.set()
        await supervisor.task


def test_control_wire_is_bounded_and_contains_no_private_result() -> None:
    identity = _identity()
    request = ProfileWorkerSettlementRequest(request_id=uuid4(), operation_identity=identity, wait_seconds=5.0)
    parsed = ProfileWorkerRequest.model_validate_json(ProfileWorkerRequest(request).model_dump_json()).root
    assert parsed == request
    with pytest.raises(ValidationError):
        ProfileWorkerSettlementRequest(request_id=uuid4(), operation_identity=identity, wait_seconds=5.01)
    worker = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    reply = ProfileWorkerSettlement(
        identity=worker, request_id=request.request_id, operation_identity=identity, settled=True
    )
    assert ProfileWorkerReply.model_validate_json(ProfileWorkerReply(reply).model_dump_json()).root == reply
    assert "result_ref" not in reply.model_dump_json()
    with pytest.raises(ValidationError):
        ProfileWorkerSettlement.model_validate({**reply.model_dump(), "result_ref": "private"})
