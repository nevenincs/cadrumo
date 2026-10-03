"""Registered custody of one notification document AEAT already marks read."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.aeat_certificado import AeatCertificadoId
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data_ports import FiledEffectGuard
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .notification_document_read_operation import (
    NotificationDocumentServiceFactory,
    NotificationDocumentViewPublicResultV1,
    project_notification_document_record,
)
from .notification_documents import NotificationDocumentCustody
from .notifications import pull_notification_document
from .notifications_capture_operation import NotificationsCaptureComposition
from .session import LiveSessionWriteReceipt

NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID = "live.notifications.document.capture"
_PHASES = (
    "notification-document-capture.preflight",
    "notification-document-capture.acquire",
    "notification-document-capture.persist",
    "notification-document-capture.result",
)
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class NotificationDocumentCaptureRequest(CredentialFreeOperationRequest):
    """Select one already-read notification in one immutable profile worker."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    certificado_id: AeatCertificadoId


class NotificationDocumentCaptureOperationReport(BaseModel):
    """Keep the full custody result only in encrypted operation storage."""

    model_config = _PUBLIC_CONFIG
    custody: NotificationDocumentCustody


class NotificationDocumentCapturePublicResultV1(NotificationDocumentViewPublicResultV1):
    """Existing CLI document fields plus the truthful deduplication outcome."""

    already_in_custody: bool


NotificationDocumentCaptureCompositionFactory = Callable[[], NotificationsCaptureComposition]


def _require_exact_profile(profile_id: UUID, subject_ref: str) -> str:
    canonical_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != canonical_id or subject_ref != profile_operation_subject(canonical_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return canonical_id


def _project_capture(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not NotificationDocumentCaptureOperationReport:
        raise ValueError("invalid notification document capture report")
    report = NotificationDocumentCaptureOperationReport.model_validate(result, strict=True)
    custody = report.custody
    record = custody.record
    expected_effect = OperationEffect.NONE if custody.already_in_custody else OperationEffect.UPDATED
    if (
        receipt.identity.definition_id != NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(record.bucket_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not expected_effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
    ):
        raise ValueError("notification document custody contradicts its terminal receipt")
    view = project_notification_document_record(record)
    return NotificationDocumentCapturePublicResultV1.model_validate(
        {**view.model_dump(mode="python"), "already_in_custody": custody.already_in_custody}, strict=True
    )


class NotificationDocumentCaptureExecutor:
    """Fetch guarded served bytes before one fresh local custody fence."""

    def __init__(
        self,
        composition_factory: NotificationDocumentCaptureCompositionFactory,
        document_service_factory: NotificationDocumentServiceFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        self._composition_factory = composition_factory
        self._document_service_factory = document_service_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self,
        request: OperationRequest[NotificationDocumentCaptureRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        if (
            request.definition_id != NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory()
        service = self._document_service_factory()
        browser_resources = self._browser_resources_factory()
        context.cleanup.own(browser_resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])

        @asynccontextmanager
        async def fresh_custody_guard() -> AsyncGenerator[None]:
            await context.events.phase(_PHASES[2])
            await context.events.effect(OperationEffect.UNKNOWN)
            async with context.cancellation.irreversible_section():
                yield

        effect_guard: FiledEffectGuard = fresh_custody_guard
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with browser_resources.activate():
            custody = await pull_notification_document(
                bucket_id=bucket_id,
                certificado_id=str(payload.certificado_id),
                ports=composition.notifications_ports,
                service=service,
                certificate_secret_backend_factory=composition.certificate_secret_backend_factory,
                browser_session_factory=composition.browser_session_factory,
                operator_scope_ports=composition.operator_scope_ports,
                effect_guard=effect_guard,
                on_session_write=session_receipt,
                authority_operation=context.authority_operation,
            )
        if str(custody.record.bucket_id) != bucket_id or custody.record.certificado_id != payload.certificado_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        effect = OperationEffect.NONE if custody.already_in_custody else OperationEffect.UPDATED
        await context.events.phase(_PHASES[3])
        await context.events.effect(session_receipt.combine(effect))
        async with context.cancellation.irreversible_section():
            return await context.operands.put(
                NotificationDocumentCaptureOperationReport(custody=custody), written_at=now()
            )


def build_notification_document_capture_definition(
    composition_factory: NotificationDocumentCaptureCompositionFactory,
    document_service_factory: NotificationDocumentServiceFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare process-owned remote acquisition with guarded local custody."""

    def build() -> NotificationDocumentCaptureExecutor:
        return NotificationDocumentCaptureExecutor(
            composition_factory, document_service_factory, browser_resources_factory, provider_preflight
        )

    return OperationDefinition(
        definition_id=NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
        request_type=NotificationDocumentCaptureRequest,
        result_type=NotificationDocumentCaptureOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationDocumentCaptureRequest,
            executor_type=NotificationDocumentCaptureExecutor,
            build=build,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_notification_document_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile document disclosure and a fresh COMMIT fence."""
    if request.definition_id != NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, NotificationDocumentCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    disclosures = resolved.policy.disclosures
    if context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=schema.schema_id,
                category=category,
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    policy = OperationAccessPolicy.model_validate(
        {
            **dict(resolved.policy),
            "actions": resolved.policy.actions | {AccessAction.COMMIT},
            "disclosures": disclosures,
        }
    )
    return replace(resolved, policy=policy)


def build_notification_document_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind a safe summary, exact-profile policy and truthful effect receipt."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=NotificationDocumentCaptureRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationDocumentCapturePublicResultV1,
        ),
        result_projector=_project_capture,
        access_resolver=resolve_notification_document_capture_access,
    )


__all__ = [
    "NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID",
    "NotificationDocumentCaptureOperationReport",
    "NotificationDocumentCapturePublicResultV1",
    "NotificationDocumentCaptureRequest",
    "build_notification_document_capture_definition",
    "build_notification_document_capture_registration",
    "resolve_notification_document_capture_access",
]
