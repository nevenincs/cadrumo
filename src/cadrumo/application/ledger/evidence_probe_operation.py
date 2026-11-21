"""Registered exact-profile read of what a file from this computer is, before it is added as evidence.

When the person adds a document to a movement that has no purchase invoice yet,
they say whether it is that invoice or an ordinary document. This read lets a
frontend show, beside that choice, the kind the file's own bytes support: the
add path's admission and shape probe, run on the file without storing it. A
file the add would refuse is refused here in the same terms. The derived kind
is only offered; the person's choice is what is staged.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import PROJECTION_RESULT_MAX_BYTES

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.document_shape import DocumentShape
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG, host_filled_schema
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.result_size import refuse_oversized_result
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence import admit_evidence_file, readable_evidence_file_shape
from .evidence_kind_proposal import EvidenceKindProposalV1, derived_evidence_kind
from .evidence_port_identity import require_exact_evidence_ports
from .evidence_ports import LedgerEvidencePortsFactory
from .read_access import resolve_ledger_request_read_access

LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID = "ledger.evidence.probe"

_EvidencePath = Annotated[str, Field(min_length=1, max_length=4_096)]


class LedgerEvidenceProbeRequest(BaseModel):
    """Private exact-profile request naming one local file the person picked."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    source_path: _EvidencePath
    source_directory: _EvidencePath = Field(json_schema_extra=host_filled_schema())


class LedgerEvidenceProbeProjection(BaseModel):
    """What the file's bytes were recognised as, and the kind they support, if any."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    document_shape: DocumentShape
    """The readable shape the probe recognised; a file it cannot read is refused instead."""
    kind_proposal: EvidenceKindProposalV1 | None
    """The kind the bytes support, offered beside the person's choice; ``None`` when they support none."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _proposal_follows_the_shape(self) -> Self:
        if self.document_shape is DocumentShape.UNKNOWN:
            raise ValueError("an evidence probe result names a recognised document shape")
        if self.kind_proposal != derived_evidence_kind(self.document_shape):
            raise ValueError("an evidence probe proposes exactly the kind its shape supports")
        return self


class LedgerEvidenceProbeExecutionResult(BaseModel):
    """Private encrypted result wrapper carrying the projection's exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceProbeProjection

    @model_validator(mode="after")
    def _correlate_result_profile(self) -> LedgerEvidenceProbeExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence probe execution result belongs to another profile")
        return self


class LedgerEvidenceProbeExecutor:
    """Admit and probe one local file in the exact active profile, storing nothing."""

    def __init__(self, ports_factory: LedgerEvidencePortsFactory) -> None:
        """Bind the exact-profile evidence capability factory whose shape probe the add path uses."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceProbeRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Refuse a file the add would refuse; otherwise answer its shape and supported kind."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def probe() -> LedgerEvidenceProbeExecutionResult:
            ports = self._ports_factory(bucket_id=bucket_id)
            require_exact_evidence_ports(ports, bucket_id=bucket_id)
            shape = readable_evidence_file_shape(
                ports=ports,
                admitted=admit_evidence_file(payload.source_path, Path(payload.source_directory)),
            )
            result = LedgerEvidenceProbeExecutionResult(
                profile_id=payload.profile_id,
                result=LedgerEvidenceProbeProjection(
                    profile_id=payload.profile_id,
                    document_shape=shape,
                    kind_proposal=derived_evidence_kind(shape),
                ),
            )
            refuse_oversized_result(result, PROJECTION_RESULT_MAX_BYTES - 128)
            return result

        async def capture() -> str:
            result = await asyncio.to_thread(probe)
            return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-probe")


def _require_worker_identity(
    *,
    request_definition_id: str,
    request_subject_ref: str,
    context: OperationExecutorContext,
    bucket_id: str,
) -> None:
    subject = profile_operation_subject(bucket_id)
    if (
        request_definition_id != LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID
        or context.identity.definition_id != LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID
        or request_subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the exact probe result carried by its successful no-effect receipt."""
    if type(result) is not LedgerEvidenceProbeExecutionResult:
        raise ValueError("invalid ledger evidence probe execution result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        effect=OperationEffect.NONE,
        message="evidence probe result has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_evidence_probe_definition(ports_factory: LedgerEvidencePortsFactory) -> OperationDefinition:
    """Declare the read of what one picked local file is, before it is added as evidence."""
    return build_single_phase_definition(
        definition_id=LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceProbeRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerEvidenceProbeExecutionResult,
        executor_type=LedgerEvidenceProbeExecutor,
        build=lambda: LedgerEvidenceProbeExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_evidence_probe_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile read access for the probe of one picked file."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceProbeRequest,
    )


def build_ledger_evidence_probe_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bounded probe request/result, whole-profile read access, and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceProbeProjection,
        result_projector=_project_result,
        access_resolver=resolve_ledger_evidence_probe_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID",
    "LedgerEvidenceProbeExecutionResult",
    "LedgerEvidenceProbeExecutor",
    "LedgerEvidenceProbeProjection",
    "LedgerEvidenceProbeRequest",
    "build_ledger_evidence_probe_definition",
    "build_ledger_evidence_probe_registration",
    "resolve_ledger_evidence_probe_access",
]
