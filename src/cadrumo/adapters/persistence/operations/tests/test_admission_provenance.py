"""Durable admission provenance stays encrypted and bound to its invocation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.adapters.persistence.storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.composition import OperationSubmissionService
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.projection_services import OperationResponseAuthorityBroker
from cadrumo.application.operations.provenance import OperationAdmissionProvenance
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    OperationAccessRequest,
    ProfileAccessBinding,
)
from cadrumo.core.hashing import content_hash_hex

from .test_journal import _claim_lease, _lease, _snapshot
from .test_supervisor import _NOW, IdleExecutor, SupervisorRequest, _registry, _repositories, _supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_ORIGINAL_ID = "3" * 64
_RETRY_ID = "4" * 64
_DEFINITION_ID = "operation.supervisor.test"
_OWNER_MARKER = "provenance-owner-marker-never-in-journal"
_DESTINATION_ID = UUID("59653ea3-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _request(*, value: str = "encrypted-operation-input") -> OperationRequest[SupervisorRequest]:
    return OperationRequest[SupervisorRequest](
        definition_id=_DEFINITION_ID,
        subject_ref="subject:admission-provenance",
        payload=SupervisorRequest(value=value),
        idempotency_key="same-admission",
    )


def _provenance(
    operation_id: str,
    request: OperationRequest[SupervisorRequest],
    *,
    profile_id: UUID,
    allow_start: bool = False,
) -> OperationAdmissionProvenance:
    return OperationAdmissionProvenance(
        identity=OperationIdentity(
            operation_id=operation_id,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
        ),
        profile_binding=ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=uuid4(),
            os_owner_id=_OWNER_MARKER,
            custody_generation=7,
            dek_epoch=uuid4(),
        ),
        approved_scope=AccessScope(
            operations=frozenset({_DEFINITION_ID}),
            actions=frozenset({AccessAction.SUBMIT, AccessAction.START})
            if allow_start
            else frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        admitted_request=OperationAccessRequest(
            profile_id=profile_id,
            definition_id=request.definition_id,
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=_DESTINATION_ID,
        ),
        authority_generation=content_hash_hex({"publication": "first-authority-generation"}),
        request_fingerprint=content_hash_hex(request.payload.model_dump(mode="json")),
    )


def _services(root: Path, profile_objects):
    journal, leases, operands = _repositories(storage_root=root, profile_objects=profile_objects)
    supervisor = _supervisor(
        registry=_registry(executor_type=IdleExecutor, build=IdleExecutor),
        journal=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        token="2" * 64,
    )
    return journal, supervisor, OperationSubmissionService(supervisor, OperationResponseAuthorityBroker())


def test_provenance_survives_encrypted_round_trip_without_plaintext_or_replay_replacement(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable-state"
        journal, supervisor, service = _services(root, profile.repository)
        request = _request()
        original = _provenance(_ORIGINAL_ID, request, profile_id=UUID(profile.bucket_id))

        first = asyncio.run(
            service.submit(request, actor_ref="actor:provenance", operation_id=_ORIGINAL_ID, provenance=original)
        )
        snapshot = asyncio.run(journal.load(_ORIGINAL_ID))
        assert first.receipt.operation_id == _ORIGINAL_ID
        assert first.response_capability is not None
        assert snapshot.admission_provenance_reference is not None
        assert snapshot.admission_provenance_reference != original.authority_generation
        journal_bytes = next(root.rglob(f"{_ORIGINAL_ID}.json")).read_bytes()
        assert snapshot.admission_provenance_reference.encode() in journal_bytes
        assert _OWNER_MARKER.encode() not in journal_bytes
        assert b'"approved_scope"' not in journal_bytes
        assert b'"admitted_request"' not in journal_bytes
        assert str(_DESTINATION_ID).encode() not in journal_bytes
        assert str(original.profile_binding.profile_id).encode() not in journal_bytes

        _, fresh_supervisor, fresh_service = _services(root, profile.repository)
        recovered = asyncio.run(fresh_supervisor.stored_invocation(_ORIGINAL_ID))
        assert recovered.provenance == original
        assert recovered.provenance is not None
        assert recovered.provenance.admitted_request == original.admitted_request
        assert recovered.request.payload == request.payload

        proposed = _provenance(_RETRY_ID, request, profile_id=UUID(profile.bucket_id), allow_start=True)
        replay = asyncio.run(
            fresh_service.submit(request, actor_ref="actor:provenance", operation_id=_RETRY_ID, provenance=proposed)
        )
        assert replay.receipt == first.receipt
        assert replay.response_capability is None
        assert (
            asyncio.run(journal.load(_ORIGINAL_ID)).admission_provenance_reference
            == snapshot.admission_provenance_reference
        )
        assert asyncio.run(fresh_supervisor.stored_invocation(_ORIGINAL_ID)).provenance == original
        with pytest.raises(RepositoryError):
            asyncio.run(journal.load(_RETRY_ID))
        first.response_capability.close()
        asyncio.run(supervisor.shutdown())
        asyncio.run(fresh_supervisor.shutdown())


@pytest.mark.parametrize("damage", ["old_schema", "missing_request", "foreign_profile", "other_definition"])
def test_admitted_request_is_required_and_bound_to_original_invocation(damage: str) -> None:
    profile_id = uuid4()
    provenance = _provenance(_ORIGINAL_ID, _request(), profile_id=profile_id)
    payload = provenance.model_dump(mode="json")
    if damage == "old_schema":
        payload["schema_version"] = 1
    elif damage == "missing_request":
        del payload["admitted_request"]
    elif damage == "foreign_profile":
        payload["admitted_request"]["profile_id"] = str(uuid4())
    else:
        payload["admitted_request"]["definition_id"] = "other.operation"

    with pytest.raises(ValidationError):
        OperationAdmissionProvenance.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("substitution", ["identity", "payload"])
def test_substituted_provenance_refuses_before_journal_creation(tmp_path: Path, substitution: str) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable-state"
        journal, supervisor, _ = _services(root, profile.repository)
        request = _request()
        provenance = _provenance(_ORIGINAL_ID, request, profile_id=UUID(profile.bucket_id))
        if substitution == "identity":
            provenance = _provenance(_RETRY_ID, request, profile_id=UUID(profile.bucket_id))
        else:
            request = _request(value="altered-payload")

        with pytest.raises(ValueError, match="does not match stored invocation"):
            asyncio.run(supervisor.submit(request, operation_id=_ORIGINAL_ID, provenance=provenance))
        with pytest.raises(RepositoryError):
            asyncio.run(journal.load(_ORIGINAL_ID))
        asyncio.run(supervisor.shutdown())


@pytest.mark.parametrize("damaged", ["missing", "corrupt"])
def test_missing_or_corrupt_encrypted_provenance_refuses_stored_invocation(tmp_path: Path, damaged: str) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable-state"
        journal, supervisor, _ = _services(root, profile.repository)
        request = _request()
        provenance = _provenance(_ORIGINAL_ID, request, profile_id=UUID(profile.bucket_id))
        asyncio.run(supervisor.submit(request, operation_id=_ORIGINAL_ID, provenance=provenance))
        reference = asyncio.run(journal.load(_ORIGINAL_ID)).admission_provenance_reference
        assert reference is not None
        assert profile.repository.delete(OPERATION_SECURE_REFERENCE_NAMESPACE.namespace, reference)
        if damaged == "corrupt":
            profile.repository.save(
                namespace=OPERATION_SECURE_REFERENCE_NAMESPACE.namespace,
                object_key=reference,
                classification=OPERATION_SECURE_REFERENCE_NAMESPACE.sensitivity,
                schema_version=OPERATION_SECURE_REFERENCE_NAMESPACE.schema_version,
                written_at=_NOW,
                payload=b'{"substituted":"encrypted-record"}',
            )

        _, fresh_supervisor, _ = _services(root, profile.repository)
        with pytest.raises(RepositoryError, match="secure reference"):
            asyncio.run(fresh_supervisor.stored_invocation(_ORIGINAL_ID))
        asyncio.run(supervisor.shutdown())
        asyncio.run(fresh_supervisor.shutdown())


@pytest.mark.parametrize("replacement", [None, "f" * 64])
def test_journal_transition_cannot_remove_or_substitute_original_provenance_reference(
    tmp_path: Path, replacement: str | None
) -> None:
    journal = OperationJournalRepository(storage_root=tmp_path)
    original_reference = "e" * 64
    initial = _snapshot(revision=0, sequence=1).model_copy(
        update={"admission_provenance_reference": original_reference}
    )
    _claim_lease(tmp_path, _lease())
    asyncio.run(journal.create(initial, lease=_lease()))
    altered = _snapshot(revision=1, sequence=2).model_copy(update={"admission_provenance_reference": replacement})

    with pytest.raises(RepositoryError, match="provenance"):
        asyncio.run(journal.commit(altered, expected_revision=0, lease=_lease()))
    assert asyncio.run(journal.load(initial.operation_id)) == initial
