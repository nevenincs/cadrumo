"""Registered exact-profile reads of persisted workflow terminal facts."""

from __future__ import annotations

import asyncio
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
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
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
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

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="workflow-run-read")


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

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="workflow-run-list")


def _capabilities() -> OperationCapabilities:
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


def _disclosures(context: OperationAccessContext) -> frozenset[DisclosurePermission]:
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        return frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    if context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            )
        )
    return frozenset[DisclosurePermission]()


def _policy(
    context: OperationAccessContext, definition_id: str, *, periods: frozenset[Period], independent: bool
) -> OperationAccessPolicy:
    return OperationAccessPolicy(
        definition_id=definition_id,
        definition_contract_digest=context.contract.definition_contract_digest,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=_disclosures(context),
        periods=periods,
        allow_period_independent=independent,
        requires_all_periods=independent,
        backend=Availability.AVAILABLE,
        published_authority=context.published_authority,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
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
        if admitted is not None and context.action in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }:
            if (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or admitted.period_independent != independent
                or admitted.periods != periods
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        else:
            # SUBMIT and START revalidate current storage; RESULT never retargets.
            ports = _bound_ports(payload.profile_id, factory)
            _read_exact_run(payload, ports)
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=periods,
                period_independent=independent,
                destination_id=context.destination_id,
            ),
            policy=_policy(context, request.definition_id, periods=periods, independent=independent),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=WorkflowRunReadRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=WorkflowRunReadProjection
        ),
        access_resolver=resolve,
        result_projector=project_workflow_run_read_result,
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
        if (
            admitted is not None
            and context.action in {AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.CANCEL, AccessAction.DETACH}
            and (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or not admitted.period_independent
                or admitted.periods
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if admitted is None or context.action not in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }:
            _bound_ports(payload.profile_id, factory)
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=frozenset(),
                period_independent=True,
                destination_id=context.destination_id,
            ),
            policy=_policy(context, request.definition_id, periods=frozenset(), independent=True),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=WorkflowRunListRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=WorkflowRunListProjection
        ),
        access_resolver=resolve,
        result_projector=project_workflow_run_list_result,
    )
