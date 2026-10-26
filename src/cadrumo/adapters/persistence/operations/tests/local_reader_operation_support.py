"""Real supervision of the local-reader operations for tests.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The local AI program's row is the components role's quick
status, decoded from the role's recorded output. Each role's lane is answered
by an execution authority standing in for the runtime host and the agent
service, which have their own tests; the supervisor binds the model-run port it
offers exactly as it binds the host's. Every model id is synthetic.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
)

from .....application.local_reader import ProgramRow, RoleLane
from .....application.local_reader_report import (
    build_local_reader_report_definition,
    build_local_reader_report_registration,
)
from .....application.local_reader_status_operation import (
    build_local_reader_status_definition,
    build_local_reader_status_registration,
)
from .....application.operations.composition import OperationComposedServices, compose_operation_services
from .....application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .....application.operations.models import OperationIdentity, OperationRequest
from .....application.operations.registry import OperationRegistry
from .....application.operations.tests.authority_test_support import unread_authority_operation
from .....core.model_roles import ModelRole
from .....core.operations import OperationEffect, OperationEventKind, OperationTerminalCondition
from ....outbound.components.tests.recorded_rows import set_up_row
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository
from ..secure_references import operation_secure_reference_repository

__all__ = [
    "READER_LANES",
    "SET_UP_PROGRAM",
    "TEXT_MODEL",
    "VISION_MODEL",
    "SupervisedRun",
    "provisioning_registry",
    "run_supervised",
    "run_supervised_in",
]

VISION_MODEL = "synthetic-vision:small"
TEXT_MODEL = "synthetic-text:small"


#: The local AI program as the components role reports it once set up.
SET_UP_PROGRAM: ProgramRow = set_up_row("local_ai")


def _on_host_lane(model: str, *, installed: bool) -> ModelRunLane:
    return ModelRunLane(
        provider_id="ollama",
        transport="api",
        model=model,
        reads_off_host=False,
        licence=None,
        size_bytes=1024,
        vision=None,
        context_length=None,
        installed=installed,
    )


#: The person's selection: both reader roles on the local lane, the text model held by the server and the
#: vision model not, and no other role selected.
READER_LANES: Mapping[ModelRole, RoleLane] = {
    ModelRole.TEXT_EXTRACTION: _on_host_lane(TEXT_MODEL, installed=True),
    ModelRole.VISION_TRANSCRIPTION: _on_host_lane(VISION_MODEL, installed=False),
    ModelRole.COLUMN_ROLE_MAPPING: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
    ModelRole.SUPPLY_NATURE_PROPOSAL: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
}


class _SelectionAuthority:
    """An execution authority that admits every operation and answers each role's lookup from ``lanes``."""

    def __init__(self, lanes: Mapping[ModelRole, RoleLane]) -> None:
        self._lanes = lanes

    async def require[Payload: BaseModel](
        self, *, identity: OperationIdentity, request: OperationRequest[Payload], action: AccessAction
    ) -> None:
        del identity, request, action

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        del identity
        yield

    async def model_run_lookup(self, identity: OperationIdentity, role: str) -> ModelRunLane | ModelRunRefusal:
        del identity
        return self._lanes[ModelRole(role)]

    async def model_run_selections(
        self, identity: OperationIdentity
    ) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        del identity
        return ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)

    async def model_run(
        self, identity: OperationIdentity, header: ModelRunHeader, body: ModelRunBody
    ) -> ModelRunOutput | ModelRunRefusal:
        del identity, header, body
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)


def provisioning_registry(program: ProgramRow = SET_UP_PROGRAM) -> OperationRegistry:
    """Register the two local-reader operations, the status reading ``program`` as the local AI's row."""
    status = build_local_reader_status_definition(lambda: program)
    report = build_local_reader_report_definition()
    return OperationRegistry(
        definitions=(report, status),
        public_registrations=(
            build_local_reader_report_registration(report),
            build_local_reader_status_registration(status),
        ),
    )


def _services(
    root: Path, registry: OperationRegistry, lanes: Mapping[ModelRole, RoleLane]
) -> tuple[OperationComposedServices, OperationJournalRepository]:
    journal = OperationJournalRepository(storage_root=root)
    services = compose_operation_services(
        registry=registry,
        authority_operation=unread_authority_operation(),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=60),
        cleanup_timeout=timedelta(seconds=5),
        execution_authority=_SelectionAuthority(lanes),
    )
    return services, journal


@dataclass(frozen=True, slots=True)
class SupervisedRun[ResultT: BaseModel]:
    """One settled operation: its public result, committed effect and published phases."""

    result: ResultT
    effect: OperationEffect
    phases: tuple[str, ...]


def run_supervised[RequestT: BaseModel, ResultT: BaseModel](
    tmp_path: Path,
    request: OperationRequest[RequestT],
    result_type: type[ResultT],
    *,
    lanes: Mapping[ModelRole, RoleLane] = READER_LANES,
    program: ProgramRow = SET_UP_PROGRAM,
) -> SupervisedRun[ResultT]:
    """Settle ``request`` with ``lanes`` selected and ``program`` reported, and resolve its public result."""
    return run_supervised_in(tmp_path, provisioning_registry(program), request, result_type, lanes=lanes)


def run_supervised_in[RequestT: BaseModel, ResultT: BaseModel](
    tmp_path: Path,
    registry: OperationRegistry,
    request: OperationRequest[RequestT],
    result_type: type[ResultT],
    *,
    lanes: Mapping[ModelRole, RoleLane] = READER_LANES,
) -> SupervisedRun[ResultT]:
    """Submit, start and settle ``request`` in ``registry``, then resolve its public result as a frontend would."""

    async def run(root: Path) -> SupervisedRun[ResultT]:
        services, journal = _services(root, registry, lanes)
        try:
            submitted = await services.submission.submit(request, actor_ref="operator:local-reader-test")
            operation_id = submitted.receipt.operation_id
            await services.submission.start(operation_id)
            await services.submission.settled(operation_id)
            terminal = await journal.load(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=64)
            observed = await services.observation.observe(
                OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=64)
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            projection = observed.projection
            assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            schema = projection.definition_contract.result_schema
            assert schema is not None
            resolved = await services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=projection.definition_contract.definition_contract_digest,
                    result_schema=schema,
                ),
                result_type,
            )
        finally:
            await services.shutdown()
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert isinstance(resolved.projection, result_type)
        phases = tuple(event.phase_code for event in replay.events if event.kind is OperationEventKind.PHASE)
        return SupervisedRun(resolved.projection, terminal.effect, phases)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        return asyncio.run(run(profile.storage_root))
