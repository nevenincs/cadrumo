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
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence import PurchaseInvoiceEvidenceService
from .invoice_confirmation import (
    invoice_draft_review_sha256,
)
from .invoice_draft_extraction import extract_invoice_draft_from_evidence
from .invoice_draft_extraction_ports import EvidenceConsentProof
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
from .read_access import resolve_ledger_read_access

LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID = "ledger.evidence.extract"


_EXTRACT_CONSENT_SURFACE = "runtime:ledger.evidence.extract"


class LedgerEvidenceExtractRequest(BaseModel):
    """One source reference and optional per-invocation off-host consent."""

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
    """Full draft plus verified raw source and exact review digest.

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
    draft: InvoiceDraftProjectionV1
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None = None


class LedgerEvidenceExtractExecutionResult(BaseModel):
    """Encrypted worker draft and consent effect witness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceExtractProjection


class LedgerEvidenceExtractExecutor:
    """Extract one verified source with optional one-invocation off-host consent."""

    def __init__(self, ports_factory: InvoiceEvidenceOperationPortsFactory) -> None:
        """Bind the exact-profile evidence capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[LedgerEvidenceExtractRequest], context: OperationExecutorContext
    ) -> str:
        """Extract with actual consent writes, then capture the closed draft."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
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
) -> LedgerEvidenceExtractProjection:
    ports = ports_factory(
        bucket_id=bucket_id,
        before_consent_save=None if custody is None else custody.before_save,
        after_consent_save=None if custody is None else custody.after_save,
    )
    require_bound_invoice_evidence_ports(ports, bucket_id=bucket_id)
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
        draft=InvoiceDraftProjectionV1.from_draft(draft),
        label_reading_fallback=(
            None
            if (fallback := draft.label_reading_fallback) is None
            else LabelReadingFallbackProjectionV1.from_fallback(fallback)
        ),
    )
    check_invoice_evidence_result_size(result)
    return result


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
) -> OperationDefinition:
    """Register on-host extraction and explicit per-invocation off-host reading."""
    return OperationDefinition(
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceExtractRequest,
        result_type=LedgerEvidenceExtractExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerEvidenceExtractRequest,
            executor_type=LedgerEvidenceExtractExecutor,
            build=lambda: LedgerEvidenceExtractExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=invoice_evidence_operation_capabilities(mutates=False, off_host_optional=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
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
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    if request.payload.off_host_provider is None:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


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
            schema_version=2,
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
