"""Admission and durable request persistence for the operation supervisor."""

from __future__ import annotations

from datetime import datetime
from typing import override

from pydantic import BaseModel

from ...core.hashing import content_hash_hex
from ...core.operations import OperationLifecycle
from ..user_profile.access_contracts import AccessAction
from ._supervisor_host import SupervisorHost
from .capabilities import OperationRequestStoragePolicy
from .models import OperationId, OperationIdentity, OperationRequest, new_operation_id
from .operation_definition import OperationDefinition
from .persistence.idempotency import OperationIdempotencyClaim
from .persistence.journal import OperationPersistedSnapshot
from .provenance import OperationAdmissionProvenance
from .registry import OperationPublicDefinitionContractV1
from .secret_submission import OperationSecretRequirement


class SupervisorSubmissionMixin(SupervisorHost):
    """Own identity authorization, request storage, and idempotent admission."""

    @override
    async def submit[RequestPayloadT: BaseModel](
        self: SupervisorHost,
        request: OperationRequest[RequestPayloadT],
        *,
        operation_id: OperationId | None = None,
        provenance: OperationAdmissionProvenance | None = None,
    ) -> OperationId:
        """Persist one validated operation request without starting execution."""
        definition, definition_contract, identity, now = await self._authorize_submission(
            request, operation_id=operation_id, provenance=provenance
        )
        request_storage, request_reference, credential_free_request_json = await self._store_submission_request(
            request, definition, now
        )
        secret_requirement = self._submission_secret_requirement(definition, identity, now)
        return await self._persist_submission(
            request=request,
            definition_contract=definition_contract,
            identity=identity,
            now=now,
            request_storage=request_storage,
            request_reference=request_reference,
            credential_free_request_json=credential_free_request_json,
            secret_requirement=secret_requirement,
            provenance=provenance,
        )

    @override
    async def _authorize_submission[RequestPayloadT: BaseModel](
        self: SupervisorHost,
        request: OperationRequest[RequestPayloadT],
        *,
        operation_id: OperationId | None,
        provenance: OperationAdmissionProvenance | None,
    ) -> tuple[OperationDefinition, OperationPublicDefinitionContractV1, OperationIdentity, datetime]:
        definition = self.registry.lookup(request.definition_id)
        definition_contract = self.registry.lookup_public_contract(request.definition_id)
        self._validate_request_payload(request, definition.request_type)
        now = self._clock()
        identity = OperationIdentity(
            operation_id=operation_id or new_operation_id(),
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
        )
        if self._execution_authority is not None:
            await self._execution_authority.require(identity=identity, request=request, action=AccessAction.SUBMIT)
        if provenance is not None:
            provenance.require_invocation(identity, request)
            if self._operands is None:
                raise ValueError("operation admission provenance requires its encrypted operand store")
        return definition, definition_contract, identity, now

    @override
    async def _store_submission_request[RequestPayloadT: BaseModel](
        self: SupervisorHost,
        request: OperationRequest[RequestPayloadT],
        definition: OperationDefinition,
        now: datetime,
    ) -> tuple[OperationRequestStoragePolicy, str, str | None]:
        request_storage = definition.capabilities.request_storage
        if request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE:
            if self._operands is None:
                raise ValueError("secure-reference request storage requires an operand store")
            request_reference = await self._operands.put(request.payload, written_at=now)
            credential_free_request_json = None
        else:
            credential_free_request_json = request.payload.model_dump_json()
            request_reference = content_hash_hex(request.payload.model_dump(mode="json"))
        return request_storage, request_reference, credential_free_request_json

    @override
    @staticmethod
    def _submission_secret_requirement(
        definition: OperationDefinition,
        identity: OperationIdentity,
        now: datetime,
    ) -> OperationSecretRequirement | None:
        declaration = definition.ephemeral_secret
        if declaration is None:
            return None
        return OperationSecretRequirement(
            identity=identity,
            interaction_id=content_hash_hex(
                {
                    "schema_version": 1,
                    "identity": identity.model_dump(mode="json"),
                    "revision": 0,
                    "secret_kind": declaration.secret_kind,
                }
            ),
            revision=0,
            secret_kind=declaration.secret_kind,
            expires_at=now + declaration.lifetime,
        )

    @override
    async def _persist_submission[RequestPayloadT: BaseModel](
        self: SupervisorHost,
        *,
        request: OperationRequest[RequestPayloadT],
        definition_contract: OperationPublicDefinitionContractV1,
        identity: OperationIdentity,
        now: datetime,
        request_storage: OperationRequestStoragePolicy,
        request_reference: str,
        credential_free_request_json: str | None,
        secret_requirement: OperationSecretRequirement | None,
        provenance: OperationAdmissionProvenance | None,
    ) -> OperationId:
        claim = (
            OperationIdempotencyClaim.bind(
                identity=identity, idempotency_key=request.idempotency_key, request_reference=request_reference
            )
            if request.idempotency_key
            else None
        )
        existing_operation_id = await self._resolve_idempotency(claim)
        if existing_operation_id is not None:
            return existing_operation_id
        provenance_reference = (
            await self._operands.put(provenance, written_at=now)
            if provenance is not None and self._operands is not None
            else None
        )
        lease = self._candidate(identity, now)
        replayed_operation_id = await self._acquire_submission_lease(lease, claim=claim)
        if replayed_operation_id is not None:
            return replayed_operation_id
        self._leases_by_operation[identity.operation_id] = lease
        snapshot = OperationPersistedSnapshot(
            identity=identity,
            definition_contract_digest=definition_contract.definition_contract_digest,
            request_storage=request_storage,
            request_reference=request_reference,
            admission_provenance_reference=provenance_reference,
            credential_free_request_json=credential_free_request_json,
            secret_requirement=secret_requirement,
            revision=0,
            lifecycle=OperationLifecycle.CREATED,
            started_at=now,
            updated_at=now,
            execution_deadline=None,
            cleanup_deadline=None,
            cancellation_requested_at=None,
            cancellation_acknowledged_at=None,
            cancellation_deferred=False,
            idempotency_claim=claim,
        )
        try:
            created_operation_id = await self._journal.create(snapshot, lease=lease)
        except BaseException:
            await self._release_exact_lease(lease, observed_at=self._clock())
            raise
        if created_operation_id != identity.operation_id:
            await self._release_exact_lease(lease, observed_at=self._clock())
        return created_operation_id


__all__ = ["SupervisorSubmissionMixin"]
