"""Native restart cannot enlarge an operation's original admission scope."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, changed, lease, worker_profiles
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.provenance import OperationAdmissionProvenance
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, AccessSession
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.operations import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def _record(root: Path, profile_id: UUID):
    _, decode = profile_authority_contexts()
    login_profile(name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode)
    try:
        return ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    finally:
        close_active_bucket_session()


def _request(profile_id: UUID, revision: int, digest: str) -> OperationRequest[ProfileFieldMutationOperationRequest]:
    return OperationRequest[ProfileFieldMutationOperationRequest](
        definition_id="user-profile.field-mutation",
        subject_ref=f"profile:{profile_id}",
        payload=ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value="es",
        ),
    )


def _created_live(
    root: Path,
    identity: ProfileWorkerIdentity,
    key: bytes,
    request: OperationRequest[ProfileFieldMutationOperationRequest],
    *,
    narrow: bool,
) -> tuple[ProfileWorkerProcess, AccessSession, str]:
    authority = BoundaryAuthority(deny_commit=False)
    worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
    try:
        admitted = lease(identity)
        if narrow:
            scope = changed(admitted.scope, actions=admitted.scope.actions - {AccessAction.COMMIT})
            admitted = changed(admitted, scope=scope)
        worker.install(admitted, bytearray(key))
        receipt = worker.submit(admitted.session_id, request, frontend=OperationFrontendProjection.MCP).receipt
        snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(receipt.operation_id))
        assert snapshot.lifecycle is OperationLifecycle.CREATED
        assert snapshot.admission_provenance_reference is not None
        return worker, admitted, receipt.operation_id
    except BaseException:
        worker.close()
        worker.settle()
        raise


def _created(
    root: Path,
    identity: ProfileWorkerIdentity,
    key: bytes,
    request: OperationRequest[ProfileFieldMutationOperationRequest],
    *,
    narrow: bool,
) -> str:
    worker, _, operation_id = _created_live(root, identity, key, request, narrow=narrow)
    worker.close()
    worker.settle()
    return operation_id


def _replacement(
    root: Path, identity: ProfileWorkerIdentity, key: bytes
) -> tuple[ProfileWorkerProcess, AccessSession, BoundaryAuthority]:
    replacement_identity = changed(identity, worker_id=uuid4(), runtime_boot_id=uuid4())
    authority = BoundaryAuthority(deny_commit=False)
    worker = ProfileWorkerProcess(replacement_identity, storage_root=root, authorization=authority)
    admitted = lease(replacement_identity)
    worker.install(admitted, bytearray(key))
    return worker, admitted, authority


def test_fresh_full_scope_session_cannot_gain_commit_denied_at_original_admission(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        before = _record(root, profile_id)
        authority = BoundaryAuthority(deny_commit=False)
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
        try:
            narrow = lease(identity)
            narrow = changed(narrow, scope=changed(narrow.scope, actions=narrow.scope.actions - {AccessAction.COMMIT}))
            worker.install(narrow, bytearray(key))
            request = _request(profile_id, before.record_revision, before.content_digest)
            operation_id = worker.submit(
                narrow.session_id, request, frontend=OperationFrontendProjection.MCP
            ).receipt.operation_id
            assert (
                asyncio.run(OperationJournalRepository(storage_root=root).load(operation_id)).lifecycle
                is OperationLifecycle.CREATED
            )
            worker.retire(narrow.session_id)
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            worker.resume(admitted.session_id, operation_id, frontend=OperationFrontendProjection.MCP)
            observation_request = OperationObservationRequestV1(
                operation_id=operation_id, after_cursor=0, page_limit=32
            )
            deadline = time.monotonic() + 5
            while True:
                observation = worker.observe(admitted.session_id, observation_request).observation
                assert isinstance(observation, OperationObservationSuccessV1)
                if observation.projection.terminal_condition is not None:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.01)
            snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(operation_id))
            assert snapshot.terminal_condition is OperationTerminalCondition.REFUSED
            assert observation.projection.terminal_condition is OperationTerminalCondition.REFUSED
            assert AccessAction.RESUME in authority.calls
            assert AccessAction.COMMIT not in authority.calls
        finally:
            worker.close()
            worker.settle()
        after = _record(root, profile_id)
        assert after.record_revision == before.record_revision
        assert after.content_digest == before.content_digest
        assert record_to_path_values(after).get(PROFILE_OUTPUT_LANGUAGE_PATH) == record_to_path_values(before).get(
            PROFILE_OUTPUT_LANGUAGE_PATH
        )


def test_replacement_boot_cannot_take_active_lease_even_with_valid_original_provenance(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        before = _record(root, profile_id)
        operation_id = _created(
            root, identity, key, _request(profile_id, before.record_revision, before.content_digest), narrow=False
        )
        worker, admitted, authority = _replacement(root, identity, key)
        try:
            with pytest.raises(ProfileAccessRefusedError) as refused:
                worker.resume(admitted.session_id, operation_id, frontend=OperationFrontendProjection.MCP)
            assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
            assert (
                asyncio.run(OperationJournalRepository(storage_root=root).load(operation_id)).lifecycle
                is OperationLifecycle.CREATED
            )
            assert AccessAction.COMMIT not in authority.calls
        finally:
            worker.close()
            worker.settle()
        assert _record(root, profile_id).content_digest == before.content_digest


@pytest.mark.parametrize("damage", ["missing", "wrong_publication"])
def test_restarted_worker_refuses_damaged_original_provenance_before_entry(tmp_path: Path, damage: str) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = identity.binding.profile_id
        before = _record(root, profile_id)
        original_worker, original_session, operation_id = _created_live(
            root,
            identity,
            key,
            _request(profile_id, before.record_revision, before.content_digest),
            narrow=False,
        )
        try:
            journal_path = root / "operation-journals" / f"{operation_id}.json"
            document = json.loads(journal_path.read_text(encoding="utf-8"))
            if damage == "missing":
                document["snapshot"]["admission_provenance_reference"] = None
            else:
                _, decode = profile_authority_contexts()
                login_profile(
                    name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
                )
                try:
                    operands = operation_secure_reference_repository()
                    current_ref = document["snapshot"]["admission_provenance_reference"]
                    original = asyncio.run(operands.resolve(current_ref, OperationAdmissionProvenance))
                    altered = changed(original, authority_generation="f" * 64)
                    document["snapshot"]["admission_provenance_reference"] = asyncio.run(
                        operands.put(altered, written_at=now())
                    )
                finally:
                    close_active_bucket_session()
            journal_path.write_text(json.dumps(document), encoding="utf-8")

            original_worker.retire(original_session.session_id)
            same_owner_session = lease(identity)
            original_worker.install(same_owner_session, bytearray(key))
            with pytest.raises(ProfileAccessRefusedError) as same_owner_refusal:
                original_worker.resume(
                    same_owner_session.session_id, operation_id, frontend=OperationFrontendProjection.MCP
                )
            assert same_owner_refusal.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
            assert (
                asyncio.run(OperationJournalRepository(storage_root=root).load(operation_id)).lifecycle
                is OperationLifecycle.CREATED
            )
        finally:
            original_worker.close()
            original_worker.settle()

        worker, admitted, authority = _replacement(root, identity, key)
        try:
            with pytest.raises(ProfileAccessRefusedError) as refused:
                worker.resume(admitted.session_id, operation_id, frontend=OperationFrontendProjection.MCP)
            assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
            snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(operation_id))
            assert snapshot.lifecycle is OperationLifecycle.CREATED
            assert AccessAction.START not in authority.calls
            assert AccessAction.COMMIT not in authority.calls
        finally:
            worker.close()
            worker.settle()
        after = _record(root, profile_id)
        assert after.content_digest == before.content_digest


@pytest.mark.parametrize("old_provenance", ["other_dek_epoch", "other_profile_id"])
def test_old_provenance_custody_blocks_reentry_but_current_profile_can_observe_history(
    tmp_path: Path, old_provenance: str
) -> None:
    """Alter encrypted audit provenance, without simulating an actual password rotation."""
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), (foreign_identity, _)) = profiles
        profile_id = identity.binding.profile_id
        before = _record(root, profile_id)
        worker, original_session, operation_id = _created_live(
            root,
            identity,
            key,
            _request(profile_id, before.record_revision, before.content_digest),
            narrow=False,
        )
        try:
            journal_path = root / "operation-journals" / f"{operation_id}.json"
            document = json.loads(journal_path.read_text(encoding="utf-8"))
            _, decode = profile_authority_contexts()
            login_profile(
                name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
            )
            try:
                operands = operation_secure_reference_repository()
                original = asyncio.run(
                    operands.resolve(
                        document["snapshot"]["admission_provenance_reference"], OperationAdmissionProvenance
                    )
                )
                changed_binding = (
                    changed(original.profile_binding, dek_epoch=uuid4())
                    if old_provenance == "other_dek_epoch"
                    else changed(original.profile_binding, profile_id=foreign_identity.binding.profile_id)
                )
                altered = changed(
                    original,
                    profile_binding=changed_binding,
                    admitted_request=changed(original.admitted_request, profile_id=changed_binding.profile_id),
                )
                document["snapshot"]["admission_provenance_reference"] = asyncio.run(
                    operands.put(altered, written_at=now())
                )
            finally:
                close_active_bucket_session()
            journal_path.write_text(json.dumps(document), encoding="utf-8")

            worker.retire(original_session.session_id)
            current = lease(identity)
            worker.install(current, bytearray(key))
            with pytest.raises(ProfileAccessRefusedError) as refused:
                worker.resume(current.session_id, operation_id, frontend=OperationFrontendProjection.MCP)
            assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
            assert (
                asyncio.run(OperationJournalRepository(storage_root=root).load(operation_id)).lifecycle
                is OperationLifecycle.CREATED
            )

            observation = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
            if old_provenance == "other_dek_epoch":
                viewed = worker.observe(current.session_id, observation).observation
                assert isinstance(viewed, OperationObservationSuccessV1)
                assert viewed.projection.lifecycle is OperationLifecycle.CREATED
                assert viewed.projection.operation_id == operation_id
            else:
                with pytest.raises(ProfileAccessRefusedError) as observation_refusal:
                    worker.observe(current.session_id, observation)
                assert observation_refusal.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
        finally:
            worker.close()
            worker.settle()
        assert _record(root, profile_id).content_digest == before.content_digest
