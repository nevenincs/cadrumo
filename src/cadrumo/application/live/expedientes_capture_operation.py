"""Recorded exact-profile declaration-register capture and encrypted custody."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .expedientes import PersistedExpedientesSnapshot, capture_expedientes_bulk, capture_expedientes_with_outcome
from .expedientes_ports import ExpedientesPortsFactory
from .filed_history_operation import (
    FiledHistoryBrowserResources,
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryProviderPreflight,
)
from .live_operation_execution import fenced_persistence_guard, own_provider_browser, publish_live_capture_report
from .live_operation_registration import (
    build_live_operation_definition,
    require_live_capture_receipt,
    resolve_whole_profile_capture_access,
)
from .remote_state_models import ExpedientesBulkCaptureFailureRow, ExpedientesBulkCaptureReport
from .session import LiveSessionWriteReceipt

EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID = "live.expedientes.capture.single"
EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID = "live.expedientes.capture.bulk"
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_PHASES = (
    "expedientes-capture.preflight",
    "expedientes-capture.acquire",
    "expedientes-capture.persist",
    "expedientes-capture.result",
)


class ExpedientesSingleCaptureRequest(CredentialFreeOperationRequest):
    """Read one modelo and year under an exact profile worker."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    modelo: str = Field(min_length=1)
    year: int


class ExpedientesBulkCaptureRequest(CredentialFreeOperationRequest):
    """Read a year range for explicit or authority-enumerated modelos."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    modelos: tuple[str, ...] | None = None
    year_from: int
    year_to: int


class ExpedientesSingleCaptureReport(BaseModel):
    """Private persisted snapshot and local-effect evidence."""

    model_config = _PUBLIC_CONFIG
    snapshot: PersistedExpedientesSnapshot
    newly_persisted: bool


class ExpedientesSingleCapturePublicResultV1(BaseModel):
    """Bounded single-capture summary without declaration content."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    persisted_at: datetime
    declaration_count: NonNegativeInt
    source_url: str = Field(min_length=1)


class ExpedientesBulkCapturePublicResultV1(BaseModel):
    """Bounded bulk summary and isolated failed query coordinates."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    captured_snapshot_count: NonNegativeInt
    declaration_count: NonNegativeInt
    snapshot_ids: tuple[SnapshotId, ...]
    failed_count: NonNegativeInt
    failures: tuple[ExpedientesBulkCaptureFailureRow, ...]


def _require_profile(profile_id: UUID, subject_ref: str, definition_id: str, context: OperationExecutorContext) -> str:
    bucket_id = canonical_profile_bucket_id(profile_id)
    if (
        require_active_bucket_id() != bucket_id
        or subject_ref != profile_operation_subject(bucket_id)
        or context.identity.definition_id != definition_id
        or context.identity.subject_ref != subject_ref
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


_RECEIPT_CONTRADICTION = "expedientes capture result contradicts its terminal receipt"


def _project_single(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = ExpedientesSingleCaptureReport.model_validate(result, strict=True)
    snapshot = report.snapshot
    require_live_capture_receipt(
        receipt,
        definition_id=EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
        bucket_id=str(snapshot.bucket_id),
        stored=report.newly_persisted,
        message=_RECEIPT_CONTRADICTION,
    )
    return ExpedientesSingleCapturePublicResultV1(
        bucket_id=snapshot.bucket_id,
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        persisted_at=snapshot.persisted_at,
        declaration_count=len(snapshot.declarations),
        source_url=snapshot.source_url,
    )


def _project_bulk(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = ExpedientesBulkCaptureReport.model_validate(result, strict=True)
    if report.captured_snapshot_count != len(report.snapshot_ids) or report.captured_snapshot_count > 1:
        raise ValueError("expedientes bulk snapshot tally is inconsistent")
    if report.newly_persisted and not report.snapshot_ids:
        raise ValueError("expedientes bulk effect has no snapshot")
    require_live_capture_receipt(
        receipt,
        definition_id=EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
        bucket_id=str(report.bucket_id),
        stored=report.newly_persisted,
        message=_RECEIPT_CONTRADICTION,
    )
    return ExpedientesBulkCapturePublicResultV1(
        bucket_id=report.bucket_id,
        modelos=report.modelos,
        year_from=report.year_from,
        year_to=report.year_to,
        captured_snapshot_count=report.captured_snapshot_count,
        declaration_count=report.declaration_count,
        snapshot_ids=report.snapshot_ids,
        failed_count=len(report.failures),
        failures=report.failures,
    )


class _CaptureExecutorBase:
    def __init__(
        self,
        ports_factory: ExpedientesPortsFactory,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        self._ports_factory = ports_factory
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._browser_session_factory = browser_session_factory
        self._operator_scope_ports = operator_scope_ports
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def _prepare(self, profile_id: UUID, context: OperationExecutorContext) -> FiledHistoryBrowserResources:
        await context.events.phase(_PHASES[0])
        self._provider_preflight(profile_id, context.authority_operation)
        return await own_provider_browser(context, self._browser_resources_factory, acquire_phase=_PHASES[1])

    @staticmethod
    async def _publish(
        report: BaseModel, changed: bool, context: OperationExecutorContext, session_receipt: LiveSessionWriteReceipt
    ) -> str:
        effect = OperationEffect.UPDATED if changed else OperationEffect.NONE
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[3], effect=session_receipt.combine(effect)
        )


class ExpedientesSingleCaptureExecutor(_CaptureExecutorBase):
    """Own one browser-backed register walk and guarded snapshot write."""

    async def execute(
        self, request: OperationRequest[ExpedientesSingleCaptureRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if request.definition_id != EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        bucket_id = _require_profile(payload.profile_id, request.subject_ref, request.definition_id, context)
        browser_resources = await self._prepare(payload.profile_id, context)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with browser_resources.activate():
            outcome = await capture_expedientes_with_outcome(
                bucket_id=bucket_id,
                modelo=payload.modelo,
                year=payload.year,
                ports=self._ports_factory(bucket_id=bucket_id),
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                browser_session_factory=self._browser_session_factory,
                operator_scope_ports=self._operator_scope_ports,
                authority_operation=context.authority_operation,
                effect_guard=fenced_persistence_guard(context, persist_phase=_PHASES[2]),
                on_session_write=session_receipt,
            )
        if str(outcome.snapshot.bucket_id) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return await self._publish(
            ExpedientesSingleCaptureReport(snapshot=outcome.snapshot, newly_persisted=outcome.newly_persisted),
            outcome.newly_persisted,
            context,
            session_receipt,
        )


class ExpedientesBulkCaptureExecutor(_CaptureExecutorBase):
    """Own a bounded bulk register walk and one guarded aggregate write."""

    async def execute(
        self, request: OperationRequest[ExpedientesBulkCaptureRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if request.definition_id != EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        bucket_id = _require_profile(payload.profile_id, request.subject_ref, request.definition_id, context)
        browser_resources = await self._prepare(payload.profile_id, context)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with browser_resources.activate():
            report = await capture_expedientes_bulk(
                bucket_id=bucket_id,
                year_from=payload.year_from,
                year_to=payload.year_to,
                modelos=payload.modelos,
                ports=self._ports_factory(bucket_id=bucket_id),
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                browser_session_factory=self._browser_session_factory,
                operator_scope_ports=self._operator_scope_ports,
                authority_operation=context.authority_operation,
                effect_guard=fenced_persistence_guard(context, persist_phase=_PHASES[2]),
                on_session_write=session_receipt,
            )
        if str(report.bucket_id) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return await self._publish(report, report.newly_persisted, context, session_receipt)


def build_expedientes_single_capture_definition(
    ports_factory: ExpedientesPortsFactory,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare the recorded exact-profile single capture."""

    def build() -> ExpedientesSingleCaptureExecutor:
        return ExpedientesSingleCaptureExecutor(
            ports_factory,
            certificate_secret_backend_factory,
            browser_session_factory,
            operator_scope_ports,
            browser_resources_factory,
            provider_preflight,
        )

    return build_live_operation_definition(
        definition_id=EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
        request_type=ExpedientesSingleCaptureRequest,
        result_type=ExpedientesSingleCaptureReport,
        executor_type=ExpedientesSingleCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES,
    )


def build_expedientes_bulk_capture_definition(
    ports_factory: ExpedientesPortsFactory,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare the recorded exact-profile bulk capture."""

    def build() -> ExpedientesBulkCaptureExecutor:
        return ExpedientesBulkCaptureExecutor(
            ports_factory,
            certificate_secret_backend_factory,
            browser_session_factory,
            operator_scope_ports,
            browser_resources_factory,
            provider_preflight,
        )

    return build_live_operation_definition(
        definition_id=EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
        request_type=ExpedientesBulkCaptureRequest,
        result_type=ExpedientesBulkCaptureReport,
        executor_type=ExpedientesBulkCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES,
    )


def resolve_expedientes_single_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return resolve_whole_profile_capture_access(
        request,
        context,
        definition_id=EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
        payload_type=ExpedientesSingleCaptureRequest,
    )


def resolve_expedientes_bulk_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return resolve_whole_profile_capture_access(
        request,
        context,
        definition_id=EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
        payload_type=ExpedientesBulkCaptureRequest,
    )


def build_expedientes_single_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the single capture's public summary and access policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ExpedientesSingleCapturePublicResultV1,
        result_projector=_project_single,
        access_resolver=resolve_expedientes_single_capture_access,
    )


def build_expedientes_bulk_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bulk capture's public summary and access policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ExpedientesBulkCapturePublicResultV1,
        result_projector=_project_bulk,
        access_resolver=resolve_expedientes_bulk_capture_access,
    )


__all__ = [
    "EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID",
    "EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID",
    "ExpedientesBulkCapturePublicResultV1",
    "ExpedientesBulkCaptureRequest",
    "ExpedientesSingleCapturePublicResultV1",
    "ExpedientesSingleCaptureRequest",
    "build_expedientes_bulk_capture_definition",
    "build_expedientes_bulk_capture_registration",
    "build_expedientes_single_capture_definition",
    "build_expedientes_single_capture_registration",
]
