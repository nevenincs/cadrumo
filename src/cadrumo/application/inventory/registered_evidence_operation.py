"""Registered exact-profile custody of the documents behind an inventory purchase.

A purchase names its documents by digest. The worker reads the file the operator
chose, stores its bytes in the profile's encrypted attachment custody and returns
the digest, so no frontend computes one and no path stands in for evidence.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ..ledger.evidence import ingest_evidence_file
from ..ledger.evidence_port_identity import require_exact_evidence_ports
from ..ledger.evidence_ports import LedgerEvidencePorts, LedgerEvidencePortsFactory
from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError

INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID = "ledger.inventory.evidence.add"

_PERSON_FRONTEND_ACTOR = "cli"
"""The audit label of a document a person's frontend adds; an automation's is derived from its session."""
_REFERENCE_PREFIX = "attachment:"
_EvidencePath = Annotated[str, Field(min_length=1, max_length=4_096)]


class InventoryEvidenceAddRequest(BaseModel):
    """One document the operator chose, named only so the worker can read it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    source_path: _EvidencePath
    source_directory: _EvidencePath


class InventoryEvidenceAddProjection(BaseModel):
    """What a purchase needs to name the document now held in custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reference: str
    content_digest: ContentDigest

    @model_validator(mode="after")
    def _reference_names_the_digest(self) -> InventoryEvidenceAddProjection:
        if self.reference != f"{_REFERENCE_PREFIX}{self.content_digest}":
            raise ValueError("inventory evidence reference does not name its digest")
        return self


class InventoryEvidenceAddExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InventoryEvidenceAddProjection


class InventoryEvidenceAddExecutor:
    """Place one document in exact-profile attachment custody."""

    def __init__(
        self,
        ports_factory: LedgerEvidencePortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the exact-profile custody capability factory and the session host's caller reader."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[InventoryEvidenceAddRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Store the bytes and return their content-addressed identity."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID
            or context.identity.definition_id != INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=_PERSON_FRONTEND_ACTOR)

        def preflight() -> LedgerEvidencePorts:
            ports = self._ports_factory(bucket_id=bucket_id)
            require_exact_evidence_ports(ports, bucket_id=bucket_id)
            return ports

        async def capture() -> str:
            ports = await asyncio.to_thread(preflight)
            async with context.cancellation.irreversible_section():
                # The bytes and their manifest are durable once ingestion starts.
                await context.events.effect(OperationEffect.UNKNOWN)
                digest = await asyncio.to_thread(
                    ingest_evidence_file,
                    ports=ports,
                    bucket_id=bucket_id,
                    source_path=payload.source_path,
                    source_directory=Path(payload.source_directory),
                    now=now(),
                    actor=actor,
                )
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(
                    InventoryEvidenceAddExecutionResult(
                        result=InventoryEvidenceAddProjection(
                            profile_id=payload.profile_id,
                            reference=f"{_REFERENCE_PREFIX}{digest}",
                            content_digest=digest,
                        )
                    ),
                    written_at=now(),
                )

        return await await_cancellation_complete(capture(), task_name="ledger-inventory-evidence-add")


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not InventoryEvidenceAddExecutionResult:
        raise ValueError("invalid inventory evidence add result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.UPDATED,
        message="inventory evidence add has an incompatible terminal receipt",
    )
    return result.result


def build_inventory_evidence_add_definition(
    ports_factory: LedgerEvidencePortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare one bounded exact-profile custody operation for a purchase document."""
    return build_single_phase_definition(
        definition_id=INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        request_type=InventoryEvidenceAddRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InventoryEvidenceAddExecutionResult,
        executor_type=InventoryEvidenceAddExecutor,
        build=lambda: InventoryEvidenceAddExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES,
    )


def resolve_inventory_evidence_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure and COMMIT, as adding any ledger document does."""
    if request.definition_id != INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, InventoryEvidenceAddRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_inventory_evidence_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, whole-profile access and exact receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InventoryEvidenceAddProjection,
        result_projector=_project_result,
        access_resolver=resolve_inventory_evidence_add_access,
    )


__all__ = [
    "INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID",
    "InventoryEvidenceAddExecutionResult",
    "InventoryEvidenceAddExecutor",
    "InventoryEvidenceAddProjection",
    "InventoryEvidenceAddRequest",
    "build_inventory_evidence_add_definition",
    "build_inventory_evidence_add_registration",
    "resolve_inventory_evidence_add_access",
]
