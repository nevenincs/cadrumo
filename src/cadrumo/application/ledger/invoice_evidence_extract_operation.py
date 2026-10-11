"""Exact-profile invoice evidence extraction and consent operation."""

from __future__ import annotations

import asyncio
from typing import Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.config_support import LLMProvider
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
)
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.execution_actor import OperationExecutionCallerReader, execution_admitted_on_mcp
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .agent_reader_locality import require_reader_on_this_machine
from .evidence import PurchaseInvoiceEvidenceService
from .evidence_followup_contracts import LedgerEvidenceReviewSummaryProjection
from .evidence_followup_operation import review_extraction_draft
from .extraction_draft_store import StoredExtractionDraft
from .invoice_confirmation import (
    invoice_draft_review_sha256,
)
from .invoice_draft_extraction import extract_invoice_draft_from_evidence
from .invoice_draft_extraction_ports import EvidenceConsentProof
from .invoice_draft_records import InvoiceDraft
from .invoice_evidence_consent_custody import InvoiceEvidenceConsentCustody
from .invoice_evidence_operation import (
    InvoiceEvidenceOperationPorts,
    InvoiceEvidenceOperationPortsFactory,
    InvoiceEvidenceReference,
    check_invoice_evidence_result_size,
    invoice_evidence_operation_capabilities,
    require_bound_invoice_evidence_ports,
    require_invoice_evidence_terminal_success,
    resolve_invoice_evidence_authority_legends,
)
from .invoice_evidence_operation_dtos import (
    InvoiceDraftProjectionV1,
    LabelReadingFallbackProjectionV1,
)
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access

LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID = "ledger.evidence.extract"


_EXTRACT_CONSENT_SURFACE = "runtime:ledger.evidence.extract"
_DRAFT_EXTRACTOR = extract_invoice_draft_from_evidence.__name__
"""Names the function that produced the draft; which reader read each field is on its provenance."""


class LedgerEvidenceExtractRequest(BaseModel):
    """One source reference and optional per-invocation off-host consent.

    ``off_host_provider`` and ``acknowledge_off_host`` are the person's consent
    to send this one document to a hosted model. An agent cannot give it: a
    request that names an off-host provider is refused on the MCP frontend.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: InvoiceEvidenceReference | None = None
    attachment_id: InvoiceEvidenceReference | None = None
    off_host_provider: LLMProvider | None = None
    acknowledge_off_host: bool = False

    @model_validator(mode="after")
    def _one_reference_and_explicit_consent(self) -> Self:
        if (self.evidence_id is None) == (self.attachment_id is None):
            raise ValueError("exactly one evidence or attachment reference is required")
        if self.off_host_provider is None:
            if self.acknowledge_off_host:
                raise ValueError("off-host acknowledgement requires an off-host provider")
        elif self.off_host_provider is LLMProvider.LOCAL or not self.acknowledge_off_host or self.evidence_id is None:
            raise ValueError("off-host reading requires a stored evidence record and per-invocation acknowledgement")
        return self


class LedgerEvidenceExtractProjection(BaseModel):
    """One extracted draft, its verified raw source and exact review digest.

    A person's execution seals the full ``draft``, with the text the reader
    took from the document. An agent's seals ``draft_summary`` in its place:
    the same reading's figures, findings and confirmation blockers, with each
    text named as withheld. An extraction stores no draft, so the summary is
    the whole of what an agent holds of this reading.

    ``label_reading_fallback`` sits beside the draft, outside the digest the
    review is bound to, and says when fields read as unread because the model
    fill did not run.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: InvoiceEvidenceReference | None = None
    attachment_id: InvoiceEvidenceReference | None = None
    source_sha256: Hex64Str
    draft_review_sha256: Hex64Str
    off_host_provider: LLMProvider | None = None
    consent_audit_effect: OperationEffect
    draft: InvoiceDraftProjectionV1 | None = None
    draft_summary: LedgerEvidenceReviewSummaryProjection | None = None
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None = None

    @model_validator(mode="after")
    def _one_reading_and_no_agent_read_off_host(self) -> Self:
        if (self.draft is None) == (self.draft_summary is None):
            raise ValueError("an extraction result carries the full draft or its summary, never both or neither")
        if self.draft_summary is not None and (
            self.off_host_provider is not None or self.draft_summary.profile_id != self.profile_id
        ):
            raise ValueError("an agent's extraction summary belongs to this profile and to a read on this machine")
        return self

    def person_draft(self) -> InvoiceDraftProjectionV1:
        """Return the full draft a person's execution sealed, refusing a result sealed for an agent."""
        if self.draft is None:
            raise ValueError("this extraction result was sealed for an agent and carries no document text")
        return self.draft


class LedgerEvidenceExtractExecutionResult(BaseModel):
    """Encrypted worker draft and consent effect witness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceExtractProjection


class LedgerEvidenceExtractExecutor:
    """Extract one verified source with optional one-invocation off-host consent."""

    def __init__(
        self,
        ports_factory: InvoiceEvidenceOperationPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the exact-profile evidence capability factory and the session host's caller reader."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self, request: OperationRequest[LedgerEvidenceExtractRequest], context: OperationExecutorContext
    ) -> str:
        """Extract with actual consent writes, then capture the closed draft."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        for_agent = execution_admitted_on_mcp(self._execution_caller_reader, context)
        if for_agent and payload.off_host_provider is not None:
            # The access resolver refuses this first; the read itself must not
            # depend on that having happened.
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        await context.events.phase(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        custody = InvoiceEvidenceConsentCustody(context) if payload.off_host_provider is not None else None

        async def extract_and_capture() -> str:
            result = await asyncio.to_thread(
                _extract_invoice_evidence_projection,
                payload,
                bucket_id=bucket_id,
                ports_factory=self._ports_factory,
                context=context,
                custody=custody,
                for_agent=for_agent,
            )
            return await context.operands.put(
                LedgerEvidenceExtractExecutionResult(profile_id=payload.profile_id, result=result),
                written_at=now(),
            )

        return await await_cancellation_complete(extract_and_capture(), task_name="ledger-evidence-extract")


def _extract_invoice_evidence_projection(
    payload: LedgerEvidenceExtractRequest,
    *,
    bucket_id: str,
    ports_factory: InvoiceEvidenceOperationPortsFactory,
    context: OperationExecutorContext,
    custody: InvoiceEvidenceConsentCustody | None,
    for_agent: bool,
) -> LedgerEvidenceExtractProjection:
    ports = ports_factory(
        bucket_id=bucket_id,
        before_consent_save=None if custody is None else custody.before_save,
        after_consent_save=None if custody is None else custody.after_save,
    )
    require_bound_invoice_evidence_ports(ports, bucket_id=bucket_id)
    if for_agent:
        require_reader_on_this_machine(ports.settings)
    source_sha256 = _require_invoice_evidence_source(payload, ports=ports, bucket_id=bucket_id)
    consent_token = _mint_extract_consent(payload, ports=ports, source_sha256=source_sha256)
    draft = extract_invoice_draft_from_evidence(
        bucket_id=bucket_id,
        evidence_id=payload.evidence_id,
        attachment_id=payload.attachment_id,
        settings=ports.settings,
        off_host_provider=payload.off_host_provider,
        consent_token=consent_token,
        ports=ports.extraction_ports,
        operation=context.authority_operation,
        legends=resolve_invoice_evidence_authority_legends(context),
    )
    result = LedgerEvidenceExtractProjection(
        profile_id=payload.profile_id,
        evidence_id=payload.evidence_id,
        attachment_id=payload.attachment_id,
        source_sha256=source_sha256,
        draft_review_sha256=invoice_draft_review_sha256(draft),
        off_host_provider=payload.off_host_provider,
        consent_audit_effect=OperationEffect.NONE if custody is None else custody.current_effect,
        draft=None if for_agent else InvoiceDraftProjectionV1.from_draft(draft),
        draft_summary=_agent_draft_summary(payload, draft, context) if for_agent else None,
        label_reading_fallback=(
            None
            if (fallback := draft.label_reading_fallback) is None
            else LabelReadingFallbackProjectionV1.from_fallback(fallback)
        ),
    )
    check_invoice_evidence_result_size(result)
    return result


def _agent_draft_summary(
    payload: LedgerEvidenceExtractRequest,
    draft: InvoiceDraft,
    context: OperationExecutorContext,
) -> LedgerEvidenceReviewSummaryProjection:
    """Reduce the reading to what an agent may hold, by the rules the pending-review summary uses."""
    reference = payload.evidence_id if payload.evidence_id is not None else payload.attachment_id
    if reference is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    # The complete review is built once and stays in worker memory; the
    # document's text never enters the result operand.
    review = review_extraction_draft(
        payload.profile_id,
        StoredExtractionDraft(
            evidence_reference=reference,
            draft=draft,
            extractor=_DRAFT_EXTRACTOR,
            drafted_at=now(),
            label_reading_fallback=draft.label_reading_fallback,
        ),
        context.authority_operation,
    )
    return LedgerEvidenceReviewSummaryProjection.from_review_view(review)


def _require_invoice_evidence_source(
    payload: LedgerEvidenceExtractRequest,
    *,
    ports: InvoiceEvidenceOperationPorts,
    bucket_id: str,
) -> str:
    source_sha256 = payload.attachment_id
    if payload.evidence_id is not None:
        record = PurchaseInvoiceEvidenceService(ports=ports.evidence_ports).view(
            bucket_id=bucket_id,
            evidence_id=payload.evidence_id,
        )
        if (
            record.bucket_id != bucket_id
            or record.evidence_id != payload.evidence_id
            or record.attachment_id != record.source_sha256
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        source_sha256 = record.source_sha256
    if source_sha256 is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return source_sha256


def _mint_extract_consent(
    payload: LedgerEvidenceExtractRequest,
    *,
    ports: InvoiceEvidenceOperationPorts,
    source_sha256: str,
) -> EvidenceConsentProof | None:
    if payload.off_host_provider is None:
        return None
    consent_token = ports.mint_consent(
        payload.off_host_provider,
        payload.acknowledge_off_host,
        _EXTRACT_CONSENT_SURFACE,
        source_sha256,
    )
    if consent_token.evidence_content_address != source_sha256:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return consent_token


def build_ledger_evidence_extract_definition(
    ports_factory: InvoiceEvidenceOperationPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Register on-host extraction and explicit per-invocation off-host reading.

    ``execution_caller_reader`` names the frontend that admitted an execution,
    so an agent's read stays on this machine and seals a result without the
    document's text.
    """
    return build_single_phase_definition(
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceExtractRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerEvidenceExtractExecutionResult,
        executor_type=LedgerEvidenceExtractExecutor,
        build=lambda: LedgerEvidenceExtractExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=invoice_evidence_operation_capabilities(mutates=False, off_host_optional=True),
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def _project_extract(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceExtractExecutionResult:
        raise ValueError("invalid invoice extraction result")
    projection = result.result
    require_invoice_evidence_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
        effects=frozenset({projection.consent_audit_effect}),
    )
    if (
        projection.consent_audit_effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or (projection.profile_id != result.profile_id)
        or (projection.off_host_provider is None and projection.consent_audit_effect is not OperationEffect.NONE)
    ):
        raise ValueError("invoice extraction result has incompatible consent effect or profile")
    return projection


def _resolve_extract_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if (
        request.definition_id != LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID
        or type(request.payload) is not LedgerEvidenceExtractRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    off_host = request.payload.off_host_provider is not None
    if off_host and context.frontend is OperationFrontendProjection.MCP:
        # Sending the person's document to a hosted model is their consent to
        # give, for that document, and no field an agent sets can stand for it.
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    resolve = resolve_ledger_commit_access if off_host else resolve_ledger_read_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_evidence_extract_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind all-period tax disclosure and the exact consent effect witness."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerEvidenceExtractRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=3,
            model_type=LedgerEvidenceExtractProjection,
        ),
        result_projector=_project_extract,
        access_resolver=_resolve_extract_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID",
    "LedgerEvidenceExtractExecutionResult",
    "LedgerEvidenceExtractExecutor",
    "LedgerEvidenceExtractProjection",
    "LedgerEvidenceExtractRequest",
    "build_ledger_evidence_extract_definition",
    "build_ledger_evidence_extract_registration",
]
