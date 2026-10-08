"""Publish a selected saved calculation as an explicitly labeled local review workbook."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.external_constants import OutputLanguage
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
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
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ..ledger.read_access import resolve_ledger_commit_access
from ..modelo.export_sink import LocalFileExportSink
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload, require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..storage.calc_sheets.review_labels import ReviewWorkbookLabels
from ..storage.calc_sheets.review_workbook import build_review_workbook
from ..storage.calc_sheets.workbook_export import SheetWorkbookMaterializer
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .review_snapshot import CalculationReviewSelection, ReviewSnapshot, ReviewStatus

CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID = "export.calculation-review-xlsx"


class CalculationReviewXlsxRequest(CredentialFreeOperationRequest):
    """Exact saved selection and an operator-chosen absolute destination."""

    model_config = STRICT_FROZEN_CONFIG
    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    filing_record_id: Hex64Str | None = None
    output_path: str = Field(min_length=1, max_length=4096, pattern=r"\S")
    replace_existing: bool = False
    report_language: OutputLanguage = OutputLanguage.ES

    @model_validator(mode="after")
    def _absolute_path(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("review output path must be resolved by the requesting frontend")
        return self


class CalculationReviewXlsxResult(BaseModel):
    """Published-byte identity, saved lifecycle and review quality without taxpayer values."""

    model_config = STRICT_FROZEN_CONFIG
    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    output_path: str = Field(min_length=1)
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    snapshot_digest: ContentDigest
    title: str = Field(min_length=1)
    calculation_state: CalculationRevisionState
    review_status: ReviewStatus


class CalculationReviewXlsxExecutionResult(BaseModel):
    """Private settlement bound to the invocation that published the local artifact."""

    model_config = STRICT_FROZEN_CONFIG
    identity: OperationIdentity
    result: CalculationReviewXlsxResult


@dataclass(frozen=True, slots=True)
class CalculationReviewXlsxPorts:
    """Local custody and materializer bound to one profile and authority operation."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    load_snapshot: Callable[[CalculationRevisionId, Hex64Str | None], ReviewSnapshot]
    materialize: SheetWorkbookMaterializer


class CalculationReviewXlsxPortsFactory(Protocol):
    """Compose encrypted saved-revision reads and the local-only workbook transport."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> CalculationReviewXlsxPorts:
        """Bind local custody to the exact admitted profile and authority."""
        ...


class CalculationReviewXlsxExecutor:
    """Render before publication, recheck admission and retain truthful effect state."""

    def __init__(self, factory: CalculationReviewXlsxPortsFactory) -> None:
        """Retain the composition factory without opening custody or a transport."""
        self._factory = factory

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Publish only the exact saved baseline named by the admitted request."""
        payload = require_access_request_payload(
            request,
            definition_id=CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
            payload_type=CalculationReviewXlsxRequest,
        )
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID)
        ports = self._factory(profile_id=payload.profile_id, operation=context.authority_operation)
        if ports.profile_id != payload.profile_id or ports.operation is not context.authority_operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        sink = LocalFileExportSink(path=Path(payload.output_path), replace_existing=payload.replace_existing)
        sink.require_writable()
        snapshot = await asyncio.to_thread(
            ports.load_snapshot, payload.calculation_revision_id, payload.filing_record_id
        )
        selection = snapshot.selection
        if (
            not isinstance(selection, CalculationReviewSelection)
            or selection.profile_id != payload.profile_id
            or selection.calculation_revision_id != payload.calculation_revision_id
            or snapshot.calculation_lifecycle is None
            or (
                payload.filing_record_id is not None
                and snapshot.calculation_lifecycle.filing_record_id != payload.filing_record_id
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        lifecycle = snapshot.calculation_lifecycle
        plan = build_review_workbook(
            snapshot,
            publication_id=uuid4(),
            exported_at=now(),
            label=ReviewWorkbookLabels(payload.report_language),
        )
        data = await asyncio.to_thread(ports.materialize, plan)

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                require_operation_profile(request, context, payload.profile_id)
                sink.require_writable()
                await context.events.effect(OperationEffect.UNKNOWN)
                receipt = await asyncio.to_thread(sink.write, data)
                await context.events.effect(OperationEffect.UPDATED)
                result = CalculationReviewXlsxResult(
                    profile_id=payload.profile_id,
                    calculation_revision_id=payload.calculation_revision_id,
                    work_unit_id=selection.work_unit_id,
                    output_path=str(receipt.path),
                    byte_size=receipt.byte_size,
                    file_sha256=receipt.sha256,
                    snapshot_digest=snapshot.snapshot_digest,
                    title=plan.metadata.title,
                    calculation_state=lifecycle.state,
                    review_status=snapshot.status,
                )
                return await context.operands.put(
                    CalculationReviewXlsxExecutionResult(identity=context.identity, result=result),
                    written_at=now(),
                )

        return await await_cancellation_complete(publish(), task_name="calculation-review-xlsx-publication")


def build_calculation_review_xlsx_definition(factory: CalculationReviewXlsxPortsFactory) -> OperationDefinition:
    """Enroll local review exports for saved drafts and historical sealed calculations."""
    return build_single_phase_definition(
        definition_id=CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
        request_type=CalculationReviewXlsxRequest,
        result_type=CalculationReviewXlsxExecutionResult,
        executor_type=CalculationReviewXlsxExecutor,
        build=lambda: CalculationReviewXlsxExecutor(factory),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _resolve_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    payload = require_access_request_payload(
        request,
        definition_id=CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
        payload_type=CalculationReviewXlsxRequest,
    )
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def _project_result(value: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(value) is not CalculationReviewXlsxExecutionResult:
        raise ValueError("invalid local calculation review result")
    if (
        receipt.identity != value.identity
        or receipt.identity.definition_id != CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(value.result.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("local calculation review result differs from its terminal receipt")
    return value.result


def build_calculation_review_xlsx_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Expose only the settled review publication receipt through admitted local clients."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=CalculationReviewXlsxResult,
        access_resolver=_resolve_access,
        result_projector=_project_result,
    )
