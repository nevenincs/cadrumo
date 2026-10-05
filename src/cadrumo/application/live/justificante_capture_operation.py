"""Recorded exact-profile capture of an AEAT justificante and its local evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import FilingRecordId, SnapshotId
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..calculations.observations_repository import ObservationSourceKind
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .justificante import JustificanteCaptureSnapshotService, capture_justificante_snapshot_outcome
from .justificante_ports import (
    JustificanteAuthenticityVerifierPort,
    JustificanteLiveReadPort,
    JustificanteRegistrationPorts,
)
from .live_operation_execution import fenced_persistence_guard, own_provider_browser, publish_live_capture_report
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .session import LiveSessionWriteReceipt
from .snapshot_base import SnapshotLifecycleState

JUSTIFICANTE_CAPTURE_DEFINITION_ID = "live.justificante.capture"
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_PHASES = (
    "justificante-capture.preflight",
    "justificante-capture.acquire",
    "justificante-capture.persist",
    "justificante-capture.result",
)


class JustificanteCaptureRequest(CredentialFreeOperationRequest):
    """Capture the selected filing's AEAT receipt for one exact profile."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    modelo: str
    year: int
    period: str = Field(min_length=1, max_length=16)


class JustificanteCapturePublicResultV1(BaseModel):
    """Safe receipt/evidence summary; the signed PDF stays in encrypted custody."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)
    expediente_id: str = Field(min_length=1, max_length=128)
    csv: str = Field(min_length=1, max_length=128)
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_kind: ObservationSourceKind
    state: SnapshotLifecycleState
    captured_at: datetime
    justificante_metadata_registered: bool
    calendar_evidence_available: bool
    modelo_filing_record_required: bool
    filing_evidence_stamped: bool
    filing_record_id: FilingRecordId | None = None


class JustificanteCaptureOperationReport(BaseModel):
    """Private result with the operation's actual local effect evidence."""

    model_config = _PUBLIC_CONFIG
    projection: JustificanteCapturePublicResultV1
    local_write_performed: bool


@dataclass(frozen=True, slots=True)
class JustificanteCapturePorts:
    """Worker-bound local custody and remote receipt capabilities."""

    service: JustificanteCaptureSnapshotService
    read_port: JustificanteLiveReadPort
    registration_ports: JustificanteRegistrationPorts
    verifier: JustificanteAuthenticityVerifierPort


type JustificanteCaptureCompositionFactory = Callable[[str, PinnedAuthorityOperation], JustificanteCapturePorts]


_RECEIPT_CONTRADICTION = "justificante capture result contradicts its terminal receipt"


def _project_capture(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = JustificanteCaptureOperationReport.model_validate(result, strict=True)
    projection = report.projection
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=JUSTIFICANTE_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.bucket_id)),
        effect=OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE,
        message=_RECEIPT_CONTRADICTION,
    )
    return projection


class JustificanteCaptureExecutor:
    """Own browser cleanup and fence each local receipt/evidence write."""

    def __init__(
        self,
        composition_factory: JustificanteCaptureCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self, request: OperationRequest[JustificanteCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Fetch and register one signed receipt with correlated local effects."""
        payload = request.payload
        bucket_id = canonical_profile_bucket_id(payload.profile_id)
        if (
            request.definition_id != JUSTIFICANTE_CAPTURE_DEFINITION_ID
            or require_active_bucket_id() != bucket_id
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = Period.from_year_and_code(payload.year, payload.period)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        ports = self._composition_factory(bucket_id, context.authority_operation)
        browser_resources = await own_provider_browser(
            context, self._browser_resources_factory, acquire_phase=_PHASES[1]
        )
        with browser_resources.activate():
            session_receipt = LiveSessionWriteReceipt(context.events.effect)
            outcome = await capture_justificante_snapshot_outcome(
                bucket_id=bucket_id,
                modelo=payload.modelo,
                year=payload.year,
                period=period,
                service=ports.service,
                read_port=ports.read_port,
                registration_ports=ports.registration_ports,
                verifier=ports.verifier,
                effect_guard=fenced_persistence_guard(context, persist_phase=_PHASES[2]),
                on_session_write=session_receipt,
                authority_operation=context.authority_operation,
            )
        snapshot = outcome.snapshot
        if (
            str(snapshot.bucket_id) != bucket_id
            or snapshot.modelo != payload.modelo
            or snapshot.filing_year != payload.year
            or snapshot.period != period
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        projection = JustificanteCapturePublicResultV1(
            bucket_id=snapshot.bucket_id,
            snapshot_id=snapshot.snapshot_id,
            modelo=snapshot.modelo,
            filing_year=snapshot.filing_year,
            period=snapshot.period.registry_token,
            expediente_id=snapshot.expediente_id,
            csv=snapshot.csv,
            pdf_sha256=snapshot.pdf_sha256,
            source_kind=snapshot.source_kind,
            state=snapshot.state,
            captured_at=snapshot.captured_at,
            justificante_metadata_registered=outcome.justificante_metadata_registered,
            calendar_evidence_available=outcome.justificante_metadata_registered,
            modelo_filing_record_required=not outcome.filing_evidence_stamped,
            filing_evidence_stamped=outcome.filing_evidence_stamped,
            filing_record_id=outcome.filing_record_id,
        )
        # The authenticity verdict is persisted on every successful capture,
        # including a content-addressed recapture of an existing PDF.
        report = JustificanteCaptureOperationReport(projection=projection, local_write_performed=True)
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[3], effect=OperationEffect.UPDATED
        )


def build_justificante_capture_definition(
    composition_factory: JustificanteCaptureCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare one recorded browser-owning justificante capture."""

    def build() -> JustificanteCaptureExecutor:
        return JustificanteCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return build_live_operation_definition(
        definition_id=JUSTIFICANTE_CAPTURE_DEFINITION_ID,
        request_type=JustificanteCaptureRequest,
        result_type=JustificanteCaptureOperationReport,
        executor_type=JustificanteCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_PROCESS_UPDATE_CAPABILITIES,
    )


def resolve_justificante_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile disclosure and a fresh COMMIT fence."""
    return resolve_whole_profile_capture_access(
        request, context, definition_id=JUSTIFICANTE_CAPTURE_DEFINITION_ID, payload_type=JustificanteCaptureRequest
    )


def build_justificante_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the closed summary and exact-profile capture policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=JustificanteCapturePublicResultV1,
        result_projector=_project_capture,
        access_resolver=resolve_justificante_capture_access,
    )


__all__ = [
    "JUSTIFICANTE_CAPTURE_DEFINITION_ID",
    "JustificanteCaptureCompositionFactory",
    "JustificanteCapturePorts",
    "JustificanteCapturePublicResultV1",
    "JustificanteCaptureRequest",
    "build_justificante_capture_definition",
    "build_justificante_capture_registration",
    "resolve_justificante_capture_access",
]
