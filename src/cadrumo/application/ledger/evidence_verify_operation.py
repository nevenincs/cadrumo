"""Registered person-initiated check of whether one evidence record's stored bytes can be read.

A record added before the readability fact was kept reads as never checked. The
person asks for a check; the worker decrypts the bytes once, probes them with the
same capability the add and read paths use, and keeps the finding on the record
under its revision guard. Bytes no reader can read are a finding, not an error:
the record is kept as unreadable with the cause in the read path's vocabulary.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import PROJECTION_RESULT_MAX_BYTES

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.document_shape import DocumentShape
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.errors import AttachmentNotFoundError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
    terminal_receipt_matches,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.result_size import refuse_oversized_result
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from .evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from .evidence_port_identity import require_exact_evidence_ports
from .evidence_ports import LedgerEvidenceVerifyPorts, LedgerEvidenceVerifyPortsFactory
from .evidence_read_operation import LedgerEvidenceRecordProjection
from .evidence_readability import (
    EvidenceReadability,
    EvidenceUnreadableCause,
    readable_finding,
    unreadable_finding,
)
from .read_access import resolve_ledger_request_commit_access

LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID = "ledger.evidence.verify"
LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE = "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"
_PERSON_FRONTEND_ACTOR = "cli"
"""The audit label of a check a person's frontend asks for; an automation's is derived from its session."""

_EvidenceIdentity = Annotated[str, Field(min_length=1, max_length=64)]
_EvidenceEventId = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerEvidenceVerifyRequest(BaseModel):
    """Private exact-profile request to check one evidence record's stored bytes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    evidence_id: _EvidenceIdentity


class LedgerEvidenceVerifyChecked(BaseModel):
    """The record as kept after the check, carrying its readability finding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["checked"] = "checked"
    record: LedgerEvidenceRecordProjection
    bucket_event_ids: Annotated[tuple[_EvidenceEventId, ...], Field(min_length=1, max_length=1)]

    @model_validator(mode="after")
    def _record_was_checked(self) -> LedgerEvidenceVerifyChecked:
        if self.record.readability == "unchecked":
            raise ValueError("a checked evidence result carries the finding it kept")
        return self


class LedgerEvidenceVerifyRefusal(BaseModel):
    """Only the static missing-reference fact crosses the refusal detail door."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["refused"] = "refused"
    evidence_record_present: Literal[False] = False


class LedgerEvidenceVerifyProjection(BaseModel):
    """Exact-profile checked record or the finite missing-reference refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Annotated[LedgerEvidenceVerifyChecked | LedgerEvidenceVerifyRefusal, Field(discriminator="kind")]

    @model_validator(mode="after")
    def _correlate_record_profile(self) -> LedgerEvidenceVerifyProjection:
        if isinstance(self.outcome, LedgerEvidenceVerifyChecked) and self.outcome.record.bucket_id != str(
            self.profile_id
        ):
            raise ValueError("evidence check record belongs to another profile")
        return self


class LedgerEvidenceVerifyExecutionResult(BaseModel):
    """Private encrypted result wrapper carrying the projection's exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerEvidenceVerifyProjection

    @model_validator(mode="after")
    def _correlate_result_profile(self) -> LedgerEvidenceVerifyExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("evidence check execution result belongs to another profile")
        return self


def _check_evidence_readability(
    record: PurchaseInvoiceEvidence,
    *,
    ports: LedgerEvidenceVerifyPorts,
) -> EvidenceReadability:
    """Decrypt the record's bytes once, probe them, and return the finding.

    The bytes stay in this frame and are never kept. Bytes custody does not hold
    and bytes no reader recognises are both findings, named by their cause.
    """
    checked_at = now()
    store = ports.attachment_store
    try:
        manifest = store.load_manifest(record.attachment_id)
        data = store.read_bytes(manifest.sha256)
    except AttachmentNotFoundError:
        return unreadable_finding(
            cause=EvidenceUnreadableCause.BYTES_UNAVAILABLE,
            checked_sha256=record.attachment_id,
            checked_at=checked_at,
        )
    shape = ports.evidence.document_shape_probe(data)
    del data
    if shape is DocumentShape.UNKNOWN:
        return unreadable_finding(
            cause=EvidenceUnreadableCause.BYTES_UNRECOGNIZED,
            checked_sha256=record.attachment_id,
            checked_at=checked_at,
        )
    return readable_finding(shape=shape, checked_sha256=record.attachment_id, checked_at=checked_at)


@dataclass(frozen=True, slots=True)
class _PreparedCheck:
    service: PurchaseInvoiceEvidenceService
    finding: EvidenceReadability


class LedgerEvidenceVerifyExecutor:
    """Check one record's stored bytes and keep the finding in the exact active profile."""

    def __init__(
        self,
        ports_factory: LedgerEvidenceVerifyPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the exact-profile check capability factory and the session host's caller reader."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[LedgerEvidenceVerifyRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Probe in a no-effect preflight, then keep the finding behind the effect fence."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request_definition_id=request.definition_id,
            request_subject_ref=request.subject_ref,
            context=context,
            bucket_id=bucket_id,
        )
        await context.events.phase(LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=_PERSON_FRONTEND_ACTOR)

        def preflight() -> _PreparedCheck | None:
            ports = self._ports_factory(bucket_id=bucket_id)
            _require_exact_verify_ports(ports, bucket_id=bucket_id)
            service = PurchaseInvoiceEvidenceService(ports=ports.evidence)
            try:
                record = service.view(bucket_id=bucket_id, evidence_id=payload.evidence_id)
            except PurchaseInvoiceEvidenceNotFoundError:
                return None
            if record.bucket_id != bucket_id or record.evidence_id != payload.evidence_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return _PreparedCheck(service=service, finding=_check_evidence_readability(record, ports=ports))

        async def capture() -> str | OperationRefusalEvidence:
            prepared = await asyncio.to_thread(preflight)
            if prepared is None:
                await context.events.effect(OperationEffect.NONE)
                refused = LedgerEvidenceVerifyExecutionResult(
                    profile_id=payload.profile_id,
                    result=LedgerEvidenceVerifyProjection(
                        profile_id=payload.profile_id, outcome=LedgerEvidenceVerifyRefusal()
                    ),
                )
                detail_ref = await context.operands.put(refused, written_at=now())
                return OperationRefusalEvidence(
                    refusal_code=LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE,
                    detail_ref=detail_ref,
                )
            async with context.cancellation.irreversible_section():
                # The catalogue and its event commit as one guarded batch; the
                # outcome is unknown from here until that batch has returned.
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(
                    prepared.service.record_readability,
                    bucket_id=bucket_id,
                    evidence_id=payload.evidence_id,
                    finding=prepared.finding,
                    actor=actor,
                )
                await context.events.effect(OperationEffect.UPDATED)
                if result.record.readability != prepared.finding or result.record.evidence_id != payload.evidence_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                execution_result = LedgerEvidenceVerifyExecutionResult(
                    profile_id=payload.profile_id,
                    result=LedgerEvidenceVerifyProjection(
                        profile_id=payload.profile_id,
                        outcome=LedgerEvidenceVerifyChecked(
                            record=LedgerEvidenceRecordProjection.from_record(result.record),
                            bucket_event_ids=result.bucket_event_ids,
                        ),
                    ),
                )
                refuse_oversized_result(execution_result, PROJECTION_RESULT_MAX_BYTES - 128)
                return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-verify")


def _require_exact_verify_ports(ports: LedgerEvidenceVerifyPorts, *, bucket_id: str) -> None:
    """Require the byte reader to share the evidence catalogue's exact profile custody."""
    require_exact_evidence_ports(ports.evidence, bucket_id=bucket_id)
    evidence_objects = getattr(ports.evidence.evidence_repository, "secure_object_repository", None)
    if getattr(ports.attachment_store, "objects", None) is not evidence_objects:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_worker_identity(
    *,
    request_definition_id: str,
    request_subject_ref: str,
    context: OperationExecutorContext,
    bucket_id: str,
) -> None:
    subject = profile_operation_subject(bucket_id)
    if (
        request_definition_id != LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID
        or context.identity.definition_id != LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID
        or request_subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the closed outcome matching its exact terminal receipt."""
    if type(result) is not LedgerEvidenceVerifyExecutionResult:
        raise ValueError("invalid ledger evidence check execution result")
    subject_ref = profile_operation_subject(str(result.profile_id))
    if isinstance(result.result.outcome, LedgerEvidenceVerifyRefusal):
        if (
            not terminal_receipt_matches(
                receipt,
                definition_id=LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
                subject_ref=subject_ref,
                condition=OperationTerminalCondition.REFUSED,
                effect=OperationEffect.NONE,
            )
            or receipt.refusal_ref != LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
        ):
            raise ValueError("evidence check refusal has an incompatible terminal receipt")
        return result.result
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        effect=OperationEffect.UPDATED,
        message="evidence check result has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_evidence_verify_definition(
    ports_factory: LedgerEvidenceVerifyPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare the person-initiated check of one evidence record's stored bytes."""
    return build_single_phase_definition(
        definition_id=LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceVerifyRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerEvidenceVerifyExecutionResult,
        executor_type=LedgerEvidenceVerifyExecutor,
        build=lambda: LedgerEvidenceVerifyExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        refusal_detail_codes=frozenset({LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE}),
    )


def resolve_ledger_evidence_verify_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure and COMMIT for an evidence check."""
    return resolve_ledger_request_commit_access(
        request,
        context,
        definition_id=LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceVerifyRequest,
    )


def build_ledger_evidence_verify_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bounded check request/result, whole-profile access, and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceVerifyProjection,
        result_projector=_project_result,
        access_resolver=resolve_ledger_evidence_verify_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE",
    "LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID",
    "LedgerEvidenceVerifyChecked",
    "LedgerEvidenceVerifyExecutionResult",
    "LedgerEvidenceVerifyExecutor",
    "LedgerEvidenceVerifyProjection",
    "LedgerEvidenceVerifyRefusal",
    "LedgerEvidenceVerifyRequest",
    "build_ledger_evidence_verify_definition",
    "build_ledger_evidence_verify_registration",
    "resolve_ledger_evidence_verify_access",
]
