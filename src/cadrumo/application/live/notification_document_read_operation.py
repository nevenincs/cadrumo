"""Registered exact-profile reads for notification documents in custody."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, NonNegativeInt, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.aeat_certificado import AeatCertificadoId
from ...core.identity.aeat_clave_liquidacion import AeatClaveLiquidacion
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
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
from ...core.text_bounds import NonEmptyStr, PositiveCount
from ...core.time.clock import now
from ...domain.notifications.sancion import SancionLiquidacion
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
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
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .notification_documents import (
    NotificationDocumentRecord,
    NotificationDocumentService,
    NotificationParseRefusal,
)

NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID = "live.notifications.document.view"
NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID = "live.notifications.document.history"
_VIEW_PHASES = ("notification-document-view.read", "notification-document-view.result")
_HISTORY_PHASES = ("notification-document-history.read", "notification-document-history.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class NotificationDocumentViewRequest(CredentialFreeOperationRequest):
    """Read one stored notification document by its exact certificado id."""

    profile_id: UUID
    certificado_id: AeatCertificadoId


class NotificationDocumentHistoryRequest(CredentialFreeOperationRequest):
    """Read this profile's parsed notification-document readings."""

    profile_id: UUID


class NotificationDocumentSancionPublicV1(BaseModel):
    """Wire-safe reading that preserves each amount's printed decimal scale."""

    model_config = _PUBLIC_CONFIG

    certificado_id: AeatCertificadoId
    clave_liquidacion: AeatClaveLiquidacion
    referencia: str
    nif: str
    objeto_tributario: Literal["sancion", "liquidacion"]
    base_sancion: NonEmptyStr
    porcentaje_minimo: NonEmptyStr
    sancion_resultante: NonEmptyStr
    reduccion_conformidad: NonEmptyStr | None
    reduccion_pronto_pago: NonEmptyStr | None
    diferencia: NonEmptyStr | None
    importe_a_ingresar: NonEmptyStr
    document_sha256: ContentDigest


class NotificationDocumentViewPublicResultV1(BaseModel):
    """Closed projection of the selected record, without PDF bytes."""

    model_config = _PUBLIC_CONFIG

    bucket_id: BucketId
    certificado_id: AeatCertificadoId
    attachment_id: ContentDigest
    document_sha256: ContentDigest
    byte_size: PositiveCount
    source_url: NonEmptyStr
    fetched_at: datetime
    sancion_parsed: bool
    sancion: NotificationDocumentSancionPublicV1 | None = None
    parse_refusal: NotificationParseRefusal | None = None
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    def _reading_flag_matches_payload(self) -> NotificationDocumentViewPublicResultV1:
        if self.sancion_parsed != (self.sancion is not None):
            raise ValueError("sancion_parsed must match the presence of a sancion reading")
        if (self.sancion is None) != (self.parse_refusal is not None):
            raise ValueError("notification document view must carry a reading or its refusal")
        if self.sancion is not None and (
            self.sancion.certificado_id != self.certificado_id or self.sancion.document_sha256 != self.document_sha256
        ):
            raise ValueError("notification document view reading differs from its stored document")
        return self


class NotificationDocumentHistoryEntryPublicV1(BaseModel):
    """One parsed document reading in the profile's local history."""

    model_config = _PUBLIC_CONFIG

    certificado_id: AeatCertificadoId
    fetched_at: datetime
    sancion: NotificationDocumentSancionPublicV1

    @model_validator(mode="after")
    def _reading_matches_document(self) -> NotificationDocumentHistoryEntryPublicV1:
        if self.sancion.certificado_id != self.certificado_id:
            raise ValueError("notification document history reading differs from its record")
        return self


class NotificationDocumentHistoryPublicResultV1(BaseModel):
    """Parsed document readings held by this profile, without an aggregate."""

    model_config = _PUBLIC_CONFIG

    bucket_id: BucketId
    count: NonNegativeInt
    documents: tuple[NotificationDocumentHistoryEntryPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_documents(self) -> NotificationDocumentHistoryPublicResultV1:
        if self.count != len(self.documents):
            raise ValueError("notification document history count does not match its rows")
        return self


class NotificationDocumentViewOperationReport(BaseModel):
    """Private selected record retained only in encrypted operation custody."""

    model_config = _PUBLIC_CONFIG

    profile_id: UUID
    certificado_id: AeatCertificadoId
    record: NotificationDocumentRecord

    @model_validator(mode="after")
    def _record_matches_scope(self) -> NotificationDocumentViewOperationReport:
        if str(self.record.bucket_id) != canonical_profile_bucket_id(self.profile_id):
            raise ValueError("notification document belongs to another profile")
        if str(self.record.certificado_id) != self.certificado_id:
            raise ValueError("notification document differs from the selected certificado")
        if self.record.sancion is not None and (
            self.record.sancion.certificado_id != self.record.certificado_id
            or self.record.sancion.document_sha256 != self.record.document_sha256
        ):
            raise ValueError("notification document reading differs from its stored document")
        return self


class NotificationDocumentHistoryOperationReport(BaseModel):
    """Private full custody inventory retained in encrypted operation custody."""

    model_config = _PUBLIC_CONFIG

    profile_id: UUID
    records: tuple[NotificationDocumentRecord, ...]

    @model_validator(mode="after")
    def _every_record_matches_scope(self) -> NotificationDocumentHistoryOperationReport:
        bucket_id = canonical_profile_bucket_id(self.profile_id)
        if any(str(record.bucket_id) != bucket_id for record in self.records):
            raise ValueError("notification document history contains another profile's record")
        if any(
            record.sancion is not None
            and (
                record.sancion.certificado_id != record.certificado_id
                or record.sancion.document_sha256 != record.document_sha256
            )
            for record in self.records
        ):
            raise ValueError("notification document history contains a mismatched reading")
        return self


NotificationDocumentServiceFactory = Callable[[], NotificationDocumentService]


def _require_exact_profile(profile_id: UUID, subject_ref: str) -> str:
    """Refuse a request outside the exact profile worker currently active."""
    canonical_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != canonical_id or subject_ref != profile_operation_subject(canonical_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return canonical_id


def _require_operation_identity[Payload: BaseModel](
    request: OperationRequest[Payload], context: OperationExecutorContext
) -> None:
    if context.identity.definition_id != request.definition_id or context.identity.subject_ref != request.subject_ref:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_document_record(record: NotificationDocumentRecord, *, bucket_id: str) -> None:
    """Refuse a repository record outside the exact service bucket."""
    if str(record.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _sancion_public(sancion: SancionLiquidacion) -> NotificationDocumentSancionPublicV1:
    """Project stored Decimal values as strings without changing their scale."""
    return NotificationDocumentSancionPublicV1(
        certificado_id=sancion.certificado_id,
        clave_liquidacion=sancion.clave_liquidacion,
        referencia=sancion.referencia,
        nif=sancion.nif,
        objeto_tributario=sancion.objeto_tributario,
        base_sancion=str(sancion.base_sancion),
        porcentaje_minimo=str(sancion.porcentaje_minimo),
        sancion_resultante=str(sancion.sancion_resultante),
        reduccion_conformidad=(None if sancion.reduccion_conformidad is None else str(sancion.reduccion_conformidad)),
        reduccion_pronto_pago=None if sancion.reduccion_pronto_pago is None else str(sancion.reduccion_pronto_pago),
        diferencia=None if sancion.diferencia is None else str(sancion.diferencia),
        importe_a_ingresar=str(sancion.importe_a_ingresar),
        document_sha256=sancion.document_sha256,
    )


class NotificationDocumentViewExecutor:
    """Read one local document record without opening browser or process resources."""

    def __init__(self, service_factory: NotificationDocumentServiceFactory) -> None:
        self._service_factory = service_factory

    async def execute(
        self, request: OperationRequest[NotificationDocumentViewRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        _require_operation_identity(request, context)
        if request.definition_id != NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_VIEW_PHASES[0])

        def read() -> NotificationDocumentViewOperationReport:
            record = self._service_factory().show(
                bucket_id=bucket_id,
                certificado_id=payload.certificado_id,
            )
            _require_document_record(record, bucket_id=bucket_id)
            if str(record.certificado_id) != payload.certificado_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return NotificationDocumentViewOperationReport(
                profile_id=payload.profile_id,
                certificado_id=payload.certificado_id,
                record=record,
            )

        report = await asyncio.to_thread(read)
        await context.events.phase(_VIEW_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="notification-document-view-result"
        )


class NotificationDocumentHistoryExecutor:
    """Read the local custody index and disclose only parsed reading rows."""

    def __init__(self, service_factory: NotificationDocumentServiceFactory) -> None:
        self._service_factory = service_factory

    async def execute(
        self, request: OperationRequest[NotificationDocumentHistoryRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        _require_operation_identity(request, context)
        if request.definition_id != NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_HISTORY_PHASES[0])

        def read() -> NotificationDocumentHistoryOperationReport:
            records = self._service_factory().list_documents(bucket_id=bucket_id)
            for record in records:
                _require_document_record(record, bucket_id=bucket_id)
            return NotificationDocumentHistoryOperationReport(profile_id=payload.profile_id, records=records)

        report = await asyncio.to_thread(read)
        await context.events.phase(_HISTORY_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="notification-document-history-result"
        )


def _capabilities() -> OperationCapabilities:
    """Describe durable local reads with no provider or owned resource."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        sensitive_input=OperationSensitiveInputPolicy.NONE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def build_notification_document_view_definition(
    service_factory: NotificationDocumentServiceFactory,
) -> OperationDefinition:
    """Declare an exact-profile local notification-document view."""
    return OperationDefinition(
        definition_id=NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
        request_type=NotificationDocumentViewRequest,
        result_type=NotificationDocumentViewOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationDocumentViewRequest,
            executor_type=NotificationDocumentViewExecutor,
            build=lambda: NotificationDocumentViewExecutor(service_factory),
        ),
        phase_codes=_VIEW_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_notification_document_history_definition(
    service_factory: NotificationDocumentServiceFactory,
) -> OperationDefinition:
    """Declare an exact-profile local notification-document history."""
    return OperationDefinition(
        definition_id=NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
        request_type=NotificationDocumentHistoryRequest,
        result_type=NotificationDocumentHistoryOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationDocumentHistoryRequest,
            executor_type=NotificationDocumentHistoryExecutor,
            build=lambda: NotificationDocumentHistoryExecutor(service_factory),
        ),
        phase_codes=_HISTORY_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def _validate_receipt(receipt: OperationTerminalReceipt, *, definition_id: str, profile_id: UUID) -> None:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("notification document read result contradicts its terminal receipt")


def project_notification_document_record(record: NotificationDocumentRecord) -> NotificationDocumentViewPublicResultV1:
    """Build the shared closed document view from encrypted custody metadata."""
    sancion = None if record.sancion is None else _sancion_public(record.sancion)
    return NotificationDocumentViewPublicResultV1(
        bucket_id=record.bucket_id,
        certificado_id=record.certificado_id,
        attachment_id=record.attachment_id,
        document_sha256=record.document_sha256,
        byte_size=record.byte_size,
        source_url=record.source_url,
        fetched_at=record.fetched_at,
        sancion_parsed=sancion is not None,
        sancion=sancion,
        parse_refusal=record.parse_refusal,
        mode=record.mode,
    )


def _project_view(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not NotificationDocumentViewOperationReport:
        raise ValueError("invalid notification-document view report")
    report = NotificationDocumentViewOperationReport.model_validate(result.model_dump(mode="python"), strict=True)
    _validate_receipt(
        receipt,
        definition_id=NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
        profile_id=report.profile_id,
    )
    return project_notification_document_record(report.record)


def _project_history(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not NotificationDocumentHistoryOperationReport:
        raise ValueError("invalid notification-document history report")
    report = NotificationDocumentHistoryOperationReport.model_validate(result.model_dump(mode="python"), strict=True)
    _validate_receipt(
        receipt,
        definition_id=NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
        profile_id=report.profile_id,
    )
    documents = tuple(
        NotificationDocumentHistoryEntryPublicV1(
            certificado_id=record.certificado_id,
            fetched_at=record.fetched_at,
            sancion=_sancion_public(record.sancion),
        )
        for record in report.records
        if record.sancion is not None
    )
    return NotificationDocumentHistoryPublicResultV1(
        bucket_id=canonical_profile_bucket_id(report.profile_id),
        count=len(documents),
        documents=documents,
    )


def _resolve_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    request_type: type[BaseModel],
    categories: frozenset[DisclosureCategory],
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id or type(request.payload) is not request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if not isinstance(payload, (NotificationDocumentViewRequest, NotificationDocumentHistoryRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = payload.profile_id
    resolved = resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())
    if context.action is not AccessAction.RESULT:
        return resolved
    schema = context.contract.result_schema
    if schema is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosures = frozenset(
        DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=category,
        )
        for category in categories
    )
    policy = resolved.policy.model_copy(update={"disclosures": disclosures})
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def resolve_notification_document_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile authority for the selected document projection."""
    return _resolve_read_access(
        request,
        context,
        definition_id=NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
        request_type=NotificationDocumentViewRequest,
        categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
    )


def resolve_notification_document_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure for parsed document history."""
    return _resolve_read_access(
        request,
        context,
        definition_id=NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
        request_type=NotificationDocumentHistoryRequest,
        categories=frozenset({DisclosureCategory.TAX_VALUES}),
    )


def build_notification_document_view_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind selected-record result fields to the exact-profile access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=NotificationDocumentViewRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationDocumentViewPublicResultV1,
        ),
        result_projector=_project_view,
        access_resolver=resolve_notification_document_view_access,
    )


def build_notification_document_history_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind parsed history result fields to whole-profile tax-value disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=NotificationDocumentHistoryRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationDocumentHistoryPublicResultV1,
        ),
        result_projector=_project_history,
        access_resolver=resolve_notification_document_history_access,
    )


__all__ = [
    "NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID",
    "NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID",
    "NotificationDocumentHistoryEntryPublicV1",
    "NotificationDocumentHistoryPublicResultV1",
    "NotificationDocumentHistoryRequest",
    "NotificationDocumentSancionPublicV1",
    "NotificationDocumentServiceFactory",
    "NotificationDocumentViewPublicResultV1",
    "NotificationDocumentViewRequest",
    "build_notification_document_history_definition",
    "build_notification_document_history_registration",
    "build_notification_document_view_definition",
    "build_notification_document_view_registration",
    "project_notification_document_record",
    "resolve_notification_document_history_access",
    "resolve_notification_document_view_access",
]
