"""Authenticated capture of resume context without starting a filing attempt."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..modelo.calculation_action_ports import CalculationActionPortsFactory
from ..modelo.selectors import ModeloCalculationRevisionSelector
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
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .abort import WorkflowAbortReason
from .resume import (
    WorkflowResumeRefusalReason,
    WorkflowResumeRefusedError,
    WorkflowResumeRunAmbiguousError,
    WorkflowResumeRunCandidate,
    WorkflowResumeTargetResolution,
    resolve_modelo_workflow_resume_target,
    resume_modelo_workflow,
    workflow_resume_refusal_reason,
)
from .run_models import WorkflowStage
from .run_projection import WorkflowObligationSnapshot, validate_run_period_facts
from .run_read_ports import WorkflowRunReadPortsFactory

WORKFLOW_RESUME_OPERATION_DEFINITION_ID = "workflow.resume.context"
WORKFLOW_RESUME_REFUSAL_CODE = "REFUSED_WORKFLOW_RESUME"
WORKFLOW_RESUME_AMBIGUITY_CODE = "REFUSED_WORKFLOW_RESUME_RUN_AMBIGUOUS"


class WorkflowResumeRequest(BaseModel):
    """One exact address or a complete visible filing target, stored privately."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    target: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{16}|[0-9a-f]{64})$")] | None = None
    work_unit_id: WorkUnitId | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")] | None = None
    period: PublicPeriod | None = None
    expected_period: PublicPeriod | None = None
    revision_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    selector: ModeloCalculationRevisionSelector | None = None

    @model_validator(mode="after")
    def _address(self) -> Self:
        exact = sum(item is not None for item in (self.target, self.work_unit_id, self.calculation_revision_id))
        visible = any(item is not None for item in (self.modelo, self.period, self.revision_id))
        if exact > 1 or (exact and visible):
            raise ValueError("resume requires one unambiguous target")
        if not exact and (self.modelo is None or self.period is None):
            raise ValueError("resume requires a complete visible filing target")
        if self.expected_period is not None and not exact:
            raise ValueError("expected period constrains only an exact resume target")
        if self.selector is not None and (
            self.calculation_revision_id is not None or (self.target is not None and len(self.target) == 16)
        ):
            raise ValueError("a direct run or revision does not accept a revision selector")
        return self

    def scope_period(self) -> PublicPeriod | None:
        """Return the explicit constraint without consulting mutable history."""
        return self.period if self.period is not None else self.expected_period


class WorkflowResumeAddress(BaseModel):
    """Closed projection of the canonical selector resolution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    source: Literal[
        "workflow_run_id",
        "work_unit_id",
        "calculation_revision_id",
        "visible_target",
        "visible_target_revision_selector",
    ]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")] | None
    period: PublicPeriod | None
    filing_year: int | None
    work_unit_id: WorkUnitId | None
    short_work_unit_id: str | None
    calculation_revision_id: CalculationRevisionId | None
    short_calculation_revision_id: str | None

    @classmethod
    def from_resolution(cls, resolution: WorkflowResumeTargetResolution) -> Self:
        """Copy selected coordinates without the domain period serializer."""
        return cls.model_validate(
            resolution.model_dump(mode="python")
            | {
                "period": PublicPeriod.from_period(resolution.period) if resolution.period is not None else None,
            }
        )

    def to_resolution(self) -> WorkflowResumeTargetResolution:
        """Restore the canonical address for established CLI presentation."""
        return WorkflowResumeTargetResolution.model_validate(
            self.model_dump(mode="python")
            | {
                "period": self.period.to_period() if self.period is not None else None,
            }
        )


class WorkflowResumeSuccess(BaseModel):
    """The same captured obligation the resumability policy approved."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["success"] = "success"
    address: WorkflowResumeAddress
    obligation: WorkflowObligationSnapshot
    aborted_reason: WorkflowAbortReason

    @model_validator(mode="after")
    def _coordinates(self) -> Self:
        if self.address.period is not None and (
            self.address.period != self.obligation.period or self.address.modelo != self.obligation.modelo
        ):
            raise ValueError("resume context differs from its selected target")
        if (
            workflow_resume_refusal_reason(
                final_stage=WorkflowStage.ABORTED, aborted_reason=self.aborted_reason, has_obligation=True
            )
            is not None
        ):
            raise ValueError("resume success contains a non-resumable abort reason")
        return self


class WorkflowResumeRefusal(BaseModel):
    """Bounded factual guidance for a canonical resumability refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["refused"] = "refused"
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    reason: WorkflowResumeRefusalReason
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None

    @model_validator(mode="after")
    def _canonical_reason(self) -> Self:
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError("resume refusal requires terminal facts")
        if self.final_stage is WorkflowStage.DONE and self.aborted_reason is not None:
            raise ValueError("completed run cannot carry an abort reason")
        expected = workflow_resume_refusal_reason(
            final_stage=self.final_stage,
            aborted_reason=self.aborted_reason,
            has_obligation=self.reason is not WorkflowResumeRefusalReason.NO_OBLIGATION,
        )
        if expected is not self.reason:
            raise ValueError("resume refusal contradicts its terminal facts")
        return self


class WorkflowResumeCandidateSnapshot(BaseModel):
    """One candidate in an explicitly authorized ambiguous filing period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    run_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None
    started_at: datetime
    short_work_unit_id: str | None
    work_unit_id: WorkUnitId | None

    @model_validator(mode="after")
    def _terminal(self) -> Self:
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError("resume candidate requires terminal facts")
        if (self.final_stage is WorkflowStage.ABORTED) != (self.aborted_reason is not None):
            raise ValueError("resume candidate has contradictory abort facts")
        return self

    @classmethod
    def from_candidate(cls, candidate: WorkflowResumeRunCandidate) -> Self:
        """Project typed canonical facts rather than exception context text."""
        return cls.model_validate(
            candidate.model_dump(mode="python")
            | {
                "period": PublicPeriod.from_period(candidate.period),
                "final_stage": WorkflowStage(candidate.final_stage),
                "aborted_reason": WorkflowAbortReason(candidate.aborted_reason) if candidate.aborted_reason else None,
            }
        )

    def to_candidate(self) -> WorkflowResumeRunCandidate:
        """Restore the existing localized guidance input."""
        return WorkflowResumeRunCandidate.model_validate(
            self.model_dump(mode="python")
            | {
                "period": self.period.to_period(),
                "final_stage": self.final_stage.value,
                "aborted_reason": self.aborted_reason.value if self.aborted_reason else None,
            }
        )


class WorkflowResumeAmbiguity(BaseModel):
    """Multiple captured candidates; no automatic retry target is chosen."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["ambiguous"] = "ambiguous"
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    candidates: tuple[WorkflowResumeCandidateSnapshot, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _coordinates(self) -> Self:
        if any(item.modelo != self.modelo or item.period != self.period for item in self.candidates):
            raise ValueError("resume ambiguity crosses filing targets")
        if len({item.run_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("resume ambiguity repeats a run")
        return self


type WorkflowResumeOutcome = Annotated[
    WorkflowResumeSuccess | WorkflowResumeRefusal | WorkflowResumeAmbiguity, Field(discriminator="kind")
]


class WorkflowResumeResult(BaseModel):
    """Private encrypted resume-context operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    outcome: WorkflowResumeOutcome


class WorkflowResumeProjection(BaseModel):
    """Independent frontend schema for explicitly disclosed resume facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    outcome: WorkflowResumeOutcome


def project_workflow_resume_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Match the captured outcome to its supervisor-owned terminal receipt."""
    if type(result) is not WorkflowResumeResult:
        raise ValueError("invalid resume result type")
    private = WorkflowResumeResult.model_validate(result.model_dump(mode="python"), strict=True)
    outcome = private.outcome
    code = (
        WORKFLOW_RESUME_REFUSAL_CODE
        if isinstance(outcome, WorkflowResumeRefusal)
        else WORKFLOW_RESUME_AMBIGUITY_CODE
        if isinstance(outcome, WorkflowResumeAmbiguity)
        else None
    )
    if (
        receipt.identity.definition_id != WORKFLOW_RESUME_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(private.profile_id))
        or receipt.effect is not OperationEffect.NONE
        or receipt.condition
        is not (OperationTerminalCondition.REFUSED if code else OperationTerminalCondition.SUCCEEDED)
        or receipt.refusal_ref != code
        or (receipt.refusal_detail_ref is not None) != (code is not None)
    ):
        raise ValueError("resume result differs from its terminal receipt")
    return WorkflowResumeProjection(profile_id=private.profile_id, outcome=outcome)


class WorkflowResumeExecutor:
    """Resolve and validate the same captured record inside profile custody."""

    def __init__(self, runs: WorkflowRunReadPortsFactory, calculations: CalculationActionPortsFactory) -> None:
        """Retain explicit factories, never an ambient profile repository."""
        self._runs = runs
        self._calculations = calculations

    def _capture(self, payload: WorkflowResumeRequest, operation: PinnedAuthorityOperation) -> WorkflowResumeOutcome:
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
        constraint = payload.scope_period()
        expected = constraint.to_period() if constraint is not None else None
        visible_period = payload.period.to_period() if payload.period is not None else None
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
            if expected is not None and (
                exc.period != expected or (payload.modelo is not None and exc.modelo != payload.modelo)
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
            return WorkflowResumeAmbiguity(
                modelo=exc.modelo,
                period=PublicPeriod.from_period(exc.period),
                candidates=tuple(WorkflowResumeCandidateSnapshot.from_candidate(item) for item in exc.candidates),
            )
        prior = selected.prior
        validate_run_period_facts(prior)
        if expected is not None and (
            prior.obligation is None
            or prior.obligation.period != expected
            or (payload.modelo is not None and prior.obligation.modelo != payload.modelo)
        ):
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
    return OperationDefinition(
        definition_id=WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
        request_type=WorkflowResumeRequest,
        result_type=WorkflowResumeResult,
        executor_factory=OperationExecutorFactory(
            request_type=WorkflowResumeRequest,
            executor_type=WorkflowResumeExecutor,
            build=lambda: WorkflowResumeExecutor(runs, calculations),
        ),
        phase_codes=(WORKFLOW_RESUME_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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
