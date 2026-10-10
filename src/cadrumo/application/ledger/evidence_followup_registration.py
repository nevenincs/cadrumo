"""Operation registration and receipt-bound projections for evidence follow-up reads."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceAttachmentQueueExecutionResult,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewExecutionResult,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListExecutionResult,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceFollowupOperationPorts,
    LedgerEvidenceReviewListExecutionResult,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewSummaryExecutionResult,
    LedgerEvidenceReviewSummaryProjection,
    LedgerEvidenceReviewViewExecutionResult,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from .evidence_followup_operation import (
    LedgerEvidenceAttachmentQueueExecutor,
    LedgerEvidenceAttachmentViewExecutor,
    LedgerEvidenceConsentListExecutor,
    LedgerEvidenceReviewListExecutor,
    LedgerEvidenceReviewSummaryExecutor,
    LedgerEvidenceReviewViewExecutor,
)
from .read_access import resolve_ledger_request_read_access

_PERSON_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_AGENT_READ_FRONTENDS = _PERSON_FRONTENDS | {OperationFrontendProjection.MCP}
_AGENT_ONLY_FRONTENDS = frozenset({OperationFrontendProjection.MCP})


def _build_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
    permitted_frontends: frozenset[OperationFrontendProjection],
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=build,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        permitted_frontends=permitted_frontends,
    )


def build_ledger_evidence_followup_definitions(
    ports: LedgerEvidenceFollowupOperationPorts,
) -> tuple[OperationDefinition, ...]:
    """Build the five exact-profile follow-up read definitions."""
    return (
        _build_definition(
            definition_id=LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceAttachmentQueueRequest,
            result_type=LedgerEvidenceAttachmentQueueExecutionResult,
            executor_type=LedgerEvidenceAttachmentQueueExecutor,
            build=lambda: LedgerEvidenceAttachmentQueueExecutor(ports),
            permitted_frontends=_AGENT_READ_FRONTENDS,
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceAttachmentViewRequest,
            result_type=LedgerEvidenceAttachmentViewExecutionResult,
            executor_type=LedgerEvidenceAttachmentViewExecutor,
            build=lambda: LedgerEvidenceAttachmentViewExecutor(ports),
            permitted_frontends=_AGENT_READ_FRONTENDS,
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceConsentListRequest,
            result_type=LedgerEvidenceConsentListExecutionResult,
            executor_type=LedgerEvidenceConsentListExecutor,
            build=lambda: LedgerEvidenceConsentListExecutor(ports),
            permitted_frontends=_AGENT_READ_FRONTENDS,
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceReviewListRequest,
            result_type=LedgerEvidenceReviewListExecutionResult,
            executor_type=LedgerEvidenceReviewListExecutor,
            build=lambda: LedgerEvidenceReviewListExecutor(ports),
            permitted_frontends=_AGENT_READ_FRONTENDS,
        ),
        _build_definition(
            definition_id=LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceReviewViewRequest,
            result_type=LedgerEvidenceReviewViewExecutionResult,
            executor_type=LedgerEvidenceReviewViewExecutor,
            build=lambda: LedgerEvidenceReviewViewExecutor(ports),
            permitted_frontends=_PERSON_FRONTENDS,
        ),
    )


def build_ledger_evidence_review_summary_definition(
    ports: LedgerEvidenceFollowupOperationPorts,
) -> OperationDefinition:
    """Build the agent-only review read that serves the review view without document text."""
    return _build_definition(
        definition_id=LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceReviewViewRequest,
        result_type=LedgerEvidenceReviewSummaryExecutionResult,
        executor_type=LedgerEvidenceReviewSummaryExecutor,
        build=lambda: LedgerEvidenceReviewSummaryExecutor(ports),
        permitted_frontends=_AGENT_ONLY_FRONTENDS,
    )


def _project_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    expected_type: type[BaseModel],
    definition_id: str,
) -> BaseModel:
    if type(result) is not expected_type:
        raise ValueError("invalid evidence follow-up result")
    profile_id = getattr(result, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ValueError("invalid evidence follow-up profile")
    require_terminal_receipt_match(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="evidence follow-up read is not bound to its successful receipt",
    )
    projection = getattr(result, "result", None)
    if not isinstance(projection, BaseModel):
        raise ValueError("invalid evidence follow-up projection")
    return projection


def project_attachment_queue_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the queue only when its receipt confirms a successful no-effect read."""
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceAttachmentQueueExecutionResult,
        definition_id=LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    )


def project_attachment_view_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the attachment manifest only under its exact terminal receipt."""
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceAttachmentViewExecutionResult,
        definition_id=LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    )


def project_consent_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the consent survey only under its exact terminal receipt."""
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceConsentListExecutionResult,
        definition_id=LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    )


def project_review_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the review queue only under its exact terminal receipt."""
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceReviewListExecutionResult,
        definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    )


def project_review_view_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the review view only under its exact terminal receipt."""
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceReviewViewExecutionResult,
        definition_id=LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )


def project_review_summary_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the review summary only under its exact terminal receipt."""
    return _project_result(
        result,
        receipt,
        expected_type=LedgerEvidenceReviewSummaryExecutionResult,
        definition_id=LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    )


def _resolve_review_summary_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if context.frontend is not OperationFrontendProjection.MCP:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceReviewViewRequest,
    )


def build_ledger_evidence_review_summary_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the review summary's typed contracts and all-period tax disclosure."""
    if definition.definition_id != LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID:
        raise ValueError("review summary registration requires the review summary definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceReviewSummaryProjection,
        result_projector=project_review_summary_result,
        access_resolver=_resolve_review_summary_access,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    result_schema_version: int = 1,
    projector: Callable[[BaseModel, OperationTerminalReceipt], BaseModel],
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=result_schema_version,
            model_type=result_type,
        ),
        result_projector=projector,
        access_resolver=lambda request, context: resolve_ledger_request_read_access(
            request,
            context,
            definition_id=definition.definition_id,
            request_type=request_type,
        ),
    )


def build_ledger_evidence_followup_registrations(
    definitions: Sequence[OperationDefinition],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind exact typed contracts and all-period tax disclosure for each read."""
    by_id = {definition.definition_id: definition for definition in definitions}
    expected = (
        LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )
    if len(by_id) != len(definitions) or set(by_id) != set(expected):
        raise ValueError("follow-up registration requires the exact five read definitions")
    return (
        _registration(
            by_id[expected[0]],
            request_type=LedgerEvidenceAttachmentQueueRequest,
            result_type=LedgerEvidenceAttachmentQueueProjection,
            projector=project_attachment_queue_result,
        ),
        _registration(
            by_id[expected[1]],
            request_type=LedgerEvidenceAttachmentViewRequest,
            result_type=LedgerEvidenceAttachmentViewProjection,
            projector=project_attachment_view_result,
        ),
        _registration(
            by_id[expected[2]],
            request_type=LedgerEvidenceConsentListRequest,
            result_type=LedgerEvidenceConsentListProjection,
            projector=project_consent_list_result,
        ),
        _registration(
            by_id[expected[3]],
            request_type=LedgerEvidenceReviewListRequest,
            result_type=LedgerEvidenceReviewListProjection,
            projector=project_review_list_result,
        ),
        _registration(
            by_id[expected[4]],
            request_type=LedgerEvidenceReviewViewRequest,
            result_type=LedgerEvidenceReviewViewProjection,
            result_schema_version=2,
            projector=project_review_view_result,
        ),
    )


__all__ = [
    "build_ledger_evidence_followup_definitions",
    "build_ledger_evidence_followup_registrations",
    "build_ledger_evidence_review_summary_definition",
    "build_ledger_evidence_review_summary_registration",
    "project_attachment_queue_result",
    "project_attachment_view_result",
    "project_consent_list_result",
    "project_review_list_result",
    "project_review_summary_result",
    "project_review_view_result",
]
