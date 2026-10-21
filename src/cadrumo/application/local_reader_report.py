"""The measured machine and model-selection report for local inference, and its read operation.

:func:`read_local_reader_report` measures hardware, resolves a model for each
reader role and judges whether the first assessable one could be loaded right
now. ``local-reader.report`` serves that measurement to every frontend. It
reads only: nothing is pulled, loaded or started.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from pydantic import BaseModel, Field, NonNegativeInt

from ..core.config import Settings, load_settings
from ..core.hardware import AcceleratorKind
from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader_contracts import (
    LOCAL_READER_OPERATION_SUBJECT,
    LocalReaderContentionV1,
    LocalReaderFactV1,
    local_reader_public_facts,
    local_reader_verdict_condition,
    local_reader_verdict_facts,
    project_local_reader_contention,
)
from .local_reader_operation import bind_machine_provisioning_access
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.operation_definition import OperationDefinition, build_single_phase_definition
from .operations.owner import OperationExecutorContext
from .operations.registry import OperationPublicDefinitionRegistrationV1
from .operations.subject_reference import OperationSubjectReferenceV1
from .operator_actions.models import PreconditionVerdict
from .provisioning import probe_hardware_profile, select_model_for_role
from .provisioning_contracts import ProvisioningFactValue
from .provisioning_runtime import (
    ContentionSnapshot,
    assess_model_load_contention,
    read_runtime_residents,
    runtime_model_names_match,
)

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
    """One role's resolved model and whether the runtime holds it in memory."""

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    selected: bool
    resident: bool = False
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None


class LocalReaderReport(BaseModel):
    """What the machine measures, which model each role resolves to, and whether one could load now.

    Totals are for reporting and free amounts for acting, as on the hardware
    profile they are read from. ``residents`` is empty both when nothing is
    resident and when the runtime did not answer; ``runtime_reachable`` tells
    the two apart. ``contention`` judges the first role whose selection names
    a model with a known memory requirement, and is absent when none does.
    """

    model_config = STRICT_FROZEN_CONFIG

    accelerator: AcceleratorKind
    total_vram_bytes: int | None = Field(default=None, ge=0)
    free_vram_bytes: int | None = Field(default=None, ge=0)
    total_system_memory_bytes: int | None = Field(default=None, ge=0)
    free_system_memory_bytes: int | None = Field(default=None, ge=0)
    runtime_reachable: bool
    residents: tuple[str, ...] = ()
    models: tuple[LocalReaderReportModel, ...]
    contention: ContentionSnapshot | None = None


def read_local_reader_report(settings: Settings | None = None) -> LocalReaderReport:
    """Measure hardware, select a model per role, and judge admission of the first assessable load.

    Reads only, and never raises for an unreachable runtime or an unmeasurable
    device: each is reported as the state it is.
    """
    resolved = settings if settings is not None else load_settings()
    profile = probe_hardware_profile()
    residents = read_runtime_residents(resolved)
    resident_names = tuple(entry.name for entry in residents) if residents is not None else ()
    models: list[LocalReaderReportModel] = []
    primary: tuple[str, int] | None = None
    for role in ModelRole:
        selection = select_model_for_role(role, profile=profile, settings=resolved)
        runtime_id = selection.runtime_id
        models.append(
            LocalReaderReportModel(
                role=role,
                model=runtime_id,
                selected=selection.selected,
                resident=runtime_id is not None
                and any(runtime_model_names_match(name, runtime_id) for name in resident_names),
                facts=selection.facts,
                precondition_verdict=selection.precondition_verdict,
            )
        )
        if primary is None:
            primary = selection.assessable_load
    contention = None
    if primary is not None:
        contention = assess_model_load_contention(
            primary[0],
            primary[1],
            profile=profile,
            residents=residents,
            residents_measured=residents is not None,
            settings=resolved,
        )
    return LocalReaderReport(
        accelerator=profile.accelerator.kind,
        total_vram_bytes=profile.total_vram_bytes,
        free_vram_bytes=profile.free_vram_bytes,
        total_system_memory_bytes=profile.memory.total_bytes,
        free_system_memory_bytes=profile.memory.free_bytes,
        runtime_reachable=residents is not None,
        residents=resident_names,
        models=tuple(models),
        contention=contention,
    )


class LocalReaderReportRequest(CredentialFreeOperationRequest):
    """One report read; the machine is the whole subject, so the request carries nothing."""


class LocalReaderReportModelV1(BaseModel):
    """Public projection of one role's resolved model."""

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = Field(default=None, min_length=1, max_length=256)
    selected: bool
    resident: bool
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
    runtime_reachable: bool
    residents: tuple[str, ...]
    models: tuple[LocalReaderReportModelV1, ...]
    contention: LocalReaderContentionV1 | None = None


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
        report = await asyncio.to_thread(read_local_reader_report)
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
    return bind_machine_provisioning_access(
        request,
        context,
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        payload_type=LocalReaderReportRequest,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        commits=lambda _payload: False,
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
        runtime_reachable=report.runtime_reachable,
        residents=report.residents,
        models=tuple(
            LocalReaderReportModelV1(
                role=row.role,
                model=row.model,
                selected=row.selected,
                resident=row.resident,
                facts=local_reader_public_facts(row.facts),
                verdict_condition_id=local_reader_verdict_condition(row.precondition_verdict),
                verdict_facts=local_reader_verdict_facts(row.precondition_verdict),
            )
            for row in report.models
        ),
        contention=project_local_reader_contention(report.contention),
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
