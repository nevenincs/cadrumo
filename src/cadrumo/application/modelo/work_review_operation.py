"""Registered exact-profile capture of the compact canonical work review."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition
from ..operations.access_resolution import (
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_or_fresh_single_period_access,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_work_unit_payload, require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .history_operation import bind_profile_history_ports, read_profile_work_unit
from .history_ports import ModeloHistoryPortsFactory
from .work_review import build_modelo_work_review
from .work_review_contracts import (
    MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
    ModeloWorkReviewProjection,
    ModeloWorkReviewRequest,
    ModeloWorkReviewResult,
    ModeloWorkReviewSnapshot,
)


def project_modelo_work_review_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Explicitly disclose only the admitted review identity and compact fields."""
    if type(result) is not ModeloWorkReviewResult:
        raise ValueError("invalid work review result type")
    private = ModeloWorkReviewResult.model_validate(result.model_dump(mode="python"), strict=True)
    require_terminal_receipt_match(
        receipt,
        definition_id=MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
        subject_ref=private.review.work_unit_id,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="work review result does not match its request",
    )
    return ModeloWorkReviewProjection(profile_id=private.profile_id, review=private.review)


class ModeloWorkReviewExecutor:
    """Build a canonical review inside the bound profile worker."""

    def __init__(self, factory: ModeloHistoryPortsFactory) -> None:
        """Retain composition's profile-bound repository factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkReviewRequest], context: OperationExecutorContext
    ) -> str:
        """Build and encrypt the canonical review under the retained authority pin."""
        payload = request.payload
        if request.definition_id != MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id, expected_subject_ref=payload.work_unit_id)
        await context.events.phase(MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkReviewResult:
            ports = bind_profile_history_ports(payload, self._factory, operation=context.authority_operation)
            unit = read_profile_work_unit(payload, ports)
            review = build_modelo_work_review(
                unit.bucket_id,
                unit.modelo,
                unit.filing_year,
                unit.period,
                operation=context.authority_operation,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
                verification_repository=ports.verification_repository,
            )
            snapshot = ModeloWorkReviewSnapshot.from_review(review)
            if snapshot.work_unit_id != unit.work_unit_id or snapshot.registry_revision_id != unit.revision_id:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return ModeloWorkReviewResult(profile_id=payload.profile_id, review=snapshot)

        return await capture_read_result(context, read, task_name="modelo-work-review")


def build_modelo_work_review_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare one recorded, encrypted exact-unit review read."""
    return build_single_phase_definition(
        definition_id=MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkReviewRequest,
        result_type=ModeloWorkReviewResult,
        executor_type=ModeloWorkReviewExecutor,
        build=lambda: ModeloWorkReviewExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_review_registration(
    definition: OperationDefinition, factory: ModeloHistoryPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the stored work period and explicit tax-value result disclosure."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = require_access_request_work_unit_payload(
            request,
            definition_id=definition.definition_id,
            payload_type=ModeloWorkReviewRequest,
            access_profile_id=context.profile_id,
        )
        return bind_replayed_or_fresh_single_period_access(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            definition_id=request.definition_id,
            fresh_period=lambda operation: (
                read_profile_work_unit(
                    payload, bind_profile_history_ports(payload, factory, operation=operation)
                ).period
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkReviewProjection,
        result_projector=project_modelo_work_review_result,
        access_resolver=resolve,
    )
