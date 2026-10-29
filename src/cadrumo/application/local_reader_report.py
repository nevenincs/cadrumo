"""The measured machine and per-role derived model report for local inference, and its read operation.

:func:`read_local_reader_report` measures this computer's memory and
accelerator and reports the lane the agent service derives for each role.
``local-reader.report`` serves that measurement to every frontend. It reads
only: nothing is pulled, loaded or started, and the local AI server is not
asked anything. Whether a model fits the memory free is the agent's answer
when it loads the model.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from pydantic import BaseModel, Field, NonNegativeInt

from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_MODEL_ID_MAX_LENGTH,
    ModelRunLane,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ..core.hardware import AcceleratorKind
from ..core.model_roles import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader import RoleLane, read_role_lanes, selected_model_condition
from .local_reader_contracts import (
    LOCAL_READER_OPERATION_SUBJECT,
    LocalReaderFactV1,
    local_reader_public_facts,
    local_reader_verdict_condition,
    local_reader_verdict_facts,
)
from .local_reader_operation import bind_machine_reader_access
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.operation_definition import OperationDefinition, build_single_phase_definition
from .operations.owner import OperationExecutorContext
from .operations.registry import OperationPublicDefinitionRegistrationV1
from .operations.subject_reference import OperationSubjectReferenceV1
from .operator_actions.models import PreconditionVerdict
from .probe_outcomes import ProbeFactValue, probe_no_recovery_verdict
from .workstation_probes import probe_hardware_profile

__all__ = [
    "LOCAL_READER_REPORT_OPERATION_DEFINITION_ID",
    "LocalReaderReport",
    "LocalReaderReportExecutor",
    "LocalReaderReportModel",
    "LocalReaderReportModelV1",
    "LocalReaderReportPublicResultV1",
    "LocalReaderReportRequest",
    "build_local_reader_report_definition",
    "build_local_reader_report_registration",
    "local_reader_report_public_result",
    "project_local_reader_report_result",
    "read_local_reader_report",
    "resolve_local_reader_report_access",
]

LOCAL_READER_REPORT_OPERATION_DEFINITION_ID = "local-reader.report"


class LocalReaderReportModel(BaseModel):
    """One role's resolved model."""

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    selected: bool
    facts: Mapping[str, ProbeFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None


class LocalReaderReport(BaseModel):
    """What the machine measures and which model each role resolves to.

    Each figure is ``None`` when it could not be measured, as on the hardware
    profile it is read from.
    """

    model_config = STRICT_FROZEN_CONFIG

    accelerator: AcceleratorKind
    total_vram_bytes: int | None = Field(default=None, ge=0)
    free_vram_bytes: int | None = Field(default=None, ge=0)
    total_system_memory_bytes: int | None = Field(default=None, ge=0)
    free_system_memory_bytes: int | None = Field(default=None, ge=0)
    models: tuple[LocalReaderReportModel, ...]


def read_local_reader_report(lanes: Mapping[ModelRole, RoleLane]) -> LocalReaderReport:
    """Measure hardware and report each role's selected lane.

    ``lanes`` is what :func:`~.local_reader.read_role_lanes` resolved for every
    role. Only a lane that stays on this computer names a model here, because
    only its model loads on this machine; an off-host lane is selected and
    names none. Reads only, and never raises for an unmeasurable device: each
    figure is reported as the state it is.
    """
    profile = probe_hardware_profile()
    return LocalReaderReport(
        accelerator=profile.accelerator.kind,
        total_vram_bytes=profile.total_vram_bytes,
        free_vram_bytes=profile.free_vram_bytes,
        total_system_memory_bytes=profile.memory.total_bytes,
        free_system_memory_bytes=profile.memory.free_bytes,
        models=tuple(_report_model(role, lanes.get(role)) for role in ModelRole),
    )


def _report_model(role: ModelRole, answer: RoleLane | None) -> LocalReaderReportModel:
    if not isinstance(answer, ModelRunLane):
        code = (answer or ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)).code
        facts: dict[str, ProbeFactValue] = {
            "role": role.value,
            "model_run_refusal": code.value,
            "role_selection_required": code is ModelRunRefusalCode.NO_SELECTION,
        }
        return LocalReaderReportModel(
            role=role,
            selected=False,
            facts=facts,
            precondition_verdict=probe_no_recovery_verdict(selected_model_condition(code), facts=facts),
        )
    if answer.reads_off_host:
        return LocalReaderReportModel(role=role, selected=True, facts={"role": role.value, "reads_off_host": True})
    facts = {"role": role.value, "reads_off_host": False, "selected_model": answer.model}
    # The catalogue states 0 for an unknown size, which is no size to report.
    size = answer.size_bytes
    if size is not None and size > 0:
        facts["size_bytes"] = size
    return LocalReaderReportModel(role=role, model=answer.model, selected=True, facts=facts)


class LocalReaderReportRequest(CredentialFreeOperationRequest):
    """One report read; the machine is the whole subject, so the request carries nothing."""


class LocalReaderReportModelV1(BaseModel):
    """Public projection of one role's resolved model."""

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = Field(default=None, min_length=1, max_length=MODEL_RUN_MODEL_ID_MAX_LENGTH)
    selected: bool
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


class LocalReaderReportPublicResultV1(BaseModel):
    """Public projection of the local-inference report."""

    model_config = STRICT_FROZEN_CONFIG

    accelerator: AcceleratorKind
    total_vram_bytes: NonNegativeInt | None = None
    free_vram_bytes: NonNegativeInt | None = None
    total_system_memory_bytes: NonNegativeInt | None = None
    free_system_memory_bytes: NonNegativeInt | None = None
    models: tuple[LocalReaderReportModelV1, ...]


class LocalReaderReportExecutor:
    """Measure the report and persist it; nothing is pulled, loaded or started."""

    async def execute(
        self,
        request: OperationRequest[LocalReaderReportRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the report and persist it."""
        if request.subject_ref != LOCAL_READER_OPERATION_SUBJECT:
            raise ValueError("local-reader operation subject must name the local runtime")
        await context.events.phase(LOCAL_READER_REPORT_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        lanes = await read_role_lanes(ModelRole)
        report = await asyncio.to_thread(read_local_reader_report, lanes)
        return await context.operands.put(report, written_at=now())


def build_local_reader_report_definition() -> OperationDefinition:
    """Declare the local-inference report read."""
    return build_single_phase_definition(
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        request_type=LocalReaderReportRequest,
        subject_reference=OperationSubjectReferenceV1.fixed(LOCAL_READER_OPERATION_SUBJECT),
        result_type=LocalReaderReport,
        executor_type=LocalReaderReportExecutor,
        build=LocalReaderReportExecutor,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def resolve_local_reader_report_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind access to the machine's reader without COMMIT: a report changes no record."""
    return bind_machine_reader_access(
        request,
        context,
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        payload_type=LocalReaderReportRequest,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
    )


def project_local_reader_report_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    """Project a settled report into its public result."""
    del terminal_receipt
    return local_reader_report_public_result(LocalReaderReport.model_validate(result, strict=True))


def local_reader_report_public_result(report: LocalReaderReport) -> LocalReaderReportPublicResultV1:
    """Return the public result of one report, whichever caller measured it."""
    return LocalReaderReportPublicResultV1(
        accelerator=report.accelerator,
        total_vram_bytes=report.total_vram_bytes,
        free_vram_bytes=report.free_vram_bytes,
        total_system_memory_bytes=report.total_system_memory_bytes,
        free_system_memory_bytes=report.free_system_memory_bytes,
        models=tuple(
            LocalReaderReportModelV1(
                role=row.role,
                model=row.model,
                selected=row.selected,
                facts=local_reader_public_facts(row.facts),
                verdict_condition_id=local_reader_verdict_condition(row.precondition_verdict),
                verdict_facts=local_reader_verdict_facts(row.precondition_verdict),
            )
            for row in report.models
        ),
    )


def build_local_reader_report_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the report definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LocalReaderReportPublicResultV1,
        result_projector=project_local_reader_report_result,
        access_resolver=resolve_local_reader_report_access,
    )
