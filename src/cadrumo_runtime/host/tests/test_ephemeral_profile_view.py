"""An ephemeral profile-view read in a real profile worker leaves nothing durable behind."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationId, OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessSession
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ...adapters.profile_worker import ProfileWorkerProcess
from ...adapters.tests.profile_worker_support import PROFILE_INPUT, changed, lease, worker_profiles
from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]

_FRONTEND = OperationFrontendProjection.CLI
_RECORDED = "user-profile.field-mutation"


def _secure_reference_rows(profile_id: UUID) -> int:
    """Count the profile's encrypted operation operand rows through its real secure-object store."""
    _, decode = profile_authority_contexts()
    authenticate_profile_for_invocation(
        name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
    )
    try:
        session = current_active_bucket_session()
        assert session is not None
        objects = secure_object_repository_for_bucket(session.bucket_id)
        return len(objects.list_keys(OPERATION_SECURE_REFERENCE_NAMESPACE.namespace))
    finally:
        close_active_bucket_session()


def _profile_baseline(profile_id: UUID) -> tuple[int, str]:
    _, decode = profile_authority_contexts()
    authenticate_profile_for_invocation(
        name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
    )
    try:
        record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
        return record.record_revision, record.content_digest
    finally:
        close_active_bucket_session()


def _session(identity: ProfileWorkerIdentity) -> AccessSession:
    admitted = lease(identity)
    operations = frozenset({PROFILE_VIEW_OPERATION_DEFINITION_ID, _RECORDED})
    return changed(admitted, scope=changed(admitted.scope, operations=operations))


def _view_request(profile_id: UUID) -> OperationRequest[ProfileViewOperationRequest]:
    return OperationRequest[ProfileViewOperationRequest](
        definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.FACTS),
    )


def _settled(
    worker: ProfileWorkerProcess, session: AccessSession, operation_id: OperationId
) -> OperationTerminalCondition:
    request = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
    deadline = time.monotonic() + 30
    while True:
        observation = worker.observe(session.session_id, request, frontend=_FRONTEND).observation
        assert isinstance(observation, OperationObservationSuccessV1), observation
        condition = observation.projection.terminal_condition
        if condition is not None:
            return condition
        assert time.monotonic() < deadline
        time.sleep(0.01)


def _run[Payload: BaseModel](
    worker: ProfileWorkerProcess, session: AccessSession, request: OperationRequest[Payload]
) -> OperationId:
    operation_id = worker.submit(session.session_id, request, frontend=_FRONTEND).receipt.operation_id
    worker.start(session.session_id, operation_id, frontend=_FRONTEND)
    assert _settled(worker, session, operation_id) is OperationTerminalCondition.SUCCEEDED
    return operation_id


def test_an_ephemeral_read_writes_no_operation_operand_row_while_a_recorded_one_does(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        revision, digest = _profile_baseline(profile_id)
        baseline = _secure_reference_rows(profile_id)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=BoundaryAuthority(deny_commit=False))
        try:
            session = _session(identity)
            worker.install(session, bytearray(key))
            _run(worker, session, _view_request(profile_id))
            after_read = _secure_reference_rows(profile_id)
            # Positive control: a recorded operation's admission provenance is an encrypted operand row.
            _run(
                worker,
                session,
                OperationRequest[ProfileFieldMutationOperationRequest](
                    definition_id=_RECORDED,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=ProfileFieldMutationOperationRequest(
                        profile_id=profile_id,
                        expected_revision=revision,
                        expected_content_digest=digest,
                        path=PROFILE_OUTPUT_LANGUAGE_PATH,
                        value="es",
                    ),
                ),
            )
            after_recorded = _secure_reference_rows(profile_id)
        finally:
            worker.close()
            worker.settle()
    assert after_read == baseline, (baseline, after_read)
    assert after_recorded > after_read, (after_read, after_recorded)


def _unknown(worker: ProfileWorkerProcess, session: AccessSession, operation_id: OperationId) -> bool:
    request = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
    try:
        observation = worker.observe(session.session_id, request, frontend=_FRONTEND).observation
    except ProfileAccessRefusedError as refused:
        return refused.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    return (
        isinstance(observation, OperationObservationRefusalV1)
        and observation.code is OperationObservationRefusalCode.UNKNOWN_OPERATION
    )


def test_a_delivered_view_result_is_forgotten_and_an_unread_one_ends_with_the_last_session(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=BoundaryAuthority(deny_commit=False))
        try:
            session = _session(identity)
            worker.install(session, bytearray(key))
            contract = worker.describe(session.session_id, PROFILE_VIEW_OPERATION_DEFINITION_ID).contract
            assert contract.result_schema is not None
            delivered = _run(worker, session, _view_request(profile_id))
            terminal = worker.observe(
                session.session_id,
                OperationObservationRequestV1(operation_id=delivered, after_cursor=0, page_limit=32),
                frontend=_FRONTEND,
            ).observation
            assert isinstance(terminal, OperationObservationSuccessV1)
            projected = worker.project(
                session.session_id,
                OperationResultProjectionRequestV1(
                    operation_id=delivered,
                    terminal_revision=terminal.projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                frontend=_FRONTEND,
            )
            assert projected.document["outcome"] == "success"
            # The reader has its whole result: the decrypted page is gone from the worker.
            assert _unknown(worker, session, delivered)

            unread = _run(worker, session, _view_request(profile_id))
            assert not _unknown(worker, session, unread)
            # Locking ends the last session; the worker lives on, its unread result does not.
            worker.retire(session.session_id)
            assert worker.status().sessions == ()
            successor = _session(identity)
            worker.install(successor, bytearray(key))
            assert _unknown(worker, successor, unread)
        finally:
            worker.close()
            worker.settle()


def test_a_worker_ended_during_an_ephemeral_read_leaves_its_successor_answering_unknown(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        authority = BoundaryAuthority(deny_commit=False)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        try:
            session = _session(identity)
            worker.install(session, bytearray(key))
            reading = worker.submit(session.session_id, _view_request(profile_id), frontend=_FRONTEND).receipt
            worker.start(session.session_id, reading.operation_id, frontend=_FRONTEND)
        finally:
            # Ended without waiting for the read: whatever it reached dies with the process.
            worker.close()
            worker.settle()
        journal = root / storage_location(StorageCategory.OPERATION_JOURNAL).subpath
        assert not (journal.is_dir() and any(reading.operation_id in path.name for path in journal.iterdir()))
        successor_identity = changed(identity, worker_id=uuid4(), runtime_boot_id=uuid4())
        successor = ProfileWorkerProcess(successor_identity, storage_root=root, authorization=authority)
        try:
            fresh = _session(successor_identity)
            successor.install(fresh, bytearray(key))
            assert _unknown(successor, fresh, reading.operation_id)
        finally:
            successor.close()
            successor.settle()
