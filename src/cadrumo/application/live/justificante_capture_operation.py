"""Recorded exact-profile capture of an AEAT justificante and its local evidence."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import FilingRecordId, SnapshotId
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
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..calculations.observations_repository import ObservationSourceKind
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
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .justificante import JustificanteCaptureSnapshotService, capture_justificante_snapshot_outcome
from .justificante_ports import (
    JustificanteAuthenticityVerifierPort,
    JustificanteLiveReadPort,
    JustificanteRegistrationPorts,
)
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


def _project_capture(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = JustificanteCaptureOperationReport.model_validate(result, strict=True)
    projection = report.projection
    expected_effect = OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE
    if (
        receipt.identity.definition_id != JUSTIFICANTE_CAPTURE_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.bucket_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not expected_effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
    ):
        raise ValueError("justificante capture result contradicts its terminal receipt")
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
        browser_resources = self._browser_resources_factory()
        context.cleanup.own(browser_resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])

        @asynccontextmanager
        async def fresh_local_guard() -> AsyncGenerator[None]:
            await context.events.phase(_PHASES[2])
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                yield

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
                effect_guard=fresh_local_guard,
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
        await context.events.phase(_PHASES[3])
        await context.events.effect(OperationEffect.UPDATED)
        async with context.cancellation.irreversible_section():
            return await context.operands.put(report, written_at=now())


def build_justificante_capture_definition(
    composition_factory: JustificanteCaptureCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare one recorded browser-owning justificante capture."""

    def build() -> JustificanteCaptureExecutor:
        return JustificanteCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=JUSTIFICANTE_CAPTURE_DEFINITION_ID,
        request_type=JustificanteCaptureRequest,
        result_type=JustificanteCaptureOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=JustificanteCaptureRequest,
            executor_type=JustificanteCaptureExecutor,
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


def resolve_justificante_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile disclosure and a fresh COMMIT fence."""
    if request.definition_id != JUSTIFICANTE_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, JustificanteCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_justificante_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the closed summary and exact-profile capture policy."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=JustificanteCaptureRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=JustificanteCapturePublicResultV1,
        ),
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
