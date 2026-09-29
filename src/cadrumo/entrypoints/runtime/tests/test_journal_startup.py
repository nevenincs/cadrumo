"""Native workers refuse unreadable existing journals before admitting private work."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from cadrumo.application.operations.capabilities import OperationRequestStoragePolicy
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.persistence.events import OperationPhaseEvent
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.custody_ports import profile_custody_secure_object_repository
from cadrumo.application.user_profile.operations import ProfileFieldMutationOperationRequest
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationLifecycle
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from .test_profile_worker_operations import BoundaryAuthority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


async def _create(root: Path, operation_id: str) -> None:
    """Publish one valid foreign-owned journal through the public adapter ports."""
    started = datetime(2026, 8, 13, 20, tzinfo=UTC)
    identity = OperationIdentity(operation_id=operation_id, definition_id="test.operation", subject_ref="subject")
    event = OperationPhaseEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=started,
        code="phase.0",
        phase_code="phase.0",
    )
    snapshot = OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest="c" * 64,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code=event.phase_code,
        started_at=started,
        updated_at=started,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
    )
    owned = OperationOwnerLease(
        operation_id=operation_id,
        scope_ref=operation_conflict_scope_reference(
            definition_id=identity.definition_id, subject_ref=identity.subject_ref
        ),
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=started,
        expires_at=started + timedelta(hours=1),
    )
    acquired = await OperationLeaseFilesystemRepository(storage_root=root).acquire(owned, observed_at=started)
    assert acquired.disposition is OperationLeaseDisposition.ACQUIRED
    await OperationJournalRepository(storage_root=root).create(snapshot, lease=owned)


def _secure_operand_keys(root: Path, profile_id: UUID, dek: bytes) -> tuple[bytes, ...]:
    """Read ciphertext-layer keys without decoding any private operand."""
    from cadrumo.adapters.persistence.storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE

    with profile_custody_secure_object_repository(profile_id=profile_id, dek=dek, root=root) as objects:
        assert isinstance(objects, SecureObjectRepository)
        return tuple(
            row.object_key
            for row in objects.iter_all_records_raw(namespace=OPERATION_SECURE_REFERENCE_NAMESPACE.namespace)
        )


@pytest.mark.parametrize("damage", ["superseded", "malformed_name"])
def test_native_worker_refuses_private_submit_when_startup_journal_is_unreadable(tmp_path: Path, damage: str) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        journal_id = "a" * 64
        asyncio.run(_create(root, journal_id))
        journal_dir = root / "operation-journals"
        journal_path = journal_dir / f"{journal_id}.json"
        if damage == "superseded":
            document = json.loads(journal_path.read_text(encoding="utf-8"))
            document["snapshot"]["schema_version"] = 6
            journal_path.write_text(json.dumps(document), encoding="utf-8")
            refused_path = journal_path
        else:
            refused_path = journal_dir / "malformed.json"
            refused_path.write_text("{}", encoding="utf-8")
        refused_bytes = refused_path.read_bytes()
        journal_names_before = frozenset(path.name for path in journal_dir.iterdir() if path.suffix == ".json")

        opened = datetime.now(UTC)
        with activate_session(
            BucketSession.open_resumed(
                bucket_id=str(identity.binding.profile_id),
                dek=key,
                idle_minutes=15,
                opened_at=opened,
                idle_deadline=opened + timedelta(minutes=15),
                absolute_deadline=opened + timedelta(minutes=240),
                storage_root=root,
            )
        ):
            record = load_test_profile_record(identity.binding.profile_id, root=root)
        request = OperationRequest(
            definition_id="user-profile.field-mutation",
            subject_ref=f"profile:{identity.binding.profile_id}",
            payload=ProfileFieldMutationOperationRequest(
                profile_id=identity.binding.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                path=PROFILE_OUTPUT_LANGUAGE_PATH,
                value="es",
            ),
        )

        authority = BoundaryAuthority(deny_commit=False)
        with override_settings(
            cadrumo_local_storage_root=root, cadrumo_active_profile=str(identity.binding.profile_id)
        ):
            worker = ProfileWorkerProcess(identity, storage_root=root, authorization=authority)
            try:
                admitted = lease(identity)
                worker.install(admitted, bytearray(key))
                contract = worker.contract(admitted.session_id, request.definition_id)
                assert contract.definition_id == request.definition_id
                operand_keys_before = _secure_operand_keys(root, identity.binding.profile_id, key)

                for _ in range(2):
                    with pytest.raises(ProfileAccessRefusedError) as refusal:
                        worker.submit(admitted.session_id, request, frontend=OperationFrontendProjection.MCP)
                    assert refusal.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
                    assert refused_path.read_bytes() == refused_bytes
                    assert frozenset(path.name for path in journal_dir.iterdir() if path.suffix == ".json") == (
                        journal_names_before
                    )
                    assert _secure_operand_keys(root, identity.binding.profile_id, key) == operand_keys_before
                    worker.require_alive()
                    assert worker.status().sessions
                    assert worker.contract(admitted.session_id, request.definition_id) == contract
                assert authority.calls == []
            finally:
                worker.close()
                worker.settle()
