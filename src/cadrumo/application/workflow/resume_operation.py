"""Authenticated capture of resume context without starting a filing attempt."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..modelo.calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from ..operations.access_resolution import (
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_admitted_submission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .obligation_snapshot import WorkflowObligationSnapshot
from .resume import (
    WorkflowResumeRefusedError,
    WorkflowResumeRunAmbiguousError,
    WorkflowResumeSelection,
    resolve_modelo_workflow_resume_target,
    resume_modelo_workflow,
)
from .resume_contracts import (
    WorkflowResumeAddress,
    WorkflowResumeAmbiguity,
    WorkflowResumeCandidateSnapshot,
    WorkflowResumeOutcome,
    WorkflowResumeProjection,
    WorkflowResumeRefusal,
    WorkflowResumeRequest,
    WorkflowResumeResult,
    WorkflowResumeSuccess,
)
from .run_models import WorkflowResult
from .run_projection import validate_run_period_facts
from .run_read_ports import WorkflowRunReadPorts, WorkflowRunReadPortsFactory

WORKFLOW_RESUME_OPERATION_DEFINITION_ID = "workflow.resume.context"
WORKFLOW_RESUME_REFUSAL_CODE = "REFUSED_WORKFLOW_RESUME"
WORKFLOW_RESUME_AMBIGUITY_CODE = "REFUSED_WORKFLOW_RESUME_RUN_AMBIGUOUS"


def _resume_receipt_refusal_code(outcome: WorkflowResumeOutcome) -> str | None:
    if isinstance(outcome, WorkflowResumeRefusal):
        return WORKFLOW_RESUME_REFUSAL_CODE
    if isinstance(outcome, WorkflowResumeAmbiguity):
        return WORKFLOW_RESUME_AMBIGUITY_CODE
    return None


def _validate_resume_receipt_identity(receipt: OperationTerminalReceipt, profile_id: str) -> None:
    if receipt.identity.definition_id != WORKFLOW_RESUME_OPERATION_DEFINITION_ID:
        raise ValueError("resume result differs from its terminal receipt")
    if receipt.identity.subject_ref != profile_operation_subject(profile_id):
        raise ValueError("resume result differs from its terminal receipt")


def _validate_resume_receipt_outcome(receipt: OperationTerminalReceipt, refusal_code: str | None) -> None:
    condition = OperationTerminalCondition.REFUSED if refusal_code else OperationTerminalCondition.SUCCEEDED
    if receipt.effect is not OperationEffect.NONE:
        raise ValueError("resume result differs from its terminal receipt")
    if receipt.condition is not condition:
        raise ValueError("resume result differs from its terminal receipt")
    if receipt.refusal_ref != refusal_code:
        raise ValueError("resume result differs from its terminal receipt")
    if (receipt.refusal_detail_ref is not None) != (refusal_code is not None):
        raise ValueError("resume result differs from its terminal receipt")


def project_workflow_resume_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Match the captured outcome to its supervisor-owned terminal receipt."""
    if type(result) is not WorkflowResumeResult:
        raise ValueError("invalid resume result type")
    private = WorkflowResumeResult.model_validate(result.model_dump(mode="python"), strict=True)
    _validate_resume_receipt_identity(receipt, str(private.profile_id))
    _validate_resume_receipt_outcome(receipt, _resume_receipt_refusal_code(private.outcome))
    return WorkflowResumeProjection(profile_id=private.profile_id, outcome=private.outcome)


class WorkflowResumeExecutor:
    """Resolve and validate the same captured record inside profile custody."""

    def __init__(self, runs: WorkflowRunReadPortsFactory, calculations: CalculationActionPortsFactory) -> None:
        """Retain explicit factories, never an ambient profile repository."""
        self._runs = runs
        self._calculations = calculations

    def _capture(self, payload: WorkflowResumeRequest, operation: PinnedAuthorityOperation) -> WorkflowResumeOutcome:
        runs, ports = self._capture_authorities(payload, operation)
        expected, visible_period = self._capture_periods(payload)
        selected = self._resolve_capture_target(payload, expected, visible_period, ports, runs)
        if isinstance(selected, WorkflowResumeAmbiguity):
            return selected
        return self._capture_selected_outcome(payload, expected, selected)

    def _capture_authorities(
        self, payload: WorkflowResumeRequest, operation: PinnedAuthorityOperation
    ) -> tuple[WorkflowRunReadPorts, CalculationActionPorts]:
        profile = str(payload.profile_id)
        runs = self._runs(bucket_id=profile)
        ports = self._calculations(bucket_id=profile, operation=operation)
        if runs.bucket_id != profile or any(
            repo.bucket_id != profile
            for repo in (
                ports.work_unit_repository,
                ports.work_lifecycle_ports.work_unit_repository,
                ports.calculation_repository,
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return runs, ports

    @staticmethod
    def _capture_periods(payload: WorkflowResumeRequest) -> tuple[Period | None, Period | None]:
        constraint = payload.scope_period()
        expected = constraint.to_period() if constraint is not None else None
        visible_period = payload.period.to_period() if payload.period is not None else None
        return expected, visible_period

    @staticmethod
    def _ambiguity_matches_request(
        payload: WorkflowResumeRequest, expected: Period | None, error: WorkflowResumeRunAmbiguousError
    ) -> bool:
        if expected is None:
            return True
        if error.period != expected:
            return False
        return payload.modelo is None or error.modelo == payload.modelo

    def _resolve_capture_target(
        self,
        payload: WorkflowResumeRequest,
        expected: Period | None,
        visible_period: Period | None,
        ports: CalculationActionPorts,
        runs: WorkflowRunReadPorts,
    ) -> WorkflowResumeSelection | WorkflowResumeAmbiguity:
        try:
            selected = resolve_modelo_workflow_resume_target(
                target=payload.target,
                work_unit_id=payload.work_unit_id,
                calculation_revision_id=payload.calculation_revision_id,
                modelo=payload.modelo,
                year=visible_period.filing_year if visible_period is not None else None,
                period=visible_period,
                registry_revision_id=payload.revision_id,
                selector=payload.selector,
                ports=ports,
                runs=runs.runs,
            )
        except WorkflowResumeRunAmbiguousError as exc:
            if not self._ambiguity_matches_request(payload, expected, exc):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
            return WorkflowResumeAmbiguity(
                modelo=exc.modelo,
                period=PublicPeriod.from_period(exc.period),
                candidates=tuple(WorkflowResumeCandidateSnapshot.from_candidate(item) for item in exc.candidates),
            )
        return selected

    @staticmethod
    def _obligation_matches_request(
        payload: WorkflowResumeRequest, expected: Period | None, prior: WorkflowResult
    ) -> bool:
        if expected is None:
            return True
        obligation = prior.obligation
        return (
            obligation is not None
            and obligation.period == expected
            and (payload.modelo is None or obligation.modelo == payload.modelo)
        )

    def _capture_selected_outcome(
        self, payload: WorkflowResumeRequest, expected: Period | None, selected: WorkflowResumeSelection
    ) -> WorkflowResumeOutcome:
        prior = selected.prior
        validate_run_period_facts(prior)
        if not self._obligation_matches_request(payload, expected, prior):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        try:
            context = resume_modelo_workflow(prior)
        except WorkflowResumeRefusedError as exc:
            return WorkflowResumeRefusal(
                run_id=prior.run_id,
                reason=exc.reason,
                final_stage=prior.final_stage,
                aborted_reason=prior.aborted_reason,
            )
        return WorkflowResumeSuccess(
            address=WorkflowResumeAddress.from_resolution(selected.resolution),
            obligation=WorkflowObligationSnapshot.from_obligation(context.obligation),
            aborted_reason=context.aborted_reason,
        )

    async def execute(
        self, request: OperationRequest[WorkflowResumeRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Publish bounded context or refusal evidence without running the workflow."""
        payload = request.payload
        if (
            request.definition_id != WORKFLOW_RESUME_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(WORKFLOW_RESUME_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            outcome = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(
                WorkflowResumeResult(profile_id=payload.profile_id, outcome=outcome),
                written_at=now(),
            )
            await context.events.effect(OperationEffect.NONE)
            if isinstance(outcome, WorkflowResumeRefusal):
                return OperationRefusalEvidence(refusal_code=WORKFLOW_RESUME_REFUSAL_CODE, detail_ref=reference)
            if isinstance(outcome, WorkflowResumeAmbiguity):
                return OperationRefusalEvidence(refusal_code=WORKFLOW_RESUME_AMBIGUITY_CODE, detail_ref=reference)
            return reference

        return await await_cancellation_complete(capture(), task_name="workflow-resume-context")


def build_workflow_resume_definition(
    runs: WorkflowRunReadPortsFactory, calculations: CalculationActionPortsFactory
) -> OperationDefinition:
    """Declare recorded context capture with no domain or provider effects."""
    return build_single_phase_definition(
        definition_id=WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
        request_type=WorkflowResumeRequest,
        result_type=WorkflowResumeResult,
        executor_type=WorkflowResumeExecutor,
        build=lambda: WorkflowResumeExecutor(runs, calculations),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        refusal_detail_codes=frozenset({WORKFLOW_RESUME_REFUSAL_CODE, WORKFLOW_RESUME_AMBIGUITY_CODE}),
    )


def build_workflow_resume_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Authorize the immutable request scope; executor checks the captured data."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, WorkflowResumeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        constraint = payload.scope_period()
        independent = constraint is None
        periods = frozenset[Period]() if constraint is None else frozenset({constraint.to_period()})
        admitted = context.admitted_request
        if admitted is not None:
            require_admitted_submission(admitted, profile_id=context.profile_id, definition_id=request.definition_id)
            if admitted.periods != periods or admitted.period_independent != independent:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return bind_operation_access_profile(
            context,
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
            if independent
            else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=WorkflowResumeProjection,
        result_projector=project_workflow_resume_result,
        access_resolver=resolve,
    )
