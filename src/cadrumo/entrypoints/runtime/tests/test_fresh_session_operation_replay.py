"""A fresh session resumes, observes and reads admitted work from a new destination."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import changed, lease, worker_profiles
from cadrumo.application.auth.apoderado_contracts import (
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoStatusRequest,
)
from cadrumo.application.diagnostics_operation import DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
from cadrumo.application.diagnostics_read_contracts import DiagnosticsReadRequest
from cadrumo.application.ledger.llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessSession
from cadrumo.core.operations import OperationTerminalCondition

from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def _session(identity: ProfileWorkerIdentity, definition_id: str) -> AccessSession:
    """A new lease always carries a new client, so each session is a new destination."""
    admitted = lease(identity)
    return changed(admitted, scope=changed(admitted.scope, operations=frozenset({definition_id})))


def _payload(definition_id: str, profile_id: UUID) -> BaseModel:
    if definition_id == DIAGNOSTICS_READ_OPERATION_DEFINITION_ID:
        return DiagnosticsReadRequest(profile_id=profile_id, kind="errors")
    if definition_id == LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID:
        return LedgerLlmDiagnosticsRequest(profile_id=profile_id)
    return ApoderadoStatusRequest(profile_id=profile_id)


def _request(definition_id: str, profile_id: UUID) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=f"profile:{profile_id}",
        payload=_payload(definition_id, profile_id),
    )


def _settled(
    worker: ProfileWorkerProcess,
    session_id: UUID,
    operation_id: str,
    *,
    frontend: OperationFrontendProjection,
) -> OperationPublicProjectionV1:
    request = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
    deadline = time.monotonic() + 30
    while True:
        observation = worker.observe(session_id, request, frontend=frontend).observation
        assert isinstance(observation, OperationObservationSuccessV1), observation
        if observation.projection.terminal_condition is not None:
            return observation.projection
        assert time.monotonic() < deadline
        time.sleep(0.02)


@pytest.mark.parametrize(
    "definition_id",
    [
        DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
        APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ],
)
def test_a_fresh_session_on_another_frontend_observes_and_reads_a_settled_operation(
    tmp_path: Path, definition_id: str
) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        authority = BoundaryAuthority(deny_commit=False)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        try:
            original = _session(identity, definition_id)
            worker.install(original, bytearray(key))
            operation_id = worker.submit(
                original.session_id, _request(definition_id, profile_id), frontend=OperationFrontendProjection.MCP
            ).receipt.operation_id
            worker.start(original.session_id, operation_id)
            settled = _settled(worker, original.session_id, operation_id, frontend=OperationFrontendProjection.MCP)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            worker.retire(original.session_id)

            fresh = _session(identity, definition_id)
            assert fresh.client_id != original.client_id
            worker.install(fresh, bytearray(key))
            observed = _settled(worker, fresh.session_id, operation_id, frontend=OperationFrontendProjection.CLI)
            assert observed == settled
            contract = worker.describe(fresh.session_id, definition_id).contract
            assert contract.result_schema is not None
            result = worker.project(
                fresh.session_id,
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=observed.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                frontend=OperationFrontendProjection.CLI,
            )
            assert result.document["outcome"] == "success"
            released = result.document["projection"]
            assert isinstance(released, dict)
            assert released["profile_id"] == str(profile_id)
            assert result.release.request.destination_id == fresh.client_id
            assert result.release.request.frontend is OperationFrontendProjection.CLI
            assert all(item.destination_id == fresh.client_id for item in result.release.policy.disclosures)
        finally:
            worker.close()
            worker.settle()


def test_a_fresh_session_on_another_frontend_resumes_and_observes_admitted_work(tmp_path: Path) -> None:
    definition_id = DIAGNOSTICS_READ_OPERATION_DEFINITION_ID
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        authority = BoundaryAuthority(deny_commit=False)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        try:
            original = _session(identity, definition_id)
            worker.install(original, bytearray(key))
            operation_id = worker.submit(
                original.session_id,
                _request(definition_id, identity.binding.profile_id),
                frontend=OperationFrontendProjection.MCP,
            ).receipt.operation_id
            worker.retire(original.session_id)

            fresh = _session(identity, definition_id)
            assert fresh.client_id != original.client_id
            worker.install(fresh, bytearray(key))
            worker.resume(fresh.session_id, operation_id, frontend=OperationFrontendProjection.CLI)
            settled = _settled(worker, fresh.session_id, operation_id, frontend=OperationFrontendProjection.CLI)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert authority.calls[0] is AccessAction.SUBMIT
            assert AccessAction.RESUME in authority.calls
            assert AccessAction.OBSERVE in authority.calls
        finally:
            worker.close()
            worker.settle()
