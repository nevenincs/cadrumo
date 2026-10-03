"""Registered exact-profile human ledger export using the canonical serializer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import canonical_json_bytes
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..export.tabular import ExportSerializationFormat
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, terminal_receipt_matches
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload, require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_common import resolve_revision_guarded_transaction_repository
from .actions_export import export_ledger_transactions
from .commit_fence import (
    LedgerCommitAttemptTracker,
    RevisionGuardedTrackedLedgerTransactionRepository,
    run_with_ledger_commit_fence,
)
from .export_link_operation_ports import (
    resolve_export_link_access,
    settle_export_link_failure,
)
from .models import LedgerExportCommand

LEDGER_EXPORT_OPERATION_DEFINITION_ID = "ledger.export"
_PathText = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]


class LedgerExportRequest(BaseModel):
    """The operator's explicit artifact destination and canonical export filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    output_path: _PathText
    export_format: ExportSerializationFormat = ExportSerializationFormat.CSV
    include_inactive: bool = False
    period: PublicPeriod | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None


class LedgerExportRowProjection(BaseModel):
    """Lossless string cells already produced by the canonical export row builder."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: str
    transaction_id: str
    lifecycle_state: str
    invoice_id: str
    booked_date: str
    value_date: str
    effective_date: str
    amount: str
    currency: str
    direction: str
    counterparty: str
    description: str
    source_jurisdiction: str
    business_classification: str
    business_pct: str
    category_id: str
    taxable_base: str
    iva_rate: str
    iva_amount: str
    iva_category: str
    counterparty_country: str
    counterparty_identification_state: str
    irpf_category: str
    usage_ratio_id: str
    prorrata_reference: str
    purchase_invoice_evidence_id: str
    attachment_ids: str
    notes: str
    created_by: str
    created_source_command: str
    value_in_eur: str
    fx_rate: str


class LedgerExportProjection(BaseModel):
    """The complete existing human report, excluding artifact bytes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    bucket_id: str
    export_id: Hex64Str
    export_format: ExportSerializationFormat
    media_type: str
    filename_extension: str
    row_count: Annotated[int, Field(ge=0)]
    byte_size: Annotated[int, Field(ge=0)]
    sha256: ContentDigest
    fieldnames: tuple[str, ...]
    rows: tuple[LedgerExportRowProjection, ...]
    bucket_event_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=1)]
    output_path: _PathText

    @model_validator(mode="after")
    def _exact_profile(self) -> Self:
        if (
            self.bucket_id != str(self.profile_id)
            or any(row.bucket_id != self.bucket_id for row in self.rows)
            or self.row_count != len(self.rows)
        ):
            raise ValueError("ledger export report differs from its profile or complete rows")
        return self


class LedgerExportExecutionResult(BaseModel):
    """Canonical encrypted result custody for the human export report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerExportProjection


class LedgerExportExecutor:
    """Render outside COMMIT and fence only file publication and canonical co-commit."""

    def __init__(self, factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile canonical action-port factory."""
        self._factory = factory

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Publish the human export and settle each concrete write outcome."""
        payload = require_access_request_payload(
            request,
            definition_id=LEDGER_EXPORT_OPERATION_DEFINITION_ID,
            payload_type=LedgerExportRequest,
        )
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(request.definition_id)
        tracker = LedgerCommitAttemptTracker()
        artifact_confirmed = False

        def work() -> LedgerExportProjection:
            nonlocal artifact_confirmed
            ports = self._factory(bucket_id=str(payload.profile_id), operation=context.authority_operation)
            if ports.operation is not context.authority_operation:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            original = resolve_revision_guarded_transaction_repository(
                bucket_id=str(payload.profile_id), repository=ports.transaction_repository
            )
            repository = RevisionGuardedTrackedLedgerTransactionRepository(original, tracker)

            def publish(write: Callable[[], None]) -> None:
                nonlocal artifact_confirmed
                tracker.call_writer(write)
                artifact_confirmed = True

            with validating_governed_facts(context.authority_operation):
                result = export_ledger_transactions(
                    LedgerExportCommand(
                        bucket_id=str(payload.profile_id),
                        output_path=Path(payload.output_path),
                        export_format=payload.export_format,
                        include_inactive=payload.include_inactive,
                        period=payload.period.to_period() if payload.period else None,
                        actor=payload.actor or str(payload.profile_id),
                        source_command="aeat app ledger export",
                    ),
                    transaction_repository=repository,
                    bucket_event_repository=ports.bucket_event_repository,
                    mutation_writer=publish,
                )
            return LedgerExportProjection.model_validate(
                {
                    **result.model_dump(mode="python", exclude={"payload"}),
                    "profile_id": payload.profile_id,
                    "output_path": payload.output_path,
                },
                strict=True,
            )

        try:
            projection = await run_with_ledger_commit_fence(
                work, tracker=tracker, context=context, task_name=request.definition_id
            )
        except BaseException:
            await settle_export_link_failure(tracker, context)
            raise
        if not artifact_confirmed or tracker.attempt_count < 2 or tracker.has_uncertain_write:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return await context.operands.put(LedgerExportExecutionResult(projection=projection), written_at=now())


def project_ledger_export_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerExportProjection:
    """Release only the complete profile-bound report after successful publication."""
    if type(result) is not LedgerExportExecutionResult or not isinstance(result, LedgerExportExecutionResult):
        raise ValueError("invalid ledger export result")
    projection = result.projection
    if (
        not terminal_receipt_matches(
            receipt,
            definition_id=LEDGER_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(projection.profile_id)),
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.UPDATED,
        )
        or len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
    ):
        raise ValueError("ledger export report contradicts its terminal receipt")
    return LedgerExportProjection.model_validate(projection.model_dump(mode="python"), strict=True)


def resolve_ledger_export_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require current human authority for the chosen local artifact destination."""
    payload = request.payload
    if (
        request.definition_id != LEDGER_EXPORT_OPERATION_DEFINITION_ID
        or type(payload) is not LedgerExportRequest
        or not isinstance(payload, LedgerExportRequest)
        or context.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    periods = frozenset({payload.period.to_period()}) if payload.period is not None else frozenset[Period]()
    return resolve_export_link_access(
        request, context, profile_id=payload.profile_id, periods=periods, requires_human=True
    )


def build_ledger_export_definition(factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the existing human export, including partial and uncertain writes."""
    return build_single_phase_definition(
        definition_id=LEDGER_EXPORT_OPERATION_DEFINITION_ID,
        request_type=LedgerExportRequest,
        result_type=LedgerExportExecutionResult,
        executor_type=LedgerExportExecutor,
        build=lambda: LedgerExportExecutor(factory),
        capabilities=RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_ledger_export_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the strict human projection and current destination/category policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerExportProjection,
        result_projector=project_ledger_export_result,
        access_resolver=resolve_ledger_export_access,
    )
