"""Registered exact-profile reads of persisted workflow terminal facts."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_admitted_submission,
    require_period_independent_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES, OperationCapabilities
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .run_models import WorkflowResult
from .run_projection import WorkflowRunSnapshot, validate_run_period_facts
from .run_read_ports import WorkflowRunReadPorts, WorkflowRunReadPortsFactory

WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID = "workflow.run.read"
WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID = "workflow.run.list"


class WorkflowRunReadRequest(CredentialFreeOperationRequest):
    """Address one immutable profile/run and optionally constrain its period."""

    profile_id: UUID
    run_id: str = Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")
    expected_period: PublicPeriod | None = None


class WorkflowRunListRequest(CredentialFreeOperationRequest):
    """Request the complete workflow history of one authenticated profile."""

    profile_id: UUID


class WorkflowRunReadResult(BaseModel):
    """Private encrypted terminal snapshot for one exact run."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    expected_period: PublicPeriod | None
    run: WorkflowRunSnapshot

    @model_validator(mode="after")
    def _constrained(self) -> Self:
        if self.expected_period is not None and (
            self.run.obligation is None or self.run.obligation.period != self.expected_period
        ):
            raise ValueError("workflow run does not match its explicit period")
        return self


class WorkflowRunReadProjection(BaseModel):
    """Independent closed public result for one terminal run snapshot."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    expected_period: PublicPeriod | None
    run: WorkflowRunSnapshot

    @model_validator(mode="after")
    def _constrained(self) -> Self:
        if self.expected_period is not None and (
            self.run.obligation is None or self.run.obligation.period != self.expected_period
        ):
            raise ValueError("workflow run does not match its explicit period")
        return self


class WorkflowRunListResult(BaseModel):
    """Private encrypted snapshot of the complete canonical run order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    runs: tuple[WorkflowRunSnapshot, ...]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        if len({run.run_id for run in self.runs}) != len(self.runs):
            raise ValueError("workflow inventory repeats a run identity")
        return self


class WorkflowRunListProjection(BaseModel):
    """Independent public projection of the same ordered terminal summaries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    runs: tuple[WorkflowRunSnapshot, ...]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        if len({run.run_id for run in self.runs}) != len(self.runs):
            raise ValueError("workflow inventory repeats a run identity")
        return self


def project_workflow_run_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Disclose one terminal snapshot only under its exact successful receipt."""
    if type(result) is not WorkflowRunReadResult:
        raise ValueError("invalid workflow run result type")
    private = WorkflowRunReadResult.model_validate(result.model_dump(mode="python"), strict=True)
    if (
        receipt.identity.definition_id != WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != private.run.run_id
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("workflow run result does not match its receipt")
    return WorkflowRunReadProjection(
        profile_id=private.profile_id, expected_period=private.expected_period, run=private.run
    )


def project_workflow_run_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Disclose complete inventory only under its exact profile receipt."""
    if type(result) is not WorkflowRunListResult:
        raise ValueError("invalid workflow list result type")
    private = WorkflowRunListResult.model_validate(result.model_dump(mode="python"), strict=True)
    if (
        receipt.identity.definition_id != WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(private.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("workflow list result does not match its receipt")
    return WorkflowRunListProjection(profile_id=private.profile_id, runs=private.runs)


def _bound_ports(profile_id: UUID, factory: WorkflowRunReadPortsFactory) -> WorkflowRunReadPorts:
    from ...core.bucket_pointer import require_active_bucket_id

    bucket_id = str(profile_id)
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    ports = factory(bucket_id=bucket_id)
    if ports.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _read_exact_run(payload: WorkflowRunReadRequest, ports: WorkflowRunReadPorts) -> WorkflowResult:
    run = ports.runs.load(payload.run_id)
    if run.run_id != payload.run_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    validate_run_period_facts(run)
    if payload.expected_period is not None and (
        run.obligation is None or PublicPeriod.from_period(run.obligation.period) != payload.expected_period
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PERIOD_DENIED)
    return run


class WorkflowRunReadExecutor:
    """Capture one canonical record once inside the exact profile worker."""

    def __init__(self, factory: WorkflowRunReadPortsFactory) -> None:
        """Retain only composition's explicit profile-bound reader factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[WorkflowRunReadRequest], context: OperationExecutorContext
    ) -> str:
        """Encrypt the same run that satisfied the explicit request constraint."""
        payload = request.payload
        if (
            request.definition_id != WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID
            or request.subject_ref != payload.run_id
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID)

        def read() -> WorkflowRunReadResult:
            ports = _bound_ports(payload.profile_id, self._factory)
            run = _read_exact_run(payload, ports)
            return WorkflowRunReadResult(
                profile_id=payload.profile_id,
                expected_period=payload.expected_period,
                run=WorkflowRunSnapshot.from_run(run),
            )

        return await capture_read_result(context, read, task_name="workflow-run-read")


class WorkflowRunListExecutor:
    """Capture the canonical complete inventory order inside profile custody."""

    def __init__(self, factory: WorkflowRunReadPortsFactory) -> None:
        """Retain only composition's explicit profile-bound reader factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[WorkflowRunListRequest], context: OperationExecutorContext
    ) -> str:
        """Encrypt one complete terminal-summary inventory."""
        payload = request.payload
        if (
            request.definition_id != WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID)

        def read() -> WorkflowRunListResult:
            ports = _bound_ports(payload.profile_id, self._factory)
            runs = ports.runs.list()
            for run in runs:
                validate_run_period_facts(run)
            return WorkflowRunListResult(
                profile_id=payload.profile_id,
                runs=tuple(WorkflowRunSnapshot.from_run(run) for run in runs),
            )

        return await capture_read_result(context, read, task_name="workflow-run-list")


def _capabilities() -> OperationCapabilities:
    return RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES


def build_workflow_run_read_definition(factory: WorkflowRunReadPortsFactory) -> OperationDefinition:
    """Declare one exact-run recorded read with a bounded optional period."""
    return OperationDefinition(
        definition_id=WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
        request_type=WorkflowRunReadRequest,
        result_type=WorkflowRunReadResult,
        executor_factory=OperationExecutorFactory(
            request_type=WorkflowRunReadRequest,
            executor_type=WorkflowRunReadExecutor,
            build=lambda: WorkflowRunReadExecutor(factory),
        ),
        phase_codes=(WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_workflow_run_list_definition(factory: WorkflowRunReadPortsFactory) -> OperationDefinition:
    """Declare a complete exact-profile workflow inventory read."""
    return OperationDefinition(
        definition_id=WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
        request_type=WorkflowRunListRequest,
        result_type=WorkflowRunListResult,
        executor_factory=OperationExecutorFactory(
            request_type=WorkflowRunListRequest,
            executor_type=WorkflowRunListExecutor,
            build=lambda: WorkflowRunListExecutor(factory),
        ),
        phase_codes=(WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _bind_run_access(
    context: OperationAccessContext, definition_id: str, *, periods: frozenset[Period], independent: bool
) -> ResolvedOperationAccess:
    return bind_operation_access_profile(
        context,
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
        if independent
        else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=definition_id,
        periods=periods,
    )


def build_workflow_run_read_registration(
    definition: OperationDefinition, factory: WorkflowRunReadPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Use only an explicit expected period for finite-scope admission."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, WorkflowRunReadRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != payload.run_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        expected_period = payload.expected_period
        independent = expected_period is None
        periods = frozenset[Period]() if expected_period is None else frozenset({expected_period.to_period()})
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            require_admitted_submission(admitted, profile_id=context.profile_id, definition_id=request.definition_id)
            if admitted.period_independent != independent or admitted.periods != periods:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        else:
            # SUBMIT and START revalidate current storage; RESULT never retargets.
            ports = _bound_ports(payload.profile_id, factory)
            _read_exact_run(payload, ports)
        return _bind_run_access(context, request.definition_id, periods=periods, independent=independent)

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=WorkflowRunReadProjection,
        result_projector=project_workflow_run_read_result,
        access_resolver=resolve,
    )


def build_workflow_run_list_registration(
    definition: OperationDefinition, factory: WorkflowRunReadPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Require independent/all-period disclosure for complete run inventory."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, WorkflowRunListRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            require_period_independent_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            _bound_ports(payload.profile_id, factory)
        return _bind_run_access(context, request.definition_id, periods=frozenset(), independent=True)

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=WorkflowRunListProjection,
        result_projector=project_workflow_run_list_result,
        access_resolver=resolve,
    )
